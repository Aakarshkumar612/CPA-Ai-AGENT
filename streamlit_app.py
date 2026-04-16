"""CPA AI Agent — Streamlit UI for the Crowd Wisdom Trading invoice auditing pipeline."""

import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# ── Bootstrap ──────────────────────────────────────────────────────────────────
load_dotenv()

# Inject Streamlit secrets into env (works on Streamlit Cloud + Render)
if hasattr(st, "secrets"):
    for _key in ("GROQ_API_KEY", "APIFY_API_TOKEN", "USE_MOCK_APIFY", "DATABASE_URL"):
        if _key in st.secrets:
            os.environ[_key] = str(st.secrets[_key])

# Silence heavy third-party loggers
for _lib in ("httpx", "httpcore", "urllib3", "huggingface_hub", "torch", "docling", "transformers"):
    logging.getLogger(_lib).setLevel(logging.WARNING)

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CPA AI Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Directory setup ────────────────────────────────────────────────────────────
INPUT_DIR = Path("input_docs")
OUTPUT_DIR = Path("output_reports")
INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


# ── DB init — cached once per server lifetime ──────────────────────────────────
@st.cache_resource(show_spinner="Initializing database...")
def _init_db() -> None:
    from utils.db_utils import init_db
    init_db()


_init_db()


# ── Session state defaults ─────────────────────────────────────────────────────
# job dict is mutated in-place by the background thread — safe because dict is
# a mutable reference stored in session_state (thread writes into it, not to
# session_state directly which is not thread-safe).
if "job" not in st.session_state:
    st.session_state.job = {
        "status": "idle",   # idle | running | completed | failed
        "logs": [],
        "result": None,
        "error": None,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────
def _severity_icon(sev: str) -> str:
    return {
        "critical": "🔴 Critical",
        "high": "🟠 High",
        "medium": "🟡 Medium",
        "low": "🟢 Low",
        "clean": "🟢 Clean",
    }.get((sev or "").lower(), f"⚪ {sev or '—'}")


def _render_report(report: dict) -> None:
    """Render one audit JSON report in a structured layout."""
    meta = report.get("report_metadata", {})
    anomaly = report.get("anomaly_report", {})
    invoice = report.get("invoice_data", {})
    benchmarks = report.get("benchmark_results", [])

    c1, c2, c3 = st.columns(3)
    c1.metric("Invoice #", invoice.get("invoice_number", "—"))
    c2.metric("Vendor", invoice.get("vendor_name", "—"))
    c3.metric("Severity", _severity_icon(anomaly.get("severity", "")))

    if anomaly.get("summary"):
        st.info(anomaly["summary"])

    anomalies = anomaly.get("anomalies", [])
    if anomalies:
        st.write("**Anomalies detected:**")
        for a in anomalies:
            st.write(f"- {a}")

    line_items = invoice.get("line_items", [])
    if line_items:
        st.write("**Line items:**")
        st.dataframe(pd.DataFrame(line_items), use_container_width=True, hide_index=True)

    if benchmarks:
        st.write("**Price benchmarks:**")
        df_bm = pd.DataFrame(benchmarks)
        df_bm["flag"] = df_bm["is_overpriced"].map({True: "⚠️ Overpriced", False: "✅ OK"})
        display_cols = [c for c in
                        ["route", "invoice_price", "market_average", "deviation_percent", "flag"]
                        if c in df_bm.columns]
        st.dataframe(df_bm[display_cols], use_container_width=True, hide_index=True)

    timing = meta.get("pipeline_timing", {})
    if timing:
        with st.expander("Pipeline timing breakdown"):
            st.json(timing)


def _render_dashboard(dash: dict) -> None:
    """Render the dashboard aggregate JSON."""
    run = dash.get("run_summary", {})
    sev = dash.get("severity_breakdown", {})

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Invoices processed", run.get("invoices_processed", 0))
    c2.metric("Total value (USD)", f"${run.get('total_invoice_value_usd', 0):,.0f}")
    c3.metric("🔴 Critical", sev.get("critical", 0))
    c4.metric("🟠 High", sev.get("high", 0))
    c5.metric("🟡 Medium", sev.get("medium", 0))

    per_invoice = dash.get("per_invoice_summary", [])
    if per_invoice:
        st.write("**Per-invoice summary:**")
        st.dataframe(pd.DataFrame(per_invoice), use_container_width=True, hide_index=True)

    top_vendors = dash.get("top_vendors_by_spend", {})
    if top_vendors:
        st.write("**Top vendors by spend:**")
        st.bar_chart(pd.Series(top_vendors).sort_values(ascending=False))

    top_anomaly = dash.get("top_anomaly_types", {})
    if top_anomaly:
        st.write("**Most common anomaly types:**")
        st.bar_chart(pd.Series(top_anomaly))


# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 CPA AI Agent")
    st.caption("Crowd Wisdom Trading — Invoice Auditor")
    st.divider()

    page = st.radio(
        "Navigate",
        ["🚀 Upload & Run", "📋 Invoices", "📄 Reports", "💬 Feedback"],
        label_visibility="collapsed",
    )

    st.divider()

    groq_ok = bool(os.getenv("GROQ_API_KEY"))
    mock_mode = os.getenv("USE_MOCK_APIFY", "true").lower() == "true"
    job_status = st.session_state.job["status"]

    st.caption("**Config**")
    st.write(f"{'✅' if groq_ok else '❌'} Groq API key")
    st.write(f"{'🔧' if mock_mode else '🌐'} {'Mock freight rates' if mock_mode else 'Live Apify rates'}")

    pdf_count = len(list(INPUT_DIR.glob("*.pdf")))
    report_count = len(list(OUTPUT_DIR.glob("audit_*.json")))
    st.write(f"📁 {pdf_count} PDF(s) in queue")
    st.write(f"📊 {report_count} audit report(s)")

    st.divider()
    if job_status == "running":
        st.warning("⏳ Pipeline running…")
    elif job_status == "completed":
        st.success("✅ Last run completed")
    elif job_status == "failed":
        st.error("❌ Last run failed")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Upload & Run
# ══════════════════════════════════════════════════════════════════════════════
if page == "🚀 Upload & Run":
    st.header("Upload Invoices & Run Audit Pipeline")

    # ── File upload ────────────────────────────────────────────────────────────
    uploaded_files = st.file_uploader(
        "Upload PDF invoice(s)",
        type="pdf",
        accept_multiple_files=True,
        help="Drag and drop one or more freight invoices. Saved into input_docs/.",
    )
    if uploaded_files:
        for uf in uploaded_files:
            dest = INPUT_DIR / uf.name
            with open(dest, "wb") as fh:
                fh.write(uf.getvalue())
        st.success(f"Saved {len(uploaded_files)} file(s) to queue.")
        st.rerun()

    # ── Queue viewer ───────────────────────────────────────────────────────────
    pdfs = sorted(INPUT_DIR.glob("*.pdf"))
    if pdfs:
        st.write(f"**Queued ({len(pdfs)}):**")
        for pdf in pdfs:
            col_name, col_btn = st.columns([6, 1])
            col_name.write(f"📄 {pdf.name}")
            if col_btn.button("✕", key=f"rm_{pdf.name}", help="Remove from queue"):
                pdf.unlink()
                st.rerun()
    else:
        st.info("No PDFs in queue. Upload invoices above.")

    st.divider()

    job = st.session_state.job

    # ── Running state — auto-refresh every 2s ─────────────────────────────────
    if job["status"] == "running":
        st.info("⏳ Pipeline is running — this page refreshes every 2 seconds.")

        logs = job["logs"]
        if logs:
            with st.expander("Live logs", expanded=True):
                st.code("\n".join(f"[{l['ts']}] {l['msg']}" for l in logs[-30:]))

        time.sleep(2)
        st.rerun()

    # ── Idle / completed / failed ──────────────────────────────────────────────
    else:
        export_csv = st.checkbox("Export results as CSV", value=False)

        can_run = bool(pdfs) and groq_ok
        run_btn = st.button(
            "▶ Run Audit Pipeline",
            type="primary",
            disabled=not can_run,
        )

        if not groq_ok:
            st.warning("Set `GROQ_API_KEY` in `.env` or Streamlit secrets to enable the pipeline.")
        if not pdfs:
            st.info("Upload at least one PDF to enable the Run button.")

        if run_btn:
            job["status"] = "running"
            job["logs"] = []
            job["result"] = None
            job["error"] = None

            def _push_log(msg: str) -> None:
                job["logs"].append({"ts": datetime.now().strftime("%H:%M:%S"), "msg": msg})

            def _run_pipeline() -> None:
                try:
                    from utils.db_utils import init_db
                    from agents.orchestrator import HermesOrchestrator

                    _push_log("Initializing database…")
                    init_db()
                    _push_log("Loading LangGraph agents (Groq + Docling) — this takes ~30s on first run…")
                    orchestrator = HermesOrchestrator()
                    pdf_list = list(INPUT_DIR.glob("*.pdf"))
                    _push_log(f"Processing {len(pdf_list)} PDF(s) in input_docs/…")
                    result = orchestrator.run(str(INPUT_DIR), export_csv=export_csv)
                    _push_log(f"Done: {result.get('summary', 'completed')}")
                    job["result"] = result
                    job["status"] = "completed"
                except Exception as exc:
                    _push_log(f"ERROR: {exc}")
                    job["error"] = str(exc)
                    job["status"] = "failed"

            threading.Thread(target=_run_pipeline, daemon=True).start()
            st.rerun()

        # ── Show last result ───────────────────────────────────────────────────
        if job["status"] in ("completed", "failed"):
            st.divider()

            if job["status"] == "failed":
                st.error(f"Pipeline failed: {job.get('error', 'Unknown error')}")
            else:
                result = job["result"] or {}
                st.success(result.get("summary", "Pipeline completed"))

                file_results = result.get("results", [])
                if file_results:
                    df = pd.DataFrame(file_results)
                    if "severity" in df.columns:
                        df["severity"] = df["severity"].apply(_severity_icon)
                    st.dataframe(df, use_container_width=True, hide_index=True)

                errors = result.get("errors", [])
                if errors:
                    with st.expander(f"⚠️ {len(errors)} error(s)"):
                        for err in errors:
                            st.error(err)

                reports = result.get("reports_saved", [])
                if reports:
                    st.caption(f"Reports written: {', '.join(Path(r).name for r in reports)}")

                if result.get("csv_path"):
                    st.caption(f"CSV export: {result['csv_path']}")

            logs = job.get("logs", [])
            if logs:
                with st.expander("Run logs"):
                    st.code("\n".join(f"[{l['ts']}] {l['msg']}" for l in logs))

            if st.button("Reset for next run"):
                job.update({"status": "idle", "logs": [], "result": None, "error": None})
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Invoices
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Invoices":
    st.header("Invoice Database")

    try:
        from utils.db_utils import get_session
        from models.database import Invoice

        session = get_session()
        rows = session.query(Invoice).order_by(Invoice.created_at.desc()).all()
        session.close()

        if not rows:
            st.info("No invoices in the database yet. Run the pipeline to populate it.")
            st.stop()

        # ── Summary table ──────────────────────────────────────────────────────
        table_data = [
            {
                "ID": r.id,
                "Vendor": r.vendor_name or "—",
                "Invoice #": r.invoice_number or "—",
                "Date": str(r.invoice_date) if r.invoice_date else "—",
                "Currency": r.currency or "—",
                "Incoterms": r.incoterms or "—",
                "Total": r.total_amount or 0.0,
                "Status": r.status or "—",
            }
            for r in rows
        ]
        st.dataframe(pd.DataFrame(table_data), use_container_width=True, hide_index=True)

        st.divider()

        # ── Detail view ────────────────────────────────────────────────────────
        st.subheader("Invoice Detail")
        selected_id = st.selectbox(
            "Select invoice",
            [r.id for r in rows],
            format_func=lambda i: next(
                (f"#{r.id} — {r.invoice_number} ({r.vendor_name})" for r in rows if r.id == i),
                str(i),
            ),
        )

        inv = next((r for r in rows if r.id == selected_id), None)
        if inv:
            c1, c2, c3 = st.columns(3)
            c1.metric("Vendor", inv.vendor_name or "—")
            c2.metric("Invoice #", inv.invoice_number or "—")
            c3.metric("Total", f"{inv.currency or ''} {(inv.total_amount or 0):,.2f}")

            c4, c5, c6 = st.columns(3)
            c4.metric("Date", str(inv.invoice_date) if inv.invoice_date else "—")
            c5.metric("Incoterms", inv.incoterms or "—")
            c6.metric("Status", _severity_icon(inv.status))

            if inv.raw_extracted_data:
                with st.expander("Raw extracted JSON"):
                    try:
                        st.json(json.loads(inv.raw_extracted_data))
                    except Exception:
                        st.text(inv.raw_extracted_data)

            # Matching audit report
            matches = sorted(OUTPUT_DIR.glob(f"audit_{inv.invoice_number}_*.json"), reverse=True)
            if matches:
                with st.expander("Latest audit report", expanded=True):
                    try:
                        with open(matches[0]) as fh:
                            _render_report(json.load(fh))
                    except Exception as exc:
                        st.error(f"Could not load report: {exc}")

            # CPA correction form
            with st.expander("Submit CPA correction"):
                with st.form(f"fb_{selected_id}"):
                    field = st.text_input("Field name", placeholder="e.g. total_amount")
                    original = st.text_input("Original (extracted) value")
                    corrected = st.text_input("Corrected value")
                    notes = st.text_area("Notes (optional)")
                    if st.form_submit_button("Log correction"):
                        if field and corrected:
                            from agents.feedback import FeedbackAgent
                            FeedbackAgent().log_correction(
                                invoice_id=selected_id,
                                field_name=field,
                                original_value=original,
                                corrected_value=corrected,
                                notes=notes or None,
                            )
                            st.success("Correction logged successfully.")
                        else:
                            st.warning("Field name and corrected value are required.")

    except Exception as exc:
        st.error(f"Database error: {exc}")
        with st.expander("Details"):
            st.exception(exc)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Reports
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📄 Reports":
    st.header("Audit Reports")

    # Dashboard aggregate
    dashboard_files = sorted(OUTPUT_DIR.glob("dashboard_*.json"), reverse=True)
    if dashboard_files:
        with st.expander("📊 Latest pipeline dashboard", expanded=True):
            try:
                with open(dashboard_files[0]) as fh:
                    _render_dashboard(json.load(fh))
            except Exception as exc:
                st.error(f"Could not read dashboard: {exc}")
    else:
        st.info("No dashboard yet — run the pipeline to generate one.")

    st.divider()

    # Individual audit reports
    report_files = sorted(OUTPUT_DIR.glob("audit_*.json"), reverse=True)
    st.subheader(f"Individual audit reports ({len(report_files)})")

    if not report_files:
        st.info("No reports yet. Upload PDFs and run the pipeline.")
    else:
        for rf in report_files:
            with st.expander(rf.name):
                try:
                    with open(rf) as fh:
                        _render_report(json.load(fh))
                except Exception as exc:
                    st.error(f"Could not read {rf.name}: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE: Feedback
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💬 Feedback":
    st.header("CPA Correction Log")

    try:
        from agents.feedback import FeedbackAgent
        agent = FeedbackAgent()
        entries = agent.get_feedback_summary()
        common = agent.get_common_corrections()

        if not entries:
            st.info("No CPA corrections recorded yet. Open an invoice and submit a correction.")
            st.stop()

        st.metric("Total corrections logged", len(entries))
        st.dataframe(pd.DataFrame(entries), use_container_width=True, hide_index=True)

        if common:
            st.subheader("Most frequently corrected fields")
            st.bar_chart(pd.Series(common).sort_values(ascending=False))

    except Exception as exc:
        st.error(f"Error loading feedback: {exc}")
        with st.expander("Details"):
            st.exception(exc)
