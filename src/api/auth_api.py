
# src/api/auth_api.py
from __future__ import annotations

from typing import Any, Dict, Literal, Union, cast
from fastapi import APIRouter, HTTPException, Form, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse
import os

from src.ingestion.db import get_conn
from src.services.auth_service import (
    create_token,
    decode_token,
    verify_and_upgrade_password,
    TOKEN_COOKIE_NAME,
)
from src.services.security import (
    check_login_rate_limit,
    register_login_failure,
    reset_login_attempts,
    issue_csrf_token,
    require_csrf,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# --------------------------------------------------------------------
# Cookie / Session configuration (env-tunable; safe defaults for dev)
# --------------------------------------------------------------------
DEFAULT_AUTH_EXP_MINUTES: int = int(os.getenv("AUTH_EXP_MINUTES", "10080"))  # 7 days
AUTH_COOKIE_SECURE = bool(int(os.getenv("AUTH_COOKIE_SECURE", "0")))  # 0/1
AUTH_COOKIE_SAMESITE_ENV = os.getenv("AUTH_COOKIE_SAMESITE", "lax").lower()  # lax|strict|none


def _normalize_samesite(val: str) -> Literal["lax", "strict", "none"]:
    v = val.lower().strip()
    if v == "strict":
        return cast(Literal["strict"], "strict")
    if v == "none":
        return cast(Literal["none"], "none")
    return cast(Literal["lax"], "lax")


def _set_cookie(resp: Union[JSONResponse, RedirectResponse], token: str) -> None:
    """
    Set the session cookie with secure defaults; compatible with JSONResponse/RedirectResponse.
    """
    resp.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=_normalize_samesite(AUTH_COOKIE_SAMESITE_ENV),
        secure=AUTH_COOKIE_SECURE,
        max_age=DEFAULT_AUTH_EXP_MINUTES * 60,
        path="/",
    )


# --------------------------------------------------------------------
# CSRF Token
# --------------------------------------------------------------------
@router.get("/csrf")
def get_csrf() -> JSONResponse:
    """
    Issue a CSRF token and set a readable cookie "csrf_token".
    Client JS should echo this value in the "X-CSRF-Token" header for state-changing calls.
    """
    token = issue_csrf_token()
    resp = JSONResponse({"status": "OK", "csrf_token": token})
    # Not HttpOnly so JS can read and set X-CSRF-Token
    resp.set_cookie(
        "csrf_token",
        token,
        httponly=False,
        samesite=_normalize_samesite(AUTH_COOKIE_SAMESITE_ENV),
        secure=AUTH_COOKIE_SECURE,
        path="/",
    )
    return resp


# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _update_last_login(conn, user_id: int, new_hash: str | None) -> None:
    """
    Update last_login; if verify_and_upgrade_password provided a new hash, persist it.
    """
    with conn.cursor() as cur:
        if new_hash:
            cur.execute(
                "UPDATE `users` SET `password_hash`=%s, `last_login`=NOW() WHERE `id`=%s",
                (new_hash, user_id),
            )
        else:
            cur.execute(
                "UPDATE `users` SET `last_login`=NOW() WHERE `id`=%s",
                (user_id,),
            )
    conn.commit()


# --------------------------------------------------------------------
# Agent login (Agent Code + Password)
# --------------------------------------------------------------------
@router.post("/login/agent")
def login_agent_by_code(
    request: Request,
    agent_code: str = Form(...),
    password: str = Form(...),
    _: Any = Depends(require_csrf),
) -> JSONResponse:
    if not agent_code or not password:
        raise HTTPException(status_code=422, detail="agent_code and password are required")

    user_key = f"agent:{agent_code}"
    check_login_rate_limit(request, user_key)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM `users` WHERE `agent_code`=%s AND `role`='agent' "
                "ORDER BY `id` DESC LIMIT 1",
                (agent_code,),
            )
            u = cur.fetchone() or None

        if not u:
            register_login_failure(user_key)
            raise HTTPException(status_code=404, detail="Agent user not found")

        if int(u.get("is_active") or 0) != 1:
            register_login_failure(user_key)
            raise HTTPException(status_code=403, detail="User inactive")

        ok, maybe_new_hash = verify_and_upgrade_password(password, u.get("password_hash") or "")
        if not ok:
            register_login_failure(user_key)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        _update_last_login(conn, int(u["id"]), maybe_new_hash)

        payload: Dict[str, Any] = {
            "role": "agent",
            "user_id": int(u["id"]),
            "user_email": u.get("email"),
            "agent_code": u.get("agent_code"),
            "agent_name": u.get("agent_name"),
        }
        token = create_token(payload, DEFAULT_AUTH_EXP_MINUTES)
        resp = JSONResponse(
            {
                "status": "OK",
                "role": "agent",
                "user_id": int(u["id"]),
                "user_email": u.get("email"),
                "agent_code": u.get("agent_code"),
                "agent_name": u.get("agent_name"),
            }
        )
        _set_cookie(resp, token)
        reset_login_attempts(user_key)
        return resp
    finally:
        conn.close()


# --------------------------------------------------------------------
# Agent login (User ID + Password)
# --------------------------------------------------------------------
@router.post("/login/agent-user")
def login_agent_by_user_id(
    request: Request,
    user_id: int = Form(...),
    password: str = Form(...),
    _: Any = Depends(require_csrf),
) -> JSONResponse:
    if not user_id or not password:
        raise HTTPException(status_code=422, detail="user_id and password are required")

    user_key = f"user:{user_id}"
    check_login_rate_limit(request, user_key)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM `users` WHERE `id`=%s", (user_id,))
            u = cur.fetchone() or None

        if not u:
            register_login_failure(user_key)
            raise HTTPException(status_code=404, detail="User not found")

        if int(u.get("is_active") or 0) != 1:
            register_login_failure(user_key)
            raise HTTPException(status_code=403, detail="User inactive")

        if (u.get("role") or "").lower() != "agent":
            register_login_failure(user_key)
            raise HTTPException(status_code=403, detail="Role not permitted (requires agent)")

        ok, maybe_new_hash = verify_and_upgrade_password(password, u.get("password_hash") or "")
        if not ok:
            register_login_failure(user_key)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        _update_last_login(conn, int(u["id"]), maybe_new_hash)

        payload: Dict[str, Any] = {
            "role": "agent",
            "user_id": int(u["id"]),
            "user_email": u.get("email"),
            "agent_code": u.get("agent_code"),
            "agent_name": u.get("agent_name"),
        }
        token = create_token(payload, DEFAULT_AUTH_EXP_MINUTES)
        resp = JSONResponse(
            {
                "status": "OK",
                "role": "agent",
                "user_id": int(u["id"]),
                "user_email": u.get("email"),
                "agent_code": u.get("agent_code"),
                "agent_name": u.get("agent_name"),
            }
        )
        _set_cookie(resp, token)
        reset_login_attempts(user_key)
        return resp
    finally:
        conn.close()


# --------------------------------------------------------------------
# Admin & Superuser login (User ID + Password)
# --------------------------------------------------------------------
@router.post("/login/user")
def login_admin_or_superuser(
    request: Request,
    user_id: int = Form(...),
    password: str = Form(...),
    _: Any = Depends(require_csrf),
) -> JSONResponse:
    if not user_id or not password:
        raise HTTPException(status_code=422, detail="user_id and password are required")

    user_key = f"user:{user_id}"
    check_login_rate_limit(request, user_key)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM `users` WHERE `id`=%s", (user_id,))
            u = cur.fetchone() or None

        if not u:
            register_login_failure(user_key)
            raise HTTPException(status_code=404, detail="User not found")

        if int(u.get("is_active") or 0) != 1:
            register_login_failure(user_key)
            raise HTTPException(status_code=403, detail="User inactive")

        role = (u.get("role") or "").lower()
        if role not in ("admin", "superuser"):
            register_login_failure(user_key)
            raise HTTPException(status_code=403, detail="Role not permitted")

        ok, maybe_new_hash = verify_and_upgrade_password(password, u.get("password_hash") or "")
        if not ok:
            register_login_failure(user_key)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        _update_last_login(conn, int(u["id"]), maybe_new_hash)

        payload: Dict[str, Any] = {
            "role": role,
            "user_id": int(u["id"]),
            "user_email": u.get("email"),
            "agent_code": u.get("agent_code"),
            "agent_name": u.get("agent_name"),
        }
        token = create_token(payload, DEFAULT_AUTH_EXP_MINUTES)
        resp = JSONResponse(
            {
                "status": "OK",
                "role": role,
                "user_id": int(u["id"]),
                "user_email": u.get("email"),
                "agent_code": u.get("agent_code"),
                "agent_name": u.get("agent_name"),
            }
        )
        _set_cookie(resp, token)
        reset_login_attempts(user_key)
        return resp
    finally:
        conn.close()


# --------------------------------------------------------------------
# Logout & Identity
# --------------------------------------------------------------------
@router.post("/logout")
def logout_post() -> RedirectResponse:
    resp = RedirectResponse(url="/ui/", status_code=303)
    resp.delete_cookie(TOKEN_COOKIE_NAME, path="/")
    return resp


@router.get("/logout")
def logout_get() -> RedirectResponse:
    resp = RedirectResponse(url="/ui/", status_code=302)
    resp.delete_cookie(TOKEN_COOKIE_NAME, path="/")
    return resp


@router.get("/me")
def me(request: Request) -> JSONResponse:
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if not token:
        return JSONResponse(status_code=401, content={"status": "ANON"})
    payload = decode_token(token)
    if not payload:
        return JSONResponse(status_code=401, content={"status": "INVALID"})
    return JSONResponse(status_code=200, content={"status": "OK", "identity": payload})
