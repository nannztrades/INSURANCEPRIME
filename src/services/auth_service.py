
# src/services/auth_service.py
from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
import json, uuid, hmac, hashlib
import jwt  # PyJWT
from passlib.hash import argon2
from src.ingestion.db import get_conn
from src.services.config import (
    JWT_SECRET, ACCESS_TOKEN_TTL_MIN, REFRESH_TOKEN_TTL_DAYS, TOKEN_ISSUER,
    AUTH_COOKIE_SECURE, AUTH_COOKIE_SAMESITE, COOKIE_DOMAIN,
)

# ── Cookie names (keep legacy name for access to avoid breaking UI/routes) ──
TOKEN_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"

ALG = "HS256"

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

# ───────────────────────────────────────────────────────────────────────────────
# Password hashing (Argon2) – keep API you already call elsewhere
# ───────────────────────────────────────────────────────────────────────────────
def hash_password(plaintext: str) -> str:
    return argon2.hash(plaintext)

def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return argon2.verify(plaintext, hashed)
    except Exception:
        return False

def verify_and_upgrade_password(plaintext: str, hashed: str) -> Tuple[bool, Optional[str]]:
    """
    Verify and optionally upgrade hash params. Returns (ok, new_hash_or_None).
    """
    try:
        ok = argon2.verify(plaintext, hashed)
        if not ok:
            return False, None
        # 'needs_update' will depend on passlib policy; regenerate hash if needed
        if argon2.identify(hashed) and argon2.needs_update(hashed):
            return True, argon2.hash(plaintext)
        return True, None
    except Exception:
        return False, None

# ───────────────────────────────────────────────────────────────────────────────
# JWT helpers: Access + Refresh with JTI
# ───────────────────────────────────────────────────────────────────────────────
def _base_claims() -> Dict[str, Any]:
    return {"iss": TOKEN_ISSUER}

def _encode(payload: Dict[str, Any], expires_in: timedelta) -> str:
    now = _utcnow()
    to_encode = {
        **_base_claims(),
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_in).timestamp()),
    }
    return jwt.encode(to_encode, JWT_SECRET, algorithm=ALG)

def _decode(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[ALG], options={"require": ["exp", "iat"]})
    except Exception:
        return None

# Access token (short-lived)
def create_access_token(identity: Dict[str, Any]) -> str:
    return _encode({"typ": "access", **identity}, timedelta(minutes=ACCESS_TOKEN_TTL_MIN))

# Refresh token (rotating; persists JTI in DB)
def create_refresh_token(user_id: int, meta: Optional[Dict[str, Any]] = None) -> Tuple[str, str, datetime]:
    jti = str(uuid.uuid4())
    expires = _utcnow() + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    tok = _encode({"typ": "refresh", "sub": str(user_id), "jti": jti, **(meta or {})},
                  expires_in=timedelta(days=REFRESH_TOKEN_TTL_DAYS))
    # Persist
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO `auth_refresh_tokens`
                (`jti`,`user_id`,`issued_at`,`expires_at`,`rotated_from`,`is_revoked`,`client_fingerprint`,`ip_address`)
                VALUES (%s,%s,UTC_TIMESTAMP(),%s,NULL,0,%s,%s)
                """,
                (jti, int(user_id), expires.strftime("%Y-%m-%d %H:%M:%S"), None, None),
            )
        conn.commit()
    finally:
        conn.close()
    return tok, jti, expires

def revoke_refresh_jti(jti: str, reason: str = "logout", expires_at: Optional[datetime] = None) -> None:
    # mark token row revoked & insert deny entry
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE `auth_refresh_tokens` SET `is_revoked`=1 WHERE `jti`=%s", (jti,))
            cur.execute(
                "INSERT IGNORE INTO `auth_token_denylist` (`jti`,`reason`,`created_at`,`expires_at`) VALUES (%s,%s,UTC_TIMESTAMP(),%s)",
                (jti, reason, (expires_at or (_utcnow() + timedelta(days=REFRESH_TOKEN_TTL_DAYS))).strftime("%Y-%m-%d %H:%M:%S")),
            )
        conn.commit()
    finally:
        conn.close()

def is_denied(jti: str) -> bool:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM `auth_token_denylist` WHERE `jti`=%s LIMIT 1", (jti,))
            row = cur.fetchone()
            return bool(row)
    finally:
        conn.close()

def rotate_refresh_token(old_jti: str, user_id: int, meta: Optional[Dict[str, Any]] = None) -> Tuple[str, str, datetime]:
    # Issue a new RT and link back, then deny old
    new_tok, new_jti, expires = create_refresh_token(user_id, meta=meta)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE `auth_refresh_tokens` SET `is_revoked`=1 WHERE `jti`=%s", (old_jti,))
            cur.execute("UPDATE `auth_refresh_tokens` SET `rotated_from`=%s WHERE `jti`=%s", (old_jti, new_jti))
            cur.execute(
                "INSERT IGNORE INTO `auth_token_denylist` (`jti`,`reason`,`created_at`,`expires_at`) VALUES (%s,%s,UTC_TIMESTAMP(),%s)",
                (old_jti, "rotated", expires.strftime("%Y-%m-%d %H:%M:%S")),
            )
        conn.commit()
    finally:
        conn.close()
    return new_tok, new_jti, expires

# ───────────────────────────────────────────────────────────────────────────────
# Public decode shims (keep names used across code)
# ───────────────────────────────────────────────────────────────────────────────
def decode_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Legacy-friendly: decode access token only (used by UI pages & roles).
    """
    if not token:
        return None
    claims = _decode(token)
    if not claims or claims.get("typ") != "access":
        return None
    return claims

def decode_refresh_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    claims = _decode(token)
    if not claims or claims.get("typ") != "refresh":
        return None
    # deny-list check
    jti = claims.get("jti")
    if not jti or is_denied(jti):
        return None
    # check DB row status & expiry window
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT `is_revoked`,`expires_at` FROM `auth_refresh_tokens` WHERE `jti`=%s", (jti,))
            row = cur.fetchone() or {}
            if int(row.get("is_revoked") or 0) == 1:
                return None
    finally:
        conn.close()
    return claims

# ───────────────────────────────────────────────────────────────────────────────
# Backward compatibility helpers used by current auth_api
# ───────────────────────────────────────────────────────────────────────────────
def create_token(payload: Dict[str, Any], ttl_minutes: int) -> str:
    """Legacy: create an access token for given minutes (used by current login)."""
    return _encode({"typ": "access", **payload}, timedelta(minutes=int(ttl_minutes)))

# Cookie helpers (set flags in the routers)
def cookie_args(max_age: int) -> Dict[str, Any]:
    args: Dict[str, Any] = {
        "httponly": True,
        "secure": AUTH_COOKIE_SECURE,
        "samesite": AUTH_COOKIE_SAMESITE,
        "max_age": max_age,
        "path": "/",
    }
    if COOKIE_DOMAIN:
        args["domain"] = COOKIE_DOMAIN
    return args
