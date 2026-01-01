
# src/api/agent_api.py
from __future__ import annotations
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.api import admin_reports as admin
from src.api.agent_missing import missing as agent_missing
from src.services.auth_service import decode_token, TOKEN_COOKIE_NAME


def _user_from_cookie(request: Request) -> Dict[str, Any] | None:
    tok = request.cookies.get(TOKEN_COOKIE_NAME)
    return decode_token(tok) if tok else None


def _agent_code_required(request: Request) -> str:
    """
    Extracts and validates agent_code from the cookie token.
    Returns a non-empty string or raises HTTPException.
    This also satisfies Pylance since the return type is guaranteed to be str.
    """
    u = _user_from_cookie(request)
    if not u:
        raise HTTPException(status_code=403, detail="Agent authentication required")
    role = str((u or {}).get("role") or "").lower()
    if role != "agent":
        raise HTTPException(status_code=403, detail="Agent role required")
    ac = (u or {}).get("agent_code")
    if not isinstance(ac, str) or not ac.strip():
        raise HTTPException(status_code=400, detail="agent_code must be a non-empty string")
    return ac


def require_agent(request: Request) -> Dict[str, Any]:
    """
    Router-level guard to enforce agent role. Kept for global dependency.
    """
    u = _user_from_cookie(request)
    role = str((u or {}).get("role") or "").lower()
    agent_code = (u or {}).get("agent_code")
    if not u or role != "agent" or not agent_code:
        raise HTTPException(status_code=403, detail="Agent authentication required")
    if not isinstance(agent_code, str) or not agent_code.strip():
        raise HTTPException(status_code=400, detail="agent_code must be a non-empty string")
    return u


# Global dependency enforces cookie identity for all Agent routes
router = APIRouter(prefix="/api/agent", tags=["Agent API"], dependencies=[Depends(require_agent)])


@router.get("/me")
def agent_me(request: Request) -> Dict[str, Any]:
    # Use helper to ensure type is correct and cookie is present
    agent_code = _agent_code_required(request)
    u = _user_from_cookie(request) or {}
    return {"status": "OK", "role": u.get("role"), "agent_code": agent_code}


# ---------- Statements ----------
@router.get("/statements")
def statements_for_agent(
    request: Request,
    upload_id: Optional[int] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    agent_code = _agent_code_required(request)
    return admin.list_statements(
        upload_id=upload_id,
        agent_code=agent_code,
        month_year=month_year,
        policy_no=policy_no,
        limit=limit,
        offset=offset,
    )


@router.get("/statements.csv")
def statements_csv_for_agent(
    request: Request,
    upload_id: Optional[int] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    # Delegates to admin CSV export (already aliases MONTH_YEAR -> month_year)
    agent_code = _agent_code_required(request)
    return admin.export_statements_csv(
        upload_id=upload_id,
        agent_code=agent_code,
        month_year=month_year,
        policy_no=policy_no,
        limit=limit,
        offset=offset,
    )


# ---------- Uploads ----------
@router.get("/uploads")
def uploads_for_agent(
    request: Request,
    doc_type: Optional[str] = None,
    month_year: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    agent_code = _agent_code_required(request)
    return admin.list_uploads(
        doc_type=doc_type,
        agent_code=agent_code,
        month_year=month_year,
        limit=limit,
        offset=offset,
    )


# ---------- Schedule ----------
@router.get("/schedule")
def schedule_for_agent(
    request: Request,
    upload_id: Optional[int] = None,
    month_year: Optional[str] = None,
    latest_only: Optional[int] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    agent_code = _agent_code_required(request)
    return admin.list_schedule(
        upload_id=upload_id,
        agent_code=agent_code,
        month_year=month_year,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )


# ---------- Terminated ----------
@router.get("/terminated")
def terminated_for_agent(
    request: Request,
    upload_id: Optional[int] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    agent_code = _agent_code_required(request)
    return admin.list_terminated(
        upload_id=upload_id,
        agent_code=agent_code,
        month_year=month_year,
        policy_no=policy_no,
        limit=limit,
        offset=offset,
    )


# ---------- Active policies ----------
@router.get("/active-policies")
def active_policies_for_agent(
    request: Request,
    month_year: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    agent_code = _agent_code_required(request)
    return admin.list_active_policies(
        agent_code=agent_code,
        month_year=month_year,
        status=status,
        limit=limit,
        offset=offset,
    )


# ---------- Missing ----------
@router.get("/missing")
def missing_for_agent(
    request: Request,
    month_year: str,
) -> Dict[str, Any]:
    agent_code = _agent_code_required(request)
    # Pylance-safe: agent_code is str
    return agent_missing(agent_code=agent_code, month_year=month_year)


# ---------- Uploads tracker ----------
@router.get("/uploads/tracker")
def uploads_tracker_for_agent(
    request: Request,
    months_back: int = 36,
) -> Dict[str, Any]:
    agent_code = _agent_code_required(request)
    # Pylance-safe: agent_code is str
    return admin.uploads_tracker(agent_code=agent_code, months_back=months_back)
