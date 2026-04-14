"""
start_backend.py — Start the CPA AI Agent REST API server.

Usage:
    uv run python start_backend.py            # port 8000 (default)
    uv run python start_backend.py --port 8080
    uv run python start_backend.py --no-reload

The frontend (from Google Stitch) runs separately:
    cd frontend && npm run dev     → http://localhost:3000
    (or 5173 if Vite)

API docs once running:
    http://localhost:8000/api/docs
"""

import argparse
import sys
import io

# Force UTF-8 on Windows terminals
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from utils.db_utils import init_db


def main():
    parser = argparse.ArgumentParser(description="CPA AI Agent API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    args = parser.parse_args()

    print("=" * 60)
    print("  CPA AI Agent — API Server")
    print("=" * 60)

    # Init DB on startup
    print("Initializing database...")
    init_db()
    print("Database ready.")

    print(f"\nStarting API server at http://{args.host}:{args.port}")
    print(f"  API docs  →  http://localhost:{args.port}/api/docs")
    print(f"  Health    →  http://localhost:{args.port}/api/health")
    print()
    print("To run the frontend separately:")
    print("  cd frontend && npm run dev")
    print("  (or: npm install && npm run dev)")
    print()
    print("Press Ctrl+C to stop.")
    print("=" * 60)

    import uvicorn
    uvicorn.run(
        "api.server:app",
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
