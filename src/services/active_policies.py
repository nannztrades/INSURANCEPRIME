# src/services/active_policies.py
from __future__ import annotations

from typing import Optional, Dict, Any, List

from src.ingestion.db import get_conn
from src.services.periods import canonicalize_period

"""
Maintain a snapshot of active policies as of a given month (period_key: YYYY-MM).

- first_seen_date: earliest period_date from statement
- last_seen_date:  latest period_date from statement
- last_premium:    premium in the last_seen_date row
- last_com_rate:   com_rate in the last_seen_date row

Excludes policies that have been terminated on or before the target period.
"""

def refresh_active_policies(
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Recompute active_policies up to and including 'month_year' (if given),
    optionally filtering by agent_code.

    If month_year is None, uses all historical data and excludes any policy
    that was ever terminated (period_key <= MAX(period_key) in terminated).
    """
    # Derive canonical cut-off period_key (YYYY-MM) or None
    period_key_limit: Optional[str] = None
    if month_year:
        period_key_limit = canonicalize_period(month_year)
        if not period_key_limit:
            raise ValueError(f"Invalid month_year for active_policies: {month_year}")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # 1) Compute set of terminated policies up to limit
            term_sql = "SELECT DISTINCT `policy_no` FROM `terminated` WHERE 1=1"
            term_params: List[Any] = []
            if agent_code:
                term_sql += " AND `agent_code`=%s"
                term_params.append(agent_code)
            if period_key_limit:
                term_sql += " AND `period_key` <= %s"
                term_params.append(period_key_limit)

            cur.execute(term_sql, tuple(term_params))
            terminated = {
                r.get("policy_no")
                for r in (cur.fetchall() or [])
                if r.get("policy_no")
            }

            # 2) Pull statement rows up to limit
            stmt_sql = """
                SELECT
                    `policy_no`,
                    `agent_code`,
                    `period_date`,
                    `period_key`,
                    `premium`,
                    `com_rate`
                FROM `statement`
                WHERE 1=1
            """
            stmt_params: List[Any] = []
            if agent_code:
                stmt_sql += " AND `agent_code`=%s"
                stmt_params.append(agent_code)
            if period_key_limit:
                stmt_sql += " AND `period_key` <= %s"
                stmt_params.append(period_key_limit)

            cur.execute(stmt_sql, tuple(stmt_params))
            rows = cur.fetchall() or []

            # 3) Aggregate first_seen / last_seen info
            agg: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                p = r.get("policy_no")
                if not p or p in terminated:
                    continue
                ac = r.get("agent_code")
                pd = r.get("period_date")
                prem = r.get("premium")
                cr = r.get("com_rate")
                if p not in agg:
                    agg[p] = {
                        "policy_no": p,
                        "agent_code": ac,
                        "first_seen_date": pd,
                        "last_seen_date": pd,
                        "last_premium": prem,
                        "last_com_rate": cr,
                    }
                else:
                    # update if newer period_date
                    cur_last = agg[p]["last_seen_date"]
                    if pd and (cur_last is None or pd > cur_last):
                        agg[p]["last_seen_date"] = pd
                        agg[p]["last_premium"] = prem
                        agg[p]["last_com_rate"] = cr
                    # keep agent_code sync
                    agg[p]["agent_code"] = ac

            # 4) Upsert into active_policies
            upsert_sql = """
                INSERT INTO `active_policies`
                    (`policy_no`,
                     `agent_code`,
                     `first_seen_date`,
                     `last_seen_date`,
                     `last_premium`,
                     `last_com_rate`,
                     `last_seen_month_year`)
                VALUES (%s,%s,%s,%s,%s,%s,
                        DATE_FORMAT(%s, '%%Y-%%m'))
                ON DUPLICATE KEY UPDATE
                  `agent_code` = VALUES(`agent_code`),
                  `first_seen_date` = LEAST(`first_seen_date`, VALUES(`first_seen_date`)),
                  `last_seen_date`  = GREATEST(`last_seen_date`,  VALUES(`last_seen_date`)),
                  `last_premium`    = VALUES(`last_premium`),
                  `last_com_rate`   = VALUES(`last_com_rate`),
                  `last_seen_month_year` = VALUES(`last_seen_month_year`)
            """

            inserted = 0
            for v in agg.values():
                last_seen_date = v["last_seen_date"]
                cur.execute(
                    upsert_sql,
                    (
                        v["policy_no"],
                        v["agent_code"],
                        v["first_seen_date"],
                        last_seen_date,
                        v["last_premium"],
                        v["last_com_rate"],
                        last_seen_date,
                    ),
                )
                inserted += cur.rowcount

            conn.commit()
            return {
                "status": "SUCCESS",
                "policies_upserted": inserted,
                "scope_rows": len(rows),
                "terminated_excluded": len(terminated),
                "period_key_limit": period_key_limit,
            }
    finally:
        conn.close()