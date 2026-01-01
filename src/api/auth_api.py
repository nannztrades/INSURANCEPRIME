
# src/api/auth_api.py
from __future__ import annotations
from typing import Dict, Any, Optional, Literal, cast
from fastapi import APIRouter, HTTPException, Form, Request
from fastapi.responses import JSONResponse
from src.ingestion.db import get_conn
from src.services.auth_service import (
    create_token, decode_token, verify_password, TOKEN_COOKIE_NAME
)
import os

router = APIRouter(prefix="/api/auth", tags=["Auth"])

DEFAULT_AUTH_EXP_MINUTES: int = int(os.getenv("AUTH_EXP_MINUTES", "10080"))  # 7 days
AUTH_COOKIE_SECURE = bool(int(os.getenv("AUTH_COOKIE_SECURE", "0")))        # 0/1
AUTH_COOKIE_SAMESITE_ENV = os.getenv("AUTH_COOKIE_SAMESITE", "lax").lower() # 'lax'|'strict'|'none'

def _normalize_samesite(val: str) -> Literal['lax', 'strict', 'none']:
    v = val.lower().strip()
    if v == 'strict':
        return cast(Literal['strict'], 'strict')
    if v == 'none':
        return cast(Literal['none'], 'none')
    return cast(Literal['lax'], 'lax')

def _set_cookie(resp: JSONResponse, token: str) -> None:
    resp.set_cookie(
        key=TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite=_normalize_samesite(AUTH_COOKIE_SAMESITE_ENV),  # Pylance-safe Literal
        secure=AUTH_COOKIE_SECURE,
        max_age=DEFAULT_AUTH_EXP_MINUTES * 60,
        path="/",
    )

@router.post("/login/agent")
def login_agent(agent_code: str = Form(...)) -> JSONResponse:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT agent_code, agent_name, is_active FROM `agents` WHERE `agent_code`=%s",
                (agent_code,)
            )
            a = cur.fetchone() or None
            if not a or int(a.get("is_active") or 0) != 1:
                raise HTTPException(status_code=403, detail="Agent not found or inactive")

            cur.execute(
                "SELECT id, email, role, is_active FROM `users` WHERE `agent_code`=%s ORDER BY id DESC LIMIT 1",
                (agent_code,)
            )
            u = cur.fetchone() or {}
            user_id = u.get("id")
            email = u.get("email")
            role = "agent"

            payload: Dict[str, Any] = {
                "role": role,
                "agent_code": agent_code,
                "agent_name": a.get("agent_name"),
                "user_id": user_id,
                "user_email": email,
            }
            token = create_token(payload, DEFAULT_AUTH_EXP_MINUTES)
            resp = JSONResponse({
                "status": "OK",
                "role": role,
                "agent_code": agent_code,
                "agent_name": a.get("agent_name"),
                "user_id": user_id,
                "user_email": email,
            })
            _set_cookie(resp, token)
            return resp
    finally:
        conn.close()

@router.post("/login/user")
def login_user(
    user_id: Optional[int] = Form(None),
    email: Optional[str] = Form(None),
    password: str = Form(...)
) -> JSONResponse:
    if not user_id and not email:
        raise HTTPException(status_code=400, detail="Provide user_id or email")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if user_id is not None:
                cur.execute("SELECT * FROM `users` WHERE `id`=%s", (user_id,))
            else:
                cur.execute("SELECT * FROM `users` WHERE `email`=%s", (email,))
            u = cur.fetchone() or None
            if not u:
                raise HTTPException(status_code=404, detail="User not found")
            if int(u.get("is_active") or 0) != 1:
                raise HTTPException(status_code=403, detail="User inactive")

            role = str(u.get("role") or "").lower()
            if role not in ("admin", "superuser"):
                raise HTTPException(status_code=403, detail="Role not permitted")

            ph = u.get("password_hash") or ""
            if not verify_password(password, ph):
                raise HTTPException(status_code=401, detail="Invalid credentials")

            # Audit: update last_login on successful admin/superuser login
            with conn.cursor() as cur2:
                cur2.execute("UPDATE `users` SET `last_login`=NOW() WHERE `id`=%s", (u["id"],))
                conn.commit()

            payload: Dict[str, Any] = {
                "role": role,
                "user_id": int(u["id"]),
                "user_email": u.get("email"),
                "agent_code": u.get("agent_code"),
                "agent_name": u.get("agent_name"),
            }
            token = create_token(payload, DEFAULT_AUTH_EXP_MINUTES)
            resp = JSONResponse({
                "status": "OK",
                "role": role,
                "user_id": int(u["id"]),
                "user_email": u.get("email"),
                "agent_code": u.get("agent_code"),
                "agent_name": u.get("agent_name"),
            })
            _set_cookie(resp, token)
            return resp
    finally:
        conn.close()

@router.post("/logout")
def logout_post() -> JSONResponse:
    resp = JSONResponse({"status": "OK", "message": "Logged out"})
    resp.delete_cookie(TOKEN_COOKIE_NAME, path="/")
    return resp

@router.get("/logout")
def logout_get() -> JSONResponse:
    resp = JSONResponse({"status": "OK", "message": "Logged out"})
    resp.delete_cookie(TOKEN_COOKIE_NAME, path="/")
    return resp

@router.get("/me")
def me(request: Request) -> Dict[str, Any]:
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if not token:
        return {"status": "ANON"}
    payload = decode_token(token)
    if not payload:
        return {"status": "INVALID"}
    return {"status": "OK", "identity": payload}
