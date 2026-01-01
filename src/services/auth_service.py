
# src/services/auth_service.py
from __future__ import annotations
import os, json, hmac, hashlib, time, base64
from typing import Any, Dict, Optional

# Environment-driven configuration
AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-secret-change-me")
TOKEN_COOKIE_NAME = os.getenv("AUTH_COOKIE", "access_token")
DEFAULT_EXP_MINUTES = int(os.getenv("AUTH_EXP_MINUTES", str(7 * 24 * 60)))  # default 7 days

def _b64url_encode(data: bytes) -> str:
    """Base64 URL-safe encoding without padding."""
    return base64.urlsafe_b64encode(data).decode().rstrip("=")

def _b64url_decode(s: str) -> bytes:
    """Base64 URL-safe decoding with restored padding."""
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)

def create_token(payload: Dict[str, Any], exp_minutes: int = DEFAULT_EXP_MINUTES) -> str:
    """
    Create a compact HS256-signed token (JWT-like) without external deps.
    Includes standard 'iat' and 'exp' claims.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())

    body = dict(payload)
    body["iat"] = now
    body["exp"] = now + exp_minutes * 60

    h = _b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    p = _b64url_encode(json.dumps(body, separators=(",", ":")).encode())

    signing_input = f"{h}.{p}".encode()
    sig = hmac.new(AUTH_SECRET.encode(), signing_input, hashlib.sha256).digest()
    s = _b64url_encode(sig)

    return f"{h}.{p}.{s}"

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify and decode the token. Returns payload dict or None if invalid/expired.
    """
    try:
        h, p, s = token.split(".")
        signing_input = f"{h}.{p}".encode()
        expected = hmac.new(AUTH_SECRET.encode(), signing_input, hashlib.sha256).digest()

        # Constant-time comparison
        if not hmac.compare_digest(expected, _b64url_decode(s)):
            return None

        payload = json.loads(_b64url_decode(p).decode())
        exp = int(payload.get("exp", 0))
        if exp and int(time.time()) > exp:
            return None
        return payload
    except Exception:
        return None

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt if available; fallback to SHA-256 for dev.
    NOTE: Use bcrypt in production. SHA-256 fallback is not suitable for prod.
    """
    try:
        import bcrypt  # type: ignore
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()
    except Exception:
        # Development-only fallback
        return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, stored_hash: str) -> bool:
    """
    Verify a password against a stored hash (supports bcrypt and SHA-256 fallback).
    """
    if not stored_hash:
        return False
    try:
        import bcrypt  # type: ignore
        # Bcrypt hashes typically start with "$2"
        if stored_hash.startswith("$2"):
            return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except Exception:
        # If bcrypt import fails or stored_hash isn't bcrypt, fall through to SHA-256
        pass

    # SHA-256 fallback comparison (constant-time)
    candidate = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(candidate, stored_hash)
