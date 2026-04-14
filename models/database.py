from sqlalchemy import Column, Integer, String, Float, Date, DateTime, JSON, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime, timezone


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    
    Why DeclarativeBase?
    - It's the modern SQLAlchemy 2.0 approach
    - Combines table definition and Python class in one step
    - Older code uses `declarative_base()` function — this is the newer, cleaner version
    """
    pass


class Invoice(Base):
    """
    Represents a stored invoice record in the database.
    
    Why these columns?
    - `id`: Auto-incrementing primary key (unique identifier for each DB row)
    - `vendor_name` + `invoice_number`: Used together for duplicate detection
    - `raw_extracted_data`: Stores the full Pydantic model as JSON for audit trail
    - `status`: Tracks where the invoice is in the pipeline (extracted, benchmarked, flagged)
    
    Why UniqueConstraint?
    - Prevents the same invoice (same vendor + same invoice number) from being stored twice
    - This is how the Deduplication Agent works — it relies on this DB constraint
    """
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    invoice_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    incoterms: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_amount: Mapped[float] = mapped_column(Float, nullable=True)
    raw_extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="extracted")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Duplicate detection: same vendor + same invoice number = duplicate
    __table_args__ = (
        UniqueConstraint("vendor_name", "invoice_number", name="uq_vendor_invoice"),
    )

    def __repr__(self) -> str:
        return f"<Invoice(id={self.id}, vendor='{self.vendor_name}', number='{self.invoice_number}')>"


class Feedback(Base):
    """
    Stores user corrections to extracted data.
    
    Why this matters:
    - If the LLM extracts the wrong vendor name and a CPA corrects it,
      we log that correction.
    - In a real system, this feedback would be used to improve prompts
      or fine-tune the model over time.
    - For this project, it demonstrates you understand the concept of
      **human-in-the-loop AI** — which is a hot topic in enterprise AI.
    
    How it works:
    1. LLM extracts: vendor_name = "Shanghai Freight"
    2. CPA corrects: vendor_name = "Shanghai Freight Co. Ltd."
    3. We log both values + the correction in this table
    4. We also write to feedback_log.json for easy analysis
    """
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "vendor_name"
    original_value: Mapped[str] = mapped_column(Text, nullable=False)  # What LLM extracted
    corrected_value: Mapped[str] = mapped_column(Text, nullable=False)  # What CPA corrected
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<Feedback(id={self.id}, field='{self.field_name}', invoice_id={self.invoice_id})>"
