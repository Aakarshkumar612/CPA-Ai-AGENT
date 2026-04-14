"""
Unit tests for Pydantic models — validation edge cases.
"""

import pytest
from datetime import date
from pydantic import ValidationError

from models.pydantic_models import (
    InvoiceData,
    LineItem,
    ClassificationResult,
    BenchmarkResult,
    AnomalyReport,
)


class TestLineItem:
    def test_valid_line_item(self):
        item = LineItem(description="Freight", quantity=1, unit_price=100.0, total=100.0)
        assert item.total == 100.0

    def test_zero_quantity_allowed(self):
        # Zero quantity is allowed — validation doesn't enforce qty > 0
        item = LineItem(description="Waiver", quantity=0, unit_price=0.0, total=0.0)
        assert item.quantity == 0

    def test_missing_description_raises(self):
        with pytest.raises(ValidationError):
            LineItem(quantity=1, unit_price=100.0, total=100.0)  # type: ignore

    def test_missing_unit_price_raises(self):
        with pytest.raises(ValidationError):
            LineItem(description="X", quantity=1, total=100.0)  # type: ignore


class TestInvoiceData:
    def test_valid_invoice(self, sample_invoice):
        assert sample_invoice.vendor_name == "Shanghai Freight Co. Ltd."
        assert sample_invoice.currency == "USD"

    def test_currency_defaults_to_usd(self, sample_line_items):
        inv = InvoiceData(
            vendor_name="ACME",
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 1),
            line_items=sample_line_items,
            total_amount=100.0,
        )
        assert inv.currency == "USD"

    def test_incoterms_optional(self, sample_line_items):
        inv = InvoiceData(
            vendor_name="ACME",
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 1),
            line_items=sample_line_items,
            total_amount=100.0,
        )
        assert inv.incoterms is None

    def test_missing_vendor_raises(self, sample_line_items):
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_number="INV-001",
                invoice_date=date(2024, 1, 1),
                line_items=sample_line_items,
                total_amount=100.0,
            )  # type: ignore

    def test_negative_total_allowed(self, sample_line_items):
        # Credit notes can have negative totals — model should accept them
        inv = InvoiceData(
            vendor_name="ACME",
            invoice_number="CN-001",
            invoice_date=date(2024, 1, 1),
            line_items=sample_line_items,
            total_amount=-500.0,
        )
        assert inv.total_amount == -500.0

    def test_empty_line_items_allowed(self):
        # Analysis agent handles this — model itself doesn't block it
        inv = InvoiceData(
            vendor_name="ACME",
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 1),
            line_items=[],
            total_amount=0.0,
        )
        assert inv.line_items == []


class TestClassificationResult:
    def test_valid_classification(self):
        r = ClassificationResult(document_type="invoice", confidence=0.95, reason="Has line items")
        assert r.document_type == "invoice"

    def test_missing_confidence_raises(self):
        with pytest.raises(ValidationError):
            ClassificationResult(document_type="invoice", reason="OK")  # type: ignore


class TestBenchmarkResult:
    def test_is_overpriced_true(self):
        b = BenchmarkResult(
            route="A -> B",
            invoice_price=2000.0,
            market_average=1000.0,
            deviation_percent=100.0,
            is_overpriced=True,
        )
        assert b.is_overpriced is True

    def test_zero_market_average(self):
        b = BenchmarkResult(
            route="A -> B",
            invoice_price=100.0,
            market_average=0.0,
            deviation_percent=0.0,
            is_overpriced=False,
        )
        assert b.market_average == 0.0


class TestAnomalyReport:
    def test_no_anomalies(self):
        r = AnomalyReport(
            invoice_number="INV-001",
            vendor_name="ACME",
            anomalies=[],
            severity="low",
            summary="All clear",
        )
        assert r.anomalies == []

    def test_anomalies_list(self):
        r = AnomalyReport(
            invoice_number="INV-001",
            vendor_name="ACME",
            anomalies=["Price 50% above market", "Missing incoterms"],
            severity="critical",
            summary="Issues found",
        )
        assert len(r.anomalies) == 2
