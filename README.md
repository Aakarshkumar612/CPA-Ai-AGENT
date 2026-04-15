# CPA AI Agent

> End-to-end multi-agent AI system for automated freight invoice auditing — from raw PDF to a live analytics dashboard, deployed on Google Cloud Platform.

Accepts PDF invoices, extracts structured data with an LLM, benchmarks freight rates against live market prices, flags pricing anomalies, and serves everything through a FastAPI REST API to an interactive dashboard built with Google Stitch.

---

## What it does

1. **Ingests PDFs** — scans `input_docs/` for freight invoices, classifies them via Groq LLM
2. **Extracts structured data** — Docling converts PDF tables to Markdown; Llama 3.3-70B pulls vendor, dates, line items, currency, incoterms
3. **Deduplicates & persists** — Supabase (PostgreSQL) stores invoices with dedup checks to prevent double-processing
4. **Benchmarks prices** — compares invoice rates against live market freight data (Apify) or mock rates
5. **Flags anomalies** — Critical / High / Medium / Low severity by % deviation from market
6. **Generates reports** — JSON audit reports persisted to a GCP Storage Bucket
7. **Serves a dashboard** — 18 FastAPI endpoints + SSE streaming + a Google Stitch HTML frontend with Supabase auth

---

## Tech Stack

### Frontend
| Technology | Purpose |
|-----------|---------|
| **Google Stitch** | AI-generated HTML/CSS frontend (landing page + dashboard) |
| **HTML5 + CSS3** | Markup and styling output from Stitch |
| **TypeScript** | Typed API client, SSE streaming, dashboard logic |
| **Vite** | Multi-page static build + dev server with `/api` proxy |
| **Tailwind CSS** | Utility-first styling, custom dark design tokens |

### Backend
| Technology | Purpose |
|-----------|---------|
| **Python 3.12** | Backend runtime |
| **FastAPI + Uvicorn** | Async REST API, auto OpenAPI docs, Pydantic-native |
| **LangGraph** | Multi-agent state machine orchestration |
| **Groq API (Llama 3.3-70B)** | LLM inference for classification + extraction (~300 tok/s) |
| **Docling (IBM)** | PDF → Markdown with preserved table structure |
| **Pydantic v2** | Runtime validation on all LLM outputs and API boundaries |
| **SQLAlchemy 2.0** | ORM layer over Supabase PostgreSQL |
| **Apify Client** | Managed scraper for live freight rate market data |
| **uv** | 10–100× faster than pip, lock-file reproducibility |

### Authentication & Database
| Technology | Purpose |
|-----------|---------|
| **Supabase Auth** | User authentication, session management, JWT tokens |
| **Supabase (PostgreSQL)** | Primary database for invoices, feedback, audit metadata |

### Cloud Infrastructure — Google Cloud Platform
| Service | Purpose |
|---------|---------|
| **GCP Cloud Run** | Containerized FastAPI backend hosting (auto-scaling, serverless) |
| **GCP Cloud Storage Bucket** | Object storage for uploaded PDFs and generated JSON audit reports |
| **GCP Web Hosting** | Static frontend delivery for the Stitch-generated dashboard |

### Security & Networking
| Technology | Purpose |
|-----------|---------|
| **Cloudflare CDN** | Global edge caching + DDoS protection |
| **HTTPS / TLS / SSL** | End-to-end encrypted traffic on all endpoints |
| **Supabase RLS** | Row-level security policies on database tables |
| **Pydantic Settings** | Env var validation at startup (secrets never in code) |

### DevOps & Tooling
| Technology | Purpose |
|-----------|---------|
| **Docker (multi-stage)** | Reproducible containerization (builder + slim runtime) |
| **GitHub Actions** | CI/CD pipelines — lint, test, build, deploy to GCP |
| **GitHub** | Source control + release management |
| **Postman** | API testing, request/response verification between frontend ↔ backend |
| **pytest + pytest-mock** | 8 test modules covering all agents and utilities |

---

## Architecture Overview

```
 ┌────────────────────┐     HTTPS      ┌────────────────────┐
 │  Google Stitch UI  │ ─────────────► │   Cloudflare CDN   │
 │  (HTML + TS + Vite)│                │   (DDoS + TLS)     │
 └────────────────────┘                └──────────┬─────────┘
         │                                        │
         │ Supabase Auth (JWT)                    ▼
         │                              ┌────────────────────┐
         │                              │   GCP Cloud Run    │
         │                              │   FastAPI Backend  │
         │                              │   (Dockerized)     │
         │                              └──────────┬─────────┘
         │                                         │
         │                     ┌───────────────────┼────────────────────┐
         │                     ▼                   ▼                    ▼
         │            ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
         └──────────► │ Supabase (PG)  │  │  GCP Storage   │  │   Groq LLM     │
                      │ users/invoices │  │  PDFs/Reports  │  │ Llama 3.3-70B  │
                      └────────────────┘  └────────────────┘  └────────────────┘
```

---

## Project Structure

```
cpa-ai-agent/
├── agents/
│   ├── orchestrator.py        Hermes Orchestrator — LangGraph state machine
│   ├── ingestion.py           Classifies PDFs: invoice vs. other document
│   ├── extraction.py          Docling + Groq → structured InvoiceData
│   ├── storage.py             Supabase dedup + save
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
│   ├── settings.py            Pydantic Settings — env var validation
│   ├── db_utils.py            Supabase connection helpers
│   ├── freight_rate_service.py  Strategy pattern: Apify / Mock
│   ├── cache.py               File-hash cache for Docling + LLM
│   ├── retry.py               Exponential backoff decorator
│   └── timer.py               Pipeline step timing
│
├── frontend/                  Google Stitch HTML + Vite + TypeScript
│   ├── index.html             Landing page (Stitch)
│   ├── dashboard.html         Dashboard SPA (Stitch)
│   ├── src/
│   │   ├── api.ts             Typed API client — all 18 endpoints
│   │   ├── dashboard.ts       Dashboard logic + SSE streaming
│   │   └── main.ts            Landing interactions
│   └── vite.config.ts
│
├── tests/                     pytest suite (8 modules)
├── input_docs/                Drop PDFs here for local runs
├── output_reports/            Generated JSON audit reports
├── main.py                    CLI entry point
├── start_backend.py           Uvicorn launcher
├── Dockerfile                 Multi-stage Docker build
├── .github/workflows/         GitHub Actions CI/CD
├── pyproject.toml
└── SYSTEM_DESIGN.html         Full HLD + LLD document
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

```env
GROQ_API_KEY=gsk_...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...
GCP_PROJECT_ID=your-project
GCP_STORAGE_BUCKET=cpa-reports
USE_MOCK_APIFY=true
```

### 3. Start the backend
```bash
uv run python start_backend.py
# → API at http://localhost:8000
# → Docs at http://localhost:8000/api/docs
```

### 4. Start the frontend
```bash
cd frontend
npm install
npm run dev
# → Dashboard at http://localhost:3000/dashboard.html
```

---

## API Endpoints

All endpoints prefixed `/api`. Tested via **Postman** collection. OpenAPI docs at `/api/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/status` | Config + DB counts + pipeline state |
| `GET` | `/api/dashboard` | Aggregated analytics |
| `GET` | `/api/invoices` | Paginated invoice list |
| `GET` | `/api/invoices/:id` | Single invoice + audit report |
| `POST` | `/api/invoices/:id/feedback` | Submit a CPA correction |
| `GET` | `/api/reports` | List saved audit reports |
| `GET` | `/api/reports/:filename` | Download JSON report (from GCP bucket) |
| `POST` | `/api/pipeline/run` | Trigger full pipeline |
| `GET` | `/api/pipeline/status` | Poll pipeline state |
| `GET` | `/api/pipeline/stream` | SSE stream of pipeline logs |
| `POST` | `/api/upload` | Upload PDFs → GCP Storage |
| `GET` | `/api/feedback` | All correction entries |
| `DELETE` | `/api/cache` | Clear Docling + LLM cache |

---

## Agent Pipeline (LangGraph)

```
scan_docs → classify ──► not invoice → END
                  │
                  ▼ invoice
              extract   (Docling + Groq LLM)
                  │
              store     (Supabase dedup + save)
                  │
              benchmark (Apify / mock rates)
                  │
              analyze   (flag anomalies by severity)
                  │
              save_report (JSON → GCP Storage Bucket)
```

**Anomaly severity thresholds:**

| Severity | Condition |
|----------|-----------|
| Critical | Price > 50% above market |
| High | Price 30–50% above market |
| Medium | Price 15–30% above market |
| Low | Within threshold / minor field issues |

---

## Security

| Control | Implementation |
|---------|---------------|
| **Transport** | HTTPS everywhere — TLS/SSL certificates via Cloudflare |
| **DDoS** | Cloudflare CDN edge protection on all public routes |
| **Auth** | Supabase Auth with JWT validation on every protected endpoint |
| **Database** | Supabase Row-Level Security (RLS) policies |
| **Secrets** | Env vars only — never in code, logs, or error responses |
| **Validation** | Pydantic v2 schemas at every API boundary |
| **Containers** | Non-root user, multi-stage Docker, minimal slim runtime |

---

## Deployment — Google Cloud Platform

### Backend → GCP Cloud Run
```bash
# Build + push to Artifact Registry
docker build -t gcr.io/$GCP_PROJECT_ID/cpa-backend .
docker push gcr.io/$GCP_PROJECT_ID/cpa-backend

# Deploy to Cloud Run
gcloud run deploy cpa-backend \
  --image gcr.io/$GCP_PROJECT_ID/cpa-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GROQ_API_KEY=...,SUPABASE_URL=...
```

### Frontend → GCP Web Hosting
```bash
cd frontend && npm run build
gsutil -m rsync -r dist gs://cpa-frontend-bucket
```

### Storage → GCP Cloud Storage Bucket
- **`cpa-uploads`** — uploaded PDF invoices
- **`cpa-reports`** — generated JSON audit reports

### CDN → Cloudflare
Point Cloudflare DNS at the GCP load balancer, enable **Full (Strict) SSL**, **Always Use HTTPS**, and **DDoS protection**.

### CI/CD → GitHub Actions
`.github/workflows/deploy.yml` runs on push to `main`:
1. Lint + pytest
2. Build Docker image
3. Push to GCP Artifact Registry
4. Deploy to Cloud Run
5. Build frontend + sync to GCP bucket

---

## Running Tests

```bash
uv run pytest            # full suite
uv run pytest -v         # verbose
```

8 test modules cover: analysis, benchmarking, cache, feedback, models, retry, storage, timer.

---

## Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **State Machine** | `HermesOrchestrator` | LangGraph typed state flow |
| **Strategy** | `FreightRateService` | Swap mock ↔ live Apify |
| **Factory** | `create_rate_service()` | Env-driven instantiation |
| **Dependency Injection** | `BenchmarkingAgent` | Trivial unit testing |
| **Human-in-the-Loop** | `FeedbackAgent` | CPA corrections for fine-tuning |
| **Cache-Aside** | `utils/cache.py` | Skip redundant Docling + LLM calls |

---

## License

MIT
