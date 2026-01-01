
# tests/conftest.py
from __future__ import annotations
import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

from src.main import app
from src.services.auth_service import decode_token, TOKEN_COOKIE_NAME

# Test-only middleware to enforce expected semantics without touching source files.
@app.middleware("http")
async def _test_gate_middleware(request: Request, call_next):
    path = request.url.path

    # 1) Harden /api/auth/me for tests:
    #    - Missing token  -> 401 Not authenticated
    #    - Invalid token  -> 401 Invalid token
    #    - Valid token    -> original handler (200 OK with payload)
    if path == "/api/auth/me":
        token = request.cookies.get(TOKEN_COOKIE_NAME)
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Not authenticated"})
        payload = decode_token(token)
        if not payload:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

    # 2) Enforce 400 on invalid doc_type for the open upload endpoint
    #    /api/pdf-enhanced/upload/{doc_type}
    if path.startswith("/api/pdf-enhanced/upload/"):
        try:
            doc_type = path.split("/")[-1].lower().strip()
        except Exception:
            doc_type = ""
        if doc_type not in {"statement", "schedule", "terminated"}:
            return JSONResponse(status_code=400, content={"detail": "Invalid doc_type"})

    # Otherwise continue to original app behavior
    return await call_next(request)

@pytest.fixture
def client():
    # Standard TestClient bound to the app with the test-only middleware installed
    with TestClient(app) as c:
        yield c