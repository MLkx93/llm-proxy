"""LLM Proxy Web UI API - Pure backend API server.

This server provides REST API endpoints for the React frontend.
It proxies chat requests to the LLM Security Proxy (port 8080)
which handles all security scanning before forwarding to LLM providers.

Architecture:
    React Frontend (port 3000) → API Server (port 8000) → LLM Security Proxy (port 8080) → LLM Providers
"""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routes.providers import router as providers_router
from .routes.chat import router as chat_router
from .routes.dashboard import router as dashboard_router
from .routes.auth import router as auth_router
from .routes.audit import router as audit_router
from .routes.history import router as history_router

# ── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LLM Proxy Web UI API",
    description="Backend API for the LLM Security Proxy Web Interface",
    version="1.0.0",
)

# ── CORS Middleware ──────────────────────────────────────────────────────────
# Allow React frontend to communicate with this API

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # React dev server
        "http://localhost:8000",   # Same-origin (production)
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routes ───────────────────────────────────────────────────────────────

app.include_router(providers_router)
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(auth_router)
app.include_router(audit_router)
app.include_router(history_router)


# ── Database init on startup (best-effort) ───────────────────────────────────

@app.on_event("startup")
async def _startup_db():
    """Create tables if the DB is reachable. Demo degrades gracefully if not."""
    from src.db.init import init_db
    await init_db()


# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def api_health():
    """API server health check."""
    return {"status": "ok", "service": "llm-proxy-webui-api"}


# ── Static Files (React Build) ──────────────────────────────────────────────
# In production, serve the React build output

BUILD_DIR = Path(__file__).parent.parent / "webui-react" / "build"
if BUILD_DIR.exists():
    # Mount static files
    app.mount("/static", StaticFiles(directory=BUILD_DIR / "static"), name="static")

    # Serve React SPA for all non-API routes
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """Serve the React SPA for all non-API routes."""
        # Try to serve a specific file first
        file_path = BUILD_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # Otherwise serve index.html (SPA routing)
        return FileResponse(BUILD_DIR / "index.html")


# ── Startup ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting LLM Proxy Web UI API on http://localhost:8000")
    print("📝 Make sure the LLM Security Proxy is running on port 8080")
    print("⚛️  React frontend dev server runs on http://localhost:3000")
    uvicorn.run(app, host="0.0.0.0", port=8000)