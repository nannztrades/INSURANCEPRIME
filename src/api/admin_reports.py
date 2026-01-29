
# src/api/admin_reports.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple, Callable, cast
from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import StreamingResponse
import csv
import io
import importlib

from src.ingestion.db import get_conn
from src.services.roles import require_role
from src.services.security import require_csrf

router = APIRouter(
    prefix="/api/admin",
    tags=["Admin Reports"],
    dependencies=[Depends(require_role("admin", "superuser"))],
)

# ---------- Utilities ----------
def _dicts_to_csv_stream(
    rows: Iterable[Dict[str, Any]],
    field_order: Optional[List[str]] = None,
    filename: Optional[str] = None,
) -> StreamingResponse:
    buf = io.StringIO()
    rows_list = list(rows)
    if rows_list:
        if field_order is None:
            field_order = list(rows_list[0].keys())
        writer = csv.DictWriter(buf, fieldnames=field_order, extrasaction="ignore")
        writer.writeheader()
        for r in rows_list:
            writer.writerow(r)
    buf.seek(0)
    headers = {"Content-Type": "text/csv; charset=utf-8"}
    if filename:
        headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return StreamingResponse(buf, headers=headers)

def _split_holder(holder: Optional[str]) -> Tuple[str, str]:
    s = str(holder or "").strip()
    if not s:
        return "", ""
    parts = s.split()
    surname = parts[0]
    other = " ".join(parts[1:]) if len(parts) > 1 else ""
    return surname, other

# --- Robust dynamic import of monthly_reports module, Pylance-friendly ---
_mr = importlib.import_module("src.reports.monthly_reports")

_tmp_compute = getattr(_mr, "compute_month_summary", None)
if not callable(_tmp_compute):
    raise RuntimeError("monthly_reports.compute_month_summary is required but missing or not callable")
_compute_month_summary: Callable[[str, str], Dict[str, Any]] = cast(
    Callable[[str, str], Dict[str, Any]], _tmp_compute
)

# Optional: schedule components (only used when include_raw=1). Safe fallback to {}.
_fetch_schedule_components: Optional[Callable[[str, str], Dict[str, Any]]] = None
_tmp_sched = getattr(_mr, "_fetch_schedule_components", None)
if callable(_tmp_sched):
    _fetch_schedule_components = cast(Callable[[str, str], Dict[str, Any]], _tmp_sched)

# ---------- Endpoints ----------

@router.get("/uploads")
def list_uploads(
    doc_type: Optional[str] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    conn = get_conn()
    try:
        sql = """
        SELECT `UploadID`,`agent_code`,`AgentName`,`doc_type`,`FileName`,`UploadTimestamp`,
               `month_year`,`is_active`
        FROM `uploads` WHERE 1=1
        """
        params: List[Any] = []
        if doc_type:
            sql += " AND `doc_type`=%s"
            params.append(doc_type)
        if agent_code:
            sql += " AND `agent_code`=%s"
            params.append(agent_code)
        if month_year:
            sql += " AND `month_year`=%s"
            params.append(month_year)
        sql += " ORDER BY `UploadID` DESC LIMIT %s OFFSET %s"
        params += [limit, offset]
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            items = list(cur.fetchall() or [])
        return {"count": len(items), "items": items}
    finally:
        conn.close()

@router.get("/uploads.csv")
def list_uploads_csv(
    doc_type: Optional[str] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    data = list_uploads(
        doc_type=doc_type,
        agent_code=agent_code,
        month_year=month_year,
        limit=limit,
        offset=offset,
    )
    return _dicts_to_csv_stream(data.get("items", []), filename="uploads.csv")

@router.get("/uploads/tracker")
def uploads_tracker(agent_code: str, months_back: int = 36) -> Dict[str, Any]:
    """
    Shows whether each month has active uploads and/or rows in statement/schedule/terminated.
    Canonical order: newest month first using YYYY-MM ordering.
    """
    conn = get_conn()
    items: List[Dict[str, Any]] = []
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
              SELECT DISTINCT u.`month_year` FROM `uploads` u
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
                agent_code, agent_code, agent_code,
                agent_code, agent_code, agent_code, agent_code,
                months_back,
            ]
            cur.execute(sql, tuple(params))
            items = list(cur.fetchall() or [])
        return {"count": len(items), "items": items}
    finally:
        conn.close()

@router.get("/uploads/tracker.csv")
def uploads_tracker_csv(agent_code: str, months_back: int = 36) -> StreamingResponse:
    data = uploads_tracker(agent_code=agent_code, months_back=months_back)
    return _dicts_to_csv_stream(data.get("items", []), filename="uploads_tracker.csv")

@router.get("/statements")
def list_statements(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
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
            base += " AND `upload_id`=%s"
            params.append(upload_id)
        if agent_code:
            base += " AND `agent_code`=%s"
            params.append(agent_code)
        if month_year:
            base += " AND `MONTH_YEAR`=%s"
            params.append(month_year)
        if policy_no:
            base += " AND `policy_no`=%s"
            params.append(policy_no)
        base += " ORDER BY `statement_id` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            items = list(cur.fetchall() or [])
            for it in items:
                sur, other = _split_holder(it.get("holder"))
                it["holder_surname"] = sur
                it["other_name"] = other
        return {"count": len(items), "items": items}
    finally:
        conn.close()

@router.get("/statements.csv")
def list_statements_csv(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    data = list_statements(
        upload_id=upload_id,
        agent_code=agent_code,
        month_year=month_year,
        policy_no=policy_no,
        limit=limit,
        offset=offset,
    )
    return _dicts_to_csv_stream(data.get("items", []), filename="statements.csv")

def _select_schedule_latest(conn, agent_code: str, limit: int, offset: int) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        try:
            cur.execute(
                """
                SELECT sc.`month_year`, sc.`schedule_id`, sc.`upload_id`, sc.`agent_code`, sc.`agent_name`,
                       sc.`commission_batch_code`, sc.`total_premiums`, sc.`income`,
                       sc.`total_deductions`, sc.`net_commission`,
                       sc.`siclase`, sc.`premium_deduction`, sc.`pensions`, sc.`welfareko`
                FROM `schedule` sc
                JOIN (
                  SELECT `month_year`, MAX(`upload_id`) AS max_upload
                  FROM `schedule` WHERE `agent_code`=%s
                  GROUP BY `month_year`
                ) t ON sc.`month_year`=t.`month_year` AND sc.`upload_id`=t.`max_upload`
                ORDER BY STR_TO_DATE(CONCAT(sc.`month_year`,'-01'), '%Y-%m-%d') DESC
                LIMIT %s OFFSET %s
                """,
                (agent_code, limit, offset),
            )
            rows = list(cur.fetchall() or [])
        except Exception:
            cur.execute(
                """
                SELECT sc.`month_year`, sc.`schedule_id`, sc.`upload_id`, sc.`agent_code`, sc.`agent_name`,
                       sc.`commission_batch_code`, sc.`total_premiums`, sc.`income`,
                       sc.`total_deductions`, sc.`net_commission`
                FROM `schedule` sc
                JOIN (
                  SELECT `month_year`, MAX(`upload_id`) AS max_upload
                  FROM `schedule` WHERE `agent_code`=%s
                  GROUP BY `month_year`
                ) t ON sc.`month_year`=t.`month_year` AND sc.`upload_id`=t.`max_upload`
                ORDER BY STR_TO_DATE(CONCAT(sc.`month_year`,'-01'), '%Y-%m-%d') DESC
                LIMIT %s OFFSET %s
                """,
                (agent_code, limit, offset),
            )
            rows = list(cur.fetchall() or [])
            for r in rows:
                r["siclase"] = 0.0
                r["premium_deduction"] = 0.0
                r["pensions"] = 0.0
                r["welfareko"] = 0.0
        return rows

@router.get("/schedule")
def list_schedule(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    latest_only: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    eff_latest_int = 0
    if latest_only is None and agent_code:
        eff_latest_int = 1
    elif latest_only is not None:
        val = str(latest_only).strip()
        eff_latest_int = 0 if val == "" else int(bool(int(val)))
    conn = get_conn()
    items: List[Dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            if eff_latest_int and agent_code:
                items = _select_schedule_latest(conn, agent_code, limit, offset)
                return {"count": len(items), "items": items}
            base = """
            SELECT `month_year`,`schedule_id`,`upload_id`,`agent_code`,`agent_name`,
                   `commission_batch_code`,`total_premiums`,`income`,
                   `total_deductions`,`net_commission`,
                   `siclase`,`premium_deduction`,`pensions`,`welfareko`
            FROM `schedule` WHERE 1=1
            """
            params: List[Any] = []
            if upload_id is not None:
                base += " AND `upload_id`=%s"
                params.append(upload_id)
            if agent_code:
                base += " AND `agent_code`=%s"
                params.append(agent_code)
            if month_year:
                base += " AND `month_year`=%s"
                params.append(month_year)
            base += " ORDER BY `schedule_id` DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            cur.execute(base, tuple(params))
            items = list(cur.fetchall() or [])
        return {"count": len(items), "items": items}
    finally:
        conn.close()

@router.get("/schedule.csv")
def list_schedule_csv(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    latest_only: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    data = list_schedule(
        upload_id=upload_id,
        agent_code=agent_code,
        month_year=month_year,
        latest_only=latest_only,
        limit=limit,
        offset=offset,
    )
    return _dicts_to_csv_stream(data.get("items", []), filename="schedule.csv")

@router.get("/terminated")
def list_terminated(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    conn = get_conn()
    items: List[Dict[str, Any]] = []
    try:
        base = """
        SELECT `terminated_id`,`upload_id`,`agent_code`,`policy_no`,`holder`,
               `policy_type`,`premium`,`status`,`reason`,`month_year`,`termination_date`
        FROM `terminated` WHERE 1=1
        """
        params: List[Any] = []
        if upload_id is not None:
            base += " AND `upload_id`=%s"
            params.append(upload_id)
        if agent_code:
            base += " AND `agent_code`=%s"
            params.append(agent_code)
        if month_year:
            base += " AND `month_year`=%s"
            params.append(month_year)
        if policy_no:
            base += " AND `policy_no`=%s"
            params.append(policy_no)
        base += " ORDER BY `terminated_id` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            items = list(cur.fetchall() or [])
            for it in items:
                sur, other = _split_holder(it.get("holder"))
                it["holder_surname"] = sur
                it["other_name"] = other
        return {"count": len(items), "items": items}
    finally:
        conn.close()

@router.get("/terminated.csv")
def list_terminated_csv(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    data = list_terminated(
        upload_id=upload_id,
        agent_code=agent_code,
        month_year=month_year,
        policy_no=policy_no,
        limit=limit,
        offset=offset,
    )
    return _dicts_to_csv_stream(data.get("items", []), filename="terminated.csv")

@router.get("/active-policies")
def list_active_policies(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    conn = get_conn()
    items: List[Dict[str, Any]] = []
    try:
        base = """
        SELECT `id`,`agent_code`,`policy_no`,`policy_type`,`holder_name`,
               `inception_date`,`first_seen_date`,`last_seen_date`,`last_seen_month_year`,
               `last_premium`,`last_com_rate`,`status`,`consecutive_missing_months`
        FROM `active_policies` WHERE 1=1
        """
        params: List[Any] = []
        if agent_code:
            base += " AND `agent_code`=%s"
            params.append(agent_code)
        if month_year:
            base += " AND `last_seen_month_year`=%s"
            params.append(month_year)
        if status:
            base += " AND `status`=%s"
            params.append(status)
        base += " ORDER BY `id` DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            items = list(cur.fetchall() or [])
        return {"count": len(items), "items": items}
    finally:
        conn.close()

@router.get("/active-policies.csv")
def list_active_policies_csv(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0,
) -> StreamingResponse:
    data = list_active_policies(
        agent_code=agent_code,
        month_year=month_year,
        status=status,
        limit=limit,
        offset=offset,
    )
    return _dicts_to_csv_stream(data.get("items", []), filename="active_policies.csv")

@router.post("/reports/generate-agent-month", dependencies=[Depends(require_csrf)])
def generate_agent_month(
    agent_code: str = Form(...),
    month_year: str = Form(...),
    upload_id: Optional[int] = Form(None),
) -> Dict[str, Any]:
    try:
        _ = _compute_month_summary(agent_code, month_year)
        return {
            "status": "SUCCESS",
            "message": f"Monthly report successfully generated for {month_year}",
            "agent_code": agent_code,
            "month_year": month_year,
            "upload_id": upload_id,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/commission-comparison")
def commission_comparison_admin(
    agent_code: str,
    month_year: str,
    upload_id: Optional[int] = None,
    include_raw: int = 0,
) -> Dict[str, Any]:
    try:
        summary = _compute_month_summary(agent_code, month_year)
        comp = summary.get("commission_comparison", {}) or {}
        inputs = comp.get("inputs", {}) or {}
        tax_percent = inputs.get("tax_percent", 10.0)
        welfareko = inputs.get("welfareko", 0.0)
        siclase = inputs.get("siclase", 0.0)

        out: Dict[str, Any] = {
            "status": "OK",
            "inputs": {
                "agent_code": agent_code,
                "month_year": month_year,
                "upload_id": upload_id,
                "tax_percent": tax_percent,
                "welfareko": welfareko,
                "siclase": siclase,
            },
            "net": {
                "expected": comp.get("expected_net", 0.0),
                "statement": comp.get("statement_net", 0.0),
                "schedule": comp.get("schedule_net", 0.0),
            },
            "diffs_vs_expected": {
                "statement": (comp.get("diffs_vs_expected", {}) or {}).get(
                    "statement", {"amount": 0.0, "percent": 0.0}
                ),
                "schedule": (comp.get("diffs_vs_expected", {}) or {}).get(
                    "schedule", {"amount": 0.0, "percent": 0.0}
                ),
            },
        }

        if include_raw:
            try:
                comps_sched: Dict[str, Any] = {}
                if _fetch_schedule_components:
                    comps_sched = _fetch_schedule_components(agent_code, month_year)
            except Exception:
                comps_sched = {}
            out["raw"] = {
                "totals": {
                    "total_expected": summary.get("total_commission_expected", 0.0),
                    "total_reported": summary.get("total_commission_reported", 0.0),
                    "variance_amount": summary.get("variance_amount", 0.0),
                    "variance_percentage": summary.get("variance_percentage", 0.0),
                },
                "schedule_components": {
                    "gov_tax": comps_sched.get("gov_tax", 0.0),
                    "siclase": comps_sched.get("siclase", 0.0),
                    "welfareko": comps_sched.get("welfareko", 0.0),
                    "premium_deductions": comps_sched.get("premium_deduction", 0.0),
                    "pensions": comps_sched.get("pensions", 0.0),
                    "total_deductions": comps_sched.get("total_deductions", 0.0),
                    "net_commission": comps_sched.get("net_commission", 0.0),
                },
                "notes": "Derived from compute_month_summary() + schedule components when available.",
            }

        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/reports/commission-comparison.csv")
def commission_comparison_admin_csv(
    agent_code: str,
    month_year: str,
    upload_id: Optional[int] = None,
) -> StreamingResponse:
    summary = _compute_month_summary(agent_code, month_year)
    comp = summary.get("commission_comparison", {}) or {}
    inputs = comp.get("inputs", {}) or {}
    row = {
        "agent_code": agent_code,
        "month_year": month_year,
        "upload_id": upload_id,
        "expected_net": comp.get("expected_net", 0.0),
        "statement_net": comp.get("statement_net", 0.0),
        "schedule_net": comp.get("schedule_net", 0.0),
        "statement_diff_amt": (comp.get("diffs_vs_expected", {}) or {}).get("statement", {}).get("amount", 0.0),
        "statement_diff_pct": (comp.get("diffs_vs_expected", {}) or {}).get("statement", {}).get("percent", 0.0),
        "schedule_diff_amt": (comp.get("diffs_vs_expected", {}) or {}).get("schedule", {}).get("amount", 0.0),
        "schedule_diff_pct": (comp.get("diffs_vs_expected", {}) or {}).get("schedule", {}).get("percent", 0.0),
        "tax_percent": inputs.get("tax_percent", 10.0),
        "welfareko": inputs.get("welfareko", 0.0),
        "siclase": inputs.get("siclase", 0.0),
        "total_expected": summary.get("total_commission_expected", 0.0),
        "total_reported": summary.get("total_commission_reported", 0.0),
        "variance_amount": summary.get("variance_amount", 0.0),
        "variance_percentage": summary.get("variance_percentage", 0.0),
    }
    headers = list(row.keys())
    return _dicts_to_csv_stream([row], field_order=headers, filename="commission_comparison.csv")
