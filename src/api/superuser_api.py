
# src/api/superuser_api.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import csv
import io
import re
from datetime import datetime

from src.ingestion.db import get_conn
from src.services.roles import require_role
# Keep only the business function that exists in your repo
from src.reports.monthly_reports import _fetch_missing_policies  # non-route logic

# ------------------------------------------------------------------------------
# Router-level guard: SUPERUSER only (no handler→handler coupling)
# ------------------------------------------------------------------------------
router = APIRouter(
    prefix="/api/superuser",
    tags=["Superuser API"],
    dependencies=[Depends(require_role("superuser"))],
)

# ------------------------------------------------------------------------------
# Local helpers (no imports from other route modules)
# ------------------------------------------------------------------------------

def _dicts_to_csv_stream(
    rows: List[Dict[str, Any]],
    field_order: Optional[List[str]] = None,
    filename: Optional[str] = None,
) -> StreamingResponse:
    buf = io.StringIO()
    if rows:
        if field_order is None:
            field_order = list(rows[0].keys())
        writer = csv.DictWriter(buf, fieldnames=field_order, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    buf.seek(0)
    headers = {"Content-Type": "text/csv; charset=utf-8"}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return StreamingResponse(buf, headers=headers)


_YYYY_MM_RE = re.compile(r"^\s*(\d{4})[-/](\d{1,2})\s*$")

def _norm_yyyy_mm(val: Optional[str]) -> Optional[str]:
    """
    Normalize common month labels to canonical 'YYYY-MM'.

    Accepts:
      - 'YYYY-MM' / 'YYYY/M' / 'YYYY/MM'
      - 'Mon YYYY'  (e.g., 'Jun 2025')
      - 'Month YYYY' (e.g., 'June 2025')
      - Strings prefixed with 'COM_' (prefix removed)
      - Permissive spaces

    Returns:
      - 'YYYY-MM' (zero-padded month) or None if input is empty.
    """
    if not val:
        return None
    s = str(val).strip()
    if not s:
        return None

    # Remove known prefixes
    if s.startswith("COM_"):
        s = s[4:].strip()

    # Quick pass: YYYY-MM (strict)
    if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", s):
        return s

    # YYYY-M or YYYY/MM or YYYY/M -> format to YYYY-MM
    m = _YYYY_MM_RE.match(s.replace("\\", "/"))
    if m:
        year, month = m.groups()
        try:
            month_i = int(month)
            if 1 <= month_i <= 12:
                return f"{year}-{month_i:02d}"
        except Exception:
            pass  # fallthrough

    # 'Jun 2025' / 'June 2025'
    for fmt in ("%b %Y", "%B %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return f"{dt.year}-{dt.month:02d}"
        except Exception:
            continue

    # 'YYYY Mon' / 'YYYY Month' (less common)
    for fmt in ("%Y %b", "%Y %B"):
        try:
            dt = datetime.strptime(s, fmt)
            return f"{dt.year}-{dt.month:02d}"
        except Exception:
            continue

    # As a last resort: collapse multiple spaces, replace '/' with '-', and attempt strict match again
    s2 = re.sub(r"\s+", " ", s).replace("/", "-").strip()
    if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", s2):
        return s2

    # Unknown; return original trimmed
    return s2 or None


def _split_holder(holder: Optional[str]) -> Tuple[str, str]:
    s = str(holder or "").strip()
    if not s:
        return "", ""
    parts = s.split()
    surname = parts[0]
    other = " ".join(parts[1:]) if len(parts) > 1 else ""
    return surname, other


# ------------------------------------------------------------------------------
# DB helper functions (mirror admin logic but local to avoid route→route calls)
# ------------------------------------------------------------------------------

def _list_uploads_items(
    doc_type: Optional[str],
    agent_code: Optional[str],
    month_year: Optional[str],
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        sql = """
            SELECT `UploadID`,`agent_code`,`AgentName`,`doc_type`,`FileName`,`UploadTimestamp`,
                   `month_year`,`is_active`
            FROM `uploads` WHERE 1=1
        """
        params: List[Any] = []
        if doc_type:
            sql += " AND `doc_type`=%s"; params.append(doc_type)
        if agent_code:
            sql += " AND `agent_code`=%s"; params.append(agent_code)
        if month_year:
            sql += " AND `month_year`=%s"; params.append(month_year)
        sql += " ORDER BY `UploadID` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            return list(cur.fetchall() or [])
    finally:
        conn.close()


def _uploads_tracker_items(agent_code: str, months_back: int) -> List[Dict[str, Any]]:
    """
    Canonical tracker using YYYY-MM ordering.
    """
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


def _list_statements_items(
    upload_id: Optional[int],
    agent_code: Optional[str],
    month_year: Optional[str],
    policy_no: Optional[str],
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        base = """
            SELECT `statement_id`,`upload_id`,`agent_code`,`policy_no`,`holder`,
                   `policy_type`,`pay_date`,`receipt_no`,`premium`,`com_rate`,
                   `com_amt`,`inception`,`MONTH_YEAR` AS `month_year`,`AGENT_LICENSE_NUMBER`
            FROM `statement` WHERE 1=1
        """
        params: List[Any] = []
        if upload_id is not None:
            base += " AND `upload_id`=%s"; params.append(upload_id)
        if agent_code:
            base += " AND `agent_code`=%s"; params.append(agent_code)
        if month_year:
            base += " AND `MONTH_YEAR`=%s"; params.append(month_year)
        if policy_no:
            base += " AND `policy_no`=%s"; params.append(policy_no)
        base += " ORDER BY `statement_id` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            items: List[Dict[str, Any]] = list(cur.fetchall() or [])
            for it in items:
                sur, other = _split_holder(it.get("holder"))
                it["holder_surname"] = sur
                it["other_name"] = other
            return items
    finally:
        conn.close()


def _list_schedule_items(
    upload_id: Optional[int],
    agent_code: Optional[str],
    month_year: Optional[str],
    latest_only: Optional[str],
    limit: int,
    offset: int,
) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            eff_latest = 0
            if latest_only is None and agent_code:
                eff_latest = 1
            elif latest_only is not None:
                val = str(latest_only).strip()
                eff_latest = 0 if val == "" else int(bool(int(val)))

            if eff_latest and agent_code:
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
                FROM `schedule` WHERE 1=1
            """
            params: List[Any] = []
            if upload_id is not None:
                base += " AND `upload_id`=%s"; params.append(upload_id)
            if agent_code:
                base += " AND `agent_code`=%s"; params.append(agent_code)
            if month_year:
                base += " AND `month_year`=%s"; params.append(month_year)
            base += " ORDER BY `schedule_id` DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            cur.execute(base, tuple(params))
            return list(cur.fetchall() or [])
    finally:
        conn.close()


def _list_terminated_items(
    upload_id: Optional[int],
    agent_code: Optional[str],
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
            FROM `terminated` WHERE 1=1
        """
        params: List[Any] = []
        if upload_id is not None:
            base += " AND `upload_id`=%s"; params.append(upload_id)
        if agent_code:
            base += " AND `agent_code`=%s"; params.append(agent_code)
        if month_year:
            base += " AND `month_year`=%s"; params.append(month_year)
        if policy_no:
            base += " AND `policy_no`=%s"; params.append(policy_no)
        base += " ORDER BY `terminated_id` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            items: List[Dict[str, Any]] = list(cur.fetchall() or [])
            for it in items:
                sur, other = _split_holder(it.get("holder"))
                it["holder_surname"] = sur
                it["other_name"] = other
            return items
    finally:
        conn.close()


def _list_active_policies_items(
    agent_code: Optional[str],
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
            FROM `active_policies` WHERE 1=1
        """
        params: List[Any] = []
        if agent_code:
            base += " AND `agent_code`=%s"; params.append(agent_code)
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


def _missing_items(agent_code: str, month_year: str) -> List[Dict[str, Any]]:
    """
    Business-layer 'missing' without calling a route.
    """
    month_year = _norm_yyyy_mm(month_year) or month_year
    raw = _fetch_missing_policies(agent_code, month_year) or []  # list[dict]
    out: List[Dict[str, Any]] = []
    for r in raw:
        holder_name = r.get("holder_name") or ""
        sur, other = _split_holder(holder_name)
        out.append(
            {
                "policy_no": r.get("policy_no"),
                "holder_name": holder_name,
                "holder_surname": sur,
                "other_name": other,
                "last_seen_month": r.get("last_seen_month"),
                "last_premium": r.get("last_premium"),
                "last_com_rate": r.get("last_com_rate"),
            }
        )
    return out


# ------------------------------------------------------------------------------
# Endpoints (all local/business functions; no handler→handler calls)
# ------------------------------------------------------------------------------

@router.get("/me")
def superuser_me() -> Dict[str, Any]:
    return {"status": "OK", "role": "superuser"}


# Uploads
@router.get("/uploads")
def uploads_for_superuser(
    doc_type: Optional[str] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = Query(None, description="YYYY-MM (canonical)"),
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    month_year = _norm_yyyy_mm(month_year)
    items = _list_uploads_items(doc_type, agent_code, month_year, limit, offset)
    return {"count": len(items), "items": items}


@router.get("/uploads.csv")
def uploads_csv_for_superuser(
    doc_type: Optional[str] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = Query(None, description="YYYY-MM (canonical)"),
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    month_year = _norm_yyyy_mm(month_year)
    items = _list_uploads_items(doc_type, agent_code, month_year, limit, offset)
    return _dicts_to_csv_stream(items, filename="uploads.csv")


# Uploads tracker
@router.get("/uploads/tracker")
def uploads_tracker_for_superuser(
    agent_code: str,
    months_back: int = 36,
) -> Dict[str, Any]:
    items = _uploads_tracker_items(agent_code=agent_code, months_back=months_back)
    return {"count": len(items), "items": items}


@router.get("/uploads/tracker.csv")
def uploads_tracker_csv_for_superuser(
    agent_code: str,
    months_back: int = 36,
) -> StreamingResponse:
    rows = _uploads_tracker_items(agent_code=agent_code, months_back=months_back)
    csv_rows: List[Dict[str, Any]] = []
    for r in rows:
        csv_rows.append({
            "month_year": r.get("month_year"),
            "statement": 1 if r.get("statement_present") else 0,
            "schedule": 1 if r.get("schedule_present") else 0,
            "terminated": 1 if r.get("terminated_present") else 0,
            "statement_upload_id": r.get("statement_upload_id"),
            "schedule_upload_id": r.get("schedule_upload_id"),
            "terminated_upload_id": r.get("terminated_upload_id"),
        })
    return _dicts_to_csv_stream(
        csv_rows,
        field_order=[
            "month_year", "statement", "schedule", "terminated",
            "statement_upload_id", "schedule_upload_id", "terminated_upload_id",
        ],
        filename="uploads_tracker.csv",
    )


# Statements
@router.get("/statements")
def statements_for_superuser(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = Query(None, description="YYYY-MM (canonical)"),
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    month_year = _norm_yyyy_mm(month_year)
    items = _list_statements_items(upload_id, agent_code, month_year, policy_no, limit, offset)
    return {"count": len(items), "items": items}


@router.get("/statements.csv")
def statements_csv_for_superuser(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = Query(None, description="YYYY-MM (canonical)"),
    policy_no: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    month_year = _norm_yyyy_mm(month_year)
    items = _list_statements_items(upload_id, agent_code, month_year, policy_no, limit, offset)
    return _dicts_to_csv_stream(items, filename="statements.csv")


# Schedule
@router.get("/schedule")
def schedule_for_superuser(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = Query(None, description="YYYY-MM (canonical)"),
    latest_only: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    month_year = _norm_yyyy_mm(month_year)
    items = _list_schedule_items(upload_id, agent_code, month_year, latest_only, limit, offset)
    return {"count": len(items), "items": items}


@router.get("/schedule.csv")
def schedule_csv_for_superuser(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = Query(None, description="YYYY-MM (canonical)"),
    latest_only: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    month_year = _norm_yyyy_mm(month_year)
    items = _list_schedule_items(upload_id, agent_code, month_year, latest_only, limit, offset)
    return _dicts_to_csv_stream(items, filename="schedule.csv")


# Terminated
@router.get("/terminated")
def terminated_for_superuser(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = Query(None, description="YYYY-MM (canonical)"),
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    month_year = _norm_yyyy_mm(month_year)
    items = _list_terminated_items(upload_id, agent_code, month_year, policy_no, limit, offset)
    return {"count": len(items), "items": items}


@router.get("/terminated.csv")
def terminated_csv_for_superuser(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = Query(None, description="YYYY-MM (canonical)"),
    policy_no: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    month_year = _norm_yyyy_mm(month_year)
    items = _list_terminated_items(upload_id, agent_code, month_year, policy_no, limit, offset)
    return _dicts_to_csv_stream(items, filename="terminated.csv")


# Active policieser.get("/active-policies")
def active_policies_for_superuser(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = Query(None, description="YYYY-MM (canonical)"),
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    month_year = _norm_yyyy_mm(month_year)
    items = _list_active_policies_items(agent_code, month_year, status, limit, offset)
    return {"count": len(items), "items": items}


@router.get("/active-policies.csv")
def active_policies_csv_for_superuser(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = Query(None, description="YYYY-MM (canonical)"),
    status: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    month_year = _norm_yyyy_mm(month_year)
    items = _list_active_policies_items(agent_code, month_year, status, limit, offset)
    return _dicts_to_csv_stream(items, filename="active_policies.csv")


# Missing (business function, not a route)
@router.get("/missing")
def missing_for_superuser(
    agent_code: str,
    month_year: str = Query(..., description="YYYY-MM (canonical)"),
) -> Dict[str, Any]:
    items = _missing_items(agent_code, month_year)
    return {"count": len(items), "items": items}


@router.get("/missing.csv")
def missing_csv_for_superuser(
    agent_code: str,
    month_year: str = Query(..., description="YYYY-MM (canonical)"),
) -> StreamingResponse:
    rows = _missing_items(agent_code, month_year)
    return _dicts_to_csv_stream(
        rows,
        field_order=[
            "policy_no", "holder_name", "holder_surname", "other_name",
            "last_seen_month", "last_premium", "last_com_rate",
        ],
        filename="missing.csv",
    )
