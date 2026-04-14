"""
Unit tests for BenchmarkingAgent — route extraction heuristics and deviation calc.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import date

from agents.benchmarking import BenchmarkingAgent
from models.pydantic_models import InvoiceData, LineItem, BenchmarkResult
from utils.freight_rate_service import MockApifyService


@pytest.fixture
def mock_rate_service():
    svc = MagicMock()
    svc.get_rate.return_value = 1500.0
    return svc


@pytest.fixture
def agent(mock_rate_service):
    return BenchmarkingAgent(rate_service=mock_rate_service, threshold_percent=15.0)


@pytest.fixture
def base_invoice():
    return InvoiceData(
        vendor_name="Vendor",
        invoice_number="INV-001",
        invoice_date=date(2024, 1, 1),
        line_items=[],
        total_amount=0.0,
        incoterms="FOB Shanghai",
    )


class TestRouteExtraction:
    def test_two_cities_in_description(self, agent, base_invoice):
        item = LineItem(
            description="Freight Shanghai to Los Angeles",
            quantity=1, unit_price=1500.0, total=1500.0,
        )
        route = agent._extract_route_from_line_item(item, base_invoice)
        assert "Shanghai" in route
        assert "Los Angeles" in route

    def test_incoterms_fallback(self, agent, base_invoice):
        item = LineItem(
            description="Ocean freight charge",
            quantity=1, unit_price=1500.0, total=1500.0,
        )
        route = agent._extract_route_from_line_item(item, base_invoice)
        # Should use incoterms "FOB Shanghai" → origin = Shanghai
        assert "Shanghai" in route

    def test_llm_fallback_called_when_no_match(self, mock_rate_service, base_invoice):
        """When heuristic and incoterms both fail, LLM fallback is invoked."""
        invoice_no_incoterms = InvoiceData(
            vendor_name="Vendor",
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 1),
            line_items=[],
            total_amount=0.0,
            incoterms=None,
        )
        item = LineItem(
            description="Misc logistics charge",
            quantity=1, unit_price=100.0, total=100.0,
        )
        agent = BenchmarkingAgent(rate_service=mock_rate_service, threshold_percent=15.0)
        with patch.object(agent, "_extract_route_via_llm", return_value="Mumbai -> Rotterdam") as mock_llm:
            route = agent._extract_route_from_line_item(item, invoice_no_incoterms)
        mock_llm.assert_called_once()
        assert route == "Mumbai -> Rotterdam"


class TestDeviationCalculation:
    def test_exact_market_price_zero_deviation(self, agent, base_invoice, mock_rate_service):
        mock_rate_service.get_rate.return_value = 1500.0
        item = LineItem(
            description="Ocean Freight Shanghai to Los Angeles",
            quantity=1, unit_price=1500.0, total=1500.0,
        )
        result = agent.benchmark_line_item(item, base_invoice)
        assert result.deviation_percent == 0.0
        assert result.is_overpriced is False

    def test_overpriced_detection(self, agent, base_invoice, mock_rate_service):
        mock_rate_service.get_rate.return_value = 1000.0
        item = LineItem(
            description="Freight Shanghai Los Angeles",
            quantity=1, unit_price=2000.0, total=2000.0,
        )
        result = agent.benchmark_line_item(item, base_invoice)
        assert result.is_overpriced is True
        assert result.deviation_percent == pytest.approx(100.0, abs=0.1)

    def test_zero_market_rate_no_division_error(self, agent, base_invoice, mock_rate_service):
        mock_rate_service.get_rate.return_value = 0.0
        item = LineItem(
            description="Freight Shanghai Los Angeles",
            quantity=1, unit_price=500.0, total=500.0,
        )
        result = agent.benchmark_line_item(item, base_invoice)
        assert result.deviation_percent == 0.0


class TestBenchmarkFilter:
    def test_only_freight_items_benchmarked(self, agent, base_invoice):
        inv = InvoiceData(
            vendor_name="Vendor",
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 1),
            line_items=[
                LineItem(description="Ocean freight charge", quantity=1, unit_price=1500.0, total=1500.0),
                LineItem(description="Documentation fee", quantity=1, unit_price=100.0, total=100.0),
            ],
            total_amount=1600.0,
            incoterms="FOB Shanghai",
        )
        results = agent.benchmark(inv)
        # Only the freight line item should be benchmarked
        assert len(results) == 1

    def test_no_freight_items_returns_empty(self, agent, base_invoice):
        inv = InvoiceData(
            vendor_name="Vendor",
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 1),
            line_items=[
                LineItem(description="Consulting fee", quantity=1, unit_price=500.0, total=500.0),
            ],
            total_amount=500.0,
        )
        results = agent.benchmark(inv)
        assert results == []
