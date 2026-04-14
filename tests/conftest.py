"""
Shared pytest fixtures for the CPA AI Agent test suite.
"""

import os
import pytest
from datetime import date
from unittest.mock import MagicMock

# ── Make sure tests never need a real GROQ_API_KEY ──
os.environ.setdefault("GROQ_API_KEY", "test-key-for-unit-tests")


from models.pydantic_models import (
    InvoiceData,
    LineItem,
    ClassificationResult,
    BenchmarkResult,
    AnomalyReport,
)


@pytest.fixture
def sample_line_items() -> list[LineItem]:
    return [
        LineItem(
            description="Ocean Freight - Shanghai to Los Angeles",
            quantity=1,
            unit_price=2500.0,
            total=2500.0,
        ),
        LineItem(
            description="Documentation fee",
            quantity=1,
            unit_price=150.0,
            total=150.0,
        ),
    ]


@pytest.fixture
def sample_invoice(sample_line_items) -> InvoiceData:
    return InvoiceData(
        vendor_name="Shanghai Freight Co. Ltd.",
        invoice_number="INV-2024-0042",
        invoice_date=date(2024, 3, 15),
        currency="USD",
        incoterms="FOB Shanghai",
        line_items=sample_line_items,
        total_amount=2650.0,
    )


@pytest.fixture
def sample_benchmark_ok() -> BenchmarkResult:
    """A benchmark result with no price anomaly."""
    return BenchmarkResult(
        route="Shanghai -> Los Angeles",
        invoice_price=1500.0,
        market_average=1450.0,
        deviation_percent=3.45,
        is_overpriced=False,
    )


@pytest.fixture
def sample_benchmark_overpriced() -> BenchmarkResult:
    """A benchmark result flagged as overpriced (>15%)."""
    return BenchmarkResult(
        route="Shanghai -> Los Angeles",
        invoice_price=2500.0,
        market_average=1500.0,
        deviation_percent=66.67,
        is_overpriced=True,
    )


@pytest.fixture
def in_memory_db(tmp_path):
    """
    Provide a fresh in-memory SQLite database for each test.

    Patches db_utils so agents use this isolated DB instead of the
    project's real cpa_agent.db.
    """
    import utils.db_utils as db_utils
    from models.database import Base
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(test_db_url)
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    # Patch module-level singletons
    original_engine = db_utils._engine
    original_url = db_utils.DATABASE_URL
    db_utils._engine = engine
    db_utils.DATABASE_URL = test_db_url

    def _get_session():
        return TestSession()

    original_get_session = db_utils.get_session
    db_utils.get_session = _get_session

    yield engine

    db_utils._engine = original_engine
    db_utils.DATABASE_URL = original_url
    db_utils.get_session = original_get_session
    engine.dispose()
