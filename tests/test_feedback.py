"""
Integration tests for FeedbackAgent — DB + JSON log file.
"""

import json
import pytest
from pathlib import Path

from agents.feedback import FeedbackAgent
from agents.storage import StorageAgent
from models.pydantic_models import InvoiceData, LineItem
from datetime import date


@pytest.fixture
def feedback_agent(in_memory_db, tmp_path):
    log_path = str(tmp_path / "feedback_log.json")
    return FeedbackAgent(log_path=log_path)


@pytest.fixture
def stored_invoice_id(in_memory_db) -> int:
    """Store a sample invoice and return its DB id."""
    agent = StorageAgent()
    inv = InvoiceData(
        vendor_name="FB Vendor",
        invoice_number="INV-FB-001",
        invoice_date=date(2024, 1, 1),
        line_items=[LineItem(description="Freight", quantity=1, unit_price=1000.0, total=1000.0)],
        total_amount=1000.0,
    )
    result = agent.store_invoice(inv)
    return result.invoice_id


class TestLogCorrection:
    def test_logs_to_db(self, feedback_agent, stored_invoice_id):
        feedback_agent.log_correction(
            invoice_id=stored_invoice_id,
            field_name="vendor_name",
            original_value="FB Vendor",
            corrected_value="FB Vendor Ltd.",
        )
        summary = feedback_agent.get_feedback_summary()
        assert len(summary) == 1
        assert summary[0]["field_name"] == "vendor_name"
        assert summary[0]["corrected_value"] == "FB Vendor Ltd."

    def test_logs_to_json(self, feedback_agent, stored_invoice_id):
        feedback_agent.log_correction(
            invoice_id=stored_invoice_id,
            field_name="invoice_date",
            original_value="2024-01-01",
            corrected_value="2024-01-15",
            notes="Scanned wrong date",
        )
        log_path = Path(feedback_agent.log_path)
        assert log_path.exists()
        with open(log_path) as f:
            entries = json.load(f)
        assert len(entries) == 1
        assert entries[0]["notes"] == "Scanned wrong date"

    def test_multiple_corrections(self, feedback_agent, stored_invoice_id):
        feedback_agent.log_correction(stored_invoice_id, "f1", "a", "b")
        feedback_agent.log_correction(stored_invoice_id, "f2", "c", "d")
        summary = feedback_agent.get_feedback_summary()
        assert len(summary) == 2


class TestGetCommonCorrections:
    def test_counts_corrections(self, feedback_agent, stored_invoice_id):
        feedback_agent.log_correction(stored_invoice_id, "vendor_name", "A", "B")
        feedback_agent.log_correction(stored_invoice_id, "vendor_name", "A", "B")
        feedback_agent.log_correction(stored_invoice_id, "vendor_name", "C", "D")
        counts = feedback_agent.get_common_corrections("vendor_name")
        assert counts["A → B"] == 2
        assert counts["C → D"] == 1

    def test_filter_by_field(self, feedback_agent, stored_invoice_id):
        feedback_agent.log_correction(stored_invoice_id, "vendor_name", "X", "Y")
        feedback_agent.log_correction(stored_invoice_id, "invoice_date", "X", "Y")
        counts = feedback_agent.get_common_corrections("vendor_name")
        assert len(counts) == 1

    def test_empty_log(self, feedback_agent):
        counts = feedback_agent.get_common_corrections()
        assert counts == {}
