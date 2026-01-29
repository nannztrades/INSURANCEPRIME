
# src/services/config.py
from __future__ import annotations
import os
from datetime import timedelta

def env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None: return default
    try:
        return bool(int(v))
    except Exception:
        return str(v).strip().lower() in ("true", "yes", "y", "on")

def env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None: return default
    try:
        return int(v)
    except Exception:
        return default

def env_str(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v is not None else default

# Environment
ENV = env_str("ENV", "local")                 # local | dev | prod

# JWT & Cookies
JWT_SECRET = env_str("JWT_SECRET", "dev-secret-please-change")
ACCESS_TOKEN_TTL_MIN = env_int("ACCESS_TOKEN_TTL_MIN", 15)    # 15 minutes
REFRESH_TOKEN_TTL_DAYS = env_int("REFRESH_TOKEN_TTL_DAYS", 7) # 7 days
TOKEN_ISSUER = env_str("TOKEN_ISSUER", "icrs.local")

# Cookies
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", False)
AUTH_COOKIE_SAMESITE = env_str("AUTH_COOKIE_SAMESITE", "lax").lower()  # lax|strict|none
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN")  # optional in local

# CSRF
CSRF_ENABLED = env_bool("CSRF_ENABLED", ENV == "prod")

# Rate limits (window & caps)
# Format is kept simple so we can tune via env if needed.
RL_LOGIN_IP_MAX = env_int("RL_LOGIN_IP_MAX", 20)     # per 15 min
RL_LOGIN_USER_MAX = env_int("RL_LOGIN_USER_MAX", 10) # per 15 min
RL_LOGIN_WINDOW_SEC = env_int("RL_LOGIN_WINDOW_SEC", 15 * 60)
RL_INGEST_IP_MAX = env_int("RL_INGEST_IP_MAX", 30)       # per hour
RL_INGEST_AGENT_MAX = env_int("RL_INGEST_AGENT_MAX", 10) # per hour
RL_INGEST_WINDOW_SEC = env_int("RL_INGEST_WINDOW_SEC", 60 * 60)
