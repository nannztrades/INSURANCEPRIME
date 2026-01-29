
# src/api/agent_reports.py
from __future__ import annotations

from decimal import Decimal
from mimetypes import guess_type
from pathlib import Path
from typing import Any, Dict, Optional, List, Callable, cast
import csv
import io
import os
import importlib

from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse

from src.ingestion.commission import (
    compute_expected_for_upload_dynamic,
    insert_expected_rows,
)
from src.ingestion.db import get_conn

# --- Robust dynamic import to satisfy Pylance and runtime ---
# We bind required functions from src.reports.monthly_reports at runtime.
_mr = importlib.import_module("src.reports.monthly_reports")

# period key normalizer: prefer _period_key_from_month_year, fallback to period_key_from_month_year, then _safe_period_key
_period_key_from_month_year_fn: Optional[Callable[[str], Optional[str]]] = None
for _candidate in (
    getattr(_mr, "_period_key_from_month_year", None),
    getattr(_mr, "period_key_from_month_year", None),
    getattr(_mr, "_safe_period_key", None),
):
    if callable(_candidate):
        _period_key_from_month_year_fn = cast(Callable[[str], Optional[str]], _candidate)
        break

# Required public helpers: validate presence, then cast to precise types
_tmp_compute = getattr(_mr, "compute_month_summary", None)
if not callable(_tmp_compute):
    raise RuntimeError("monthly_reports.compute_month_summary is required but was not found or not callable")
_compute_month_summary: Callable[[str, str], Dict[str, Any]] = cast(
    Callable[[str, str], Dict[str, Any]], _tmp_compute
)

_tmp_build = getattr(_mr, "build_csv_rows", None)
if not callable(_tmp_build):
    raise RuntimeError("monthly_reports.build_csv_rows is required but was not found or not callable")
_build_csv_rows: Callable[[str, str, str], List[List[Any]]] = cast(
    Callable[[str, str, str], List[List[Any]]], _tmp_build
)

_tmp_local_gcs = getattr(_mr, "local_and_gcs", None)
if not callable(_tmp_local_gcs):
    raise RuntimeError("monthly_reports.local_and_gcs is required but was not found or not callable")
_local_and_gcs: Callable[[str, str, str, Path, Optional[int]], Dict[str, Any]] = cast(
    Callable[[str, str, str, Path, Optional[int]], Dict[str, Any]], _tmp_local_gcs
)

def _period_key_from_month_year_proxy(month_year: str) -> str:
    """
    Delegate to whichever normalizer exists in monthly_reports.
    Returns a canonical 'YYYY-MM' (or the best-available normalized key).
    """
    if _period_key_from_month_year_fn is None:
        # As a last resort, normalize similar to DB-side logic
        return (month_year or "").replace("COM_", "").replace("/", "-").strip()
    out = _period_key_from_month_year_fn(month_year)
    if not out:
        return (month_year or "").replace("COM_", "").replace("/", "-").strip()
    return out

router = APIRouter(prefix="/api/agent", tags=["Agent Reports"])

def _active_upload_id(agent_code: str, month_year: str) -> Optional[int]:
    """
    Return the latest active STATEMENT upload_id for an agent+month_year, or None.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT `UploadID`
                FROM `uploads`
                WHERE `agent_code`=%s
                  AND `month_year`=%s
                  AND `doc_type`='STATEMENT'
                  AND `is_active`=1
                ORDER BY `UploadID` DESC
                LIMIT 1
                """,
                (agent_code, month_year),
            )
            r = cur.fetchone() or {}
            return r.get("UploadID")
    finally:
        conn.close()

def _insert_monthly_report_row(
    conn,
    agent_code: str,
    agent_name: str,
    report_period: str,
    upload_id: Optional[int],
    summary: dict,
    pdf_path: Optional[str],
) -> int:
    from datetime import datetime as _dt
    import os as _os

    commission = summary.get("commission", {}) or {}
    reported = commission.get("reported", {}) or {}
    expected = commission.get("expected", {}) or {}
    total_reported = Decimal(str(reported.get("net", 0.0)))
    total_expected = Decimal(str(expected.get("net", 0.0)))
    variance_amount = total_reported - total_expected
    variance_percentage = Decimal("0.00")
    if total_expected != Decimal("0.00"):
        variance_percentage = (variance_amount / total_expected * Decimal("100")).quantize(Decimal("0.01"))

    audit_counts = summary.get("audit_counts", {}) or {}
    missing_policies_count = len(summary.get("missing_all", []) or [])
    commission_mismatches_count = int(audit_counts.get("commission_mismatches", 0) or 0)
    data_quality_issues_count = int(audit_counts.get("data_quality_issues", 0) or 0)
    terminated_policies_count = int(audit_counts.get("terminated_policies_in_month", 0) or 0)
    overall_status = "OK"
    if (
        missing_policies_count > 0
        or terminated_policies_count > 0
        or data_quality_issues_count > 0
    ):
        overall_status = "ATTENTION"

    now_dt = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf_size = 0
    try:
        pdf_size = _os.path.getsize(pdf_path) if pdf_path else 0
    except Exception:
        pdf_size = 0

    sql = """
    INSERT INTO `monthly_reports`
    (`agent_code`,`agent_name`,`report_period`,`upload_id`,
     `policies_reported`,`total_premium`,`total_commission_reported`,
     `total_commission_expected`,`variance_amount`,`variance_percentage`,
     `missing_policies_count`,`commission_mismatches_count`,`data_quality_issues_count`,
     `terminated_policies_count`,`overall_status`,`report_html`,
     `report_pdf_path`,`report_pdf_s3_url`,`report_pdf_size_bytes`,
     `report_pdf_generated_at`,`generated_at`)
    VALUES
    (%s,%s,%s,%s,
     %s,%s,%s,
     %s,%s,%s,
     %s,%s,%s,
     %s,%s,%s,
     %s,%s,%s,
     %s,%s)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                agent_code,
                agent_name,
                report_period,
                upload_id,
                int(summary.get("policies_reported", 0)),
                float(summary.get("total_premium_reported", 0.0)),
                float(total_reported),
                float(total_expected),
                float(variance_amount),
                float(variance_percentage),
                missing_policies_count,
                commission_mismatches_count,
                data_quality_issues_count,
                terminated_policies_count,
                overall_status,
                None,  # report_html
                pdf_path or None,
                None,  # report_pdf_s3_url
                int(pdf_size),
                now_dt if pdf_path else None,
                now_dt,
            ),
        )
        conn.commit()
        return 1

def _select_schedule_latest(conn, agent_code: str, limit: int, offset: int) -> List[Dict[str, Any]]:
    """
    Uses canonical YYYY-MM ordering.
    """
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

@router.post("/reports/generate")
def generate_report(
    agent_code: str = Form(...),
    month_year: str = Form(...),
    upload_id: Optional[int] = Form(None),
    agent_name: Optional[str] = Form(None),
    out: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    skip_pdf: bool = Form(False),
    dry_run: bool = Form(False),
) -> Dict[str, Any]:
    # Resolve upload_id if not provided
    resolved_upload_id = upload_id if upload_id is not None else _active_upload_id(agent_code, month_year)

    # Dynamic expected rows for this upload
    rows: List[Dict[str, Any]] = []
    inserted = 0
    if resolved_upload_id is not None:
        rows = compute_expected_for_upload_dynamic(resolved_upload_id)
        rows_agent = [r for r in rows if r.get("agent_code") == agent_code]
        if not dry_run:
            inserted = insert_expected_rows(rows_agent)

    # Enriched summary
    summary = _compute_month_summary(agent_code, month_year)

    # Output dir
    reports_dir = Path(out or os.getenv("REPORTS_DIR", "reports"))
    pdf_meta: Optional[Dict[str, Any]] = None
    if not skip_pdf:
        try:
            pdf_meta = _local_and_gcs(agent_code, agent_name or agent_code, month_year, reports_dir, user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    # Monthly_reports insert
    report_period = _period_key_from_month_year_proxy(month_year)
    conn = get_conn()
    try:
        _insert_monthly_report_row(
            conn,
            agent_code,
            agent_name or agent_code,
            report_period,
            resolved_upload_id,
            summary,
            (pdf_meta or {}).get("pdf_path") if pdf_meta else None,
        )
    finally:
        conn.close()

    # Best-effort discrepancies emission
    try:
        from src.audit.discrepancies import emit_discrepancies_for_month
        emit_discrepancies_for_month(agent_code, month_year)
    except Exception:
        pass

    return {
        "status": "SUCCESS",
        "agent_code": agent_code,
        "agent_name": agent_name or agent_code,
        "month_year": month_year,
        "report_period": report_period,
        "upload_id_used": resolved_upload_id,
        "expected_rows_inserted": inserted,
        "pdf": pdf_meta or None,
        "summary": summary,
    }

@router.get("/reports")
def list_reports(agent_code: str, month_year: str) -> Dict[str, Any]:
    conn = get_conn()
    try:
        period = _period_key_from_month_year_proxy(month_year)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT `report_id`,`report_period`,`upload_id`,
                       `report_pdf_path`,`report_pdf_size_bytes`,`generated_at`
                FROM `monthly_reports`
                WHERE `agent_code`=%s AND `report_period`=%s
                ORDER BY `report_id` DESC
                """,
                (agent_code, period),
            )
            rows = cur.fetchall() or []
        return {"count": len(rows), "items": rows}
    finally:
        conn.close()

@router.get("/reports/download/{report_id}")
def download_report(report_id: int) -> FileResponse:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT `report_pdf_path` FROM `monthly_reports` WHERE `report_id`=%s",
                (report_id,),
            )
            r = cur.fetchone() or {}
        pdf_path = r.get("report_pdf_path")
        if not pdf_path:
            raise HTTPException(status_code=404, detail="PDF path not found for report")
        p = Path(str(pdf_path))
        if not p.exists():
            raise HTTPException(status_code=404, detail="PDF file not found on disk")
        mt, _ = guess_type(p.name)
        return FileResponse(path=str(p), media_type=mt or "application/octet-stream", filename=p.name)
    finally:
        conn.close()

@router.get("/reports/export-csv")
def export_report_csv(
    agent_code: str, month_year: str, agent_name: Optional[str] = None
) -> StreamingResponse:
    try:
        rows = _build_csv_rows(agent_code, agent_name or agent_code, month_year)
        buf = io.StringIO()
        writer = csv.writer(buf)
        for r in rows:
            writer.writerow(r)
        buf.seek(0)
        period = _period_key_from_month_year_proxy(month_year)
        filename = f"ICRS_{agent_code}_{period}.csv"
        headers = {
            "Content-Type": "text/csv; charset=utf-8",
            "Content-Disposition": f'attachment; filename="{filename}"',
        }
        return StreamingResponse(buf, headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
