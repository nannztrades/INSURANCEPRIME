
# src/ingestion/audit_flags.py
from __future__ import annotations
from typing import Optional, Dict, List
from datetime import datetime
from .db import get_conn

def emit_supposed_to_be_terminated(period_date_iso: str) -> int:
    """
    Flag policies that appear in `statement` AFTER their recorded termination_date.
    period_date_iso: 'YYYY-MM-DD' anchor for the month being audited (e.g., '2025-07-28').
    """
    conn = get_conn()
    try:
        inserted = 0
        with conn.cursor() as cur:
            # Find policies terminated on or before period, but still present in statements after that termination
            cur.execute("""
                SELECT s.`policy_no`, s.`agent_code`, s.`MONTH_YEAR`, s.`statement_id`
                FROM `statement` s
                JOIN `terminated` t ON t.`policy_no` = s.`policy_no`
                WHERE t.`termination_date` IS NOT NULL
                  AND s.`period_date` > t.`termination_date`
            """)
            rows = cur.fetchall()
            for r in rows:
                cur.execute("""
                    INSERT INTO `audit_flags`
                    (`agent_code`,`policy_no`,`month_year`,`flag_type`,`severity`,`flag_detail`,`created_at`,`resolved`)
                    VALUES (%s,%s,%s,%s,%s,%s,NOW(),0)
                """, (
                    r.get('agent_code'), r.get('policy_no'), r.get('MONTH_YEAR'),
                    'SUPPOSED_TO_BE_TERMINATED', 'high',
                    'Appeared in statement after termination date'
                ))
                inserted += cur.rowcount
        conn.commit()
        return inserted
    finally:
        conn.close()

def emit_multiple_entries_in_month(period_month_year: str) -> int:
    """
    Flag policies that appear multiple times in the same MONTH_YEAR (duplicate rows).
    """
    conn = get_conn()
    try:
        inserted = 0
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.`policy_no`, s.`agent_code`, s.`MONTH_YEAR`, COUNT(*) AS cnt
                FROM `statement` s
                WHERE s.`MONTH_YEAR`=%s
                GROUP BY s.`policy_no`, s.`agent_code`, s.`MONTH_YEAR`
                HAVING cnt > 1
            """, (period_month_year,))
            rows = cur.fetchall()
            for r in rows:
                cur.execute("""
                    INSERT INTO `audit_flags`
                    (`agent_code`,`policy_no`,`month_year`,`flag_type`,`severity`,`flag_detail`,`created_at`,`resolved`)
                    VALUES (%s,%s,%s,%s,%s,%s,NOW(),0)
                """, (
                    r.get('agent_code'), r.get('policy_no'), r.get('MONTH_YEAR'),
                    'MULTIPLE_ENTRIES_IN_MONTH', 'medium',
                    f"Duplicate entries in month; count={r.get('cnt')}"
                ))
                inserted += cur.rowcount
        conn.commit()
        return inserted
    finally:
        conn.close()
