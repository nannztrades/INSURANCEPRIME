
# src/api/agent_api.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from datetime import datetime
import re

from src.ingestion.db import get_conn
from src.services.roles import require_agent_user
from src.utils.csv_io import dicts_to_csv_stream
from src.reports.monthly_reports import _fetch_missing_policies  # business helper (non-route)

router = APIRouter(
    prefix="/api/agent",
    tags=["Agent API"],
    dependencies=[Depends(require_agent_user)],
)

# ──────────────────────────────────────────────────────────────────────────────
# Local helpers
# ──────────────────────────────────────────────────────────────────────────────

def _agent_code_from_user(user: Dict[str, Any]) -> str:
    ac = user.get("agent_code")
    if not isinstance(ac, str) or not ac.strip():
        raise HTTPException(status_code=400, detail="agent_code must be a non-empty string")
    return ac.strip()


def _split_holder(holder: Optional[str]) -> Tuple[str, str]:
    s = str(holder or "").strip()
    if not s:
        return "", ""
    parts = s.split()
    surname = parts[0]
    other = " ".join(parts[1:]) if len(parts) > 1 else ""
    return surname, other


def _norm_yyyy_mm(val: Optional[str]) -> Optional[str]:
    """
    Normalize common month labels to canonical 'YYYY-MM'.
    Accepts 'YYYY-MM', 'YYYY/M', 'YYYY/MM', 'Mon YYYY', 'Month YYYY', and strips 'COM_'.
    """
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None
    if s.startswith("COM_"):
        s = s[4:].strip()

    # Strict YYYY-MM
    if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", s):
        return s

    # YYYY/M or YYYY/MM
    m = re.fullmatch(r"^\s*(\d{4})[/-](\d{1,2})\s*$", s)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return f"{y:04d}-{mo:02d}"

    # Mon YYYY / Month YYYY
    for fmt in ("%b %Y", "%B %Y", "%Y %b", "%Y %B"):
        try:
            dt = datetime.strptime(s, fmt)
            return f"{dt.year:04d}-{dt.month:02d}"
        except Exception:
            pass

    # Last resort: replace '/' with '-' and re-check strict
    s2 = s.replace("/", "-")
    if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", s2):
        return s2
    return s2 or None


# ──────────────────────────────────────────────────────────────────────────────
# Local DB accessors (no calls to admin routes)
# ──────────────────────────────────────────────────────────────────────────────

def _list_statements_items(
    agent_code: str,
    upload_id: Optional[int],
    month_year: Optional[str],
    policy_no: Optional[str],
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        sql = """
            SELECT `statement_id`,`upload_id`,`agent_code`,`policy_no`,`holder`,
                   `policy_type`,`pay_date`,`receipt_no`,`premium`,`com_rate`,
                   `com_amt`,`inception`,`MONTH_YEAR` AS `month_year`,`AGENT_LICENSE_NUMBER`
            FROM `statement`
            WHERE `agent_code`=%s
        """
        params: List[Any] = [agent_code]
        if upload_id is not None:
            sql += " AND `upload_id`=%s"; params.append(upload_id)
        if month_year:
            sql += " AND `MONTH_YEAR`=%s"; params.append(month_year)
        if policy_no:
            sql += " AND `policy_no`=%s"; params.append(policy_no)
        sql += " ORDER BY `statement_id` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            rows = list(cur.fetchall() or [])
            for r in rows:
                sur, other = _split_holder(r.get("holder"))
                r["holder_surname"] = sur
                r["other_name"] = other
            return rows
    finally:
        conn.close()


def _list_uploads_items(
    agent_code: str,
    doc_type: Optional[str],
    month_year: Optional[str],
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        sql = """
            SELECT `UploadID`,`agent_code`,`AgentName`,`doc_type`,`FileName`,`UploadTimestamp`,
                   `month_year`,`is_active`
            FROM `uploads` WHERE `agent_code`=%s
        """
        params: List[Any] = [agent_code]
        if doc_type:
            sql += " AND `doc_type`=%s"; params.append(doc_type)
        if month_year:
            sql += " AND `month_year`=%s"; params.append(month_year)
        sql += " ORDER BY `UploadID` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return list(cur.fetchall() or [])
    finally:
        conn.close()


def _list_schedule_items(
    agent_code: str,
    upload_id: Optional[int],
    month_year: Optional[str],
    latest_only: Optional[str],
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Default to latest per month when agent_code present and latest_only unset
            eff_latest = 1 if (latest_only is None and agent_code) else 0
            if latest_only is not None:
                val = str(latest_only).strip()
                eff_latest = 0 if val == "" else int(bool(int(val)))

            if eff_latest:
                sql = """
                    SELECT sc.`month_year`, sc.`schedule_id`, sc.`upload_id`, sc.`agent_code`, sc.`agent_name`,
                           sc.`commission_batch_code`, sc.`total_premiums`, sc.`income`,
                           sc.`total_deductions`, sc.`net_commission`,
                           sc.`siclase`, sc.`premium_deduction`, sc.`pensions`, sc.`welfareko`
                    FROM `schedule` sc
                    JOIN (
                        SELECT `month_year`, MAX(`upload_id`) AS max_upload
                        FROM `schedule`
                        WHERE `agent_code`=%s
                        GROUP BY `month_year`
                    ) t ON sc.`month_year`=t.`month_year` AND sc.`upload_id`=t.`max_upload`
                    ORDER BY STR_TO_DATE(CONCAT(sc.`month_year`,'-01'), '%Y-%m-%d') DESC
                    LIMIT %s OFFSET %s
                """
                cur.execute(sql, (agent_code, limit, offset))
                return list(cur.fetchall() or [])

            base = """
                SELECT `month_year`,`schedule_id`,`upload_id`,`agent_code`,`agent_name`,
                       `commission_batch_code`,`total_premiums`,`income`,
                       `total_deductions`,`net_commission`,
                       `siclase`,`premium_deduction`,`pensions`,`welfareko`
                FROM `schedule`
                WHERE `agent_code`=%s
            """
            params: List[Any] = [agent_code]
            if upload_id is not None:
                base += " AND `upload_id`=%s"; params.append(upload_id)
            if month_year:
                base += " AND `month_year`=%s"; params.append(month_year)
            base += " ORDER BY `schedule_id` DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            cur.execute(base, tuple(params))
            return list(cur.fetchall() or [])
    finally:
        conn.close()


def _list_terminated_items(
    agent_code: str,
    upload_id: Optional[int],
    month_year: Optional[str],
    policy_no: Optional[str],
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        base = """
            SELECT `terminated_id`,`upload_id`,`agent_code`,`policy_no`,`holder`,
                   `policy_type`,`premium`,`status`,`reason`,`month_year`,`termination_date`
            FROM `terminated`
            WHERE `agent_code`=%s
        """
        params: List[Any] = [agent_code]
        if upload_id is not None:
            base += " AND `upload_id`=%s"; params.append(upload_id)
        if month_year:
            base += " AND `month_year`=%s"; params.append(month_year)
        if policy_no:
            base += " AND `policy_no`=%s"; params.append(policy_no)
        base += " ORDER BY `terminated_id` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            rows = list(cur.fetchall() or [])
            for r in rows:
                sur, other = _split_holder(r.get("holder"))
                r["holder_surname"] = sur
                r["other_name"] = other
            return rows
    finally:
        conn.close()


def _list_active_policies_items(
    agent_code: str,
    month_year: Optional[str],
    status: Optional[str],
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        base = """
            SELECT `id`,`agent_code`,`policy_no`,`policy_type`,`holder_name`,
                   `inception_date`,`first_seen_date`,`last_seen_date`,`last_seen_month_year`,
                   `last_premium`,`last_com_rate`,`status`,`consecutive_missing_months`
            FROM `active_policies`
            WHERE `agent_code`=%s
        """
        params: List[Any] = [agent_code]
        if month_year:
            base += " AND `last_seen_month_year`=%s"; params.append(month_year)
        if status:
            base += " AND `status`=%s"; params.append(status)
        base += " ORDER BY `id` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            return list(cur.fetchall() or [])
    finally:
        conn.close()


def _uploads_tracker_items(agent_code: str, months_back: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            sql = """
                SELECT m.`month_year`,
                GREATEST(
                    IFNULL((SELECT MAX(CASE WHEN u.`doc_type`='STATEMENT' AND u.`is_active`=1 THEN 1 ELSE 0 END)
                            FROM `uploads` u
                            WHERE u.`agent_code`=%s AND u.`month_year`=m.`month_year`), 0),
                    IFNULL((SELECT MAX(1) FROM `statement` s
                            WHERE s.`agent_code`=%s AND s.`MONTH_YEAR`=m.`month_year`), 0)
                ) AS `statement_present`,
                GREATEST(
                    IFNULL((SELECT MAX(CASE WHEN u.`doc_type`='SCHEDULE' AND u.`is_active`=1 THEN 1 ELSE 0 END)
                            FROM `uploads` u
                            WHERE u.`agent_code`=%s AND u.`month_year`=m.`month_year`), 0),
                    IFNULL((SELECT MAX(1) FROM `schedule` sc
                            WHERE sc.`agent_code`=%s AND sc.`month_year`=m.`month_year`), 0)
                ) AS `schedule_present`,
                GREATEST(
                    IFNULL((SELECT MAX(CASE WHEN u.`doc_type`='TERMINATED' AND u.`is_active`=1 THEN 1 ELSE 0 END)
                            FROM `uploads` u
                            WHERE u.`agent_code`=%s AND u.`month_year`=m.`month_year`), 0),
                    IFNULL((SELECT MAX(1) FROM `terminated` t
                            WHERE t.`agent_code`=%s AND t.`month_year`=m.`month_year`), 0)
                ) AS `terminated_present`,
                (SELECT MAX(u.`UploadID`) FROM `uploads` u
                 WHERE u.`agent_code`=%s AND u.`month_year`=m.`month_year` AND u.`doc_type`='STATEMENT') AS `statement_upload_id`,
                (SELECT MAX(u.`UploadID`) FROM `uploads` u
                 WHERE u.`agent_code`=%s AND u.`month_year`=m.`month_year` AND u.`doc_type`='SCHEDULE') AS `schedule_upload_id`,
                (SELECT MAX(u.`UploadID`) FROM `uploads` u
                 WHERE u.`agent_code`=%s AND u.`month_year`=m.`month_year` AND u.`doc_type`='TERMINATED') AS `terminated_upload_id`
                FROM (
                  SELECT DISTINCT u.`month_year`
                  FROM `uploads` u
                  WHERE u.`agent_code`=%s AND u.`month_year` IS NOT NULL
                  UNION
                  SELECT DISTINCT s.`MONTH_YEAR` AS `month_year`
                  FROM `statement` s
                  WHERE s.`agent_code`=%s AND s.`MONTH_YEAR` IS NOT NULL
                  UNION
                  SELECT DISTINCT sc.`month_year`
                  FROM `schedule` sc
                  WHERE sc.`agent_code`=%s AND sc.`month_year` IS NOT NULL
                  UNION
                  SELECT DISTINCT t.`month_year`
                  FROM `terminated` t
                  WHERE t.`agent_code`=%s AND t.`month_year` IS NOT NULL
                ) AS m
                ORDER BY STR_TO_DATE(CONCAT(m.`month_year`,'-01'), '%Y-%m-%d') DESC
                LIMIT %s
            """
            params = [
                agent_code, agent_code,
                agent_code, agent_code,
                agent_code, agent_code,
                agent_code,
                agent_code,
                agent_code,
                agent_code,
                agent_code,
                months_back,
            ]
            cur.execute(sql, tuple(params))
            return list(cur.fetchall() or [])
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Routes (decoupled, with input normalization where applicable)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/me")
def agent_me(current_user: Dict[str, Any] = Depends(require_agent_user)) -> Dict[str, Any]:
    agent_code = _agent_code_from_user(current_user)
    return {"status": "OK", "role": current_user.get("role"), "agent_code": agent_code}


@router.get("/statements")
def statements_for_agent(
    request: Request,
    upload_id: Optional[int] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_agent_user),
) -> Dict[str, Any]:
    agent_code = _agent_code_from_user(current_user)
    my = _norm_yyyy_mm(month_year)
    items = _list_statements_items(agent_code, upload_id, my, policy_no, limit, offset)
    return {"count": len(items), "items": items}


@router.get("/statements.csv")
def statements_csv_for_agent(
    request: Request,
    upload_id: Optional[int] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_agent_user),
) -> StreamingResponse:
    agent_code = _agent_code_from_user(current_user)
    my = _norm_yyyy_mm(month_year)
    items = _list_statements_items(agent_code, upload_id, my, policy_no, limit, offset)
    return dicts_to_csv_stream(items, filename="statements.csv")


@router.get("/uploads")
def uploads_for_agent(
    request: Request,
    doc_type: Optional[str] = None,
    month_year: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_agent_user),
) -> Dict[str, Any]:
    agent_code = _agent_code_from_user(current_user)
    my = _norm_yyyy_mm(month_year)
    items = _list_uploads_items(agent_code, doc_type, my, limit, offset)
    return {"count": len(items), "items": items}


@router.get("/schedule")
def schedule_for_agent(
    request: Request,
    upload_id: Optional[int] = None,
    month_year: Optional[str] = None,
    latest_only: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_agent_user),
) -> Dict[str, Any]:
    agent_code = _agent_code_from_user(current_user)
    my = _norm_yyyy_mm(month_year)
    items = _list_schedule_items(agent_code, upload_id, my, latest_only, limit, offset)
    return {"count": len(items), "items": items}


@router.get("/schedule.csv")
def schedule_csv_for_agent(
    request: Request,
    upload_id: Optional[int] = None,
    month_year: Optional[str] = None,
    latest_only: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_agent_user),
) -> StreamingResponse:
    agent_code = _agent_code_from_user(current_user)
    my = _norm_yyyy_mm(month_year)
    items = _list_schedule_items(agent_code, upload_id, my, latest_only, limit, offset)
    return dicts_to_csv_stream(items, filename="schedule.csv")


@router.get("/terminated")
def terminated_for_agent(
    request: Request,
    upload_id: Optional[int] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_agent_user),
) -> Dict[str, Any]:
    agent_code = _agent_code_from_user(current_user)
    my = _norm_yyyy_mm(month_year)
    items = _list_terminated_items(agent_code, upload_id, my, policy_no, limit, offset)
    return {"count": len(items), "items": items}


@router.get("/terminated.csv")
def terminated_csv_for_agent(
    request: Request,
    upload_id: Optional[int] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_agent_user),
) -> StreamingResponse:
    agent_code = _agent_code_from_user(current_user)
    my = _norm_yyyy_mm(month_year)
    items = _list_terminated_items(agent_code, upload_id, my, policy_no, limit, offset)
    return dicts_to_csv_stream(items, filename="terminated.csv")


@router.get("/active-policies")
def active_policies_for_agent(
    request: Request,
    month_year: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(require_agent_user),
) -> Dict[str, Any]:
    agent_code = _agent_code_from_user(current_user)
    my = _norm_yyyy_mm(month_year)
    items = _list_active_policies_items(agent_code, my, status, limit, offset)
    return {"count": len(items), "items": items}


@router.get("/missing")
def missing_for_agent(
    request: Request,
    month_year: str,
    current_user: Dict[str, Any] = Depends(require_agent_user),
) -> Dict[str, Any]:
    agent_code = _agent_code_from_user(current_user)
    my = _norm_yyyy_mm(month_year) or month_year
    try:
        raw = _fetch_missing_policies(agent_code, my) or []
        items: List[Dict[str, Any]] = []
        for r in raw:
            items.append(
                {
                    "policy_no": r.get("policy_no"),
                    "last_seen_month": r.get("last_seen_month"),
                    "last_premium": r.get("last_premium"),
                }
            )
        return {"count": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/uploads/tracker")
def uploads_tracker_for_agent(
    request: Request,
    months_back: int = 36,
    current_user: Dict[str, Any] = Depends(require_agent_user),
) -> Dict[str, Any]:
    agent_code = _agent_code_from_user(current_user)
    items = _uploads_tracker_items(agent_code=agent_code, months_back=months_back)
    return {"count": len(items), "items": items}
