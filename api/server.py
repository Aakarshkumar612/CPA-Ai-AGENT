"""
CPA AI Agent — FastAPI REST Backend

Exposes the full multi-agent pipeline over HTTP so any frontend can drive it.

Endpoints
---------
GET  /api/health                     Health check
GET  /api/status                     Project config & stats
POST /api/upload                     Upload PDF(s) to input_docs/
POST /api/pipeline/run               Trigger full audit pipeline
GET  /api/pipeline/status            Poll current pipeline state
GET  /api/pipeline/stream            SSE stream of pipeline log lines
GET  /api/invoices                   Paginated invoice list from DB
GET  /api/invoices/{id}              Invoice detail + its report data
GET  /api/dashboard                  Latest dashboard aggregate JSON
GET  /api/reports                    List saved report files
GET  /api/reports/{filename}         Raw JSON content of one report
POST /api/invoices/{id}/feedback     Submit CPA correction
GET  /api/feedback                   All correction log entries
DELETE /api/cache                    Clear Docling + LLM cache

Run with:
    uv run python -m uvicorn api.server:app --reload --port 8000
"""

import json
import os
import queue
import threading
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

# ── App setup ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="CPA AI Agent",
    description="Multi-agent AI pipeline for freight invoice auditing",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:4173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

INPUT_DIR = Path("input_docs")
OUTPUT_DIR = Path("output_reports")
INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("api.server")

# ── Pipeline state (in-memory; single-user CLI tool) ───────────────────────
_pipeline_lock = threading.Lock()
_pipeline_state: dict[str, Any] = {
    "status": "idle",        # idle | running | completed | failed
    "started_at": None,
    "completed_at": None,
    "last_result": None,
    "error": None,
}
# Queue that pipeline thread pushes log lines into for SSE streaming
_log_queue: queue.Queue = queue.Queue(maxsize=500)


# ── Request / Response schemas ─────────────────────────────────────────────
class FeedbackRequest(BaseModel):
    field_name: str
    original_value: str
    corrected_value: str
    notes: Optional[str] = None


class PipelineRunRequest(BaseModel):
    export_csv: bool = False


# ── Helpers ────────────────────────────────────────────────────────────────
def _push_log(msg: str) -> None:
    """Push a log line to the SSE queue (non-blocking)."""
    try:
        _log_queue.put_nowait({"timestamp": datetime.now().isoformat(), "message": msg})
    except queue.Full:
        pass


def _run_pipeline_thread(export_csv: bool) -> None:
    """Run the full pipeline in a background thread."""
    from utils.db_utils import init_db
    from agents.orchestrator import HermesOrchestrator

    with _pipeline_lock:
        _pipeline_state["status"] = "running"
        _pipeline_state["started_at"] = datetime.now().isoformat()
        _pipeline_state["last_result"] = None
        _pipeline_state["error"] = None

    _push_log("Pipeline starting…")
    try:
        init_db()
        _push_log("Database initialised")

        orchestrator = HermesOrchestrator()
        _push_log("Agents loaded — processing PDFs in input_docs/")

        result = orchestrator.run(str(INPUT_DIR), export_csv=export_csv)

        _push_log(f"Pipeline complete: {result.get('summary', '')}")
        with _pipeline_lock:
            _pipeline_state["status"] = "completed"
            _pipeline_state["completed_at"] = datetime.now().isoformat()
            _pipeline_state["last_result"] = {
                "summary": result.get("summary"),
                "reports_saved": result.get("reports_saved", []),
                "dashboard_path": result.get("dashboard_path"),
                "csv_path": result.get("csv_path"),
                "errors": result.get("errors", []),
                "results": result.get("results", []),
            }
    except Exception as exc:
        logger.exception("Pipeline thread failed")
        _push_log(f"ERROR: {exc}")
        with _pipeline_lock:
            _pipeline_state["status"] = "failed"
            _pipeline_state["completed_at"] = datetime.now().isoformat()
            _pipeline_state["error"] = str(exc)


# ── Routes ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/status")
def project_status():
    """Return configuration status and quick stats."""
    from utils.settings import settings
    from utils.db_utils import get_session
    from models.database import Invoice, Feedback

    pdf_count = len(list(INPUT_DIR.glob("*.pdf")))
    report_count = len(list(OUTPUT_DIR.glob("audit_*.json")))

    # Quick DB counts
    session = get_session()
    try:
        invoice_count = session.query(Invoice).count()
        feedback_count = session.query(Feedback).count()
    finally:
        session.close()

    return {
        "groq_configured": bool(os.getenv("GROQ_API_KEY")),
        "apify_configured": bool(os.getenv("APIFY_API_TOKEN")),
        "mock_mode": settings.USE_MOCK_APIFY,
        "database_url": settings.DATABASE_URL,
        "input_pdfs": pdf_count,
        "reports_generated": report_count,
        "invoices_in_db": invoice_count,
        "feedback_corrections": feedback_count,
        "pipeline_status": _pipeline_state["status"],
    }


@app.post("/api/upload")
async def upload_pdfs(files: list[UploadFile] = File(...)):
    """Upload one or more PDF files into input_docs/."""
    saved = []
    for upload in files:
        if not upload.filename or not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(400, detail=f"Only PDF files accepted, got: {upload.filename}")
        dest = INPUT_DIR / upload.filename
        with open(dest, "wb") as f:
            shutil.copyfileobj(upload.file, f)
        saved.append(upload.filename)
    return {"uploaded": saved, "count": len(saved)}


@app.post("/api/pipeline/run")
def run_pipeline(body: PipelineRunRequest = PipelineRunRequest()):
    """
    Trigger the full audit pipeline asynchronously.

    Returns immediately — poll /api/pipeline/status or stream /api/pipeline/stream.
    """
    with _pipeline_lock:
        if _pipeline_state["status"] == "running":
            raise HTTPException(409, detail="Pipeline is already running")

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(body.export_csv,),
        daemon=True,
    )
    thread.start()
    return {"message": "Pipeline started", "status": "running"}


@app.get("/api/pipeline/status")
def pipeline_status():
    """Poll current pipeline run state."""
    with _pipeline_lock:
        return dict(_pipeline_state)


@app.get("/api/pipeline/stream")
def pipeline_stream():
    """
    Server-Sent Events stream of pipeline log lines.
    Connect with: EventSource('/api/pipeline/stream')
    """
    def generate():
        # Drain any buffered lines first
        while True:
            try:
                item = _log_queue.get(timeout=30)
                data = json.dumps(item)
                yield f"data: {data}\n\n"
                if "Pipeline complete" in item.get("message", "") or "ERROR:" in item.get("message", ""):
                    break
            except queue.Empty:
                # Send keep-alive comment
                yield ": keep-alive\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/invoices")
def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Return paginated list of all invoices in the database."""
    from utils.db_utils import get_session
    from models.database import Invoice

    session = get_session()
    try:
        total = session.query(Invoice).count()
        offset = (page - 1) * page_size
        rows = (
            session.query(Invoice)
            .order_by(Invoice.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        invoices = []
        for inv in rows:
            invoices.append({
                "id": inv.id,
                "vendor_name": inv.vendor_name,
                "invoice_number": inv.invoice_number,
                "invoice_date": str(inv.invoice_date) if inv.invoice_date else None,
                "currency": inv.currency,
                "incoterms": inv.incoterms,
                "total_amount": inv.total_amount,
                "status": inv.status,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
            })
        return {
            "invoices": invoices,
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_next": (offset + page_size) < total,
        }
    finally:
        session.close()


@app.get("/api/invoices/{invoice_id}")
def get_invoice(invoice_id: int):
    """Return one invoice with its latest audit report data."""
    from utils.db_utils import get_session
    from models.database import Invoice

    session = get_session()
    try:
        inv = session.query(Invoice).filter_by(id=invoice_id).first()
        if not inv:
            raise HTTPException(404, detail=f"Invoice {invoice_id} not found")

        # Try to find the matching audit report
        report_data = None
        pattern = f"audit_{inv.invoice_number}_*.json"
        matches = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
        if matches:
            try:
                with open(matches[0]) as f:
                    report_data = json.load(f)
            except (IOError, json.JSONDecodeError):
                pass

        return {
            "id": inv.id,
            "vendor_name": inv.vendor_name,
            "invoice_number": inv.invoice_number,
            "invoice_date": str(inv.invoice_date) if inv.invoice_date else None,
            "currency": inv.currency,
            "incoterms": inv.incoterms,
            "total_amount": inv.total_amount,
            "status": inv.status,
            "raw_extracted_data": inv.raw_extracted_data,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "audit_report": report_data,
        }
    finally:
        session.close()


@app.get("/api/dashboard")
def get_dashboard():
    """Return the most recent dashboard aggregate report."""
    dashboards = sorted(OUTPUT_DIR.glob("dashboard_*.json"), reverse=True)
    if not dashboards:
        # Return empty structure if no pipeline has run yet
        return {
            "run_summary": {"invoices_processed": 0, "total_invoice_value_usd": 0},
            "severity_breakdown": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "top_vendors_by_spend": {},
            "top_anomaly_types": {},
            "most_overpriced_routes": {},
            "per_invoice_summary": [],
            "_empty": True,
        }
    try:
        with open(dashboards[0]) as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        raise HTTPException(500, detail=f"Could not read dashboard: {e}")


@app.get("/api/reports")
def list_reports():
    """List all saved audit report files."""
    files = sorted(OUTPUT_DIR.glob("audit_*.json"), reverse=True)
    return {
        "reports": [
            {
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "modified_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            }
            for f in files
        ],
        "count": len(files),
    }


@app.get("/api/reports/{filename}")
def get_report(filename: str):
    """Return the JSON content of a specific audit report."""
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, detail="Invalid filename")
    path = OUTPUT_DIR / filename
    if not path.exists():
        raise HTTPException(404, detail=f"Report not found: {filename}")
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise HTTPException(500, detail=f"Malformed report JSON: {e}")


@app.post("/api/invoices/{invoice_id}/feedback")
def submit_feedback(invoice_id: int, body: FeedbackRequest):
    """Log a CPA correction for an extracted invoice field."""
    from agents.feedback import FeedbackAgent
    from utils.db_utils import get_session
    from models.database import Invoice

    session = get_session()
    try:
        inv = session.query(Invoice).filter_by(id=invoice_id).first()
        if not inv:
            raise HTTPException(404, detail=f"Invoice {invoice_id} not found")
    finally:
        session.close()

    agent = FeedbackAgent()
    record = agent.log_correction(
        invoice_id=invoice_id,
        field_name=body.field_name,
        original_value=body.original_value,
        corrected_value=body.corrected_value,
        notes=body.notes,
    )
    return {
        "success": True,
        "feedback_id": record.id if record else None,
        "message": f"Correction logged for field '{body.field_name}'",
    }


@app.get("/api/feedback")
def get_feedback():
    """Return all CPA corrections from the feedback log."""
    from agents.feedback import FeedbackAgent
    agent = FeedbackAgent()
    entries = agent.get_feedback_summary()
    common = agent.get_common_corrections()
    return {
        "entries": entries,
        "total": len(entries),
        "most_common_corrections": dict(list(common.items())[:10]),
    }


@app.delete("/api/cache")
def clear_cache():
    """Clear all Docling and LLM cache entries."""
    from utils.cache import get_cache
    count = get_cache().clear()
    return {"message": f"Cache cleared — {count} entries removed", "removed": count}


# ── Dev entrypoint ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
