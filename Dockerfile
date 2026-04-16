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
COPY agents/          ./agents/
COPY api/             ./api/
COPY models/          ./models/
COPY utils/           ./utils/
COPY main.py          ./main.py
COPY start_backend.py ./start_backend.py
COPY streamlit_app.py ./streamlit_app.py
COPY .streamlit/      ./.streamlit/

# Create persistent directories
RUN mkdir -p input_docs output_reports

# Activate venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# SERVE_MODE controls which server starts:
#   api       → FastAPI on PORT (default 8000)
#   streamlit → Streamlit on PORT (default 8501)
ENV SERVE_MODE=api \
    PORT=8000

EXPOSE 8000 8501

# Health check adapts to serve mode
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.environ[\"PORT\"]}/' + ('api/health' if os.environ.get('SERVE_MODE') == 'api' else '_stcore/health'))"

CMD ["sh", "-c", \
  "if [ \"$SERVE_MODE\" = 'streamlit' ]; then \
     streamlit run streamlit_app.py \
       --server.port \"${PORT:-8501}\" \
       --server.address 0.0.0.0 \
       --server.headless true; \
   else \
     python start_backend.py --no-reload --host 0.0.0.0 --port \"${PORT:-8000}\"; \
   fi"]
