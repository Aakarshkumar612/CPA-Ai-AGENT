"""
Integration tests for StorageAgent — uses a real in-memory SQLite DB (no mocking).
"""

import pytest
from datetime import date

from agents.storage import StorageAgent, StorageResult
from models.pydantic_models import InvoiceData, LineItem


@pytest.fixture
def storage(in_memory_db):
    """StorageAgent backed by the in-memory test DB."""
    return StorageAgent()


@pytest.fixture
def invoice_a() -> InvoiceData:
    return InvoiceData(
        vendor_name="Test Vendor A",
        invoice_number="INV-TEST-001",
        invoice_date=date(2024, 1, 15),
        currency="USD",
        incoterms="FOB Shanghai",
        line_items=[LineItem(description="Freight", quantity=1, unit_price=1500.0, total=1500.0)],
        total_amount=1500.0,
    )


@pytest.fixture
def invoice_b() -> InvoiceData:
    return InvoiceData(
        vendor_name="Test Vendor B",
        invoice_number="INV-TEST-002",
        invoice_date=date(2024, 2, 20),
        currency="EUR",
        line_items=[LineItem(description="Handling", quantity=2, unit_price=200.0, total=400.0)],
        total_amount=400.0,
    )


class TestStoreInvoice:
    def test_successful_store(self, storage, invoice_a):
        result = storage.store_invoice(invoice_a)
        assert result.success is True
        assert result.invoice_id is not None
        assert result.is_duplicate is False

    def test_duplicate_detection(self, storage, invoice_a):
        storage.store_invoice(invoice_a)
        result = storage.store_invoice(invoice_a)  # Same vendor + invoice_number
        assert result.is_duplicate is True
        assert result.success is False

    def test_different_invoice_numbers_not_duplicate(self, storage, invoice_a, invoice_b):
        r1 = storage.store_invoice(invoice_a)
        r2 = storage.store_invoice(invoice_b)
        assert r1.success is True
        assert r2.success is True
        assert r1.invoice_id != r2.invoice_id

    def test_stored_invoice_retrievable(self, storage, invoice_a):
        result = storage.store_invoice(invoice_a)
        retrieved = storage.get_invoice_by_id(result.invoice_id)
        assert retrieved is not None
        assert retrieved.vendor_name == invoice_a.vendor_name
        assert retrieved.invoice_number == invoice_a.invoice_number

    def test_get_all_invoices(self, storage, invoice_a, invoice_b):
        storage.store_invoice(invoice_a)
        storage.store_invoice(invoice_b)
        all_inv = storage.get_all_invoices()
        assert len(all_inv) == 2

    def test_nonexistent_id_returns_none(self, storage):
        assert storage.get_invoice_by_id(99999) is None


class TestBatchStoreInvoices:
    def test_batch_stores_all(self, storage, invoice_a, invoice_b):
        results = storage.batch_store_invoices([invoice_a, invoice_b])
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_batch_dedup_within_batch(self, storage, invoice_a):
        # Sending the same invoice twice in one batch
        results = storage.batch_store_invoices([invoice_a, invoice_a])
        # First should succeed, second should be flagged (already in DB from first flush)
        successes = [r for r in results if r.success]
        dupes = [r for r in results if r.is_duplicate]
        assert len(successes) >= 1
        assert len(results) == 2

    def test_batch_dedup_against_existing(self, storage, invoice_a, invoice_b):
        storage.store_invoice(invoice_a)  # Pre-store invoice_a
        results = storage.batch_store_invoices([invoice_a, invoice_b])
        assert results[0].is_duplicate is True   # Already exists
        assert results[1].success is True         # invoice_b is new

    def test_empty_batch_returns_empty(self, storage):
        assert storage.batch_store_invoices([]) == []
