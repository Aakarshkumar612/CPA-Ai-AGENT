"""
Analysis & Reporting Agent — Identifies anomalies and generates audit reports.

What it does:
1. Reviews benchmark results for price anomalies (>15% over market)
2. Checks for missing/incomplete fields
3. Reviews duplicate flags from the Storage Agent
4. Assigns severity levels (low, medium, high, critical)
5. Generates a final JSON report

Why a separate analysis agent?
- Keeps the benchmarking agent focused on price comparison only
- This agent can be extended with more rules later (trend analysis, vendor scoring)
- CPAs need a single, readable report — not raw benchmark data
"""

import csv
import json
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from models.pydantic_models import InvoiceData, BenchmarkResult, AnomalyReport
from agents.storage import StorageResult
from utils.timer import get_timer

logger = logging.getLogger(__name__)

# ── Severity Rules ──
# Each rule maps to a severity level based on how concerning the finding is
SEVERITY_RULES = {
    "price_deviation_15_25": {"threshold": 15, "cap": 25, "severity": "medium", "label": "Price 15-25% above market"},
    "price_deviation_25_50": {"threshold": 25, "cap": 50, "severity": "high", "label": "Price 25-50% above market"},
    "price_deviation_50_plus": {"threshold": 50, "cap": None, "severity": "critical", "label": "Price >50% above market"},
}

# Severity hierarchy for determining overall report severity
SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class AnalysisAgent:
    """
    Analyzes invoices for anomalies and generates audit reports.
    
    Usage:
        agent = AnalysisAgent()
        report = agent.analyze(invoice_data, benchmark_results, storage_result)
        print(report.anomalies)
        print(report.severity)
    """

    def __init__(self, output_dir: str = "output_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info("AnalysisAgent initialized (output_dir=%s)", output_dir)

    def _check_price_anomalies(
        self, benchmarks: list[BenchmarkResult]
    ) -> list[tuple[str, str]]:
        """
        Check for price deviations in benchmark results.
        
        Args:
            benchmarks: List of benchmark results for this invoice
            
        Returns:
            List of (anomaly_description, severity) tuples
        """
        anomalies = []

        for b in benchmarks:
            if not b.is_overpriced:
                continue

            deviation = abs(b.deviation_percent)

            # Check which severity bucket this falls into
            if deviation >= 50:
                anomalies.append((
                    f"CRITICAL: '{b.route}' unit price ${b.invoice_price:.2f} is "
                    f"{deviation:.1f}% above market average ${b.market_average:.2f}",
                    "critical",
                ))
            elif deviation >= 25:
                anomalies.append((
                    f"HIGH: '{b.route}' unit price ${b.invoice_price:.2f} is "
                    f"{deviation:.1f}% above market average ${b.market_average:.2f}",
                    "high",
                ))
            elif deviation >= 15:
                anomalies.append((
                    f"MEDIUM: '{b.route}' unit price ${b.invoice_price:.2f} is "
                    f"{deviation:.1f}% above market average ${b.market_average:.2f}",
                    "medium",
                ))

        return anomalies

    def _check_missing_fields(self, invoice: InvoiceData) -> list[tuple[str, str]]:
        """
        Check for missing or incomplete fields in the extracted data.
        
        Args:
            invoice: The extracted invoice data
            
        Returns:
            List of (anomaly_description, severity) tuples
        """
        anomalies = []

        if not invoice.vendor_name or invoice.vendor_name == "null":
            anomalies.append(("Vendor name missing from invoice", "high"))

        if not invoice.invoice_number or invoice.invoice_number == "null":
            anomalies.append(("Invoice number missing", "high"))

        if invoice.invoice_date is None:
            anomalies.append(("Invoice date missing", "medium"))

        if not invoice.incoterms:
            anomalies.append(("Incoterms not specified — shipping terms unknown", "low"))

        if not invoice.line_items:
            anomalies.append(("No line items found on invoice", "critical"))

        # Check if line items have complete data
        for i, item in enumerate(invoice.line_items):
            if not item.description:
                anomalies.append(
                    (f"Line item {i+1} missing description", "medium"),
                )

        return anomalies

    def _check_duplicate_flag(self, storage_result: Optional[StorageResult]) -> list[tuple[str, str]]:
        """
        Check if this invoice was flagged as a duplicate.
        
        Args:
            storage_result: Result from the Storage Agent
            
        Returns:
            List of (anomaly_description, severity) tuples
        """
        anomalies = []

        if storage_result and storage_result.is_duplicate:
            anomalies.append((
                f"DUPLICATE: This invoice was already in the system (id={storage_result.invoice_id})",
                "high",
            ))

        return anomalies

    def _determine_overall_severity(self, anomalies: list[tuple[str, str]]) -> str:
        """
        Determine the overall severity from all individual anomaly severities.
        
        The overall severity is the HIGHEST severity among all anomalies.
        E.g., if you have 2 medium + 1 critical → overall = critical
        
        Args:
            anomalies: List of (description, severity) tuples
            
        Returns:
            Overall severity string
        """
        if not anomalies:
            return "low"

        max_severity = "low"
        for _, severity in anomalies:
            if SEVERITY_ORDER.get(severity, 0) > SEVERITY_ORDER.get(max_severity, 0):
                max_severity = severity

        return max_severity

    def analyze(
        self,
        invoice: InvoiceData,
        benchmarks: list[BenchmarkResult],
        storage_result: Optional[StorageResult] = None,
    ) -> AnomalyReport:
        """
        Run all analysis checks on an invoice and generate a report.
        
        Steps:
        1. Check price anomalies (from benchmarking)
        2. Check missing/incomplete fields
        3. Check duplicate flag
        4. Determine overall severity
        5. Generate human-readable summary
        
        Args:
            invoice: The extracted invoice data
            benchmarks: Benchmark results for freight line items
            storage_result: Result from storage (for duplicate detection)
            
        Returns:
            AnomalyReport with all findings
        """
        logger.info("Analyzing invoice: %s / %s", invoice.vendor_name, invoice.invoice_number)

        # Collect all anomalies
        all_anomalies: list[tuple[str, str]] = []
        all_anomalies.extend(self._check_price_anomalies(benchmarks))
        all_anomalies.extend(self._check_missing_fields(invoice))
        all_anomalies.extend(self._check_duplicate_flag(storage_result))

        # Extract just the descriptions
        anomaly_descriptions = [desc for desc, _ in all_anomalies]

        # Determine overall severity
        overall_severity = self._determine_overall_severity(all_anomalies)

        # Generate summary
        if anomaly_descriptions:
            summary = (
                f"Found {len(anomaly_descriptions)} issue(s) in invoice "
                f"{invoice.invoice_number} from {invoice.vendor_name}. "
                f"Overall severity: {overall_severity.upper()}."
            )
        else:
            summary = (
                f"No issues found in invoice {invoice.invoice_number} from "
                f"{invoice.vendor_name}. All prices within acceptable range."
            )

        report = AnomalyReport(
            invoice_number=invoice.invoice_number,
            vendor_name=invoice.vendor_name,
            anomalies=anomaly_descriptions,
            severity=overall_severity,
            summary=summary,
        )

        logger.info(
            "Analysis complete: %d anomalies, severity=%s",
            len(anomaly_descriptions),
            overall_severity,
        )

        return report

    def save_report(
        self,
        report: AnomalyReport,
        invoice: InvoiceData,
        benchmarks: list[BenchmarkResult],
        filename: Optional[str] = None,
    ) -> str:
        """
        Save the analysis report as a JSON file.
        
        The report includes the anomaly findings plus the raw invoice data
        and benchmark data for full audit transparency.
        
        Args:
            report: The anomaly report from analyze()
            invoice: The original invoice data
            benchmarks: The benchmark results
            filename: Custom filename (auto-generated if None)
            
        Returns:
            Path to the saved report file
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"audit_{invoice.invoice_number}_{timestamp}.json"

        output_path = self.output_dir / filename

        # Combine everything into one comprehensive report
        full_report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "tool": "Crowd Wisdom Trading CPA AI Agent v0.1",
                "pipeline_timing": get_timer().to_dict(),
            },
            "anomaly_report": report.model_dump(),
            "invoice_data": invoice.model_dump(mode="json"),  # Handles date serialization
            "benchmark_results": [b.model_dump() for b in benchmarks],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2, ensure_ascii=False)

        logger.info("Report saved: %s", output_path)
        return str(output_path)

    def save_csv_export(
        self,
        file_results: list[dict],
        filename: str | None = None,
    ) -> str:
        """
        Write a CSV summary of all processed invoices for CPA Excel import.

        One row per invoice with: invoice_number, vendor_name, invoice_date,
        total_amount, currency, severity, anomaly_count, overpriced_routes,
        report_path.

        Args:
            file_results: The ``results`` list accumulated by the orchestrator
                          (each entry is the per-file summary dict).
            filename: Custom filename; auto-generated if None.

        Returns:
            Absolute path to the written CSV file.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"export_{timestamp}.csv"

        output_path = self.output_dir / filename

        fieldnames = [
            "invoice_number",
            "vendor_name",
            "invoice_date",
            "total_amount",
            "currency",
            "severity",
            "anomaly_count",
            "overpriced_routes",
            "report_path",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for fr in file_results:
                # Pull data from the full report JSON if available
                report_path = fr.get("saved_report", "")
                invoice_number = ""
                vendor_name = ""
                invoice_date = ""
                total_amount = ""
                currency = ""
                anomaly_count = 0
                overpriced_routes = ""

                if report_path:
                    try:
                        with open(report_path, "r", encoding="utf-8") as rf:
                            report_data = json.load(rf)
                        inv = report_data.get("invoice_data", {})
                        anomaly_report = report_data.get("anomaly_report", {})
                        benchmarks = report_data.get("benchmark_results", [])

                        invoice_number = inv.get("invoice_number", "")
                        vendor_name = inv.get("vendor_name", "")
                        invoice_date = inv.get("invoice_date", "")
                        total_amount = inv.get("total_amount", "")
                        currency = inv.get("currency", "USD")
                        anomaly_count = len(anomaly_report.get("anomalies", []))
                        overpriced = [
                            b["route"] for b in benchmarks if b.get("is_overpriced")
                        ]
                        overpriced_routes = "; ".join(overpriced)
                    except (IOError, json.JSONDecodeError, KeyError):
                        pass

                writer.writerow({
                    "invoice_number": invoice_number,
                    "vendor_name": vendor_name,
                    "invoice_date": invoice_date,
                    "total_amount": total_amount,
                    "currency": currency,
                    "severity": fr.get("severity", ""),
                    "anomaly_count": anomaly_count,
                    "overpriced_routes": overpriced_routes,
                    "report_path": report_path,
                })

        logger.info("CSV export saved: %s (%d rows)", output_path, len(file_results))
        return str(output_path)

    def save_dashboard_report(
        self,
        file_results: list[dict],
        reports_saved: list[str],
        errors: list[str],
        filename: str | None = None,
    ) -> str:
        """
        Write an aggregate dashboard JSON covering all invoices in this run.

        Includes: totals, severity breakdown, top anomaly types, top vendors
        by total spend, overpriced route frequency, and per-invoice table.

        Args:
            file_results: The ``results`` list from the orchestrator.
            reports_saved: Paths of all JSON reports written this run.
            errors: Any pipeline errors logged during the run.
            filename: Custom filename; auto-generated if None.

        Returns:
            Absolute path to the dashboard JSON file.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"dashboard_{timestamp}.json"

        output_path = self.output_dir / filename

        # Aggregate stats across all per-invoice reports
        severity_counts: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        total_invoice_value: float = 0.0
        all_anomaly_texts: list[str] = []
        vendor_spend: dict[str, float] = {}
        overpriced_route_counts: Counter = Counter()
        per_invoice_rows: list[dict] = []

        for report_path in reports_saved:
            try:
                with open(report_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                inv = data.get("invoice_data", {})
                anomaly_report = data.get("anomaly_report", {})
                benchmarks = data.get("benchmark_results", [])

                severity = anomaly_report.get("severity", "low")
                if severity in severity_counts:
                    severity_counts[severity] += 1

                amount = inv.get("total_amount") or 0.0
                total_invoice_value += float(amount)

                vendor = inv.get("vendor_name", "Unknown")
                vendor_spend[vendor] = vendor_spend.get(vendor, 0.0) + float(amount)

                all_anomaly_texts.extend(anomaly_report.get("anomalies", []))

                for b in benchmarks:
                    if b.get("is_overpriced"):
                        overpriced_route_counts[b["route"]] += 1

                per_invoice_rows.append({
                    "invoice_number": inv.get("invoice_number", ""),
                    "vendor_name": vendor,
                    "invoice_date": inv.get("invoice_date", ""),
                    "total_amount": amount,
                    "currency": inv.get("currency", "USD"),
                    "severity": severity,
                    "anomaly_count": len(anomaly_report.get("anomalies", [])),
                    "report_path": report_path,
                })

            except (IOError, json.JSONDecodeError, KeyError) as e:
                logger.warning("Dashboard: could not read report %s: %s", report_path, e)

        # Top 5 most common anomaly type prefixes
        anomaly_type_counts: Counter = Counter()
        for text in all_anomaly_texts:
            prefix = text.split(":")[0].strip() if ":" in text else text[:40]
            anomaly_type_counts[prefix] += 1

        dashboard = {
            "dashboard_metadata": {
                "generated_at": datetime.now().isoformat(),
                "tool": "Crowd Wisdom Trading CPA AI Agent v0.1",
            },
            "run_summary": {
                "invoices_processed": len(reports_saved),
                "invoices_with_errors": len(errors),
                "total_invoice_value_usd": round(total_invoice_value, 2),
            },
            "severity_breakdown": severity_counts,
            "top_vendors_by_spend": dict(
                sorted(vendor_spend.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "top_anomaly_types": dict(anomaly_type_counts.most_common(10)),
            "most_overpriced_routes": dict(overpriced_route_counts.most_common(10)),
            "pipeline_errors": errors,
            "per_invoice_summary": per_invoice_rows,
            "pipeline_timing": get_timer().to_dict(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, indent=2, ensure_ascii=False)

        logger.info("Dashboard report saved: %s", output_path)
        return str(output_path)
