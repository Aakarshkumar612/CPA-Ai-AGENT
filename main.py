"""
Crowd Wisdom Trading CPA AI Agent — Main Entry Point

What this is:
- The single entry point to run the full AI auditing pipeline
- Loads environment, initializes the Hermes Orchestrator, and runs it
- Can be run as a script or imported as a module

Usage:
    # Run on all PDFs in input_docs:
    uv run python main.py

    # Run on a specific folder:
    uv run python main.py --input ./my_invoices

    # Use real Apify instead of mock:
    uv run python main.py --no-mock
    

    # Show verbose output:
    uv run python main.py --verbose
"""

import argparse
import io
import logging
import sys
import json
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

# Load .env before anything else so pydantic-settings can read it
load_dotenv()

# Force UTF-8 on Windows terminals (default cp1252 can't encode emojis/arrows)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from utils.db_utils import init_db
from utils.generate_dummy_pdf import generate_dummy_invoice
from agents.orchestrator import HermesOrchestrator
from agents.feedback import FeedbackAgent


def setup_logging(verbose: bool = False) -> None:
    """
    Configure Python's logging module.
    
    Why logging?
    - print() is fine for scripts, but logging gives you:
      - Timestamps on every message
      - Severity levels (INFO, WARNING, ERROR, CRITICAL)
      - File output (save logs to disk)
      - Integration with other libraries (SQLAlchemy logs too)
    
    Args:
        verbose: If True, show DEBUG level (everything)
    """
    level = logging.DEBUG if verbose else logging.INFO

    # sys.stdout is already UTF-8 (reconfigured at module level above)
    utf8_stdout = sys.stdout

    handler = logging.StreamHandler(utf8_stdout)
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter(
            fmt="[%(levelname)s] %(asctime)s %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Silence chatty third-party libraries
    for noisy in ("httpx", "httpcore", "urllib3", "huggingface_hub", "torch"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def cmd_run(args: argparse.Namespace) -> None:
    """Run the full CPA audit pipeline."""
    logger = logging.getLogger("main")
    
    # Step 1: Initialize database
    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready")

    # Step 2: Run the orchestrator
    orchestrator = HermesOrchestrator(use_mock_benchmark=not args.no_mock)
    result = orchestrator.run(args.input, export_csv=args.csv)

    # Step 3: Print summary
    print()
    print("=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(result.get("summary", "No summary available"))
    
    reports = result.get("reports_saved", [])
    if reports:
        print(f"\n📄 Reports saved ({len(reports)}):")
        for report_path in reports:
            print(f"   {report_path}")

    dashboard = result.get("dashboard_path")
    if dashboard:
        print(f"\n📊 Dashboard: {dashboard}")

    csv_path = result.get("csv_path")
    if csv_path:
        print(f"\n📋 CSV export: {csv_path}")

    errors = result.get("errors", [])
    if errors:
        print(f"\n⚠️ Errors ({len(errors)}):")
        for error in errors:
            print(f"   ❌ {error}")

    if not reports and not errors:
        print("\nℹ️ No PDF files found to process.")
    
    print("=" * 60)


def cmd_generate_dummy(args: argparse.Namespace) -> None:
    """Generate a dummy PDF invoice for testing."""
    output_path = generate_dummy_invoice()
    print(f"✅ Generated dummy invoice: {output_path}")


def cmd_feedback(args: argparse.Namespace) -> None:
    """View feedback log (CPA corrections)."""
    agent = FeedbackAgent()
    summary = agent.get_feedback_summary()
    
    if not summary:
        print("No feedback entries recorded yet.")
        return
    
    print(f"\n📝 Feedback Log ({len(summary)} entries)")
    print("=" * 60)
    for entry in summary:
        print(f"  [{entry['timestamp']}] Invoice #{entry['invoice_id']}")
        print(f"    Field: {entry['field_name']}")
        print(f"    Was:   '{entry['original_value']}'")
        print(f"    Now:   '{entry['corrected_value']}'")
        if entry.get('notes'):
            print(f"    Note:  {entry['notes']}")
        print()


def cmd_status(args: argparse.Namespace) -> None:
    """Show project status and configuration."""
    from utils.freight_rate_service import create_rate_service
    
    print("\n🔧 Crowd Wisdom Trading CPA AI Agent — Status")
    print("=" * 60)
    
    # Check .env
    import os
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file found")
    else:
        print("⚠️ .env file NOT found (copy .env.example to .env)")
    
    # Check Groq
    if os.getenv("GROQ_API_KEY"):
        print("✅ GROQ_API_KEY set")
    else:
        print("❌ GROQ_API_KEY not set")
    
    # Check Apify
    if os.getenv("APIFY_API_TOKEN"):
        print("✅ APIFY_API_TOKEN set")
    else:
        print("ℹ️ APIFY_API_TOKEN not set (using mock mode)")
    
    # Check mock mode
    use_mock = os.getenv("USE_MOCK_APIFY", "true").lower() == "true"
    print(f"{'✅' if use_mock else 'ℹ️ '} Mock mode: {'ON' if use_mock else 'OFF'}")
    
    # Check database
    db_path = Path("cpa_agent.db")
    if db_path.exists():
        print(f"✅ Database exists: {db_path}")
    else:
        print("ℹ️ Database not yet created (will be created on first run)")
    
    # Check input docs
    input_dir = Path("input_docs")
    pdf_count = len(list(input_dir.glob("*.pdf"))) if input_dir.exists() else 0
    print(f"{'✅' if pdf_count > 0 else 'ℹ️ '} Input PDFs: {pdf_count}")
    
    # Check output reports
    output_dir = Path("output_reports")
    report_count = len(list(output_dir.glob("*.json"))) if output_dir.exists() else 0
    print(f"{'✅' if report_count > 0 else 'ℹ️ '} Output reports: {report_count}")
    
    # Show service info
    service = create_rate_service()
    if isinstance(service, type(create_rate_service(use_mock=True))):
        routes = len(service.get_all_known_routes())  # type: ignore
        print(f"✅ Rate service: {type(service).__name__} ({routes} routes)")
    
    print("=" * 60)


def main() -> None:
    """
    Main entry point with CLI argument parsing.
    
    Subcommands:
        run        — Run the full CPA audit pipeline
        generate   — Generate a dummy PDF invoice for testing
        feedback   — View the feedback correction log
        status     — Show project configuration status
    """
    parser = argparse.ArgumentParser(
        description="Crowd Wisdom Trading CPA AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run python main.py run                # Run pipeline on input_docs/
  uv run python main.py run --verbose      # Run with detailed logging
  uv run python main.py generate           # Create a test PDF
  uv run python main.py status             # Check configuration
  uv run python main.py feedback           # View corrections log
        """,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # ── run ──
    run_parser = subparsers.add_parser("run", help="Run the full CPA audit pipeline")
    run_parser.add_argument(
        "--input", "-i",
        default="input_docs",
        help="Input directory containing PDF files (default: input_docs)",
    )
    run_parser.add_argument(
        "--no-mock",
        action="store_true",
        help="Use real Apify instead of mock rates",
    )
    run_parser.add_argument(
        "--csv",
        action="store_true",
        help="Export results as CSV for CPA Excel import",
    )
    run_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed debug output",
    )
    run_parser.set_defaults(func=cmd_run)
    
    # ── generate ──
    gen_parser = subparsers.add_parser("generate", help="Generate a dummy PDF invoice")
    gen_parser.set_defaults(func=cmd_generate_dummy)
    
    # ── feedback ──
    fb_parser = subparsers.add_parser("feedback", help="View feedback correction log")
    fb_parser.set_defaults(func=cmd_feedback)
    
    # ── status ──
    st_parser = subparsers.add_parser("status", help="Show project configuration status")
    st_parser.set_defaults(func=cmd_status)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    # Setup logging (must be before any agent initialization)
    verbose = getattr(args, "verbose", False)
    setup_logging(verbose=verbose)
    
    # Run the command
    args.func(args)


if __name__ == "__main__":
    main()
