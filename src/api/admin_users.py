
# src/api/admin_users.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.ingestion.db import get_conn
from src.services.auth_service import hash_password
from src.services.roles import require_role
from src.services.security import require_csrf

router = APIRouter(
    prefix="/api/admin/users",
    tags=["Admin Users"],
)

# ----- Annotated aliases -----
AdminOnly = Annotated[Dict[str, Any], Depends(require_role("admin"))]
CSRF = Annotated[None, Depends(require_csrf)]


class UserCreate(BaseModel):
    email: str
    role: str  # 'admin' | 'superuser' | 'agent'
    agent_code: Optional[str] = None
    is_active: int = 1
    password: str


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None
    agent_code: Optional[str] = None
    is_active: Optional[int] = None
    password: Optional[str] = None


@router.get("", summary="List users")
def list_users(limit: int = 200, offset: int = 0, _current_user: AdminOnly = Depends()) -> Dict[str, Any]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT `id`,`email`,`role`,`agent_code`,`is_active`,`last_login`
                FROM `users`
                ORDER BY `id` DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            items = list(cur.fetchall() or [])
        return {"count": len(items), "items": items}
    finally:
        conn.close()


@router.post("", summary="Create user")
def create_user(payload: UserCreate, _csrf_ok: CSRF = Depends(), _current_user: AdminOnly = Depends()) -> Dict[str, Any]:
    if not payload.password or not str(payload.password).strip():
        raise HTTPException(status_code=400, detail="Password is required when creating a user")
    ac_norm: Optional[str] = None
    if payload.agent_code and str(payload.agent_code).strip():
        ac_norm = str(payload.agent_code).strip()
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if str(payload.role).lower() == "agent":
                if not ac_norm:
                    raise HTTPException(status_code=400, detail="agent_code is required when role is 'agent'")
                cur.execute("SELECT 1 FROM `agents` WHERE `agent_code`=%s", (ac_norm,))
                exists = cur.fetchone()
                if not exists:
                    cur.execute(
                        """
                        INSERT INTO `agents`
                        (`agent_code`,`agent_name`,`is_active`,`created_at`,`updated_at`)
                        VALUES (%s,%s,%s,NOW(),NOW())
                        """,
                        (ac_norm, None, 1),
                    )
            pwd_hash = hash_password(payload.password)
            cur.execute(
                """
                INSERT INTO `users`
                (`email`,`role`,`agent_code`,`is_active`,`password_hash`)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (
                    str(payload.email),
                    payload.role,
                    ac_norm,
                    int(bool(payload.is_active)),
                    pwd_hash,
                ),
            )
            new_id = cur.lastrowid
        conn.commit()
        return {"status": "SUCCESS", "id": new_id}
    finally:
        conn.close()


@router.put("/{user_id}", summary="Update user")
def update_user(user_id: int, payload: UserUpdate, _csrf_ok: CSRF = Depends(), _current_user: AdminOnly = Depends()) -> Dict[str, Any]:
    conn = get_conn()
    try:
        sets: List[str] = []
        vals: List[Any] = []
        if payload.email is not None:
            sets.append("`email`=%s")
            vals.append(str(payload.email))
        if payload.role is not None:
            sets.append("`role`=%s")
            vals.append(payload.role)
        if payload.agent_code is not None:
            ac_norm: Optional[str] = None
            if str(payload.agent_code).strip():
                ac_norm = str(payload.agent_code).strip()
            sets.append("`agent_code`=%s")
            vals.append(ac_norm)
        if payload.is_active is not None:
            sets.append("`is_active`=%s")
            vals.append(int(bool(payload.is_active)))
        if payload.password is not None:
            sets.append("`password_hash`=%s")
            vals.append(hash_password(payload.password))
        if not sets:
            return {"status": "NOOP", "id": user_id}
        sql = f"UPDATE `users` SET {', '.join(sets)} WHERE `id`=%s"
        vals.append(user_id)
        with conn.cursor() as cur:
            cur.execute(sql, tuple(vals))
        conn.commit()
        return {"status": "SUCCESS", "id": user_id}
    finally:
        conn.close()


@router.delete("/{user_id}", summary="Deactivate user")
def deactivate_user(user_id: int, _csrf_ok: CSRF = Depends(), _current_user: AdminOnly = Depends()) -> Dict[str, Any]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE `users` SET `is_active`=0 WHERE `id`=%s", (user_id,))
        conn.commit()
        return {"status": "SUCCESS", "id": user_id}
    finally:
        conn.close()


@router.post("/{user_id}/password", summary="Set password")
def set_password(user_id: int, payload: UserUpdate, _csrf_ok: CSRF = Depends(), _current_user: AdminOnly = Depends()) -> Dict[str, Any]:
    if not payload.password:
        raise HTTPException(status_code=400, detail="Password is required")
    conn = get_conn()
    try:
        hashed = hash_password(payload.password)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE `users` SET `password_hash`=%s WHERE `id`=%s",
                (hashed, user_id),
            )
        conn.commit()
        return {"status": "SUCCESS", "id": user_id}
    finally:
        conn.close()
