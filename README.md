# Crowd Wisdom Trading CPA AI Agent

> Multi-Agent System for Automated CPA Invoice Auditing and Freight Rate Benchmarking

## Overview

An AI-powered backend system that helps Certified Public Accountants (CPAs) audit shipping/logistics invoices by:

1. **Reading PDF invoices** — parses invoices using IBM Docling (table-aware PDF extraction)
2. **Extracting structured data** — uses Groq LLM (Llama 3.3) to pull vendor, dates, line items, prices
3. **Deduplicating** — checks against SQLite database to prevent double-processing
4. **Benchmarking prices** — compares invoice rates against live market freight rates (via Apify or mock data)
5. **Flagging anomalies** — identifies overpriced items, missing fields, and duplicate invoices
6. **Generating audit reports** — produces JSON reports with severity ratings

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **Package Manager** | `uv` | 10-100x faster than pip, modern dependency management |
| **LLM Provider** | Groq (Llama 3.3 70B) | Fast, free tier, open-source models |
| **PDF Parser** | Docling (IBM) | Best-in-class for tables and business documents |
| **Agent Framework** | LangGraph | Industry standard for multi-agent orchestration |
| **Database** | SQLite + SQLAlchemy | Zero config, ORM for easy swapping to PostgreSQL |
| **Web Scraping** | Apify Client | Live freight rate data from shipping websites |
| **Data Validation** | Pydantic | Runtime validation, type safety, JSON serialization |

## Project Structure

```
├── agents/
│   ├── ingestion.py       → Classifies PDFs (invoice vs other)
│   ├── extraction.py      → Docling + Groq PDF → structured data
│   ├── storage.py         → SQLite dedup + save
│   ├── benchmarking.py    → Price vs market comparison
│   ├── analysis.py        → Anomaly detection + report generation
│   ├── feedback.py        → Logs CPA corrections for learning
│   └── orchestrator.py    → Hermes Orchestrator (LangGraph workflow)
├── models/
│   ├── database.py        → SQLAlchemy models (Invoice, Feedback)
│   └── pydantic_models.py → Pydantic models (InvoiceData, etc.)
├── utils/
│   ├── db_utils.py        → Database connection helpers
│   ├── freight_rate_service.py → Apify + Mock rate services
│   └── generate_dummy_pdf.py → Test PDF generator
├── input_docs/            → Drop PDF invoices here
├── output_reports/        → Generated audit reports (JSON)
├── main.py                → CLI entry point
├── .env.example           → Environment variable template
└── pyproject.toml         → Project dependencies
```

## Quick Start

### 1. Setup

```bash
# Install dependencies
uv sync

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 2. Get a Groq API Key

1. Go to https://console.groq.com/keys
2. Create a free API key
3. Add it to your `.env` file: `GROQ_API_KEY=gsk_...`

### 3. Run the Pipeline

```bash
# Check project status
uv run python main.py status

# Generate a test invoice PDF
uv run python main.py generate

# Run the full audit pipeline
uv run python main.py run

# Verbose output
uv run python main.py run --verbose
```

### 4. CLI Commands

| Command | Description |
|---------|-------------|
| `uv run python main.py run` | Run audit pipeline on `input_docs/` |
| `uv run python main.py run --input ./my_invoices` | Run on custom folder |
| `uv run python main.py run --no-mock` | Use real Apify (not mock) |
| `uv run python main.py run --verbose` | Detailed debug output |
| `uv run python main.py generate` | Create test PDF invoice |
| `uv run python main.py status` | Show configuration status |
| `uv run python main.py feedback` | View CPA correction logs |

## Architecture

### Multi-Agent Workflow (Hermes Orchestrator)

```
                    ┌─────────────────┐
                    │   scan_docs      │  Find PDFs in input_docs/
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │    classify      │  Is this an invoice? (Groq LLM)
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  invoice?       │  Conditional routing
                    └───┬────────┬────┘
                    yes │        │ no
                ┌───────▼──┐   ┌──▼───┐
                │ extract   │   │ END  │  Skip non-invoices
                └──────┬────┘   └──────┘
                       │
                ┌──────▼──────┐
                │   store      │  SQLite dedup + save
                └──────┬──────┘
                       │
                ┌──────▼────────┐
                │  benchmark     │  Compare to market rates
                └──────┬────────┘
                       │
                ┌──────▼───────┐
                │   analyze     │  Flag anomalies
                └──────┬───────┘
                       │
                ┌──────▼─────────┐
                │  save_report    │  Write JSON audit report
                └────────────────┘
```

### Design Patterns Used

| Pattern | Where | Why |
|---------|-------|-----|
| **Strategy** | `FreightRateService` | Swap mock ↔ real Apify without changing agent code |
| **Factory** | `create_rate_service()` | Single entry point for service creation |
| **State Machine** | `HermesOrchestrator` | LangGraph manages state flow between agents |
| **Dependency Injection** | `BenchmarkingAgent(rate_service=...)` | Easy testing with mock services |
| **Human-in-the-Loop** | `FeedbackAgent` | CPA corrections improve future extractions |

## Configuration

### Environment Variables (`.env`)

```env
GROQ_API_KEY=gsk_...           # Required — LLM provider
APIFY_API_TOKEN=your_token     # Optional — only needed for live rates
USE_MOCK_APIFY=true            # true = mock data, false = real Apify
DATABASE_URL=sqlite:///cpa_agent.db  # SQLite file path
```

### Mock Mode

By default, the system uses `MockApifyService` which provides realistic freight rates for 31 routes. This ensures the project runs **fully** without Apify credits during assessment review.

To use real Apify:
1. Set `USE_MOCK_APIFY=false` in `.env`
2. Add your `APIFY_API_TOKEN`
3. Run with `--no-mock` flag

## Sample Output

```json
{
  "report_metadata": {
    "generated_at": "2026-04-15T02:51:05.597926",
    "tool": "Crowd Wisdom Trading CPA AI Agent v0.1"
  },
  "anomaly_report": {
    "invoice_number": "INV-2024-0042",
    "vendor_name": "Shanghai Global Freight Co., Ltd.",
    "anomalies": [
      "MEDIUM: 'Shanghai -> Los Angeles' unit price $1500.00 is 21.6% above market average $1234.10",
      "DUPLICATE: This invoice was already in the system (id=1)"
    ],
    "severity": "high",
    "summary": "Found 2 issue(s) in invoice INV-2024-0042..."
  },
  "invoice_data": { ... },
  "benchmark_results": [ ... ]
}
```

## For Assessment Reviewers

This project demonstrates:

- **Multi-agent architecture** using LangGraph state machines
- **Production-grade patterns**: Strategy, Factory, Dependency Injection
- **Real-world AI application**: Automating CPA invoice auditing
- **Human-in-the-loop feedback**: Corrections logged for continuous improvement
- **Clean separation**: Agents don't know about databases, services don't know about agents
- **Mock-first design**: Runs fully without paid API credits
- **Modern Python tooling**: `uv`, Pydantic v2, SQLAlchemy 2.0, type hints throughout

## License

MIT
