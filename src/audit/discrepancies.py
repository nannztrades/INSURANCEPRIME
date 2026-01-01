
# src/audit/discrepancies.py
from __future__ import annotations
from typing import List, Dict, Any, Optional
from decimal import Decimal
from datetime import datetime

from src.ingestion.db import get_conn
from src.reports.monthly_reports import (
    _fetch_discrepancies_multiple_entries,
    _fetch_discrepancies_inception_vs_first_seen,
    _fetch_discrepancies_arrears,
    _fetch_should_be_terminated,
    _period_key_from_month_year
)

def _insert_discrepancies(rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            params = []
            for r in rows:
                params.append((
                    r['agent_code'], r.get('policy_no'), r['period'], r.get('month_year'),
                    r.get('diff_amount'), r.get('statement_id'), r.get('severity'), r.get('notes'), r.get('type')
                ))
            # Use ON DUPLICATE if unique index exists
            cur.executemany("""
                INSERT INTO `discrepancies`
                (`agent_code`,`policy_no`,`period`,`month_year`,`diff_amount`,
                 `statement_id`,`severity`,`notes`,`type`)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  `diff_amount`=VALUES(`diff_amount`),
                  `severity`=VALUES(`severity`),
                  `notes`=VALUES(`notes`)
            """, params)
        conn.commit()
        return len(rows)
    finally:
        conn.close()

def emit_discrepancies_for_month(agent_code: str, month_year: str) -> int:
    """
    Compute discrepancies and emit to DB for dashboard.
    """
    period = _period_key_from_month_year(month_year) or month_year

    # Gather
    dups = _fetch_discrepancies_multiple_entries(agent_code, month_year)
    incs = _fetch_discrepancies_inception_vs_first_seen(agent_code, month_year)
    arrs = _fetch_discrepancies_arrears(agent_code, month_year)
    sbt  = _fetch_should_be_terminated(agent_code, month_year)

    rows: List[Dict[str, Any]] = []

    # MULTIPLE_ENTRIES_IN_MONTH
    for r in dups:
        rows.append({
            "agent_code": agent_code,
            "policy_no": r.get("policy_no"),
            "period": period,
            "month_year": month_year,
            "diff_amount": None,
            "statement_id": None,
            "severity": "MED",
            "notes": f"entries={r.get('entries')}",
            "type": "MULTIPLE_ENTRIES_IN_MONTH",
        })

    # INCEPTION_FIRST_SEEN_INCONSISTENCY
    for r in incs:
        notes = f"inception={r.get('inception')},first_seen={r.get('first_seen_date')}"
        rows.append({
            "agent_code": agent_code,
            "policy_no": r.get("policy_no"),
            "period": period,
            "month_year": month_year,
            "diff_amount": None,
            "statement_id": None,
            "severity": "HIGH",
            "notes": notes,
            "type": "INCEPTION_FIRST_SEEN_INCONSISTENCY",
        })

    # ARREARS_SUSPECT
    for r in arrs:
        total = r.get("total_premium")
        notes = f"entries={r.get('entries')},sum_premium={total}"
        rows.append({
            "agent_code": agent_code,
            "policy_no": r.get("policy_no"),
            "period": period,
            "month_year": month_year,
            "diff_amount": float(Decimal(str(total or 0.0))),
            "statement_id": None,
            "severity": "MED",
            "notes": notes,
            "type": "ARREARS_SUSPECT",
        })

    # SHOULD_BE_TERMINATED
    for r in sbt:
        rows.append({
            "agent_code": agent_code,
            "policy_no": r.get("policy_no"),
            "period": period,
            "month_year": month_year,
            "diff_amount": None,
            "statement_id": None,
            "severity": "HIGH",
            "notes": "Appears after termination recorded earlier/equal to month",
            "type": "SHOULD_BE_TERMINATED",
        })

    return _insert_discrepancies(rows)
