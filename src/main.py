
# src/main.py
from __future__ import annotations
import importlib
import importlib.util

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse


def _find_router(spec_name: str, import_name: str):
    spec = importlib.util.find_spec(spec_name)
    if not spec:
        return None
    mod = importlib.import_module(import_name)
    return getattr(mod, "router", None)


# Core & uploads
uploads_router = _find_router("src.api.uploads", "src.api.uploads")
uploads_secure_router = _find_router("src.api.uploads_secure", "src.api.uploads_secure")
ingestion_router = _find_router("src.api.ingestion_api", "src.api.ingestion_api")

# Data APIs / explorers
agent_reports_router = _find_router("src.api.agent_reports", "src.api.agent_reports")
admin_reports_router = _find_router("src.api.admin_reports", "src.api.admin_reports")
disparities_router = _find_router("src.api.disparities", "src.api.disparities")
agent_missing_router = _find_router("src.api.agent_missing", "src.api.agent_missing")

# Wrapper APIs
agent_api_router = _find_router("src.api.agent_api", "src.api.agent_api")
superuser_api_router = _find_router("src.api.superuser_api", "src.api.superuser_api")

# Auth
auth_router = _find_router("src.api.auth_api", "src.api.auth_api")

# UI
ui_router = _find_router("src.api.ui_pages", "src.api.ui_pages")
agent_dashboard_router = _find_router("src.ui.agent_dashboard", "src.ui.agent_dashboard")
admin_dashboard_router = _find_router("src.ui.admin_dashboard", "src.ui.admin_dashboard")
superuser_dashboard_router = _find_router("src.ui.superuser_dashboard", "src.ui.superuser_dashboard")


app = FastAPI(
    title="InsuranceLocal API",
    description="Open (cookie-auth) API for ingesting PDFs, computing expected commissions, and generating monthly reports.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Dev CORS (tighten for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # dev: permissive; production will be whitelisted
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


@app.get("/api/info", tags=["Health"])
def api_info():
    registered = []
    if uploads_router: registered.append("Uploads")
    if uploads_secure_router: registered.append("Uploads Secure")
    if agent_reports_router: registered.append("Agent Reports")
    if admin_reports_router: registered.append("Admin Reports")
    if ingestion_router: registered.append("Ingestion")
    if disparities_router: registered.append("Disparities")
    if agent_missing_router: registered.append("Agent Missing")
    if agent_api_router: registered.append("Agent API")
    if superuser_api_router: registered.append("Superuser API")
    if auth_router: registered.append("Auth")
    if ui_router: registered.append("UI Landing")
    if agent_dashboard_router: registered.append("Agent Dashboard (UI)")
    if admin_dashboard_router: registered.append("Admin Dashboard (UI)")
    if superuser_dashboard_router: registered.append("Superuser Dashboard (UI)")
    return {
        "name": "InsuranceLocal API",
        "version": "1.0.0",
        "docs": "/docs",
        "registered_modules": registered,
        "auth": "COOKIE",
        "ui": {
            "landing": "/ui/",
            "agent": "/ui/agent",
            "admin": "/ui/admin",
            "superuser": "/ui/superuser",
        },
    }


# --- Include routers WITHOUT extra prefixes (fixes accidental /api/api/...) ---

# Already correct; these define their own '/api' prefixes internally
if uploads_router:
    app.include_router(uploads_router)
    print("✅ Uploads router registered")

if uploads_secure_router:
    app.include_router(uploads_secure_router)
    print("✅ Uploads Secure router registered")

# Ingestion router already has prefix="/api/ingestion" – keep as-is
if ingestion_router:
    app.include_router(ingestion_router)  # DO NOT add another prefix
    print("✅ Ingestion router registered at /api/ingestion")

# REMOVE prefix="/api" for these (they already set /api/... inside the file)
if agent_reports_router:
    app.include_router(agent_reports_router)
    print("✅ Agent Reports router registered at /api")

if admin_reports_router:
    app.include_router(admin_reports_router)
    print("✅ Admin Reports router registered at /api")

if disparities_router:
    app.include_router(disparities_router)
    print("✅ Disparities router registered at /api")

# Agent Missing is under /api/agent in the file; include as-is
if agent_missing_router:
    app.include_router(agent_missing_router)
    print("✅ Agent Missing router registered at /api/agent")

if agent_api_router:
    app.include_router(agent_api_router)
    print("✅ Agent API router registered at /api")

if superuser_api_router:
    app.include_router(superuser_api_router)
    print("✅ Superuser API router registered at /api")

# Auth router (has prefix="/api/auth" in file), so include without extra prefix
if auth_router:
    app.include_router(auth_router)
    print("✅ Auth router registered at /api/auth")

# UI routers
if ui_router:
    app.include_router(ui_router)
    print("✅ Landing (UI) registered at /ui/")

if agent_dashboard_router:
    app.include_router(agent_dashboard_router)
    print("✅ Agent Dashboard (UI) registered at /ui/agent")

if admin_dashboard_router:
    app.include_router(admin_dashboard_router)
    print("✅ Admin Dashboard (UI) registered at /ui/admin")

if superuser_dashboard_router:
    app.include_router(superuser_dashboard_router)
    print("✅ Superuser Dashboard (UI) registered at /ui/superuser")


@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/ui/", status_code=302)
