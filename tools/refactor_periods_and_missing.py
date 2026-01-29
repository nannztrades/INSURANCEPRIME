
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Refactor script:
- Canonicalize month periods to 'YYYY-MM' in Python and embedded SQL
- Patch _period_key_from_month_year (accepts 'YYYY-MM' first; legacy fallback)
- Replace direct %b %Y Python parses
- Replace _fetch_missing_policies to follow your "active-as-of then missing" definition
- Fix ORDER BY ... STR_TO_DATE('01 ' + label, '%d %b %Y') -> canonical

Backups:
- Each changed file is saved to <file>.bak once (first modification).

Run:
  python tools/refactor_periods_and_missing.py
"""

import re
import sys
from pathlib import Path

# ────────────────────────────────────────────────────────────────────────
# Repo root detection (robust for .../tools/refactor_periods_and_missing.py)
# ────────────────────────────────────────────────────────────────────────
THIS = Path(__file__).resolve()
ROOT = THIS.parent  # usually .../INSURANCELOCAL/tools
if (ROOT / "src").exists():
    REPO = ROOT
elif (ROOT.parent / "src").exists():
    REPO = ROOT.parent  # e.g., .../INSURANCELOCAL
else:
    REPO = ROOT  # fallback; will no-op if no src/

PY_TARGETS = list((REPO / "src").rglob("*.py"))

# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────

def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write_text(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")

def backup_once(p: Path) -> None:
    b = p.with_suffix(p.suffix + ".bak")
    if not b.exists():
        b.write_text(read_text(p), encoding="utf-8")

def replace_block(text: str, func_name: str, new_block: str) -> str:
    """
    Replace a Python function by name with new_block.
    It swaps from 'def func_name(…):' up to next top-level 'def ' or EOF.

    IMPORTANT: We return a callable to re.sub so the replacement text is NOT
    parsed for escapes (avoids 'bad escape \\d' from regexes in the block).
    """
    pattern = re.compile(
        rf"(^def\s+{re.escape(func_name)}\s*\(.*?\):)(.*?)(?=^\s*def\s+\w+\s*\(|\Z)",
        re.DOTALL | re.MULTILINE
    )
    if not pattern.search(text):
        return text
    block = new_block.strip() + "\n"

    def _repl(_m):
        return block

    return pattern.sub(_repl, text, count=1)

def count_subs(text: str, pat: re.Pattern, repl: str):
    (new_text, n) = pat.subn(repl, text)
    return new_text, n

# ────────────────────────────────────────────────────────────────────────
# New implementations (outer triple SINGLE quotes so inner docstrings are fine)
# ────────────────────────────────────────────────────────────────────────

PERIOD_FUNC = r'''
def _period_key_from_month_year(label):
    """
    Normalize any month label to canonical 'YYYY-MM'.
    Accepts 'YYYY-MM' first; falls back to 'Mon YYYY' / 'Month YYYY'.
    Returns None if unparsable.
    """
    from datetime import datetime
    import re as _re

    if not label:
        return None
    s = str(label).strip().replace("COM_", "")

    # 1) Canonical 'YYYY-MM'
    if _re.match(r"^\d{4}-(0[1-9]|1[0-2])$", s):
        return s

    # 2) Legacy: 'Mon YYYY' or 'Month YYYY'
    for fmt in ("%b %Y", "%B %Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m")
        except ValueError:
            pass

    # 3) Extra tolerant: 'YYYY/MM' -> 'YYYY-MM'
    if _re.match(r"^\d{4}/(0[1-9]|1[0-2])$", s):
        return s.replace("/", "-")

    return None
'''

MISSING_FUNC = r'''
def _fetch_missing_policies(agent_code, month_year):
    """
    Missing for <month_year> = ACTIVE-AS-OF(<month_year>) \ MINUS \ STATEMENTS-IN(<month_year>)

    ACTIVE-AS-OF(month) definition:
      - appeared in `statement` on or before that month, AND
      - not appeared in `terminated` on or before that month.

    Returns rows with: policy_no, last_seen_month, last_premium, last_com_rate.
    Holder/name/type/expected fields remain blank for template alignment.
    """
    from src.ingestion.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                WITH active AS (
                  SELECT DISTINCT s.policy_no
                  FROM `statement` s
                  WHERE s.`agent_code`=%s
                    AND STR_TO_DATE(CONCAT(s.`MONTH_YEAR`,'-01'), '%Y-%m-%d')
                        <= STR_TO_DATE(CONCAT(%s,'-01'), '%Y-%m-%d')
                    AND NOT EXISTS (
                      SELECT 1 FROM `terminated` t
                      WHERE t.`agent_code` = s.`agent_code`
                        AND t.`policy_no`  = s.`policy_no`
                        AND STR_TO_DATE(CONCAT(t.`month_year`,'-01'), '%Y-%m-%d')
                            <= STR_TO_DATE(CONCAT(%s,'-01'), '%Y-%m-%d')
                    )
                ),
                in_month AS (
                  SELECT DISTINCT policy_no
                  FROM `statement`
                  WHERE `agent_code`=%s AND `MONTH_YEAR`=%s
                ),
                last_seen AS (
                  SELECT s.policy_no,
                         MAX(s.`MONTH_YEAR`) AS last_seen_month,
                         MAX(s.`premium`)    AS last_premium,
                         MAX(s.`com_rate`)   AS last_com_rate
                  FROM `statement` s
                  WHERE s.`agent_code`=%s
                  GROUP BY s.policy_no
                )
                SELECT a.policy_no,
                       ls.last_seen_month,
                       ls.last_premium,
                       ls.last_com_rate
                FROM active a
                LEFT JOIN in_month m ON m.policy_no = a.policy_no
                LEFT JOIN last_seen ls ON ls.policy_no = a.policy_no
                WHERE m.policy_no IS NULL
                ORDER BY a.policy_no ASC
                """,
                (agent_code, month_year, month_year, agent_code, month_year, agent_code),
            )
            rows = list(cur.fetchall() or [])
            out = []
            for r in rows:
                out.append(
                    {
                        "policy_no": r.get("policy_no"),
                        "holder": "",
                        "surname": "",
                        "other_name": "",
                        "policy_type": "",
                        "last_seen_month": r.get("last_seen_month"),
                        "last_premium": r.get("last_premium"),
                        "expected_premium": "",
                        "last_com_rate": r.get("last_com_rate"),
                        "expected_com_rate": "",
                        "remarks": "",
                    }
                )
            return out
    except Exception:
        return []
    finally:
        conn.close()
'''

# SQL string fixes: %b %Y -> %Y-%m-%d with '-01' concatenation
SQL_PATTERNS = [
    # '... %d %b %Y' and double-escaped '%%d %%b %%Y'
    (re.compile(r"STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^\)]+?)\s*\)\s*,\s*'%d %b %Y'\s*\)", re.I),
     r"STR_TO_DATE(CONCAT(\1,'-01'), '%Y-%m-%d')"),
    (re.compile(r"STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^\)]+?)\s*\)\s*,\s*'%%d %%b %%Y'\s*\)", re.I),
     r"STR_TO_DATE(CONCAT(\1,'-01'), '%%Y-%%m-%%d')"),
    # '%d %M %Y'
    (re.compile(r"STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^\)]+?)\s*\)\s*,\s*'%d %M %Y'\s*\)", re.I),
     r"STR_TO_DATE(CONCAT(\1,'-01'), '%Y-%m-%d')"),
    (re.compile(r"STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^\)]+?)\s*\)\s*,\s*'%%d %%M %%Y'\s*\)", re.I),
     r"STR_TO_DATE(CONCAT(\1,'-01'), '%%Y-%%m-%%d')"),
]

# ORDER BY legacy -> canonical
ORDER_BY_FIX = [
    (re.compile(r"ORDER BY\s+STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*(\w+\.\`?\w+\`?)\s*\)\s*,\s*'%%d %%b %%Y'\s*\)\s+(ASC|DESC)", re.I),
     r"ORDER BY STR_TO_DATE(CONCAT(\1,'-01'), '%%Y-%%m-%%d') \2"),
    (re.compile(r"ORDER BY\s+STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*(\w+\.\`?\w+\`?)\s*\)\s*,\s*'%d %b %Y'\s*\)\s+(ASC|DESC)", re.I),
     r"ORDER BY STR_TO_DATE(CONCAT(\1,'-01'), '%Y-%m-%d') \2"),
]

# Direct Python date parsing fixes
PY_PARSE_PATTERNS = [
    (re.compile(r"datetime\.strptime\(\s*\"01\s*\"\s*\+\s*(\w+)\s*,\s*\"%d %b %Y\"\s*\)"),
     r"datetime.strptime(\1 + \"-01\", \"%Y-%m-%d\")"),
]

# ────────────────────────────────────────────────────────────────────────
# Main refactor pass
# ────────────────────────────────────────────────────────────────────────

def main() -> int:
    if not (REPO / "src").exists():
        print("[refactor] src/ folder not found next to this script. Nothing to do.")
        return 0

    changed_files = 0
    for p in PY_TARGETS:
        txt = read_text(p)
        orig = txt

        # 1) Replace _period_key_from_month_year
        if "_period_key_from_month_year" in txt:
            txt = replace_block(txt, "_period_key_from_month_year", PERIOD_FUNC)

        # 2) Replace _fetch_missing_policies
        if "_fetch_missing_policies" in txt:
            txt = replace_block(txt, "_fetch_missing_policies", MISSING_FUNC)

        # 3) Fix ORDER BY ... legacy month parsing
        for pat, repl in ORDER_BY_FIX:
            txt, _ = count_subs(txt, pat, repl)

        # 4) Fix embedded SQL STR_TO_DATE('01 ' + col, '%d %b %Y'/'%d %M %Y')
        for pat, repl in SQL_PATTERNS:
            txt, _ = count_subs(txt, pat, repl)

        # 5) Fix direct Python datetime.strptime("01 " + s, "%d %b %Y")
        for pat, repl in PY_PARSE_PATTERNS:
            txt, _ = count_subs(txt, pat, repl)

        if txt != orig:
            backup_once(p)
            write_text(p, txt)
            changed_files += 1

    print(f"[refactor] Completed. Files changed: {changed_files}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
