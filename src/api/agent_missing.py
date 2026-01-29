
# src/api/agent_missing.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional, Tuple
import csv, io
from src.reports.monthly_reports import _fetch_missing_policies
from src.services.auth_service import decode_token, TOKEN_COOKIE_NAME
from src.ingestion.db import get_conn

router = APIRouter(prefix="/api/agent", tags=["Agent Missing (admin/superuser)"])

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

def _split_holder(holder: Optional[str]) -> Tuple[str, str]:
    s = str(holder or "").strip()
    if not s:
        return "", ""
    parts = s.split()
    surname = parts[0]
    other = " ".join(parts[1:]) if len(parts) > 1 else ""
    return surname, other

def _fallback_active_row(policy_no: Optional[str]) -> Dict[str, Any]:
    """
    When _fetch_missing_policies doesn't provide holder/com_rate, try active_policies.
    """
    if not policy_no:
        return {}
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT `holder_name`,`last_com_rate` FROM `active_policies` WHERE `policy_no`=%s LIMIT 1",
                (policy_no,),
            )
            r = cur.fetchone() or {}
            return r
    finally:
        conn.close()

# NOTE: separate path to avoid colliding with /api/agent/missing
@router.get("/missing/by-agent")
def missing_by_agent(request: Request, agent_code: str, month_year: str) -> Dict[str, Any]:
    # Enforce access: agent -> self; admin/superuser -> any
    _require_access(request, agent_code)
    try:
        raw = _fetch_missing_policies(agent_code, month_year)  # list of dicts
        items: List[Dict[str, Any]] = []
        for r in raw:
            policy_no = r.get("policy_no")
            holder_name = r.get("holder_name")
            last_com_rate = r.get("last_com_rate")

            if not (holder_name and last_com_rate is not None):
                fb = _fallback_active_row(policy_no)
                holder_name = holder_name or fb.get("holder_name")
                last_com_rate = last_com_rate if last_com_rate is not None else fb.get("last_com_rate")

            sur, other = _split_holder(holder_name)
            items.append(
                {
                    "policy_no": policy_no,
                    "holder_name": holder_name,
                    "holder_surname": sur,
                    "other_name": other,
                    "last_seen_month": r.get("last_seen_month"),
                    "last_premium": r.get("last_premium"),
                    "last_com_rate": last_com_rate,
                }
            )
        return {"count": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/missing/by-agent.csv")
def missing_by_agent_csv(request: Request, agent_code: str, month_year: str):
    _require_access(request, agent_code)
    try:
        res = missing_by_agent(request=request, agent_code=agent_code, month_year=month_year)
        rows: List[Dict[str, Any]] = res.get("items", []) if isinstance(res, dict) else []
        buf = io.StringIO()
        headers = ["policy_no","holder_name","holder_surname","other_name","last_seen_month","last_premium","last_com_rate"]
        writer = csv.DictWriter(buf, fieldnames=headers)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
        buf.seek(0)
        return StreamingResponse(buf, media_type="text/csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
