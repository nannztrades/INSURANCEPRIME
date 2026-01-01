
# src/services/active_policies.py
from __future__ import annotations

from typing import Optional, Dict, Any, List
from src.ingestion.db import get_conn

"""
Refresh active_policies snapshot up to a given month_year (e.g., 'Jun 2025')
or for a specific agent:
  - first_seen_date: earliest period_date for the policy (from statement)
  - last_seen_date: latest period_date for the policy (from statement)
  - last_premium: last premium observed
Excludes policies terminated up to and including month_year.
"""

def refresh_active_policies(agent_code: Optional[str] = None, month_year: Optional[str] = None) -> Dict[str, Any]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Build the set of terminated policies up to month_year (optional agent filter)
            term_params: List[Any] = []
            term_sql = "SELECT DISTINCT `policy_no` FROM `terminated` WHERE 1=1"
            if agent_code:
                term_sql += " AND `agent_code`=%s"; term_params.append(agent_code)
            if month_year:
                term_sql += " AND `month_year`<=%s"; term_params.append(month_year)
            cur.execute(term_sql, tuple(term_params))
            terminated = {r.get("policy_no") for r in (cur.fetchall() or []) if r.get("policy_no")}

            # Statements up to month_year (optional agent filter)
            stmt_params: List[Any] = []
            stmt_sql = (
                "SELECT `policy_no`,`agent_code`,`period_date`,`premium` "
                "FROM `statement` WHERE 1=1"
            )
            if agent_code:
                stmt_sql += " AND `agent_code`=%s"; stmt_params.append(agent_code)
            if month_year:
                stmt_sql += " AND `MONTH_YEAR`<=%s"; stmt_params.append(month_year)

            cur.execute(stmt_sql, tuple(stmt_params))
            rows = cur.fetchall() or []

            # Aggregate first_seen/last_seen/last_premium
            agg: Dict[str, Dict[str, Any]] = {}
            for r in rows:
                p = r.get("policy_no")
                if not p or p in terminated:
                    continue
                ac = r.get("agent_code")
                pd = r.get("period_date")
                prem = r.get("premium")
                if p not in agg:
                    agg[p] = {
                        "policy_no": p,
                        "agent_code": ac,
                        "first_seen_date": pd,
                        "last_seen_date": pd,
                        "last_premium": prem,
                    }
                else:
                    # Update latest observation
                    if pd and agg[p]["last_seen_date"] and pd > agg[p]["last_seen_date"]:
                        agg[p]["last_seen_date"] = pd
                        agg[p]["last_premium"] = prem
                    # Keep agent code in sync
                    agg[p]["agent_code"] = ac

            # Upsert into active_policies
            upsert_sql = """
                INSERT INTO `active_policies`
                    (`policy_no`,`agent_code`,`first_seen_date`,`last_seen_date`,`last_premium`)
                VALUES (%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  `agent_code` = VALUES(`agent_code`),
                  `first_seen_date` = LEAST(`first_seen_date`, VALUES(`first_seen_date`)),
                  `last_seen_date` = GREATEST(`last_seen_date`, VALUES(`last_seen_date`)),
                  `last_premium` = VALUES(`last_premium`)
            """
            inserted = 0
            for v in agg.values():
                cur.execute(
                    upsert_sql,
                    (
                        v["policy_no"],
                        v["agent_code"],
                        v["first_seen_date"],
                        v["last_seen_date"],
                        v["last_premium"],
                    )
                )
                inserted += cur.rowcount

            conn.commit()
            return {
                "status": "SUCCESS",
                "policies_upserted": inserted,
                "scope_rows": len(rows),
                "terminated_excluded": len(terminated),
            }
    finally:
        conn.close()
