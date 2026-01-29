
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch remaining period/ordering issues:
- Add month input normalization across endpoints (YYYY-MM canonical).
- Replace legacy 'Mon YYYY' ORDER BY with canonical YYYY-MM ordering.
- Make disparities API accept YYYY-MM.

Backups:
- Each changed file is saved as <file>.bak once.

Run from repo root:
  (.venv) python tools/patch_period_inputs_and_ordering.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repo root
SRC = ROOT / "src"
TARGETS = [
    SRC / "api" / "admin_reports.py",
    SRC / "api" / "disparities.py",
]
UTIL_PERIODS = SRC / "util" / "periods.py"


def ensure_util_periods():
    if not UTIL_PERIODS.parent.exists():
        UTIL_PERIODS.parent.mkdir(parents=True, exist_ok=True)
    if not UTIL_PERIODS.exists():
        UTIL_PERIODS.write_text(
            """# src/util/periods.py
from typing import Optional
from src.reports.monthly_reports import _period_key_from_month_year

def normalize_month_param(val: Optional[str]) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return s
    p = _period_key_from_month_year(s)
    # fall back to safe replacements if legacy tokens slipped in
    return p or s.replace("COM_", "").replace(" ", "-")
""",
            encoding="utf-8",
        )


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def write(p: Path, s: str):
    p.write_text(s, encoding="utf-8")


def backup_once(p: Path):
    b = p.with_suffix(p.suffix + ".bak")
    if not b.exists():
        b.write_text(read(p), encoding="utf-8")


def replace_block(text: str, func_name: str, new_block: str) -> str:
    """
    Replace def func_name(...) body with new_block (full function text).
    Uses callable replacement to avoid backslash-escape issues.
    """
    pattern = re.compile(
        rf"(^def\s+{re.escape(func_name)}\s*\(.*?\):)(.*?)(?=^\s*def\s+\w+\s*\(|\Z)",
        re.DOTALL | re.MULTILINE,
    )
    if not pattern.search(text):
        return text

    block = new_block.strip() + "\n"

    def _repl(_m):
        return block

    return pattern.sub(_repl, text, count=1)


# ───────────────────────────────────────────────────────────────────────
# New function blocks (drop-in replacements)
# ───────────────────────────────────────────────────────────────────────

ADMIN_UPLOADS_TRACKER = r'''
def uploads_tracker(agent_code: str, months_back: int = 36) -> Dict[str, Any]:
    from src.util.periods import normalize_month_param  # local import to avoid import cycles
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
                    WHERE u.`agent_code`=%s AND u.`month_year`=m.`month_year` AND u.`doc_type`='SCHEDULE')  AS `schedule_upload_id`,
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
            -- canonical YYYY-MM: lexicographic order is correct and fast
            ORDER BY m.`month_year` DESC
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
'''

ADMIN_SELECT_SCHEDULE_LATEST = r'''
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
                ORDER BY sc.`month_year` DESC
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
                ORDER BY sc.`month_year` DESC
                LIMIT %s OFFSET %s
                """,
                (agent_code, limit, offset),
            )
            rows = list(cur.fetchall() or [])
        for r in rows:
            r["siclase"] = r.get("siclase", 0.0) or 0.0
            r["premium_deduction"] = r.get("premium_deduction", 0.0) or 0.0
            r["pensions"] = r.get("pensions", 0.0) or 0.0
            r["welfareko"] = r.get("welfareko", 0.0) or 0.0
        return rows
'''

ADMIN_LIST_STATEMENTS = r'''
def list_statements(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    from src.util.periods import normalize_month_param
    conn = get_conn()
    items: List[Dict[str, Any]] = []
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
            month_year = normalize_month_param(month_year)
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
                holder = it.get("holder")
                s = str(holder or "").strip()
                if s:
                    parts = s.split()
                    sur = parts[0]
                    other = " ".join(parts[1:]) if len(parts) > 1 else ""
                else:
                    sur, other = "", ""
                it["holder_surname"] = sur
                it["other_name"] = other
            return {"count": len(items), "items": items}
    finally:
        conn.close()
'''

ADMIN_LIST_TERMINATED = r'''
def list_terminated(
    upload_id: Optional[int] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    policy_no: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    from src.util.periods import normalize_month_param
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
            month_year = normalize_month_param(month_year)
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
            # enrich names
            for it in items:
                holder = it.get("holder")
                s = str(holder or "").strip()
                if s:
                    parts = s.split()
                    sur = parts[0]
                    other = " ".join(parts[1:]) if len(parts) > 1 else ""
                else:
                    sur, other = "", ""
                it["holder_surname"] = sur
                it["other_name"] = other
            return {"count": len(items), "items": items}
    finally:
        conn.close()
'''

ADMIN_LIST_UPLOADS = r'''
def list_uploads(
    doc_type: Optional[str] = None,
    agent_code: Optional[str] = None,
    month_year: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    from src.util.periods import normalize_month_param
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
            month_year = normalize_month_param(month_year)
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
'''

DISPARITIES_PARSE = r'''
def _parse_month_year(label: str) -> date:
    """
    Accept robust inputs and normalize to first day of month:
    - 'YYYY-MM' (preferred), 'YYYY/MM', 'Mon YYYY', 'Month YYYY', with optional 'COM_' prefix.
    """
    from src.reports.monthly_reports import _period_key_from_month_year
    p = _period_key_from_month_year(label)
    if not p:
        raise ValueError("Month label not recognized. Use 'YYYY-MM' (preferred) or 'Mon YYYY'.")
    y, m = p.split("-")
    return date(int(y), int(m), 1)
'''


def patch_admin_reports(p: Path) -> bool:
    txt = read(p)
    orig = txt
    # Replace specific functions by name
    txt = replace_block(txt, "uploads_tracker", ADMIN_UPLOADS_TRACKER)
    txt = replace_block(txt, "_select_schedule_latest", ADMIN_SELECT_SCHEDULE_LATEST)
    txt = replace_block(txt, "list_statements", ADMIN_LIST_STATEMENTS)
    txt = replace_block(txt, "list_terminated", ADMIN_LIST_TERMINATED)
    txt = replace_block(txt, "list_uploads", ADMIN_LIST_UPLOADS)

    # As an extra safety net, de-legacy any remaining ORDER BY on %b %Y:
    # ORDER BY STR_TO_DATE(CONCAT('01 ', X), '%%d %%b %%Y') -> ORDER BY X
    # ORDER BY STR_TO_DATE(CONCAT('01 ', X), '%d %b %Y')   -> ORDER BY X
    patterns = [
        re.compile(r"ORDER BY\s+STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*(.+?)\)\s*,\s*'%%d %%b %%Y'\s*\)", re.I),
        re.compile(r"ORDER BY\s+STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*(.+?)\)\s*,\s*'%d %b %Y'\s*\)", re.I),
    ]
    for pat in patterns:
        txt = pat.sub(r"ORDER BY \1", txt)

    if txt != orig:
        backup_once(p)
        write(p, txt)
        return True
    return False


def patch_disparities(p: Path) -> bool:
    txt = read(p)
    orig = txt
    txt = replace_block(txt, "_parse_month_year", DISPARITIES_PARSE)
    if txt != orig:
        backup_once(p)
        write(p, txt)
        return True
    return False


def main() -> int:
    ensure_util_periods()
    changed = 0
    for p in TARGETS:
        if not p.exists():
            continue
        if p.name == "admin_reports.py":
            if patch_admin_reports(p):
                changed += 1
        elif p.name == "disparities.py":
            if patch_disparities(p):
                changed += 1
    print(f"[patch] Completed. Files changed: {changed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
