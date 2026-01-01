
# src/api/superuser_api.py
from __future__ import annotations
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.api import admin_reports as admin
from src.api.agent_missing import missing as agent_missing
from src.services.auth_service import decode_token, TOKEN_COOKIE_NAME


def _user_from_cookie(request: Request) -> Dict[str, Any] | None:
    tok = request.cookies.get(TOKEN_COOKIE_NAME)
    return decode_token(tok) if tok else None


def _as_int(value: Any) -> Optional[int]:
    """Safely convert to int for values that may be Any | None."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    try:
        return int(value)
    except Exception:
        return None


def require_superuser(request: Request) -> Dict[str, Any]:
    u = _user_from_cookie(request)
    role = str((u or {}).get("role") or "").lower()
    user_id_val = (u or {}).get("user_id")
    if not u or role != "superuser" or user_id_val is None:
        raise HTTPException(status_code=403, detail="Superuser authentication required")
    if _as_int(user_id_val) is None:
        raise HTTPException(status_code=400, detail="user_id must be integer or string convertible to int")
    return u or {}

# Global dependency enforces cookie role for all routes in this router
router = APIRouter(prefix="/api/superuser", tags=["Superuser API"], dependencies=[Depends(require_superuser)])


@router.get("/me")
def superuser_me(request: Request) -> Dict[str, Any]:
    u = _user_from_cookie(request) or {}
    uid = _as_int(u.get("user_id"))
    return {"status": "OK", "role": u.get("role"), "user_id": uid}


# ---------- Statements ----------
@router.get("/statements")
def statements_for_superuser(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    return admin.list_statements(
        upload_id=upload_id,
        agent_code=agent_code,
        month_year=month_year,
        policy_no=policy_no,
        limit=limit,
        offset=offset,
    )


@router.get("/statements.csv")
def statements_csv_for_superuser(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    # Thin wrapper — delegates to admin CSV export which already aliases MONTH_YEAR -> month_year
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
def uploads_for_superuser(
    doc_type: Optional[str] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    return admin.list_uploads(
        doc_type=doc_type,
        agent_code=agent_code,
        month_year=month_year,
        limit=limit,
        offset=offset,
    )


# ---------- Schedule ----------
@router.get("/schedule")
def schedule_for_superuser(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    latest_only: Optional[int] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
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
def terminated_for_superuser(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
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
def active_policies_for_superuser(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    return admin.list_active_policies(
        agent_code=agent_code,
        month_year=month_year,
        status=status,
        limit=limit,
        offset=offset,
    )


# ---------- Missing ----------
@router.get("/missing")
def missing_for_superuser(agent_code: str, month_year: str) -> Dict[str, Any]:
    return agent_missing(agent_code=agent_code, month_year=month_year)


@router.get("/missing.csv")
def missing_csv_for_superuser(agent_code: str, month_year: str) -> StreamingResponse:
    res = missing_for_superuser(agent_code=agent_code, month_year=month_year)
    rows: List[Dict[str, Any]] = res.get("items", []) if isinstance(res, dict) else []
    return admin._dicts_to_csv_stream(rows, field_order=["policy_no", "last_seen_month", "last_premium"])


# ---------- Audit flags ----------
@router.get("/audit-flags")
def audit_flags_for_superuser(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    flag_type: Optional[str] = None,
    policy_no: Optional[str] = None,
    resolved: Optional[int] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    return admin.list_audit_flags(
        agent_code=agent_code,
        month_year=month_year,
        flag_type=flag_type,
        policy_no=policy_no,
        resolved=resolved,
        limit=limit,
        offset=offset,
    )


@router.get("/audit-flags.csv")
def audit_flags_csv_for_superuser(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    flag_type: Optional[str] = None,
    policy_no: Optional[str] = None,
    resolved: Optional[int] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    res = audit_flags_for_superuser(
        agent_code=agent_code,
        month_year=month_year,
        flag_type=flag_type,
        policy_no=policy_no,
        resolved=resolved,
        limit=limit,
        offset=offset,
    )
    rows: List[Dict[str, Any]] = res.get("items", []) if isinstance(res, dict) else []
    return admin._dicts_to_csv_stream(rows, field_order=[
        "id","agent_code","policy_no","month_year","flag_type","severity",
        "flag_detail","expected_value","actual_value","created_at",
        "resolved","resolved_by","resolved_at","resolution_notes"
    ])


# ---------- Uploads tracker ----------
@router.get("/uploads/tracker")
def uploads_tracker_for_superuser(agent_code: str, months_back: int = 36) -> Dict[str, Any]:
    return admin.uploads_tracker(agent_code=agent_code, months_back=months_back)


@router.get("/uploads/tracker.csv")
def uploads_tracker_csv_for_superuser(agent_code: str, months_back: int = 36) -> StreamingResponse:
    res = uploads_tracker_for_superuser(agent_code=agent_code, months_back=months_back)
    rows = res.get("items", []) if isinstance(res, dict) else []
    csv_rows: List[Dict[str, Any]] = []
    for r in rows:
        csv_rows.append({
            "month_year": r.get("month_year"),
            "statement": 1 if r.get("statement") else 0,
            "schedule": 1 if r.get("schedule") else 0,
            "statement_upload_id": r.get("statement_upload_id"),
            "schedule_upload_id": r.get("schedule_upload_id"),
        })
    return admin._dicts_to_csv_stream(csv_rows, field_order=[
        "month_year","statement","schedule","statement_upload_id","schedule_upload_id"
    ])
