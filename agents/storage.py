"""
Storage Agent — Deduplicates and persists invoices to SQLite.

What it does:
1. Receives InvoiceData from the Extraction Agent
2. Checks if this invoice already exists (vendor_name + invoice_number)
3. If duplicate → flags it and skips save
4. If unique → converts Pydantic model → SQLAlchemy model → saves to DB

Why this separation?
- Extraction Agent shouldn't know about databases (single responsibility)
- Storage Agent handles all DB concerns: connections, transactions, constraints
- The UniqueConstraint on the DB table is our final line of defense against duplicates
"""

import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from datetime import datetime

from models.database import Invoice
from models.pydantic_models import InvoiceData
from utils.db_utils import get_session

logger = logging.getLogger(__name__)


class StorageResult:
    """Simple dataclass to hold the result of a storage operation."""

    def __init__(
        self,
        success: bool,
        message: str,
        invoice_id: int | None = None,
        is_duplicate: bool = False,
    ):
        self.success = success
        self.message = message
        self.invoice_id = invoice_id
        self.is_duplicate = is_duplicate

    def __repr__(self) -> str:
        status = "DUPLICATE" if self.is_duplicate else ("SAVED" if self.success else "FAILED")
        return f"<StorageResult(status={status}, message='{self.message}')>"


class StorageAgent:
    """
    Handles database deduplication and storage of extracted invoices.
    
    Usage:
        agent = StorageAgent()
        result = agent.store_invoice(invoice_data)
        if result.is_duplicate:
            print("Already have this invoice!")
        elif result.success:
            print(f"Saved with ID: {result.invoice_id}")
    """

    def __init__(self):
        logger.info("StorageAgent initialized")

    def _check_duplicate(self, session, vendor_name: str, invoice_number: str) -> Invoice | None:
        """
        Check if an invoice with the same vendor + invoice number exists.
        
        This is a pre-check before attempting insert.
        We also rely on the DB UniqueConstraint as a safety net.
        
        Args:
            session: Active SQLAlchemy session
            vendor_name: Name of the vendor
            invoice_number: Invoice identifier
            
        Returns:
            Existing Invoice record if found, None otherwise
        """
        existing = (
            session.query(Invoice)
            .filter_by(vendor_name=vendor_name, invoice_number=invoice_number)
            .first()
        )
        return existing

    def store_invoice(self, invoice_data: InvoiceData) -> StorageResult:
        """
        Save an InvoiceData (Pydantic) to the database as Invoice (SQLAlchemy).
        
        Steps:
        1. Open a database session (transaction)
        2. Check for duplicates
        3. If unique, create Invoice record and commit
        4. If error, rollback and report
        
        Args:
            invoice_data: Validated extraction output from ExtractionAgent
            
        Returns:
            StorageResult with success status and invoice_id
        """
        session = get_session()

        try:
            # Step 1: Check for duplicates
            existing = self._check_duplicate(
                session, invoice_data.vendor_name, invoice_data.invoice_number
            )

            if existing:
                logger.warning(
                    "Duplicate detected: vendor='%s', invoice='%s' (existing id=%d)",
                    invoice_data.vendor_name,
                    invoice_data.invoice_number,
                    existing.id,
                )
                return StorageResult(
                    success=False,
                    message=f"Duplicate invoice: already exists with id={existing.id}",
                    invoice_id=existing.id,
                    is_duplicate=True,
                )

            # Step 2: Convert Pydantic → SQLAlchemy
            invoice_record = Invoice(
                vendor_name=invoice_data.vendor_name,
                invoice_number=invoice_data.invoice_number,
                invoice_date=datetime.combine(
                    invoice_data.invoice_date, datetime.min.time()
                ),
                currency=invoice_data.currency,
                incoterms=invoice_data.incoterms,
                total_amount=invoice_data.total_amount,
                raw_extracted_data=invoice_data.model_dump(mode="json"),  # Full JSON audit trail (handles dates)
                status="extracted",
            )

            # Step 3: Save and commit
            session.add(invoice_record)
            session.commit()
            session.refresh(invoice_record)

            logger.info(
                "Saved invoice: id=%d, vendor='%s', number='%s', total=%.2f",
                invoice_record.id,
                invoice_record.vendor_name,
                invoice_record.invoice_number,
                invoice_record.total_amount,
            )

            return StorageResult(
                success=True,
                message=f"Saved successfully with id={invoice_record.id}",
                invoice_id=invoice_record.id,
                is_duplicate=False,
            )

        except IntegrityError as e:
            # UniqueConstraint violation (safety net if check_duplicate missed it)
            session.rollback()
            logger.error("Integrity error (likely duplicate): %s", e)
            return StorageResult(
                success=False,
                message=f"Database constraint violation: {str(e)[:100]}",
                is_duplicate=True,
            )

        except Exception as e:
            session.rollback()
            logger.error("Unexpected error storing invoice: %s", e)
            return StorageResult(
                success=False,
                message=f"Storage failed: {str(e)}",
            )

        finally:
            session.close()

    def get_invoice_by_id(self, invoice_id: int) -> Invoice | None:
        """Retrieve an invoice from the database by its ID."""
        session = get_session()
        try:
            return session.query(Invoice).filter_by(id=invoice_id).first()
        finally:
            session.close()

    def get_all_invoices(self) -> list[Invoice]:
        """Retrieve all invoices from the database."""
        session = get_session()
        try:
            return session.query(Invoice).order_by(Invoice.created_at.desc()).all()
        finally:
            session.close()

    def batch_store_invoices(
        self, invoices: list[InvoiceData]
    ) -> list[StorageResult]:
        """
        Store multiple invoices in a single database transaction.

        Performs one dedup query per batch (not per invoice) and one bulk
        INSERT — dramatically faster than calling store_invoice() N times
        when processing 50+ PDFs.

        Args:
            invoices: List of validated InvoiceData objects

        Returns:
            List of StorageResult in the same order as the input list
        """
        if not invoices:
            return []

        session = get_session()
        results: list[StorageResult] = []

        try:
            # Build lookup set of all (vendor, number) pairs already in the DB
            # in a single query instead of N individual SELECT checks.
            keys = [(inv.vendor_name, inv.invoice_number) for inv in invoices]
            existing_records = (
                session.query(Invoice.vendor_name, Invoice.invoice_number)
                .filter(
                    Invoice.vendor_name.in_([k[0] for k in keys]),
                )
                .all()
            )
            existing_set: set[tuple[str, str]] = {
                (r.vendor_name, r.invoice_number) for r in existing_records
            }

            new_records: list[Invoice] = []
            for inv in invoices:
                key = (inv.vendor_name, inv.invoice_number)
                if key in existing_set:
                    logger.warning(
                        "Batch dedup: skipping duplicate %s / %s",
                        inv.vendor_name, inv.invoice_number,
                    )
                    results.append(
                        StorageResult(
                            success=False,
                            message=f"Duplicate: {inv.vendor_name} / {inv.invoice_number}",
                            is_duplicate=True,
                        )
                    )
                else:
                    record = Invoice(
                        vendor_name=inv.vendor_name,
                        invoice_number=inv.invoice_number,
                        invoice_date=datetime.combine(inv.invoice_date, datetime.min.time()),
                        currency=inv.currency,
                        incoterms=inv.incoterms,
                        total_amount=inv.total_amount,
                        raw_extracted_data=inv.model_dump(mode="json"),
                        status="extracted",
                    )
                    new_records.append(record)
                    # Placeholder result — we'll fill in the ID after flush
                    results.append(
                        StorageResult(success=True, message="pending flush")
                    )

            if new_records:
                session.add_all(new_records)
                session.flush()  # Assigns auto-increment IDs without committing
                session.commit()

                # Back-fill IDs into the results list
                new_idx = 0
                for i, inv in enumerate(invoices):
                    if not results[i].is_duplicate:
                        record = new_records[new_idx]
                        results[i].invoice_id = record.id
                        results[i].message = f"Saved with id={record.id}"
                        new_idx += 1

                logger.info(
                    "Batch insert: %d saved, %d duplicates skipped",
                    len(new_records),
                    len(invoices) - len(new_records),
                )

        except Exception as e:
            session.rollback()
            logger.error("Batch store failed: %s", e)
            # Return failure for any that weren't yet resolved
            for i in range(len(results), len(invoices)):
                results.append(
                    StorageResult(success=False, message=f"Batch error: {str(e)}")
                )
        finally:
            session.close()

        return results
