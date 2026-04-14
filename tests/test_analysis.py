"""
Unit tests for the AnalysisAgent — anomaly detection and reporting.
"""

import json
import pytest
from datetime import date
from pathlib import Path

from agents.analysis import AnalysisAgent
from agents.storage import StorageResult
from models.pydantic_models import InvoiceData, LineItem, BenchmarkResult


class TestCheckPriceAnomalies:
    def setup_method(self):
        self.agent = AnalysisAgent.__new__(AnalysisAgent)

    def test_no_anomalies_when_all_ok(self, sample_benchmark_ok):
        result = self.agent._check_price_anomalies([sample_benchmark_ok])
        assert result == []

    def test_medium_severity_15_to_25(self):
        b = BenchmarkResult(
            route="A -> B", invoice_price=1200.0, market_average=1000.0,
            deviation_percent=20.0, is_overpriced=True,
        )
        result = self.agent._check_price_anomalies([b])
        assert len(result) == 1
        assert result[0][1] == "medium"

    def test_high_severity_25_to_50(self):
        b = BenchmarkResult(
            route="A -> B", invoice_price=1350.0, market_average=1000.0,
            deviation_percent=35.0, is_overpriced=True,
        )
        result = self.agent._check_price_anomalies([b])
        assert result[0][1] == "high"

    def test_critical_severity_over_50(self, sample_benchmark_overpriced):
        result = self.agent._check_price_anomalies([sample_benchmark_overpriced])
        assert result[0][1] == "critical"

    def test_multiple_benchmarks(self, sample_benchmark_ok, sample_benchmark_overpriced):
        result = self.agent._check_price_anomalies(
            [sample_benchmark_ok, sample_benchmark_overpriced]
        )
        assert len(result) == 1  # Only the overpriced one
        assert result[0][1] == "critical"


class TestCheckMissingFields:
    def setup_method(self):
        self.agent = AnalysisAgent.__new__(AnalysisAgent)

    def test_complete_invoice_no_anomalies(self, sample_invoice):
        result = self.agent._check_missing_fields(sample_invoice)
        # incoterms present → no "low" flag
        assert all(sev != "critical" for _, sev in result)

    def test_missing_vendor_name(self, sample_line_items):
        inv = InvoiceData(
            vendor_name="null",
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 1),
            line_items=sample_line_items,
            total_amount=100.0,
        )
        result = self.agent._check_missing_fields(inv)
        severities = [sev for _, sev in result]
        assert "high" in severities

    def test_no_line_items_is_critical(self, sample_line_items):
        inv = InvoiceData(
            vendor_name="ACME",
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 1),
            line_items=[],
            total_amount=0.0,
        )
        result = self.agent._check_missing_fields(inv)
        severities = [sev for _, sev in result]
        assert "critical" in severities

    def test_missing_incoterms_is_low(self, sample_line_items):
        inv = InvoiceData(
            vendor_name="ACME",
            invoice_number="INV-001",
            invoice_date=date(2024, 1, 1),
            line_items=sample_line_items,
            total_amount=100.0,
            incoterms=None,
        )
        result = self.agent._check_missing_fields(inv)
        severities = [sev for _, sev in result]
        assert "low" in severities


class TestDetermineOverallSeverity:
    def setup_method(self):
        self.agent = AnalysisAgent.__new__(AnalysisAgent)

    def test_no_anomalies_is_low(self):
        assert self.agent._determine_overall_severity([]) == "low"

    def test_highest_wins(self):
        anomalies = [("msg", "medium"), ("msg", "critical"), ("msg", "high")]
        assert self.agent._determine_overall_severity(anomalies) == "critical"

    def test_single_medium(self):
        assert self.agent._determine_overall_severity([("x", "medium")]) == "medium"


class TestAnalyze:
    def test_clean_invoice(self, sample_invoice, sample_benchmark_ok, tmp_path):
        agent = AnalysisAgent(output_dir=str(tmp_path))
        report = agent.analyze(
            invoice=sample_invoice,
            benchmarks=[sample_benchmark_ok],
            storage_result=None,
        )
        # No price anomaly, but incoterms present so only possible flag is low
        assert report.severity in ("low",)
        assert report.invoice_number == "INV-2024-0042"

    def test_overpriced_invoice(self, sample_invoice, sample_benchmark_overpriced, tmp_path):
        agent = AnalysisAgent(output_dir=str(tmp_path))
        report = agent.analyze(
            invoice=sample_invoice,
            benchmarks=[sample_benchmark_overpriced],
        )
        assert report.severity == "critical"
        assert len(report.anomalies) >= 1

    def test_duplicate_invoice(self, sample_invoice, tmp_path):
        agent = AnalysisAgent(output_dir=str(tmp_path))
        dup_result = StorageResult(
            success=False, message="dup", invoice_id=1, is_duplicate=True
        )
        report = agent.analyze(
            invoice=sample_invoice,
            benchmarks=[],
            storage_result=dup_result,
        )
        assert any("DUPLICATE" in a for a in report.anomalies)
        assert report.severity in ("high", "critical")


class TestSaveReport:
    def test_creates_json_file(self, sample_invoice, sample_benchmark_ok, tmp_path):
        from models.pydantic_models import AnomalyReport
        agent = AnalysisAgent(output_dir=str(tmp_path))
        anomaly = AnomalyReport(
            invoice_number=sample_invoice.invoice_number,
            vendor_name=sample_invoice.vendor_name,
            anomalies=[],
            severity="low",
            summary="Clean",
        )
        path = agent.save_report(anomaly, sample_invoice, [sample_benchmark_ok])
        assert Path(path).exists()

        with open(path) as f:
            data = json.load(f)
        assert "anomaly_report" in data
        assert "invoice_data" in data
        assert "benchmark_results" in data
        assert "pipeline_timing" in data["report_metadata"]
