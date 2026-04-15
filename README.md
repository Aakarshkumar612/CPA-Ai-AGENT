# CPA AI Agent

> End-to-end multi-agent AI system for automated freight invoice auditing — from raw PDF to a live analytics dashboard.

Accepts PDF invoices, extracts structured data with an LLM, benchmarks freight rates against live market prices, flags pricing anomalies, and serves everything through a REST API to an interactive TypeScript dashboard.

---

## What it does

1. **Ingests PDFs** — scans `input_docs/` for freight invoices, classifies them via Groq LLM
2. **Extracts structured data** — Docling converts PDF tables to Markdown; Llama 3.3-70B pulls vendor, dates, line items, currency, incoterms
3. **Deduplicates** — checks SQLite before saving to prevent double-processing
4. **Benchmarks prices** — compares invoice rates against live market freight data (Apify) or mock rates
5. **Flags anomalies** — Critical / High / Medium / Low severity by % deviation from market
6. **Generates reports** — JSON audit reports saved to `output_reports/`
7. **Serves a dashboard** — 18 FastAPI endpoints + SSE streaming + Vite/TypeScript frontend

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Package manager** | `uv` | 10–100× faster than pip, lock-file reproducibility |
| **Backend framework** | FastAPI + Uvicorn | Async-first, auto OpenAPI docs, Pydantic-native |
| **Agent orchestration** | LangGraph | State machine: conditional routing, shared typed state |
| **LLM provider** | Groq (Llama 3.3-70B) | ~300 tok/s inference, free tier, no vendor lock-in |
| **PDF parser** | Docling (IBM) | Preserves table structure as Markdown — the only OSS tool that does this reliably |
| **Market data** | Apify Client | Managed scraper for live freight rate sites |
| **Database** | SQLite + SQLAlchemy 2.0 | Zero config; ORM enables a one-line swap to PostgreSQL |
| **Validation** | Pydantic v2 | Runtime type enforcement on all LLM outputs and API boundaries |
| **Real-time** | SSE (Server-Sent Events) | Pipeline logs stream to dashboard without WebSocket complexity |
| **Frontend build** | Vite + TypeScript | Sub-second HMR, multi-page static output, 35KB JS bundle |
| **Styling** | Tailwind CSS | Utility-first, custom dark design tokens |
| **Containerization** | Docker (multi-stage) | Reproducible deploys; builder + slim runtime stages |
| **Test runner** | pytest + pytest-mock | 8 test modules covering all core agents and utilities |

---

## Project Structure

```
cpa-ai-agent/
├── agents/
│   ├── orchestrator.py        Hermes Orchestrator — LangGraph state machine
│   ├── ingestion.py           Classifies PDFs: invoice vs. other document
│   ├── extraction.py          Docling + Groq → structured InvoiceData
│   ├── storage.py             SQLite dedup + save, returns row ID
│   ├── benchmarking.py        Apify / mock freight rate comparison
│   ├── analysis.py            Anomaly detection + AnomalyReport generation
│   └── feedback.py            Stores CPA corrections for continuous improvement
│
├── api/
│   └── server.py              FastAPI app — all 18 REST endpoints + SSE
│
├── models/
│   ├── database.py            SQLAlchemy ORM models (Invoice, Feedback)
│   └── pydantic_models.py     Pydantic models (InvoiceData, LineItem, etc.)
│
├── utils/
│   ├── settings.py            Pydantic Settings — validates env vars at startup
│   ├── db_utils.py            Database connection + init helpers
│   ├── freight_rate_service.py  Strategy pattern: ApifyService / MockApifyService
│   ├── cache.py               File-hash-based cache for Docling + LLM responses
│   ├── retry.py               Exponential backoff decorator for LLM calls
│   ├── timer.py               Pipeline step timing utilities
│   └── generate_dummy_pdf.py  Generates test PDF invoices via ReportLab
│
├── frontend/
│   ├── dashboard.html         Multi-section SPA (overview, auditor, ledger, …)
│   ├── index.html             Landing page
│   ├── src/
│   │   ├── api.ts             Typed API client — all 18 endpoints
│   │   ├── dashboard.ts       Dashboard logic, SSE streaming, chat widget
│   │   └── main.ts            Landing page interactions
│   ├── vite.config.ts         Multi-page build + /api proxy → localhost:8000
│   └── package.json
│
├── tests/
│   ├── conftest.py
│   ├── test_analysis.py
│   ├── test_benchmarking.py
│   ├── test_cache.py
│   ├── test_feedback.py
│   ├── test_models.py
│   ├── test_retry.py
│   ├── test_storage.py
│   └── test_timer.py
│
├── input_docs/                Drop PDF invoices here before running pipeline
├── output_reports/            Generated JSON audit reports land here
├── main.py                    CLI entry point
├── start_backend.py           Convenience script: starts Uvicorn on port 8000
├── Dockerfile                 Multi-stage Docker build
├── render.yaml                Render / Railway deploy config
├── pyproject.toml
├── .env.example
└── SYSTEM_DESIGN.html         Full HLD + LLD system design document
```

---

## Quick Start

### 1. Install dependencies

```bash
# Requires Python 3.12+
uv sync
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
GROQ_API_KEY=gsk_...          # Required — get free at console.groq.com/keys
USE_MOCK_APIFY=true           # Keep true to run without Apify credits
```

### 3. Start the backend

```bash
uv run python start_backend.py
# → API running at http://localhost:8000
# → Interactive docs at http://localhost:8000/api/docs
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# → Dashboard at http://localhost:3000/dashboard.html
```

### 5. Run the pipeline (CLI)

```bash
# Generate a test invoice PDF
uv run python main.py generate

# Run full audit on input_docs/
uv run python main.py run

# Verbose output
uv run python main.py run --verbose

# Use real Apify (requires APIFY_API_TOKEN)
uv run python main.py run --no-mock
```

---

## CLI Reference

| Command | Description |
|---------|-------------|
| `uv run python main.py run` | Audit all PDFs in `input_docs/` |
| `uv run python main.py run --input ./path` | Audit PDFs from a custom folder |
| `uv run python main.py run --no-mock` | Use live Apify rates instead of mock |
| `uv run python main.py run --verbose` | Debug-level output |
| `uv run python main.py generate` | Create a sample invoice PDF |
| `uv run python main.py status` | Print current config and DB counts |
| `uv run python main.py feedback` | View all CPA correction entries |

---

## API Endpoints

All endpoints prefixed `/api`. OpenAPI docs available at `/api/docs` when the server is running.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/status` | Config + DB counts + pipeline state |
| `GET` | `/api/dashboard` | Aggregated analytics (severity, vendors, anomalies) |
| `GET` | `/api/invoices` | Paginated invoice list (`?page=1&page_size=20`) |
| `GET` | `/api/invoices/:id` | Single invoice + its audit report |
| `POST` | `/api/invoices/:id/feedback` | Submit a CPA correction |
| `GET` | `/api/reports` | List saved audit report files |
| `GET` | `/api/reports/:filename` | Download raw JSON audit report |
| `POST` | `/api/pipeline/run` | Trigger full pipeline (`{ export_csv: bool }`) |
| `GET` | `/api/pipeline/status` | Poll pipeline state (idle/running/completed/failed) |
| `GET` | `/api/pipeline/stream` | SSE stream of live pipeline log lines |
| `POST` | `/api/upload` | Upload PDF invoices (multipart) |
| `GET` | `/api/feedback` | All correction entries + most common corrections |
| `DELETE` | `/api/cache` | Clear Docling + LLM cache |

---

## Agent Pipeline

The **Hermes Orchestrator** (LangGraph state machine) runs agents as nodes in a directed graph. Each node reads from and writes to a shared `AgentState` dict — no manual parameter passing.

```
scan_docs → classify ──► not invoice → END
                  │
                  ▼ invoice
              extract (Docling + Groq LLM)
                  │
              store (SQLite dedup + save)
                  │
              benchmark (Apify / mock rates)
                  │
              analyze (flag anomalies by severity)
                  │
              save_report (JSON to output_reports/)
```

**Anomaly severity thresholds** (configurable via `BENCHMARK_THRESHOLD_PERCENT`):

| Severity | Condition |
|----------|-----------|
| Critical | Price > 50% above market |
| High | Price 30–50% above market |
| Medium | Price 15–30% above market |
| Low | Price within threshold or minor field issues |

---

## Dashboard

The frontend is a zero-framework TypeScript SPA built with Vite. Seven sections:

| Section | What it shows |
|---------|--------------|
| **Overview** | Severity donut, top vendors by spend, recent invoices |
| **AI Auditor** | Upload PDFs, trigger pipeline, live SSE log stream |
| **Entities** | Paginated invoice database table |
| **Compliance** | Anomaly type breakdown and high-risk flags |
| **Ledger** | Accounting-style view of all extracted invoices |
| **Audit Logs** | Feedback history + pipeline state |
| **API Status** | Live config check (Groq, Apify, mock mode, counts) |

A floating **Sovereign Assistant** chat widget answers questions about the system and proxies live API data (invoice count, pipeline status, anomaly counts).

---

## Configuration

Full list of environment variables (see `.env.example`):

```env
# Required
GROQ_API_KEY=gsk_...

# Optional — Apify
APIFY_API_TOKEN=your_token
USE_MOCK_APIFY=true              # false = live Apify scraping

# Database
DATABASE_URL=sqlite:///cpa_agent.db

# Tuning
BENCHMARK_THRESHOLD_PERCENT=15.0  # % above market to flag as anomaly
CACHE_TTL_HOURS=24.0              # How long to cache Docling + LLM results
GROQ_MODEL=llama-3.3-70b-versatile
LOG_LEVEL=INFO
```

**Mock mode** (`USE_MOCK_APIFY=true`) uses a built-in table of realistic freight rates for 31 routes — the pipeline runs completely without Apify credits.

---

## Running Tests

```bash
uv run pytest
uv run pytest -v              # verbose
uv run pytest tests/test_analysis.py  # single module
```

8 test modules cover: analysis, benchmarking, cache, feedback, models, retry, storage, and timer utilities.

---

## Docker

```bash
# Build
docker build -t cpa-ai-agent .

# Run (mock mode, no Apify needed)
docker run -p 8000:8000 \
  -e GROQ_API_KEY=gsk_... \
  -e USE_MOCK_APIFY=true \
  cpa-ai-agent

# Health check
curl http://localhost:8000/api/health
```

> Note: The image is ~8.7 GB due to Docling's torch/CUDA dependencies.

---

## Deployment

### Railway (recommended free tier)

1. Push to GitHub
2. New Project → Deploy from repo → Railway auto-detects the Dockerfile
3. Add env var: `GROQ_API_KEY`
4. Deploy frontend to **Vercel**: import repo, set root directory to `frontend`, add `VITE_API_URL` pointing to your Railway backend URL

### Render

`render.yaml` is included. Two services — backend (Docker web service) and frontend (static site). Import as a Blueprint in the Render dashboard.

---

## Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **State Machine** | `HermesOrchestrator` | LangGraph manages typed state flow between agents |
| **Strategy** | `FreightRateService` | Swap mock ↔ live Apify without touching agent code |
| **Factory** | `create_rate_service()` | Single creation point driven by `USE_MOCK_APIFY` env var |
| **Dependency Injection** | `BenchmarkingAgent(rate_service=...)` | Injected service makes unit testing trivial |
| **Human-in-the-Loop** | `FeedbackAgent` | CPA corrections stored for future model fine-tuning |
| **Cache-Aside** | `utils/cache.py` | File-hash cache prevents redundant Docling + LLM calls |

---

## Sample Audit Report

```json
{
  "report_metadata": {
    "generated_at": "2026-04-15T02:51:05.597926",
    "tool": "CPA AI Agent v0.1"
  },
  "anomaly_report": {
    "invoice_number": "INV-2024-0042",
    "vendor_name": "Shanghai Global Freight Co., Ltd.",
    "anomalies": [
      "MEDIUM: 'Shanghai -> Los Angeles' unit price $1500.00 is 21.6% above market average $1234.10",
      "DUPLICATE: Invoice already exists in database (id=1)"
    ],
    "severity": "high",
    "summary": "2 issue(s) found in INV-2024-0042"
  },
  "invoice_data": { "..." : "..." },
  "benchmark_results": [ "..." ]
}
```

---

## License

MIT
