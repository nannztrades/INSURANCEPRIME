
# src/api/admin_reports.py
from __future__ import annotations

from typing import Dict, Any, Optional, List, Iterable
from fastapi import APIRouter, HTTPException, Form, Body, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import csv, io
from datetime import datetime

from src.ingestion.db import get_conn
from src.ingestion.commission import compute_expected_for_upload_dynamic, insert_expected_rows
from src.reports.monthly_reports import _period_key_from_month_year, compute_month_summary
from src.services.auth_service import decode_token, TOKEN_COOKIE_NAME

# ---------- Cookie-based role guard ----------
def require_admin_or_superuser(request: Request):
    tok = request.cookies.get(TOKEN_COOKIE_NAME)
    u = decode_token(tok) if tok else None
    role = str((u or {}).get("role") or "").lower()
    if not u or role not in ("admin", "superuser"):
        raise HTTPException(status_code=403, detail="Admin/Superuser authentication required")
    return u

# Global router: all endpoints here require admin/superuser via cookie
router = APIRouter(prefix="/api/admin", tags=["Admin Reports"], dependencies=[Depends(require_admin_or_superuser)])

# ---------- Models ----------
class UpsertAgentModel(BaseModel):
    agent_code: str
    agent_name: Optional[str] = None
    license_number: Optional[str] = None
    is_active: Optional[bool] = True

class UpdateAgentModel(BaseModel):
    agent_name: Optional[str] = None
    license_number: Optional[str] = None
    is_active: Optional[bool] = None

class UpsertUserModel(BaseModel):
    email: str
    password_hash: str
    agent_code: Optional[str] = None
    role: Optional[str] = "agent"
    is_active: Optional[bool] = True
    is_verified: Optional[bool] = False

class UpdateUserModel(BaseModel):
    email: Optional[str] = None
    password_hash: Optional[str] = None
    agent_code: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None

class DeactivateOlderModel(BaseModel):
    agent_code: str
    month_year: str
    doc_type: str  # STATEMENT | SCHEDULE | TERMINATED

class ResolveAuditFlagModel(BaseModel):
    id: int
    resolved: bool = True
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None

class BackfillUploadsMonthYearModel(BaseModel):
    upload_id: Optional[int] = None
    doc_type: Optional[str] = None   # STATEMENT | SCHEDULE | TERMINATED
    dry_run: bool = True
    limit: int = 1000

# ---------- Helpers ----------
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

def _agents_for_upload(upload_id: Optional[int], month_year: Optional[str]) -> List[str]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if upload_id is not None:
                cur.execute(
                    "SELECT DISTINCT `agent_code` FROM `statement` WHERE `upload_id`=%s ORDER BY `agent_code`",
                    (upload_id,)
                )
            else:
                cur.execute(
                    "SELECT DISTINCT `agent_code` FROM `statement` WHERE `MONTH_YEAR`=%s ORDER BY `agent_code`",
                    (month_year,)
                )
            rows = cur.fetchall() or []
            return [str(r.get('agent_code')) for r in rows if r.get('agent_code')]
    finally:
        conn.close()

def _dicts_to_csv_stream(rows: Iterable[Dict[str, Any]], field_order: Optional[List[str]] = None) -> StreamingResponse:
    buf = io.StringIO()
    rows = list(rows or [])
    if rows:
        headers = field_order or list(rows[0].keys())
        writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in headers})
    else:
        writer = csv.writer(buf)
        writer.writerow([])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv")

# ---------- Batch report generation ----------
@router.post('/reports/generate-batch')
def generate_batch(
    upload_id: Optional[int] = Form(None),
    month_year: Optional[str] = Form(None),
) -> Dict[str, Any]:
    if upload_id is None and month_year is None:
        raise HTTPException(status_code=400, detail="Provide upload_id or month_year")

    agents = _agents_for_upload(upload_id, month_year)
    if not agents:
        return {"status": "EMPTY", "agents": []}

    results: List[Dict[str, Any]] = []
    for agent_code in agents:
        if upload_id is not None:
            rows = compute_expected_for_upload_dynamic(upload_id)
            rows_agent = [r for r in rows if r.get('agent_code') == agent_code]
            inserted = insert_expected_rows(rows_agent) if rows_agent else 0

            # Resolve month label if absent
            mlabel = month_year
            if not mlabel:
                conn = get_conn()
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT `MONTH_YEAR` FROM `statement` WHERE `upload_id`=%s AND `agent_code`=%s LIMIT 1",
                            (upload_id, agent_code)
                        )
                        r = cur.fetchone() or {}
                        mlabel = r.get('MONTH_YEAR')
                finally:
                    conn.close()

            summary = compute_month_summary(agent_code, mlabel or "")
            report_period = _period_key_from_month_year(mlabel or "") or (mlabel or "").replace('COM_', '').replace(' ', '-')

            # Insert monthly_reports row
            conn2 = get_conn()
            try:
                from src.api.agent_reports import _insert_monthly_report_row
                _insert_monthly_report_row(conn2, agent_code, agent_code, report_period, upload_id, summary, None)
            finally:
                conn2.close()

            results.append({"agent_code": agent_code, "expected_rows_inserted": inserted, "report_period": report_period})
        else:
            summary = compute_month_summary(agent_code, month_year or "")
            results.append({"agent_code": agent_code, "summary": summary})

    return {"status": "SUCCESS", "count": len(results), "results": results}

# ---------- Single agent + month ----------
@router.post('/reports/generate-agent-month', tags=["Admin Reports"])
def generate_agent_month(
    agent_code: str = Form(...),
    month_year: str = Form(...),
    upload_id: Optional[int] = Form(None),
    agent_name: Optional[str] = Form(None),
    out: str = Form("D:/PROJECT/INSURANCELOCAL/reports"),
    skip_pdf: bool = Form(False),
    dry_run: bool = Form(False),
) -> Dict[str, Any]:
    from src.api.agent_reports import generate_report
    result = generate_report(
        agent_code=agent_code,
        month_year=month_year,
        upload_id=upload_id,
        agent_name=agent_name,
        out=out,
        user_id=None,
        skip_pdf=skip_pdf,
        dry_run=dry_run,
    )
    return result

# ---------- Uploads (JSON) ----------
@router.get('/uploads')
def list_uploads(
    doc_type: Optional[str] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    limit: int = 200,
    offset: int = 0
) -> Dict[str, Any]:
    conn = get_conn()
    items: List[Dict[str, Any]] = []
    try:
        base = """
        SELECT `UploadID`,`agent_code`,`AgentName`,`doc_type`,`FileName`,
               `UploadTimestamp`,`month_year`,`is_active`
        FROM `uploads` WHERE 1=1
        """
        params: List[Any] = []
        if doc_type:
            base += " AND `doc_type`=%s"; params.append(doc_type.upper())
        if agent_code:
            base += " AND `agent_code`=%s"; params.append(agent_code)
        if month_year:
            base += " AND `month_year`=%s"; params.append(month_year)
        base += " ORDER BY `UploadID` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            items = list(cur.fetchall() or [])
    finally:
        conn.close()
    return {"count": len(items), "items": items}

# ---------- Statements (JSON) ----------
@router.get('/statements')
def list_statements(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0
) -> Dict[str, Any]:
    conn = get_conn()
    items: List[Dict[str, Any]] = []
    try:
        # PATCH: alias MONTH_YEAR -> month_year for consistency with schedule/terminated
        base = """
        SELECT `statement_id`,`upload_id`,`agent_code`,`policy_no`,`holder`,
               `policy_type`,`pay_date`,`receipt_no`,`premium`,`com_rate`,
               `com_amt`,`inception`,`MONTH_YEAR` AS `month_year`,`AGENT_LICENSE_NUMBER`
        FROM `statement` WHERE 1=1
        """
        params: List[Any] = []
        if upload_id is not None: base += " AND `upload_id`=%s"; params.append(upload_id)
        if agent_code: base += " AND `agent_code`=%s"; params.append(agent_code)
        # Filtering still uses the storage column name (MONTH_YEAR)
        if month_year: base += " AND `MONTH_YEAR`=%s"; params.append(month_year)
        if policy_no: base += " AND `policy_no`=%s"; params.append(policy_no)
        base += " ORDER BY `statement_id` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            items = list(cur.fetchall() or [])
    finally:
        conn.close()
    return {"count": len(items), "items": items}

# ---------- Schedule (JSON) ----------
@router.get('/schedule')
def list_schedule(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    latest_only: Optional[int] = None,
    limit: int = 200,
    offset: int = 0
) -> Dict[str, Any]:
    eff_latest = 0
    if latest_only is None and agent_code:
        eff_latest = 1
    elif latest_only is not None:
        eff_latest = int(bool(latest_only))

    conn = get_conn()
    items: List[Dict[str, Any]] = []
    try:
        if eff_latest and agent_code:
            base = """
            SELECT sc.`month_year`, sc.`schedule_id`, sc.`upload_id`, sc.`agent_code`, sc.`agent_name`,
                   sc.`commission_batch_code`, sc.`total_premiums`, sc.`income`,
                   sc.`total_deductions`, sc.`net_commission`
            FROM `schedule` sc
            JOIN (
                SELECT `month_year`, MAX(`upload_id`) AS max_upload
                FROM `schedule`
                WHERE `agent_code`=%s
                GROUP BY `month_year`
            ) mx ON mx.`month_year` = sc.`month_year` AND mx.`max_upload` = sc.`upload_id`
            WHERE sc.`agent_code`=%s
            """
            params: List[Any] = [agent_code, agent_code]
            if month_year:
                base += " AND sc.`month_year`=%s"; params.append(month_year)
            base += " ORDER BY sc.`month_year` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
            with conn.cursor() as cur:
                cur.execute(base, tuple(params))
                items = list(cur.fetchall() or [])
        else:
            base = """
            SELECT `schedule_id`,`upload_id`,`agent_code`,`agent_name`,`commission_batch_code`,
                   `total_premiums`,`income`,`total_deductions`,`net_commission`,`month_year`
            FROM `schedule` WHERE 1=1
            """
            params2: List[Any] = []
            if upload_id is not None: base += " AND `upload_id`=%s"; params2.append(upload_id)
            if agent_code: base += " AND `agent_code`=%s"; params2.append(agent_code)
            if month_year: base += " AND `month_year`=%s"; params2.append(month_year)
            base += " ORDER BY `schedule_id` DESC LIMIT %s OFFSET %s"; params2.extend([limit, offset])
            with conn.cursor() as cur:
                cur.execute(base, tuple(params2))
                items = list(cur.fetchall() or [])
    finally:
        conn.close()
    return {"count": len(items), "items": items}

# ---------- Terminated (JSON) ----------
@router.get('/terminated')
def list_terminated(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0
) -> Dict[str, Any]:
    conn = get_conn()
    items: List[Dict[str, Any]] = []
    try:
        base = """
        SELECT `terminated_id`,`upload_id`,`agent_code`,`policy_no`,`holder`,`surname`,
               `other_name`,`receipt_no`,`paydate`,`premium`,`com_rate`,`com_amt`,
               `policy_type`,`inception`,`status`,`agent_name`,`reason`,`month_year`,
               `AGENT_LICENSE_NUMBER`,`termination_date`
        FROM `terminated` WHERE 1=1
        """
        params: List[Any] = []
        if upload_id is not None: base += " AND `upload_id`=%s"; params.append(upload_id)
        if agent_code: base += " AND `agent_code`=%s"; params.append(agent_code)
        if month_year: base += " AND `month_year`=%s"; params.append(month_year)
        if policy_no: base += " AND `policy_no`=%s"; params.append(policy_no)
        base += " ORDER BY `terminated_id` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            items = list(cur.fetchall() or [])
    finally:
        conn.close()
    return {"count": len(items), "items": items}

# ---------- Active policies (JSON) ----------
@router.get('/active-policies')
def list_active_policies(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    conn = get_conn()
    items: List[Dict[str, Any]] = []
    try:
        base = """
        SELECT `id`,`agent_code`,`policy_no`,`policy_type`,`holder_name`,
               `inception_date`,`first_seen_date`,`last_seen_date`,
               `last_seen_month_year`,`last_premium`,`last_com_rate`,`status`,
               `consecutive_missing_months`,`created_at`,`updated_at`
        FROM `active_policies` WHERE 1=1
        """
        params: List[Any] = []
        if agent_code: base += " AND `agent_code`=%s"; params.append(agent_code)
        if month_year: base += " AND `last_seen_month_year`=%s"; params.append(month_year)
        if status: base += " AND `status`=%s"; params.append(status)
        base += " ORDER BY `updated_at` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            items = list(cur.fetchall() or [])
    finally:
        conn.close()
    return {"count": len(items), "items": items}

# ---------- Upload activation controls ----------
@router.post('/uploads/enable/{upload_id}')
def enable_upload(upload_id: int) -> Dict[str, Any]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE `uploads` SET `is_active`=1 WHERE `UploadID`=%s", (upload_id,))
            affected = cur.rowcount or 0
            conn.commit()
        if affected == 0:
            return {"status": "NOT_FOUND", "upload_id": upload_id}
        return {"status": "SUCCESS", "upload_id": upload_id, "enabled": True}
    finally:
        conn.close()

@router.delete('/uploads/{upload_id}')
def delete_upload(upload_id: int) -> Dict[str, Any]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE `uploads` SET `is_active`=0 WHERE `UploadID`=%s", (upload_id,))
            affected = cur.rowcount or 0
            conn.commit()
        if affected == 0:
            return {"status": "NOT_FOUND", "upload_id": upload_id}
        return {"status": "SUCCESS", "upload_id": upload_id, "deactivated": True}
    finally:
        conn.close()

@router.post('/uploads/deactivate-older')
def deactivate_older(payload: DeactivateOlderModel = Body(...)) -> Dict[str, Any]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            SELECT MAX(`UploadID`) AS max_id
            FROM `uploads`
            WHERE `agent_code`=%s AND `month_year`=%s AND `doc_type`=%s
            """, (payload.agent_code, payload.month_year, payload.doc_type.upper()))
            r = cur.fetchone() or {}
            max_id_val = r.get('max_id')
            kept_active = _as_int(max_id_val)
            if kept_active is None:
                return {"status": "EMPTY", "message": "No uploads found for given filters."}

            cur.execute("""
            UPDATE `uploads`
            SET `is_active`=0
            WHERE `agent_code`=%s AND `month_year`=%s AND `doc_type`=%s AND `UploadID`<>%s
            """, (payload.agent_code, payload.month_year, payload.doc_type.upper(), kept_active))
            affected = cur.rowcount or 0
            conn.commit()
        return {"status": "SUCCESS", "kept_active": kept_active, "deactivated_count": affected}
    finally:
        conn.close()

# ---------- NEW: Backfill uploads.month_year from row tables ----------
def _majority_month_year_for_upload(conn, doc_type: str, upload_id: int) -> Dict[str, Any]:
    table_map = {
        "STATEMENT": ("statement", "MONTH_YEAR"),
        "TERMINATED": ("terminated", "month_year"),
        "SCHEDULE": ("schedule", "month_year"),
    }
    tup = table_map.get(doc_type.upper())
    if not tup:
        return {"candidate": None, "counts": {}, "distinct": 0}

    table, col = tup
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT `{col}` AS my, COUNT(*) AS c
            FROM `{table}`
            WHERE `upload_id`=%s AND `{col}` IS NOT NULL AND TRIM(`{col}`) <> ''
            GROUP BY `{col}`
            ORDER BY c DESC
        """, (upload_id,))
        rows = cur.fetchall() or []
        counts: Dict[str, int] = {}
        for r in rows:
            mv = r.get("my")
            cnt = int(r.get("c") or 0)
            if mv:
                counts[str(mv)] = cnt
        candidate = next(iter(counts)) if counts else None
        return {"candidate": candidate, "counts": counts, "distinct": len(counts)}

@router.post('/uploads/backfill-month-year')
def backfill_uploads_month_year(payload: BackfillUploadsMonthYearModel = Body(...)) -> Dict[str, Any]:
    conn = get_conn()
    try:
        targets: List[Dict[str, Any]] = []
        with conn.cursor() as cur:
            if payload.upload_id is not None:
                cur.execute("""
                    SELECT `UploadID`,`doc_type`,`agent_code`,`month_year`
                    FROM `uploads` WHERE `UploadID`=%s
                """, (payload.upload_id,))
            else:
                base = """
                    SELECT `UploadID`,`doc_type`,`agent_code`,`month_year`
                    FROM `uploads`
                    WHERE ( `month_year` IS NULL OR TRIM(`month_year`) = '' )
                """
                params: List[Any] = []
                if payload.doc_type:
                    base += " AND `doc_type`=%s"; params.append(payload.doc_type.upper())
                base += " ORDER BY `UploadID` DESC LIMIT %s"; params.append(payload.limit)
                cur.execute(base, tuple(params))
            targets = list(cur.fetchall() or [])

        if not targets:
            return {"status": "EMPTY", "processed": 0, "updated": 0, "items": []}

        updated = 0
        items: List[Dict[str, Any]] = []
        for t in targets:
            upload_id = _as_int(t.get("UploadID"))
            if upload_id is None:
                items.append({
                    "UploadID": t.get("UploadID"),
                    "doc_type": t.get("doc_type"),
                    "agent_code": t.get("agent_code"),
                    "current_month_year": t.get("month_year"),
                    "candidate_month_year": None,
                    "distinct_values": 0,
                    "counts": {},
                    "updated": False,
                    "dry_run": bool(payload.dry_run),
                    "error": "Invalid UploadID"
                })
                continue

            doc_type = str(t.get("doc_type") or "").upper()
            agent_code = t.get("agent_code")
            current_my = t.get("month_year")
            stats = _majority_month_year_for_upload(conn, doc_type, upload_id)
            candidate = stats.get("candidate")
            distinct = _as_int(stats.get("distinct")) or 0
            counts = stats.get("counts") or {}

            row: Dict[str, Any] = {
                "UploadID": upload_id,
                "doc_type": doc_type,
                "agent_code": agent_code,
                "current_month_year": current_my,
                "candidate_month_year": candidate,
                "distinct_values": distinct,
                "counts": counts,
                "updated": False,
                "dry_run": bool(payload.dry_run),
            }

            if candidate:
                if not payload.dry_run:
                    with conn.cursor() as cur2:
                        cur2.execute("UPDATE `uploads` SET `month_year`=%s WHERE `UploadID`=%s", (candidate, upload_id))
                    conn.commit()
                    row["updated"] = True
                    updated += 1
            else:
                row["updated"] = False

            items.append(row)

        return {"status": "SUCCESS", "processed": len(targets), "updated": updated, "items": items}

    finally:
        conn.close()

# ---------- CSV exports ----------
@router.get('/statements.csv')
def export_statements_csv(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0
):
    conn = get_conn()
    try:
        # PATCH: alias MONTH_YEAR -> month_year and adjust CSV header order
        base = """
        SELECT `statement_id`,`upload_id`,`agent_code`,`policy_no`,`holder`,
               `policy_type`,`pay_date`,`receipt_no`,`premium`,`com_rate`,
               `com_amt`,`inception`,`MONTH_YEAR` AS `month_year`,`AGENT_LICENSE_NUMBER`
        FROM `statement` WHERE 1=1
        """
        params: List[Any] = []
        if upload_id is not None: base += " AND `upload_id`=%s"; params.append(upload_id)
        if agent_code: base += " AND `agent_code`=%s"; params.append(agent_code)
        # Filtering uses storage column name
        if month_year: base += " AND `MONTH_YEAR`=%s"; params.append(month_year)
        if policy_no: base += " AND `policy_no`=%s"; params.append(policy_no)
        base += " ORDER BY `statement_id` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            rows = cur.fetchall() or []
        return _dicts_to_csv_stream(rows, field_order=[
            "statement_id","upload_id","agent_code","policy_no","holder","policy_type",
            "pay_date","receipt_no","premium","com_rate","com_amt","inception","month_year","AGENT_LICENSE_NUMBER"
        ])
    finally:
        conn.close()

@router.get('/schedule.csv')
def export_schedule_csv(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    latest_only: Optional[int] = None,
    limit: int = 100000,
    offset: int = 0
):
    eff_latest = 0
    if latest_only is None and agent_code:
        eff_latest = 1
    elif latest_only is not None:
        eff_latest = int(bool(latest_only))

    conn = get_conn()
    try:
        if eff_latest and agent_code:
            base = """
            SELECT sc.`month_year`, sc.`schedule_id`, sc.`upload_id`, sc.`agent_code`, sc.`agent_name`,
                   sc.`commission_batch_code`, sc.`total_premiums`, sc.`income`,
                   sc.`total_deductions`, sc.`net_commission`
            FROM `schedule` sc
            JOIN (
                SELECT `month_year`, MAX(`upload_id`) AS max_upload
                FROM `schedule`
                WHERE `agent_code`=%s
                GROUP BY `month_year`
            ) mx ON mx.`month_year` = sc.`month_year` AND mx.`max_upload` = sc.`upload_id`
            WHERE sc.`agent_code`=%s
            """
            params: List[Any] = [agent_code, agent_code]
            if month_year:
                base += " AND sc.`month_year`=%s"; params.append(month_year)
            base += " ORDER BY sc.`month_year` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
            with conn.cursor() as cur:
                cur.execute(base, tuple(params))
                rows = cur.fetchall() or []
        else:
            base = """
            SELECT `schedule_id`,`upload_id`,`agent_code`,`agent_name`,`commission_batch_code`,
                   `total_premiums`,`income`,`total_deductions`,`net_commission`,`month_year`
            FROM `schedule` WHERE 1=1
            """
            params: List[Any] = []
            if upload_id is not None: base += " AND `upload_id`=%s"; params.append(upload_id)
            if agent_code: base += " AND `agent_code`=%s"; params.append(agent_code)
            if month_year: base += " AND `month_year`=%s"; params.append(month_year)
            base += " ORDER BY `schedule_id` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
            with conn.cursor() as cur:
                cur.execute(base, tuple(params))
                rows = cur.fetchall() or []
        return _dicts_to_csv_stream(rows)
    finally:
        conn.close()

@router.get('/terminated.csv')
def export_terminated_csv(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0
):
    conn = get_conn()
    try:
        base = """
        SELECT `terminated_id`,`upload_id`,`agent_code`,`policy_no`,`holder`,`surname`,
               `other_name`,`receipt_no`,`paydate`,`premium`,`com_rate`,`com_amt`,
               `policy_type`,`inception`,`status`,`agent_name`,`reason`,`month_year`,
               `AGENT_LICENSE_NUMBER`,`termination_date`
        FROM `terminated` WHERE 1=1
        """
        params: List[Any] = []
        if upload_id is not None: base += " AND `upload_id`=%s"; params.append(upload_id)
        if agent_code: base += " AND `agent_code`=%s"; params.append(agent_code)
        if month_year: base += " AND `month_year`=%s"; params.append(month_year)
        if policy_no: base += " AND `policy_no`=%s"; params.append(policy_no)
        base += " ORDER BY `terminated_id` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            rows = cur.fetchall() or []
        return _dicts_to_csv_stream(rows)
    finally:
        conn.close()

@router.get('/uploads.csv')
def export_uploads_csv(
    doc_type: Optional[str] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0
):
    conn = get_conn()
    try:
        base = """
        SELECT `UploadID`,`agent_code`,`AgentName`,`doc_type`,`FileName`,
               `UploadTimestamp`,`month_year`,`is_active`
        FROM `uploads` WHERE 1=1
        """
        params: List[Any] = []
        if doc_type: base += " AND `doc_type`=%s"; params.append(doc_type.upper())
        if agent_code: base += " AND `agent_code`=%s"; params.append(agent_code)
        if month_year: base += " AND `month_year`=%s"; params.append(month_year)
        base += " ORDER BY `UploadID` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            rows = cur.fetchall() or []
        return _dicts_to_csv_stream(rows)
    finally:
        conn.close()

@router.get('/active-policies.csv')
def export_active_policies_csv(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100000,
    offset: int = 0
):
    conn = get_conn()
    try:
        base = """
        SELECT `id`,`agent_code`,`policy_no`,`policy_type`,`holder_name`,
               `inception_date`,`first_seen_date`,`last_seen_date`,
               `last_seen_month_year`,`last_premium`,`last_com_rate`,`status`,
               `consecutive_missing_months`,`created_at`,`updated_at`
        FROM `active_policies` WHERE 1=1
        """
        params: List[Any] = []
        if agent_code: base += " AND `agent_code`=%s"; params.append(agent_code)
        if month_year: base += " AND `last_seen_month_year`=%s"; params.append(month_year)
        if status: base += " AND `status`=%s"; params.append(status)
        base += " ORDER BY `updated_at` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            rows = cur.fetchall() or []
        return _dicts_to_csv_stream(rows)
    finally:
        conn.close()

@router.get('/audit-flags')
def list_audit_flags(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    flag_type: Optional[str] = None,
    policy_no: Optional[str] = None,
    resolved: Optional[int] = None,
    limit: int = 200,
    offset: int = 0
) -> Dict[str, Any]:
    conn = get_conn()
    items: List[Dict[str, Any]] = []
    try:
        base = """
        SELECT `id`,`agent_code`,`policy_no`,`month_year`,`flag_type`,`severity`,
               `flag_detail`,`expected_value`,`actual_value`,`created_at`,
               `resolved`,`resolved_by`,`resolved_at`,`resolution_notes`
        FROM `audit_flags` WHERE 1=1
        """
        params: List[Any] = []
        if agent_code: base += " AND `agent_code`=%s"; params.append(agent_code)
        if month_year: base += " AND `month_year`=%s"; params.append(month_year)
        if flag_type: base += " AND `flag_type`=%s"; params.append(flag_type)
        if policy_no: base += " AND `policy_no`=%s"; params.append(policy_no)
        if resolved is not None: base += " AND `resolved`=%s"; params.append(int(bool(resolved)))
        base += " ORDER BY `created_at` DESC LIMIT %s OFFSET %s"; params.extend([limit, offset])
        with conn.cursor() as cur:
            cur.execute(base, tuple(params))
            items = list(cur.fetchall() or [])
    finally:
        conn.close()
    return {"count": len(items), "items": items}

@router.post('/audit-flags/resolve')
def resolve_audit_flag(payload: ResolveAuditFlagModel = Body(...)) -> Dict[str, Any]:
    effective_resolved_by = payload.resolved_by
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
            UPDATE `audit_flags`
            SET `resolved`=%s,
                `resolved_by`=%s,
                `resolved_at`=NOW(),
                `resolution_notes`=%s
            WHERE `id`=%s
            """, (int(bool(payload.resolved)), effective_resolved_by, payload.resolution_notes or None, payload.id))
            affected = cur.rowcount or 0
            conn.commit()
        if affected == 0:
            return {"status": "NOT_FOUND", "id": payload.id}
        return {"status": "SUCCESS", "id": payload.id}
    finally:
        conn.close()

# ---------- Upload Tracker ----------
def _month_labels_back(n: int) -> List[str]:
    labels: List[str] = []
    now = datetime.now()
    y, m = now.year, now.month
    MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    for i in range(n):
        mm = m - i
        yy = y
        while mm <= 0:
            mm += 12
            yy -= 1
        labels.append(f"{MONTH_ABBR[mm-1]} {yy}")
    return labels

@router.get('/uploads/tracker')
def uploads_tracker(agent_code: str, months_back: int = 36) -> Dict[str, Any]:
    months = _month_labels_back(max(1, months_back))
    conn = get_conn()
    try:
        out: List[Dict[str, Any]] = []
        with conn.cursor() as cur:
            for label in months:
                cur.execute("""
                SELECT MAX(`UploadID`) AS uid
                FROM `uploads`
                WHERE `agent_code`=%s AND `month_year`=%s
                AND `doc_type`='STATEMENT' AND `is_active`=1
                """, (agent_code, label))
                s = cur.fetchone() or {}
                s_uid = _as_int(s.get('uid'))

                cur.execute("""
                SELECT MAX(`UploadID`) AS uid
                FROM `uploads`
                WHERE `agent_code`=%s AND `month_year`=%s
                AND `doc_type`='SCHEDULE' AND `is_active`=1
                """, (agent_code, label))
                sc = cur.fetchone() or {}
                sc_uid = _as_int(sc.get('uid'))

                out.append({
                    "month_year": label,
                    "statement": bool(s_uid),
                    "schedule": bool(sc_uid),
                    "statement_upload_id": s_uid,
                    "schedule_upload_id": sc_uid,
                })
        return {"count": len(out), "items": out}
    finally:
        conn.close()

@router.get('/uploads/tracker.csv')
def uploads_tracker_csv(agent_code: str, months_back: int = 36):
    res = uploads_tracker(agent_code=agent_code, months_back=months_back)
    rows = res.get("items", [])
    csv_rows = []
    for r in rows:
        csv_rows.append({
            "month_year": r.get("month_year"),
            "statement": 1 if r.get("statement") else 0,
            "schedule": 1 if r.get("schedule") else 0,
            "statement_upload_id": r.get("statement_upload_id"),
            "schedule_upload_id": r.get("schedule_upload_id"),
        })
    return _dicts_to_csv_stream(csv_rows, field_order=[
        "month_year","statement","schedule","statement_upload_id","schedule_upload_id"
    ])
