
# src/api/agent_missing.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List
import csv, io

from src.reports.monthly_reports import _fetch_missing_policies
from src.services.auth_service import decode_token, TOKEN_COOKIE_NAME

router = APIRouter(prefix="/api/agent", tags=["Agent Missing"])

def _require_access(request: Request, agent_code: str):
    """
    Gate access:
      - agents: only their own agent_code
      - admin/superuser: any agent_code
    """
    tok = request.cookies.get(TOKEN_COOKIE_NAME)
    u = decode_token(tok) if tok else None
    if not u:
        raise HTTPException(status_code=403, detail="Authentication required")
    role = str((u.get("role") or "")).lower()
    if role == "agent":
        if str(u.get("agent_code") or "") != str(agent_code):
            raise HTTPException(status_code=403, detail="Agents may only access their own data")
        return u
    if role in ("admin", "superuser"):
        return u
    raise HTTPException(status_code=403, detail="Role not permitted")

@router.get("/missing")
def missing(agent_code: str, month_year: str, user=Depends(_require_access)) -> Dict[str, Any]:
    try:
        raw = _fetch_missing_policies(agent_code, month_year)  # list of dicts
        items: List[Dict[str, Any]] = []
        for r in raw:
            items.append({
                "policy_no": r.get("policy_no"),
                "last_seen_month": r.get("last_seen_month"),
                "last_premium": r.get("last_premium"),
            })
        return {"count": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/missing.csv")
def missing_csv(agent_code: str, month_year: str, user=Depends(_require_access)):
    try:
        raw = _fetch_missing_policies(agent_code, month_year)
        rows: List[Dict[str, Any]] = []
        for r in raw:
            rows.append({
                "policy_no": r.get("policy_no"),
                "last_seen_month": r.get("last_seen_month"),
                "last_premium": r.get("last_premium"),
            })
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["policy_no","last_seen_month","last_premium"])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        buf.seek(0)
        return StreamingResponse(buf, media_type="text/csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
