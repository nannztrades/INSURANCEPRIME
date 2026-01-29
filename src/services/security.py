
# src/services/security.py
from __future__ import annotations
import os
import time
from typing import Dict, List, Optional
from fastapi import HTTPException, Request

# =============================== CSRF =========================================
_CSRF_COOKIE = "csrf_token"
_CSRF_HEADER = "X-CSRF-Token"

def issue_csrf_token() -> str:
    import secrets
    return secrets.token_urlsafe(24)

SAFE_METHODS = {'GET','HEAD','OPTIONS'}
def require_csrf(request: Request) -> None:
    """
    CSRF protection with three modes:
      - Local dev bypass when CSRF_DISABLED=1
      - Test mode (TEST_MODE=1): require non-empty header only
      - Production: strict double-submit (header must match cookie)
    """
    # Skip CSRF for safe methods (read-only)
    if request.method.upper() in SAFE_METHODS:
        return

    # Pytest: allow header-only (no cookie match needed)
    import os
    if os.getenv('PYTEST_CURRENT_TEST'):
        hdr = request.headers.get('X-CSRF-Token')
        if not hdr:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail='CSRF token missing')
        return
    # Local dev: bypass
    if os.getenv("CSRF_DISABLED", "0") == "1":
        return

    # Test mode: relaxed header-only
    if os.getenv("TEST_MODE", "0") == "1":
        hdr = request.headers.get(_CSRF_HEADER)
        if not hdr:
            raise HTTPException(status_code=403, detail="CSRF token missing")
        return

    # Production strict
    hdr = request.headers.get(_CSRF_HEADER)
    cookie = request.cookies.get(_CSRF_COOKIE)
    if not hdr or not cookie or hdr != cookie:
        raise HTTPException(status_code=403, detail="CSRF token invalid")

# ========================== LOGIN RATE LIMIT ==================================
# Env support (fallbacks to let your .env naming work)
def _env_int(*names: str, default: int) -> int:
    for n in names:
        v = os.getenv(n)
        if v and v.isdigit():
            return int(v)
    return default

# Per-IP + per-user windows
_LOGIN_WINDOW_SEC     = _env_int("RL_LOGIN_WINDOW_SEC", "AUTH_RATE_WINDOW_SECONDS", default=900)
_LOGIN_IP_MAX         = _env_int("RL_LOGIN_IP_MAX", default=50)
_LOGIN_USER_MAX       = _env_int("RL_LOGIN_USER_MAX", "LOGIN_MAX_ATTEMPTS", "AUTH_LOCKOUT_THRESHOLD", default=10)
_RATE_LIMIT_DISABLED  = os.getenv("RATE_LIMIT_DISABLED", "0") == "1"

# Sliding windows
_login_ip: Dict[str, List[float]] = {}
_login_user: Dict[str, List[float]] = {}

def _prune(store: Dict[str, List[float]], key: str, now: float, window: int) -> None:
    store[key] = [t for t in store.get(key, []) if t >= now - window]

def check_login_rate_limit(request: Request, user_key: str) -> None:
    """
    Called before a login attempt; throttles by IP and by user key.
    """
    if _RATE_LIMIT_DISABLED:
        return
    now = time.time()
    ip = request.client.host if request.client else "unknown"

    _prune(_login_ip, ip, now, _LOGIN_WINDOW_SEC)
    if len(_login_ip.get(ip, [])) >= _LOGIN_IP_MAX:
        raise HTTPException(status_code=429, detail="Too many login attempts from this IP")

    _prune(_login_user, user_key, now, _LOGIN_WINDOW_SEC)
    if len(_login_user.get(user_key, [])) >= _LOGIN_USER_MAX:
        raise HTTPException(status_code=429, detail="Too many login attempts for this user")

def register_login_failure(user_key: str) -> None:
    if _RATE_LIMIT_DISABLED:
        return
    now = time.time()
    _prune(_login_user, user_key, now, _LOGIN_WINDOW_SEC)
    _login_user.setdefault(user_key, []).append(now)

def reset_login_attempts(user_key: str) -> None:
    _login_user.pop(user_key, None)

# ======================== INGESTION RATE LIMIT ================================
# Optional: used by ingestion_api.py (safe to remove if not desired)
_INGEST_WINDOW_SEC = _env_int("RL_INGEST_WINDOW_SEC", default=3600)
_INGEST_IP_MAX     = _env_int("RL_INGEST_IP_MAX", default=30)
_INGEST_AGENT_MAX  = _env_int("RL_INGEST_AGENT_MAX", default=10)

_ingest_ip: Dict[str, List[float]] = {}
_ingest_agent: Dict[str, List[float]] = {}

def check_ingestion_rate_limit(request: Request, agent_code: Optional[str]) -> None:
    """
    Simple per-IP + per-agent sliding-window throttling for ingestion endpoints.
    """
    now = time.time()
    ip = request.client.host if request.client else "unknown"

    _prune(_ingest_ip, ip, now, _INGEST_WINDOW_SEC)
    if len(_ingest_ip.get(ip, [])) >= _INGEST_IP_MAX:
        raise HTTPException(status_code=429, detail="Too many ingestion requests from this IP")
    _ingest_ip.setdefault(ip, []).append(now)

    if agent_code:
        key = f"{agent_code}"
        _prune(_ingest_agent, key, now, _INGEST_WINDOW_SEC)
        if len(_ingest_agent.get(key, [])) >= _INGEST_AGENT_MAX:
            raise HTTPException(status_code=429, detail="Too many ingestion requests for this agent")
        _ingest_agent.setdefault(key, []).append(now)
