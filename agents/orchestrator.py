"""
Hermes Orchestrator — Multi-agent workflow coordinator using LangGraph.

What it does:
1. Chains all agents into a pipeline: Ingest → Extract → Store → Benchmark → Analyze → Report
2. Manages shared state between agents via AgentState
3. Handles errors, retries, and conditional routing (e.g., skip non-invoices)
4. Produces a final comprehensive report

Why LangGraph?
- It's a state machine: each agent is a "node" in a graph
- State flows between nodes automatically (no manual parameter passing)
- Built-in conditional routing (e.g., "if not an invoice → skip extraction")
- Industry standard: used by real companies for production AI agent workflows

Why "Hermes"?
- Hermes was the Greek messenger god — he delivered messages between gods
- Our orchestrator delivers data between agents, just like Hermes
- This follows the "Hermes Architecture" pattern: a central coordinator routes
  tasks between specialized agents

Architecture:
    ┌──────────────┐
    │  scan_docs   │  → Finds PDFs in input_docs folder
    └──────┬───────┘
           │ (list of files)
    ┌──────▼───────┐
    │  classify    │  → Is this an invoice? (IngestionAgent)
    └──────┬───────┘
           │
      ┌────┴─────┐
      │  check:  │
      │ invoice? │
      └────┬─────┘
     yes ↙     ↘ no
  ┌─────┐      ┌──────────┐
  │extract│    │ skip (end)│
  └──┬──┘      └──────────┘
     │ (InvoiceData)
  ┌──▼──────┐
  │ store   │  → Save to DB, check duplicates (StorageAgent)
  └──┬──────┘
     │ (StorageResult)
  ┌──▼──────────┐
  │ benchmark   │  → Compare prices to market (BenchmarkingAgent)
  └──┬──────────┘
     │ (BenchmarkResults)
  ┌──▼──────────┐
  │ analyze     │  → Flag anomalies (AnalysisAgent)
  └──┬──────────┘
     │ (AnomalyReport)
  ┌──▼──────────┐
  │ save_report │  → Write JSON report (AnalysisAgent)
  └─────────────┘
"""

import os
import logging
from typing import Optional, TypedDict
from pathlib import Path
from datetime import datetime

from langgraph.graph import StateGraph, END

from models.pydantic_models import InvoiceData, ClassificationResult, BenchmarkResult, AnomalyReport
from agents.ingestion import IngestionAgent
from agents.extraction import ExtractionAgent
from agents.storage import StorageAgent, StorageResult
from agents.benchmarking import BenchmarkingAgent
from agents.analysis import AnalysisAgent
from utils.timer import get_timer, reset_timer

logger = logging.getLogger(__name__)


# ── AgentState ──
# This TypedDict is the "envelope" that carries data between agents.
# Each agent reads what it needs and writes its results.
class AgentState(TypedDict, total=False):
    """
    Shared state passed between all agent nodes in the workflow.
    
    Why TypedDict?
    - Type-safe: LangGraph validates the state shape at runtime
    - Self-documenting: you can see exactly what data flows through the pipeline
    - IDE autocomplete works — no guessing what keys are available
    
    total=False means all keys are optional (LangGraph handles missing keys gracefully).
    """
    # Input
    input_dir: str                          # Where to find PDFs
    pdf_files: list[str]                    # List of ALL PDF file paths found
    file_index: int                         # Current file being processed (0-based)
    total_files: int                        # Total number of PDFs to process
    
    # Per-file state (overwritten for each file processed)
    current_file: str                       # Current PDF being processed
    cached_markdown: str                    # Cached Docling output (avoids re-parsing)
    classification: Optional[ClassificationResult]  # Document type + confidence
    invoice_data: Optional[InvoiceData]     # Extracted structured data
    storage_result: Optional[StorageResult]  # DB save result
    benchmarks: Optional[list[BenchmarkResult]]  # Price comparison results
    anomaly_report: Optional[AnomalyReport]  # Final audit findings
    
    # Output (accumulates across all files)
    reports_saved: list[str]                # Paths to saved JSON report files
    errors: list[str]                       # Any errors encountered
    results: list[dict]                     # Per-file results summary
    summary: Optional[str]                  # Pipeline run summary
    dashboard_path: Optional[str]           # Path to aggregate dashboard JSON
    csv_path: Optional[str]                 # Path to CSV export (if requested)


# ── HermesOrchestrator ──
class HermesOrchestrator:
    """
    Main orchestrator that chains all agents into a LangGraph workflow.
    
    Usage:
        orchestrator = HermesOrchestrator()
        state = orchestrator.run(input_dir="input_docs")
        print(state["summary"])
        print(f"Reports saved: {state['reports_saved']}")
    """

    def __init__(self, use_mock_benchmark: Optional[bool] = None):
        """
        Initialize all agents and build the LangGraph workflow.
        
        Args:
            use_mock_benchmark: If True, use mock rates instead of Apify
        """
        logger.info("Initializing HermesOrchestrator...")

        # Initialize all agents
        self.ingestion_agent = IngestionAgent()
        self.extraction_agent = ExtractionAgent()
        self.storage_agent = StorageAgent()
        self.benchmarking_agent = BenchmarkingAgent(use_mock=use_mock_benchmark)
        self.analysis_agent = AnalysisAgent()

        # Build the workflow graph
        self.workflow = self._build_graph()
        self.app = self.workflow.compile()

        logger.info("HermesOrchestrator ready")

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph state machine.
        
        This defines:
        1. Nodes (what each agent does)
        2. Edges (what order they run in)
        3. Conditional routing (skip non-invoices, loop for next file)
        
        Graph structure:
            scan_docs → select_file → classify → [invoice?] → extract → store → 
            benchmark → analyze → save_report → select_next → [more files?] → select_file
                                                                        ↓ (no)
                                                                       END
        
        Returns:
            Compiled LangGraph workflow
        """
        graph = StateGraph(AgentState)

        # ── Add nodes ──
        graph.add_node("scan_docs", self._scan_docs)
        graph.add_node("select_file", self._select_file)
        graph.add_node("classify", self._classify)
        graph.add_node("extract", self._extract)
        graph.add_node("store", self._store)
        graph.add_node("benchmark", self._benchmark)
        graph.add_node("analyze", self._analyze)
        graph.add_node("save_report", self._save_report)
        graph.add_node("select_next", self._select_next_file)

        # ── Define edges ──

        # Start → scan → select first file
        graph.add_edge("scan_docs", "select_file")
        graph.add_edge("select_file", "classify")

        # classify → conditional: invoice? → extract OR skip to next file
        graph.add_conditional_edges(
            "classify",
            self._route_by_classification,
            {
                "extract": "extract",
                "next_file": "select_next",  # Non-invoice → skip to next file
            },
        )

        # Linear flow after extraction
        graph.add_edge("extract", "store")
        graph.add_edge("store", "benchmark")
        graph.add_edge("benchmark", "analyze")
        graph.add_edge("analyze", "save_report")
        graph.add_edge("save_report", "select_next")

        # select_next → conditional: more files? → select_file OR END
        graph.add_conditional_edges(
            "select_next",
            self._route_next_file_or_end,
            {
                "select_file": "select_file",
                "END": END,
            },
        )

        # Set the entry point
        graph.set_entry_point("scan_docs")

        return graph

    # ── Node Functions ──
    # Each function receives the current state and returns updates to the state.
    # LangGraph merges these updates automatically.

    def _scan_docs(self, state: AgentState) -> dict:
        """Find all PDF files in the input directory."""
        input_path = Path(state["input_dir"])
        pdf_files = sorted([str(p) for p in input_path.glob("*.pdf")])

        logger.info("Found %d PDF(s) in %s", len(pdf_files), state["input_dir"])

        if not pdf_files:
            state["errors"].append(f"No PDF files found in {state['input_dir']}")

        return {
            "pdf_files": pdf_files,
            "file_index": 0,
            "total_files": len(pdf_files),
        }

    def _select_file(self, state: AgentState) -> dict:
        """Select the current file to process based on file_index."""
        idx = state.get("file_index", 0)
        pdf_files = state.get("pdf_files", [])

        if idx >= len(pdf_files):
            # Shouldn't happen, but safety check
            return {"current_file": ""}

        current_file = pdf_files[idx]
        logger.info(
            "Processing file %d/%d: %s",
            idx + 1,
            state.get("total_files", len(pdf_files)),
            Path(current_file).name,
        )

        return {"current_file": current_file}

    def _classify(self, state: AgentState) -> dict:
        """Classify the current PDF (invoice vs other)."""
        current_file = state.get("current_file", "")
        if not current_file:
            logger.warning("No current file selected — skipping classification")
            return {"classification": None}

        logger.info("Classifying: %s", Path(current_file).name)

        timer = get_timer()
        with timer.step("classify"):
            # For classification, we need some text from the PDF
            # In a full system, Docling would extract text first
            # For MVP, we'll extract during the classify+extract phase
            try:
                # Extract markdown for classification (reuse extraction's docling call)
                markdown = self.extraction_agent.parse_pdf_to_markdown(current_file)

                # Classify using the extracted text
                classification = self.ingestion_agent.classify_document(
                    markdown, Path(current_file).name
                )

                # Also cache the markdown for the extraction step (avoids re-parsing)
                return {
                    "classification": classification,
                    "cached_markdown": markdown,
                }

            except Exception as e:
                logger.error("Classification failed for %s: %s", current_file, e)
                state["errors"].append(f"Classification error for {current_file}: {str(e)}")
                return {"classification": None}

    def _extract(self, state: AgentState) -> dict:
        """Extract structured data from the current PDF."""
        current_file = state["current_file"]
        logger.info("Extracting data from: %s", Path(current_file).name)

        timer = get_timer()
        with timer.step("extract"):
            try:
                # Use cached markdown if available (from classify step)
                markdown = state.get("cached_markdown")
                if markdown:
                    invoice_data = self.extraction_agent.extract_from_markdown(
                        markdown, Path(current_file).name
                    )
                else:
                    invoice_data = self.extraction_agent.extract_from_pdf(current_file)

                return {"invoice_data": invoice_data}

            except Exception as e:
                logger.error("Extraction failed for %s: %s", current_file, e)
                state["errors"].append(f"Extraction error for {current_file}: {str(e)}")
                return {"invoice_data": None}

    def _store(self, state: AgentState) -> dict:
        """Store the extracted invoice in the database."""
        invoice_data = state.get("invoice_data")
        if not invoice_data:
            logger.warning("No invoice data to store — skipping storage")
            return {"storage_result": None}

        logger.info("Storing invoice: %s / %s", invoice_data.vendor_name, invoice_data.invoice_number)

        timer = get_timer()
        with timer.step("store"):
            try:
                storage_result = self.storage_agent.store_invoice(invoice_data)
                return {"storage_result": storage_result}

            except Exception as e:
                logger.error("Storage failed: %s", e)
                state["errors"].append(f"Storage error: {str(e)}")
                return {"storage_result": None}

    def _benchmark(self, state: AgentState) -> dict:
        """Benchmark invoice prices against market rates."""
        invoice_data = state.get("invoice_data")
        if not invoice_data:
            logger.warning("No invoice data to benchmark")
            return {"benchmarks": []}

        timer = get_timer()
        with timer.step("benchmark"):
            try:
                benchmarks = self.benchmarking_agent.benchmark(invoice_data)
                return {"benchmarks": benchmarks}

            except Exception as e:
                logger.error("Benchmarking failed: %s", e)
                state["errors"].append(f"Benchmarking error: {str(e)}")
                return {"benchmarks": []}

    def _analyze(self, state: AgentState) -> dict:
        """Analyze invoice for anomalies and generate report."""
        invoice_data = state.get("invoice_data")
        benchmarks = state.get("benchmarks", [])
        storage_result = state.get("storage_result")

        if not invoice_data:
            logger.warning("No invoice data to analyze")
            return {"anomaly_report": None}

        timer = get_timer()
        with timer.step("analyze"):
            try:
                anomaly_report = self.analysis_agent.analyze(
                    invoice=invoice_data,
                    benchmarks=benchmarks,
                    storage_result=storage_result,
                )
                return {"anomaly_report": anomaly_report}

            except Exception as e:
                logger.error("Analysis failed: %s", e)
                state["errors"].append(f"Analysis error: {str(e)}")
                return {"anomaly_report": None}

    def _save_report(self, state: AgentState) -> dict:
        """Save the analysis report as a JSON file."""
        invoice_data = state.get("invoice_data")
        anomaly_report = state.get("anomaly_report")
        benchmarks = state.get("benchmarks", [])

        if not anomaly_report or not invoice_data:
            logger.warning("No report to save")
            return {"reports_saved": []}

        try:
            report_path = self.analysis_agent.save_report(
                report=anomaly_report,
                invoice=invoice_data,
                benchmarks=benchmarks,
            )

            reports_saved = state.get("reports_saved", []) + [report_path]

            logger.info("Pipeline complete for: %s", Path(state["current_file"]).name)

            return {"reports_saved": reports_saved}

        except Exception as e:
            logger.error("Failed to save report: %s", e)
            state["errors"].append(f"Report save error: {str(e)}")
            return {"reports_saved": []}

    def _route_by_classification(self, state: AgentState) -> str:
        """
        Conditional routing: is this document an invoice?
        
        Returns:
            "extract" if it's an invoice, "next_file" to skip to next PDF
        """
        classification = state.get("classification")

        if classification and classification.document_type == "invoice":
            logger.info(
                "Document classified as INVOICE (confidence=%.2f) → proceeding to extraction",
                classification.confidence,
            )
            return "extract"
        else:
            doc_type = classification.document_type if classification else "unknown"
            logger.info(
                "Document classified as '%s' → skipping to next file",
                doc_type,
            )
            return "next_file"

    def _select_next_file(self, state: AgentState) -> dict:
        """
        Increment file_index and record per-file result summary.
        
        This is called after save_report OR when a non-invoice is skipped.
        It accumulates results and prepares for the next iteration.
        """
        current_idx = state.get("file_index", 0)
        new_idx = current_idx + 1
        total = state.get("total_files", 0)
        current_file = state.get("current_file", "")
        
        # Build per-file result summary
        file_result = {
            "file": Path(current_file).name if current_file else "unknown",
            "classification": state.get("classification").document_type if state.get("classification") else "unknown",
            "saved_report": state.get("reports_saved", [])[-1] if state.get("reports_saved") else None,
            "has_anomaly": state.get("anomaly_report") is not None,
            "severity": state.get("anomaly_report").severity if state.get("anomaly_report") else None,
        }

        results = state.get("results", []) + [file_result]

        logger.info("Completed file %d/%d: %s", current_idx + 1, total, Path(current_file).name)

        return {
            "file_index": new_idx,
            "results": results,
            # Reset per-file state for next iteration
            "classification": None,
            "cached_markdown": "",
            "invoice_data": None,
            "storage_result": None,
            "benchmarks": None,
            "anomaly_report": None,
        }

    def _route_next_file_or_end(self, state: AgentState) -> str:
        """
        Conditional routing: are there more files to process?
        
        Returns:
            "select_file" if more files remain, "END" if all done
        """
        idx = state.get("file_index", 0)
        total = state.get("total_files", 0)

        if idx < total:
            logger.info("Moving to next file (%d/%d remaining)", total - idx, total)
            return "select_file"
        else:
            logger.info("All %d files processed — pipeline complete", total)
            return "END"

    def run(self, input_dir: str = "input_docs", export_csv: bool = False) -> AgentState:
        """
        Run the full pipeline on all PDFs in the input directory.
        
        Args:
            input_dir: Path to folder containing PDF files
            
        Returns:
            Final AgentState with all results
        """
        logger.info("=" * 60)
        logger.info("HERMES ORCHESTRATOR — Starting pipeline")
        logger.info("=" * 60)

        # Reset timer so each run gets clean measurements
        reset_timer()

        # Initialize state
        initial_state: AgentState = {
            "input_dir": input_dir,
            "pdf_files": [],
            "file_index": 0,
            "total_files": 0,
            "current_file": "",
            "classification": None,
            "invoice_data": None,
            "storage_result": None,
            "benchmarks": None,
            "anomaly_report": None,
            "reports_saved": [],
            "errors": [],
            "results": [],
            "summary": None,
            "dashboard_path": None,
            "csv_path": None,
        }

        # Run the workflow
        try:
            result = self.app.invoke(initial_state)

            # Generate summary
            files_processed = len(result.get("reports_saved", []))
            error_count = len(result.get("errors", []))
            total = result.get("total_files", 0)
            file_results = result.get("results", [])
            
            # Count by severity
            severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
            for fr in file_results:
                sev = fr.get("severity")
                if sev in severity_counts:
                    severity_counts[sev] += 1

            result["summary"] = (
                f"Pipeline completed: {total} file(s) scanned, "
                f"{files_processed} invoice(s) processed, "
                f"{error_count} error(s). "
                f"Severity: {severity_counts['critical']} critical, "
                f"{severity_counts['high']} high, "
                f"{severity_counts['medium']} medium, "
                f"{severity_counts['low']} low/clean. "
                f"Timestamp: {datetime.now().isoformat()}"
            )

            # Dashboard report (always generated)
            dashboard_path = self.analysis_agent.save_dashboard_report(
                file_results=result.get("results", []),
                reports_saved=result.get("reports_saved", []),
                errors=result.get("errors", []),
            )
            result["dashboard_path"] = dashboard_path

            # CSV export (opt-in via export_csv flag)
            if export_csv and result.get("results"):
                csv_path = self.analysis_agent.save_csv_export(
                    file_results=result.get("results", []),
                )
                result["csv_path"] = csv_path

            # Log timing breakdown
            get_timer().log_stats()

            logger.info("=" * 60)
            logger.info("HERMES ORCHESTRATOR — Pipeline Complete")
            logger.info(result["summary"])
            logger.info("=" * 60)

            return result

        except Exception as e:
            logger.critical("Orchestrator fatal error: %s", e)
            initial_state["errors"].append(f"Orchestrator fatal error: {str(e)}")
            initial_state["summary"] = f"Pipeline FAILED: {str(e)}"
            return initial_state
