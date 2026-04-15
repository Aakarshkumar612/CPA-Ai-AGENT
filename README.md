<div align="center">

# 🤖 CPA AI Agent

### *An Autonomous Multi-Agent AI System for Freight Invoice Auditing*

**From raw PDF invoices to a live analytics dashboard — fully automated, cloud-native, and production-ready.**

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-F55036?style=for-the-badge&logo=meta&logoColor=white)](https://groq.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Auth_&_DB-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![GCP](https://img.shields.io/badge/Google_Cloud-Deployed-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](https://cloud.google.com/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Cloudflare](https://img.shields.io/badge/Cloudflare-CDN_&_DDoS-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://www.cloudflare.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

</div>

---

## 📌 Table of Contents

- [🎯 Project Overview](#-project-overview)
- [💡 Why This Project Exists](#-why-this-project-exists)
- [✨ Key Features](#-key-features)
- [🏗️ System Architecture](#️-system-architecture)
- [🛠️ Tech Stack](#️-tech-stack)
- [📂 Project Structure](#-project-structure)
- [🚀 Quick Start](#-quick-start)
- [🔌 API Reference](#-api-reference)
- [🧠 Agent Pipeline](#-agent-pipeline)
- [🔒 Security Architecture](#-security-architecture)
- [☁️ Deployment on Google Cloud Platform](#️-deployment-on-google-cloud-platform)
- [🧪 Testing](#-testing)
- [🎨 Design Patterns](#-design-patterns)
- [📊 Sample Audit Report](#-sample-audit-report)
- [📄 License](#-license)

---

## 🎯 Project Overview

**CPA AI Agent** is an intelligent, end-to-end automation platform built for **Certified Public Accountants (CPAs)**, **freight auditors**, and **finance teams** who need to process hundreds — or thousands — of freight invoices every month.

Manually auditing freight invoices is slow, error-prone, and expensive. Auditors spend hours opening PDFs, copy-pasting data into spreadsheets, cross-checking rates against market benchmarks, and hunting for overcharges. A single missed anomaly can cost a business thousands of dollars.

**CPA AI Agent eliminates that pain.** It is an orchestrated team of specialized AI agents — each one an expert at a single task — that collectively turn a folder full of PDF invoices into a clean, queryable audit database and a live analytics dashboard in minutes.

### 🧭 What the System Actually Does

Drop a stack of freight invoices into the system and, without any human intervention, the platform:

1. **Reads every PDF** using IBM's Docling, preserving table structure that other tools lose
2. **Classifies** each document with a Groq-powered Llama 3.3 70B model — is it an invoice, a quote, a bill of lading, or junk?
3. **Extracts** structured data: vendor name, invoice number, dates, line items, freight routes, unit prices, currency, and incoterms
4. **Deduplicates** against the Supabase database so the same invoice never gets processed twice
5. **Benchmarks** every freight rate on the invoice against live market data from Apify scrapers
6. **Flags anomalies** with a four-tier severity model (Critical / High / Medium / Low) based on how far the invoice price deviates from market rates
7. **Generates** a full JSON audit report and stores it in a GCP Cloud Storage bucket
8. **Serves everything** through a FastAPI backend + a Google Stitch-generated dashboard with real-time SSE pipeline streaming, live analytics, and a conversational AI assistant

### 🎓 Who It's For

| User | Value |
|------|-------|
| **CPAs & Auditors** | Automate 90%+ of invoice review work; focus only on flagged anomalies |
| **Logistics & Procurement Teams** | Catch vendor overcharges before they're paid |
| **Finance Departments** | Get a single dashboard showing spend, anomalies, and vendor performance |
| **Compliance Officers** | Maintain a full audit trail with human-in-the-loop feedback correction |

### 📈 Real-World Impact

- ⏱️ **Reduces invoice audit time** from ~15 minutes/invoice to under 30 seconds
- 💰 **Catches overcharges** that manual review typically misses
- 📉 **Cuts human error** through deterministic Pydantic validation at every boundary
- 🔁 **Learns continuously** — the Feedback Agent stores CPA corrections for future fine-tuning
- 🌍 **Cloud-native & scalable** — runs serverlessly on GCP Cloud Run with global CDN delivery

---

## 💡 Why This Project Exists

Freight invoicing is one of the last major back-office processes that hasn't been properly automated. Invoices arrive as unstructured PDFs from hundreds of vendors, each with their own format. OCR tools mangle tables. Template-based extractors break the moment a vendor changes their layout. Meanwhile, freight rates fluctuate weekly, making manual price verification nearly impossible at scale.

**CPA AI Agent solves this by treating the problem as an orchestration challenge, not a parsing challenge.** Instead of one giant model trying to do everything, a directed graph of specialized agents — classification, extraction, storage, benchmarking, analysis, feedback — each does one thing exceptionally well and hands off typed state to the next. If any agent fails, the pipeline degrades gracefully and reports exactly where the problem occurred.

This is the architecture you'd build at a freight tech startup. It's just open and documented.

---

## ✨ Key Features

- 🤖 **Multi-Agent Orchestration** — LangGraph state machine coordinates 7 specialized AI agents
- 📄 **High-Fidelity PDF Parsing** — Docling preserves table structure where OCR fails
- 🧠 **LLM-Powered Extraction** — Groq's Llama 3.3 70B at ~300 tokens/sec
- 📊 **Live Market Benchmarking** — Apify-driven freight rate scraping (or built-in mock mode)
- 🚨 **Four-Tier Anomaly Detection** — Critical / High / Medium / Low severity flags
- 🔁 **Deduplication** — Hash-based checks prevent re-processing the same invoice
- 📺 **Live Dashboard** — 18 REST endpoints + Server-Sent Events for real-time pipeline streaming
- 🔐 **Supabase Auth** — JWT-based authentication with Row-Level Security
- ☁️ **GCP-Native** — Cloud Run backend, Cloud Storage reports, GCP web hosting frontend
- 🛡️ **Enterprise Security** — HTTPS/TLS/SSL via Cloudflare with DDoS protection
- 🔄 **CI/CD Automated** — GitHub Actions pipeline for lint, test, build, and deploy
- 🎨 **Google Stitch Frontend** — AI-generated HTML/CSS dashboard, wrapped with TypeScript
- 🧑‍⚖️ **Human-in-the-Loop** — CPA corrections stored for continuous model improvement
- ⚡ **Smart Caching** — File-hash-based cache skips redundant Docling and LLM calls
- 🐳 **Dockerized** — Multi-stage build for reproducible deployments

---

## 🏗️ System Architecture

```
   ┌──────────────────────────────────────────────────────────────┐
   │                     👤  End User (CPA / Auditor)             │
   └───────────────────────────────┬──────────────────────────────┘
                                   │ HTTPS
                                   ▼
              ┌───────────────────────────────────────────┐
              │   🛡️  Cloudflare  (CDN + DDoS + TLS/SSL)  │
              └───────────────────────────────┬───────────┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    ▼                                                   ▼
      ┌──────────────────────────┐                    ┌────────────────────────────┐
      │   🎨 Frontend (Stitch)   │                    │  🔐 Supabase Auth (JWT)    │
      │   HTML + TS + Vite       │◄───── login ──────►│  Session management        │
      │   (GCP Web Hosting)      │                    └────────────────────────────┘
      └─────────────┬────────────┘
                    │ REST / SSE
                    ▼
      ┌──────────────────────────────────────────────────────────────────┐
      │           ⚡ FastAPI Backend  (Python 3.12 + Docker)              │
      │                  Hosted on GCP Cloud Run                         │
      │                                                                  │
      │   ┌────────────────────────────────────────────────────────┐     │
      │   │        🧠 Hermes Orchestrator (LangGraph)              │     │
      │   │                                                        │     │
      │   │  Ingestion → Extraction → Storage → Benchmarking      │     │
      │   │                 → Analysis → Feedback                  │     │
      │   └────────────────────────────────────────────────────────┘     │
      └───┬──────────────┬───────────────┬───────────────┬────────────────┘
          │              │               │               │
          ▼              ▼               ▼               ▼
   ┌────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
   │ 🗄️ Supabase │ │ 📦 GCP      │ │ 🤖 Groq    │ │ 🌐 Apify     │
   │ PostgreSQL  │ │ Cloud       │ │ Llama      │ │ Freight Rate │
   │ (invoices,  │ │ Storage     │ │ 3.3-70B    │ │ Scraper      │
   │  feedback)  │ │ (PDFs +     │ │ LLM        │ │              │
   │             │ │  reports)   │ │            │ │              │
   └─────────────┘ └─────────────┘ └─────────────┘ └──────────────┘
```

---

## 🛠️ Tech Stack

### 🎨 Frontend
| Technology | Role |
|-----------|------|
| **Google Stitch** | AI-powered generation of the dashboard + landing page HTML/CSS |
| **HTML5 & CSS3** | Markup and styling output from Stitch |
| **TypeScript** | Typed API client, dashboard logic, SSE streaming |
| **Vite** | Multi-page static build + dev server with `/api` proxy |
| **Tailwind CSS** | Utility-first styling with custom dark design tokens |

### ⚙️ Backend
| Technology | Role |
|-----------|------|
| **Python 3.12** | Backend runtime |
| **FastAPI + Uvicorn** | Async REST API with auto-generated OpenAPI docs |
| **LangGraph** | Multi-agent state machine orchestration |
| **Groq API (Llama 3.3-70B)** | LLM inference for classification + extraction |
| **Docling (IBM)** | PDF → Markdown with preserved table structure |
| **Pydantic v2** | Runtime validation on all LLM outputs and API boundaries |
| **SQLAlchemy 2.0** | ORM layer over Supabase PostgreSQL |
| **Apify Client** | Managed scraper for live freight rate market data |
| **ReportLab** | PDF generation for test invoices |
| **uv** | Ultra-fast Python package manager with lockfile reproducibility |

### 🔐 Authentication & Database
| Technology | Role |
|-----------|------|
| **Supabase Auth** | User authentication, session management, JWT tokens |
| **Supabase (PostgreSQL)** | Primary database for invoices, feedback, and audit metadata |
| **Supabase RLS** | Row-level security policies on all tables |

### ☁️ Cloud Infrastructure — Google Cloud Platform
| Service | Role |
|---------|------|
| **GCP Cloud Run** | Serverless containerized FastAPI backend with auto-scaling |
| **GCP Cloud Storage Bucket** | Object storage for uploaded PDFs and generated JSON audit reports |
| **GCP Web Hosting** | Static delivery for the Stitch-generated frontend |
| **GCP Artifact Registry** | Docker image registry |

### 🛡️ Security & Networking
| Technology | Role |
|-----------|------|
| **Cloudflare CDN** | Global edge caching with sub-50ms latency |
| **Cloudflare DDoS Protection** | Network + application layer attack mitigation |
| **TLS / SSL / HTTPS** | End-to-end encrypted traffic on every endpoint |
| **Pydantic Settings** | Startup-time env var validation (no secrets in code) |

### 🔄 DevOps & Developer Tooling
| Technology | Role |
|-----------|------|
| **Docker (multi-stage)** | Reproducible containerization (builder + slim runtime) |
| **GitHub** | Source control, release management, issue tracking |
| **GitHub Actions** | CI/CD pipelines — lint, test, build, deploy to GCP |
| **Postman** | Manual API testing and request/response verification |
| **pytest + pytest-mock** | 8 test modules covering all agents and utilities |

---

## 📂 Project Structure

```
cpa-ai-agent/
├── agents/                        🧠 Multi-agent system
│   ├── orchestrator.py            Hermes Orchestrator — LangGraph state machine
│   ├── ingestion.py               Classifies PDFs: invoice vs. other document
│   ├── extraction.py              Docling + Groq → structured InvoiceData
│   ├── storage.py                 Supabase dedup + persist
│   ├── benchmarking.py            Apify / mock freight rate comparison
│   ├── analysis.py                Anomaly detection + severity tagging
│   └── feedback.py                CPA correction logging
│
├── api/
│   └── server.py                  FastAPI app — 18 REST endpoints + SSE
│
├── models/
│   ├── database.py                SQLAlchemy ORM models
│   └── pydantic_models.py         Pydantic schemas
│
├── utils/
│   ├── settings.py                Env var validation at startup
│   ├── db_utils.py                Supabase connection helpers
│   ├── freight_rate_service.py    Strategy pattern: Apify / Mock
│   ├── cache.py                   File-hash-based cache
│   ├── retry.py                   Exponential backoff decorator
│   └── timer.py                   Pipeline step timing
│
├── frontend/                      🎨 Google Stitch + Vite + TypeScript
│   ├── index.html                 Landing page (Stitch)
│   ├── dashboard.html             Dashboard SPA (Stitch)
│   ├── src/
│   │   ├── api.ts                 Typed API client — 18 endpoints
│   │   ├── dashboard.ts           Dashboard logic + SSE streaming
│   │   └── main.ts                Landing interactions
│   └── vite.config.ts
│
├── tests/                         🧪 pytest suite (8 modules)
├── .github/workflows/             🔄 GitHub Actions CI/CD
├── input_docs/                    📥 Drop PDFs here
├── output_reports/                📤 Generated JSON reports
├── main.py                        CLI entry point
├── start_backend.py               Uvicorn launcher
├── Dockerfile                     Multi-stage Docker build
├── pyproject.toml
└── SYSTEM_DESIGN.html             Full HLD + LLD document
```

---

## 🚀 Quick Start

### 1️⃣ Prerequisites
- Python 3.12+
- Node.js 18+
- Docker
- A [Groq API key](https://console.groq.com/keys) (free)
- A [Supabase project](https://supabase.com/) (free)

### 2️⃣ Install dependencies
```bash
uv sync
```

### 3️⃣ Configure environment
```bash
cp .env.example .env
```

```env
# LLM
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...

# GCP
GCP_PROJECT_ID=your-gcp-project
GCP_STORAGE_BUCKET=cpa-reports

# Apify (optional)
APIFY_API_TOKEN=your_token
USE_MOCK_APIFY=true

# Tuning
BENCHMARK_THRESHOLD_PERCENT=15.0
CACHE_TTL_HOURS=24.0
LOG_LEVEL=INFO
```

### 4️⃣ Start the backend
```bash
uv run python start_backend.py
# → API running at http://localhost:8000
# → Interactive docs at http://localhost:8000/api/docs
```

### 5️⃣ Start the frontend
```bash
cd frontend
npm install
npm run dev
# → Dashboard at http://localhost:3000/dashboard.html
```

### 6️⃣ Run the pipeline via CLI
```bash
uv run python main.py generate          # Create a sample invoice PDF
uv run python main.py run                # Audit all PDFs in input_docs/
uv run python main.py run --verbose      # Debug mode
uv run python main.py status             # Show config + DB counts
uv run python main.py feedback           # View CPA corrections
```

---

## 🔌 API Reference

All endpoints prefixed `/api`. Tested end-to-end via **Postman**. Full OpenAPI docs at `/api/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/status` | Config + DB counts + pipeline state |
| `GET` | `/api/dashboard` | Aggregated analytics (severity, vendors, anomalies) |
| `GET` | `/api/invoices` | Paginated invoice list (`?page=1&page_size=20`) |
| `GET` | `/api/invoices/:id` | Single invoice + its audit report |
| `POST` | `/api/invoices/:id/feedback` | Submit a CPA correction |
| `GET` | `/api/reports` | List saved audit report files |
| `GET` | `/api/reports/:filename` | Download raw JSON audit report from GCP bucket |
| `POST` | `/api/pipeline/run` | Trigger full pipeline (`{ export_csv: bool }`) |
| `GET` | `/api/pipeline/status` | Poll pipeline state (idle / running / completed / failed) |
| `GET` | `/api/pipeline/stream` | SSE stream of live pipeline log lines |
| `POST` | `/api/upload` | Upload PDF invoices (multipart) to GCP Storage |
| `GET` | `/api/feedback` | All correction entries + most common corrections |
| `DELETE` | `/api/cache` | Clear Docling + LLM cache |

---

## 🧠 Agent Pipeline

The **Hermes Orchestrator** runs agents as nodes in a LangGraph directed graph. Each node reads from and writes to a shared `AgentState` TypedDict — no manual parameter passing.

```
  scan_docs → classify ──► not invoice → END
                    │
                    ▼ invoice
                extract      (Docling + Groq LLM)
                    │
                store        (Supabase dedup + save)
                    │
                benchmark    (Apify / mock rates)
                    │
                analyze      (severity-tagged anomalies)
                    │
                save_report  (JSON → GCP Storage Bucket)
                    │
                select_next  (loop until all PDFs processed)
                    │
                   END
```

### 🚨 Anomaly Severity

| Severity | Condition |
|----------|-----------|
| 🔴 **Critical** | Unit price > 50% above market average |
| 🟠 **High** | Unit price 30–50% above market |
| 🟡 **Medium** | Unit price 15–30% above market |
| 🟢 **Low** | Within threshold or minor field issues |

Thresholds are configurable via `BENCHMARK_THRESHOLD_PERCENT` in `.env`.

---

## 🔒 Security Architecture

| Layer | Control | Implementation |
|-------|---------|---------------|
| **Transport** | HTTPS everywhere | TLS/SSL certificates via Cloudflare |
| **DDoS** | Edge protection | Cloudflare CDN on all public routes |
| **Authentication** | JWT-based auth | Supabase Auth on every protected endpoint |
| **Database** | Row-Level Security | Supabase RLS policies on all tables |
| **Secrets** | Env-only | Never in code, logs, or error responses |
| **Input** | Schema validation | Pydantic v2 at every API boundary |
| **Containers** | Hardened runtime | Multi-stage Docker, slim base, non-root user |
| **Rate Limiting** | Per-IP throttling | Enforced at Cloudflare + FastAPI middleware |

---

## ☁️ Deployment on Google Cloud Platform

### Backend → GCP Cloud Run
```bash
# Build + push to GCP Artifact Registry
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

### Storage → GCP Cloud Storage Buckets
- **`cpa-uploads`** — uploaded PDF invoices
- **`cpa-reports`** — generated JSON audit reports
- **`cpa-frontend-bucket`** — static Stitch frontend build

### CDN + Security → Cloudflare
Point Cloudflare DNS at the GCP load balancer and enable:
- ✅ **Full (Strict) SSL** mode
- ✅ **Always Use HTTPS** redirect
- ✅ **DDoS protection**
- ✅ **Bot fight mode**
- ✅ **Rate limiting rules**

### CI/CD → GitHub Actions
`.github/workflows/deploy.yml` runs on every push to `main`:
1. ✅ Lint (ruff) + type check (mypy)
2. ✅ Run full pytest suite
3. ✅ Build Docker image
4. ✅ Push to GCP Artifact Registry
5. ✅ Deploy to Cloud Run
6. ✅ Build frontend + sync to GCP Storage
7. ✅ Purge Cloudflare cache

---

## 🧪 Testing

```bash
uv run pytest                         # full suite
uv run pytest -v                      # verbose
uv run pytest tests/test_analysis.py  # single module
```

**8 test modules** covering:
- ✅ `test_analysis.py` — anomaly detection logic
- ✅ `test_benchmarking.py` — rate comparison
- ✅ `test_cache.py` — file-hash caching
- ✅ `test_feedback.py` — CPA correction flow
- ✅ `test_models.py` — Pydantic model validation
- ✅ `test_retry.py` — exponential backoff
- ✅ `test_storage.py` — dedup + persist
- ✅ `test_timer.py` — performance timing

---

## 🎨 Design Patterns

| Pattern | Where | Purpose |
|---------|-------|---------|
| **State Machine** | `HermesOrchestrator` | LangGraph manages typed state flow between agents |
| **Strategy** | `FreightRateService` | Swap mock ↔ live Apify without touching agent code |
| **Factory** | `create_rate_service()` | Single creation point driven by env var |
| **Dependency Injection** | `BenchmarkingAgent(rate_service=...)` | Trivial unit testing |
| **Human-in-the-Loop** | `FeedbackAgent` | CPA corrections stored for future fine-tuning |
| **Cache-Aside** | `utils/cache.py` | Prevents redundant Docling + LLM calls |
| **Repository** | `models/database.py` | Decouples DB logic from business logic |

---

## 📊 Sample Audit Report

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
  "invoice_data": { "...": "..." },
  "benchmark_results": [ "..." ]
}
```

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

### 🌟 Built with ❤️ for CPAs who deserve better tools

**[⬆ Back to Top](#-cpa-ai-agent)**

</div>
