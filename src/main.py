
# src/main.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

# ── Cookie guardrails BEFORE importing auth_api (it reads env at import time) ──
APP_ENV = os.getenv("APP_ENV", os.getenv("ENV", "development")).lower().strip()
if APP_ENV in {"prod", "production"}:
    # Enforce: SameSite=None + Secure=True for prod
    os.environ["AUTH_COOKIE_SAMESITE"] = "none"
    os.environ["AUTH_COOKIE_SECURE"] = "1"
else:
    # Dev defaults: SameSite=Lax + Secure=False
    os.environ.setdefault("AUTH_COOKIE_SAMESITE", "lax")
    os.environ.setdefault("AUTH_COOKIE_SECURE", "0")

# ── Import routers ──
from src.api import (
    admin_agents,
    admin_reports,
    admin_users,
    agent_api,
    agent_missing,
    agent_reports,
    auth_api,
    disparities,
    superuser_api,
    ui_pages,
    uploads,
    uploads_secure,
    health as health_api,
)

# ── App ──
app = FastAPI(title="ICRS", version="1.0.0")

# Optional CORS for local dev UI testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── APIVersionRewrite middleware: /api/v1/* -> /api/*; in dev /api/* responds with Deprecation header ──
@app.middleware("http")
async def api_version_rewrite(request: Request, call_next: Callable):
    path: str = request.scope.get("path", "")
    legacy = False
    if path.startswith("/api/v1/"):
        # Rewrite to /api/*
        new_path = "/api/" + path[len("/api/v1/"):]
        # mutate scope for downstream router
        request.scope["path"] = new_path
    elif path.startswith("/api/") and APP_ENV in {"dev", "development"}:
        legacy = True

    resp: Response = await call_next(request)
    if legacy:
        resp.headers["Deprecation"] = "true"
    return resp

# ── Startup: create directories and validate cookie guardrails ──
@app.on_event("startup")
async def on_startup() -> None:
    # Directories
    ingest = Path(os.getenv("INGEST_DIR", "data/incoming"))
    tmp = Path(os.getenv("TMP_DIR", "tmp_ingestion_upload"))
    reports = Path(os.getenv("REPORTS_DIR", "data/reports"))
    for p in (ingest, tmp, reports):
        p.mkdir(parents=True, exist_ok=True)

    # Final cookie guardrails check
    if APP_ENV in {"prod", "production"}:
        if os.getenv("AUTH_COOKIE_SAMESITE", "").lower() != "none" or os.getenv("AUTH_COOKIE_SECURE", "0") != "1":
            raise RuntimeError("Cookie settings invalid for production (require SameSite=None and Secure=True).")

# ── Mount all routers under /api (v1 comes via middleware) and /ui ──
app.include_router(auth_api.router, prefix="/api")
app.include_router(admin_agents.router, prefix="/api")
app.include_router(admin_users.router, prefix="/api")
app.include_router(admin_reports.router, prefix="/api")
app.include_router(agent_api.router, prefix="/api")
app.include_router(agent_missing.router, prefix="/api")
app.include_router(agent_reports.router, prefix="/api")
app.include_router(superuser_api.router, prefix="/api")
app.include_router(disparities.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(uploads_secure.router, prefix="/api")
app.include_router(ui_pages.router, prefix="")     # /ui/*
app.include_router(health_api.router, prefix="")   # /healthz, /readyz

# Root – simple redirect to /ui/
@app.get("/")
def root() -> dict:
    return {"status": "OK", "ui": "/ui/"}
