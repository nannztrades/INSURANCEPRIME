
# src/cli/expected_for_upload.py
from __future__ import annotations
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import os

from src.ingestion.db import get_conn
from src.ingestion.commission import compute_expected_for_upload_dynamic, insert_expected_rows
from src.reports.monthly_reports import local_and_gcs, _period_key_from_month_year, compute_month_summary

# --- Monthly Reports Row ---
def _insert_monthly_report_row(
    conn: Any,
    agent_code: str,
    agent_name: str,
    report_period: str,  # canonical YYYY-MM
    upload_id: int,
    summary: dict,
    pdf_path: Optional[str],
) -> int:
    from decimal import Decimal
    total_reported = Decimal(str(summary.get('total_commission_reported', 0.0)))
    total_expected = Decimal(str(summary.get('total_commission_expected', 0.0)))
    variance_amount = total_reported - total_expected
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
            agent_code,
            agent_name,
            report_period,
            upload_id,
            int(summary.get('policies_reported', 0)),
            float(summary.get('total_premium', 0.0)),
            float(summary.get('total_commission_reported', 0.0)),
            float(summary.get('total_commission_expected', 0.0)),
            float(variance_amount),
            float(variance_percentage),
            int(summary.get('missing_policies_count', 0)),
            int(summary.get('commission_mismatches_count', 0)),
            int(summary.get('data_quality_issues_count', 0)) if summary.get('data_quality_issues_count') is not None else 0,
            int(summary.get('terminated_policies_count', 0)),
            overall_status,
            None,  # report_html
            pdf_path or None,
            None,  # report_pdf_s3_url (unused now)
            int(pdf_size),
            now_dt if pdf_path else None,
            now_dt,
        ))
        conn.commit()
    return 1

# --- Monitoring (CLI runs) ---
def _ensure_cli_runs_table(conn: Any) -> None:
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS `cli_runs` (
          `run_id` INT NOT NULL AUTO_INCREMENT,
          `started_at` DATETIME NOT NULL,
          `ended_at` DATETIME NULL,
          `status` VARCHAR(20) NOT NULL,
          `message` TEXT NULL,
          `upload_id` INT NULL,
          `agent_code` VARCHAR(50) NULL,
          `report_period` VARCHAR(20) NULL,
          `expected_rows_computed` INT NULL,
          `expected_rows_inserted` INT NULL,
          `pdf_path` VARCHAR(255) NULL,
          PRIMARY KEY (`run_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
        """)
        conn.commit()

def _log_cli_run_file(record: dict) -> None:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "cli_runs.log"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

def _log_cli_run_db(conn: Any, record: dict) -> None:
    try:
        _ensure_cli_runs_table(conn)
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO `cli_runs`
            (`started_at`,`ended_at`,`status`,`message`,
             `upload_id`,`agent_code`,`report_period`,
             `expected_rows_computed`,`expected_rows_inserted`,`pdf_path`)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                record["started_at"],
                record.get("ended_at"),
                record["status"],
                record.get("message"),
                record.get("upload_id"),
                record.get("agent_code"),
                record.get("report_period"),
                record.get("expected_rows_computed"),
                record.get("expected_rows_inserted"),
                record.get("pdf_path"),
            ))
        conn.commit()
    except Exception as e:
        record["status"] = f"{record['status']} (file)"
        record["message"] = f"{record.get('message','')} db-log-failed: {e}"
        _log_cli_run_file(record)

# --- Utility ---
def _agent_list_for_scope(upload_id: Optional[int], month_year: Optional[str]) -> List[str]:
    """
    Returns distinct agent codes for the given upload or month label.
    Prefers upload_id when provided.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if upload_id is not None:
                cur.execute("""
                SELECT DISTINCT `agent_code`
                FROM `statement`
                WHERE `upload_id`=%s
                ORDER BY `agent_code`
                """, (upload_id,))
            else:
                cur.execute("""
                SELECT DISTINCT `agent_code`
                FROM `statement`
                WHERE `MONTH_YEAR`=%s
                ORDER BY `agent_code`
                """, (month_year,))
            rows = cur.fetchall() or []
            return [str(r.get("agent_code")) for r in rows if r.get("agent_code")]
    finally:
        conn.close()

# --- Main CLI ---
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compute expected commissions, insert, render timestamped PDF, and log monthly report."
    )
    ap.add_argument("--upload-id", type=int, required=True, help="Statement upload_id.")
    ap.add_argument("--agent-code", type=str, required=True, help="Agent code or 'ALL'.")
    ap.add_argument("--agent-name", type=str, help="Agent name (ignored for ALL).")
    # Env-driven and cross-platform default for reports output
    ap.add_argument(
        "--out",
        type=str,
        default=os.getenv("REPORTS_DIR", "data/reports"),
        help="Base reports directory (default: $REPORTS_DIR or 'data/reports').",
    )
    ap.add_argument("--month-year", type=str, required=True, help="Month label (e.g., 'Jun 2025' or 'COM_JUN_2025').")
    ap.add_argument("--user-id", type=int, help="ID of the user triggering the report (prefixes the PDF filename).")
    ap.add_argument("--skip-pdf", action="store_true", help="Skip PDF generation.")
    ap.add_argument("--dry-run", action="store_true", help="Compute only; do not insert expected rows.")
    ap.add_argument("--verbose", action="store_true", help="Verbose console output.")
    args = ap.parse_args()

    # Ensure reports directory exists
    Path(args.out).mkdir(parents=True, exist_ok=True)

    started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Batch mode
    if args.agent_code.strip().upper() == "ALL":
        agents = _agent_list_for_scope(args.upload_id, args.month_year)
        if args.verbose:
            print(f"[batch] agents: {agents}")
        if not agents:
            print("[batch] No agents found for the given scope.")
            return

        # Map agent names
        name_map: Dict[str, str] = {}
        conn_info = get_conn()
        try:
            with conn_info.cursor() as cur:
                cur.execute("SELECT `agent_code`,`agent_name` FROM `agents`")
                for r in cur.fetchall() or []:
                    code = str(r.get("agent_code"))
                    name = str(r.get("agent_name") or code)
                    name_map[code] = name
        finally:
            conn_info.close()

        results: List[Dict[str, Any]] = []
        for ac in agents:
            an = name_map.get(ac, ac)
            results.append(_run_single_agent(args, ac, an, started_at))

        print(json.dumps({
            "mode": "ALL",
            "upload_id": args.upload_id,
            "month_year": args.month_year,
            "out": args.out,
            "count": len(results),
            "results": results,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }, indent=2))
    else:
        # Single agent mode
        if not args.agent_name:
            ap.error("--agent-name is required in SINGLE mode")
        result = _run_single_agent(args, args.agent_code, args.agent_name, started_at)
        print(json.dumps(result, indent=2))

def _run_single_agent(args: Any, agent_code: str, agent_name: str, started_at: str) -> Dict[str, Any]:
    # Compute expected rows (all agents for upload)
    rows = compute_expected_for_upload_dynamic(args.upload_id)
    if args.verbose:
        print(f"[compute-{agent_code}] rows: {len(rows)}")

    # Filter for this agent
    rows_agent = [r for r in rows if r.get('agent_code') == agent_code]

    # Insert expected rows (unless dry-run)
    inserted = 0
    if not args.dry_run:
        inserted = insert_expected_rows(rows_agent)
    if args.verbose:
        print(f"[insert-{agent_code}] inserted: {inserted}")

    # Render PDF (unless skip)
    pdf_meta = None
    if not args.skip_pdf:
        Path(args.out).mkdir(parents=True, exist_ok=True)
        pdf_meta = local_and_gcs(agent_code, agent_name, args.month_year, Path(args.out), args.user_id)
    if args.verbose:
        print(f"[pdf-{agent_code}] {pdf_meta}")

    # Summary & monthly_reports insert
    summary = compute_month_summary(agent_code, args.month_year)
    report_period = _period_key_from_month_year(args.month_year) or args.month_year.replace('COM_', '').replace(' ', '-')

    conn = get_conn()
    try:
        _insert_monthly_report_row(
            conn=conn,
            agent_code=agent_code,
            agent_name=agent_name,
            report_period=report_period,
            upload_id=args.upload_id,
            summary=summary,
            pdf_path=(pdf_meta or {}).get('pdf_path') if pdf_meta else None,
        )
    finally:
        conn.close()

    # Emit discrepancies after insert
    from src.audit.discrepancies import emit_discrepancies_for_month
    emit_discrepancies_for_month(agent_code, args.month_year)

    # Monitoring log
    record = {
        "started_at": started_at,
        "ended_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "SUCCESS",
        "message": None,
        "upload_id": args.upload_id,
        "agent_code": agent_code,
        "report_period": report_period,
        "expected_rows_computed": len(rows_agent),
        "expected_rows_inserted": inserted,
        "pdf_path": (pdf_meta or {}).get('pdf_path') if pdf_meta else None,
    }
    conn2 = get_conn()
    try:
        _log_cli_run_db(conn2, record)
    finally:
        conn2.close()

    return {
        "mode": "SINGLE",
        "upload_id": args.upload_id,
        "agent_code": agent_code,
        "agent_name": agent_name,
        "month_year": args.month_year,
        "report_period": report_period,
        "expected_rows_computed": record["expected_rows_computed"],
        "expected_rows_inserted": inserted,
        "pdf": pdf_meta or None,
        "summary": summary,
        "timestamp": record["ended_at"],
    }

if __name__ == "__main__":
    main()
