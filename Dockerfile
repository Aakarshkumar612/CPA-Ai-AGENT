# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency manifests first (layer cache)
COPY pyproject.toml uv.lock ./

# Install deps into a virtual env inside /app/.venv
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the venv from builder (no uv needed at runtime)
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY agents/      ./agents/
COPY api/         ./api/
COPY models/      ./models/
COPY utils/       ./utils/
COPY main.py      ./main.py
COPY start_backend.py ./start_backend.py

# Create persistent directories
RUN mkdir -p input_docs output_reports

# Activate venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# Run the server (no reload in production)
CMD ["python", "start_backend.py", "--no-reload", "--host", "0.0.0.0", "--port", "8000"]
