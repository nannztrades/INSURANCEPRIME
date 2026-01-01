
# src/api/agent_reports.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Form
from fastapi.responses import FileResponse
from decimal import Decimal

from src.ingestion.db import get_conn
from src.ingestion.commission import compute_expected_for_upload_dynamic, insert_expected_rows
from src.reports.monthly_reports import (
    local_and_gcs, _period_key_from_month_year, compute_month_summary, _active_upload_id
)

router = APIRouter(prefix="/api/agent", tags=["Agent Reports"])


def _insert_monthly_report_row(
    conn,
    agent_code: str,
    agent_name: str,
    report_period: str,
    upload_id: Optional[int],
    summary: dict,
    pdf_path: Optional[str]
) -> int:
    from datetime import datetime
    import os

    total_reported = Decimal(str(summary.get('total_commission_reported', 0.0)))
    total_expected = Decimal(str(summary.get('total_commission_expected', 0.0)))
    variance_amount = total_reported - total_expected  # Actual - Expected
    variance_percentage = Decimal("0.00")
    if total_expected != Decimal("0.00"):
        variance_percentage = (variance_amount / total_expected * Decimal("100")).quantize(Decimal("0.01"))

    overall_status = "OK"
    if summary.get('missing_policies_count', 0) > 0 or summary.get('terminated_policies_count', 0) > 0:
        overall_status = "ATTENTION"

    now_dt = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    pdf_size = 0
    try:
        pdf_size = os.path.getsize(pdf_path) if pdf_path else 0
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
        cur.execute(sql, (
            agent_code, agent_name, report_period, upload_id,
            int(summary.get('policies_reported', 0)),
            float(summary.get('total_premium', 0.0)),
            float(summary.get('total_commission_reported', 0.0)),
            float(summary.get('total_commission_expected', 0.0)),
            float(variance_amount), float(variance_percentage),
            int(summary.get('missing_policies_count', 0)),
            int(summary.get('commission_mismatches_count', 0)),
            int(summary.get('data_quality_issues_count', 0)) if summary.get('data_quality_issues_count') is not None else 0,
            int(summary.get('terminated_policies_count', 0)),
            overall_status,
            None,
            pdf_path or None,
            None,
            int(pdf_size),
            now_dt if pdf_path else None,
            now_dt,
        ))
    conn.commit()
    return 1


@router.post('/reports/generate')
def generate_report(
    agent_code: str = Form(...),
    month_year: str = Form(...),
    upload_id: Optional[int] = Form(None),            # optional
    agent_name: Optional[str] = Form(None),
    out: str = Form("D:/PROJECT/INSURANCELOCAL/reports"),
    user_id: Optional[int] = Form(None),
    skip_pdf: bool = Form(False),
    dry_run: bool = Form(False),
) -> Dict[str, Any]:
    """
    If upload_id is not provided, automatically resolves using the latest active statement upload.
    """
    resolved_upload_id = upload_id if upload_id is not None else _active_upload_id(agent_code, month_year)

    rows = []
    inserted = 0
    if resolved_upload_id is not None:
        rows = compute_expected_for_upload_dynamic(resolved_upload_id)
        rows_agent = [r for r in rows if r.get('agent_code') == agent_code]
        if not dry_run:
            inserted = insert_expected_rows(rows_agent)

    pdf_meta = None
    if not skip_pdf:
        pdf_meta = local_and_gcs(agent_code, agent_name or agent_code, month_year, Path(out), user_id)

    summary = compute_month_summary(agent_code, month_year)
    report_period = _period_key_from_month_year(month_year) or month_year.replace('COM_', '').replace(' ', '-')

    conn = get_conn()
    try:
        _insert_monthly_report_row(
            conn, agent_code, agent_name or agent_code, report_period,
            resolved_upload_id, summary, (pdf_meta or {}).get('pdf_path') if pdf_meta else None
        )
    finally:
        conn.close()

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


@router.get('/reports')
def list_reports(agent_code: str, month_year: str) -> Dict[str, Any]:
    conn = get_conn()
    try:
        period = _period_key_from_month_year(month_year) or month_year.replace('COM_', '').replace(' ', '-')
        with conn.cursor() as cur:
            cur.execute("""
                SELECT `report_id`,`report_period`,`upload_id`,`report_pdf_path`,`report_pdf_size_bytes`,`generated_at`
                FROM `monthly_reports`
                WHERE `agent_code`=%s AND `report_period`=%s
                ORDER BY `report_id` DESC
            """, (agent_code, period))
            rows = cur.fetchall() or []
        return {"count": len(rows), "items": rows}
    finally:
        conn.close()


@router.get('/reports/download/{report_id}')
def download_report(report_id: int) -> FileResponse:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT `report_pdf_path` FROM `monthly_reports` WHERE `report_id`=%s", (report_id,))
            r = cur.fetchone() or {}
            pdf_path = r.get('report_pdf_path')
        if not pdf_path:
            raise HTTPException(status_code=404, detail="PDF path not found for report")
        p = Path(str(pdf_path))
        if not p.exists():
            raise HTTPException(status_code=404, detail="PDF file not found on disk")
        return FileResponse(path=str(p), media_type='application/pdf', filename=p.name)
    finally:
        conn.close()


@router.get('/summary')
def summary(agent_code: str, month_year: str) -> Dict[str, Any]:
    return compute_month_summary(agent_code, month_year)
