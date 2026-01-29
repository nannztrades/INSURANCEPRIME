
# src/api/admin_agents.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.ingestion.db import get_conn
from src.services.roles import require_role
from src.services.security import require_csrf

router = APIRouter(
    prefix="/api/admin/agents",
    tags=["Admin Agents"],
)

# ----- Annotated aliases -----
AdminOrSuper = Annotated[Dict[str, Any], Depends(require_role("admin", "superuser"))]
CSRF = Annotated[None, Depends(require_csrf)]


class AgentCreate(BaseModel):
    agent_code: str
    agent_name: Optional[str] = None
    license_number: Optional[str] = None
    agent_provided_earliest_date: Optional[str] = None
    is_active: int = 1


class AgentUpdate(BaseModel):
    agent_name: Optional[str] = None
    license_number: Optional[str] = None
    agent_provided_earliest_date: Optional[str] = None
    is_active: Optional[int] = None


@router.get("")
def list_agents(limit: int = 200, offset: int = 0, _current_user: AdminOrSuper = Depends()) -> Dict[str, Any]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT `agent_code`,`agent_name`,`license_number`,
                       `agent_provided_earliest_date`,`is_active`,
                       `created_at`,`updated_at`
                FROM `agents`
                ORDER BY `agent_code` ASC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            items = list(cur.fetchall() or [])
        return {"count": len(items), "items": items}
    finally:
        conn.close()


@router.post("")
def create_agent(payload: AgentCreate, _csrf_ok: CSRF = Depends(), _current_user: AdminOrSuper = Depends()) -> Dict[str, Any]:
    if not payload.agent_code or not str(payload.agent_code).strip():
        raise HTTPException(status_code=400, detail="agent_code is required")
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Upsert-like behavior: update if exists, else insert
            cur.execute(
                "SELECT 1 FROM `agents` WHERE `agent_code`=%s",
                (payload.agent_code,),
            )
            if cur.fetchone():
                cur.execute(
                    """
                    UPDATE `agents`
                    SET `agent_name`=%s,
                        `license_number`=%s,
                        `agent_provided_earliest_date`=%s,
                        `is_active`=%s,
                        `updated_at`=NOW()
                    WHERE `agent_code`=%s
                    """,
                    (
                        payload.agent_name,
                        payload.license_number,
                        payload.agent_provided_earliest_date,
                        int(bool(payload.is_active)),
                        payload.agent_code,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO `agents`
                    (`agent_code`,`agent_name`,`license_number`,
                     `agent_provided_earliest_date`,`is_active`,`created_at`,`updated_at`)
                    VALUES (%s,%s,%s,%s,%s,NOW(),NOW())
                    """,
                    (
                        payload.agent_code,
                        payload.agent_name,
                        payload.license_number,
                        payload.agent_provided_earliest_date,
                        int(bool(payload.is_active)),
                    ),
                )
        conn.commit()
        return {"status": "SUCCESS", "agent_code": payload.agent_code}
    finally:
        conn.close()


@router.put("/{agent_code}")
def update_agent(agent_code: str, payload: AgentUpdate, _csrf_ok: CSRF = Depends(), _current_user: AdminOrSuper = Depends()) -> Dict[str, Any]:
    sets: List[str] = []
    vals: List[Any] = []
    if payload.agent_name is not None:
        sets.append("`agent_name`=%s")
        vals.append(payload.agent_name)
    if payload.license_number is not None:
        sets.append("`license_number`=%s")
        vals.append(payload.license_number)
    if payload.agent_provided_earliest_date is not None:
        sets.append("`agent_provided_earliest_date`=%s")
        vals.append(payload.agent_provided_earliest_date)
    if payload.is_active is not None:
        sets.append("`is_active`=%s")
        vals.append(int(bool(payload.is_active)))
    if not sets:
        return {"status": "NOOP", "agent_code": agent_code}
    sql = f"UPDATE `agents` SET {', '.join(sets)}, `updated_at`=NOW() WHERE `agent_code`=%s"
    vals.append(agent_code)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(vals))
        conn.commit()
        return {"status": "SUCCESS", "agent_code": agent_code}
    finally:
        conn.close()


@router.delete("/{agent_code}")
def deactivate_agent(agent_code: str, _csrf_ok: CSRF = Depends(), _current_user: AdminOrSuper = Depends()) -> Dict[str, Any]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE `agents` SET `is_active`=0, `updated_at`=NOW() WHERE `agent_code`=%s",
                (agent_code,),
            )
        conn.commit()
        return {"status": "SUCCESS", "agent_code": agent_code}
    finally:
        conn.close()
