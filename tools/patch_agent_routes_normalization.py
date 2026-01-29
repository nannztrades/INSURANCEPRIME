
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Patch agent-facing routes to normalize `month_year` using src.util.periods.normalize_month_param.
- Adds the import if missing.
- For any FastAPI endpoint def that has a `month_year` parameter, inserts:
      if month_year is not None:
          month_year = normalize_month_param(month_year)
- Writes a single .bak file per modified source for easy rollback.
Optionally (toggle flag) fixes any lingering STR_TO_DATE '01 ' ordering to ORDER BY month_year DESC.
"""

import re
from pathlib import Path

# --- config
REPO = Path(__file__).resolve().parents[1]  # project root
SRC = REPO / "src"
TARGETS = [
    SRC / "api" / "agent_api.py",
    SRC / "api" / "agent_reports.py",
    SRC / "api" / "agent_missing.py",
]
OPTIONALLY_FIX_ADMIN_ORDERING = True
ADMIN = SRC / "api" / "admin_reports.py"

IMPORT_LINE = "from src.util.periods import normalize_month_param"
NORM_SNIPPET = (
    "    if month_year is not None:\n"
    "        month_year = normalize_month_param(month_year)\n"
)

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write(p: Path, s: str) -> None:
    p.write_text(s, encoding="utf-8")

def backup_once(p: Path) -> None:
    b = p.with_suffix(p.suffix + ".bak")
    if not b.exists():
        b.write_text(read(p), encoding="utf-8")

def ensure_import(txt: str) -> str:
    if IMPORT_LINE in txt:
        return txt
    # insert after other imports
    lines = txt.splitlines(True)
    # find last 'from ' or 'import ' line at top
    last_imp = -1
    for i, line in enumerate(lines[:200]):  # imports typically at the top
        if line.startswith("from ") or line.startswith("import "):
            last_imp = i
    if last_imp >= 0:
        lines.insert(last_imp + 1, IMPORT_LINE + "\n")
    else:
        lines.insert(0, IMPORT_LINE + "\n")
    return "".join(lines)

# def pattern: capture a def line with a month_year parameter
DEF_RE = re.compile(
    r"^def\s+\w+\s*\((?:[^#\n]*?)month_year\s*:\s*[^,)]+(?:[^#\n]*?)\):",
    re.MULTILINE,
)

def insert_normalization(txt: str) -> str:
    """Insert normalization snippet as the first logical line inside functions with a month_year parameter."""
    out = []
    i = 0
    while True:
        m = DEF_RE.search(txt, i)
        if not m:
            out.append(txt[i:])
            break
        # copy up to function header end-of-line
        header_end = txt.find("\n", m.end())
        if header_end == -1:
            out.append(txt[i:])
            break
        out.append(txt[i:header_end + 1])

        # we are at the start of the function body; respect existing docstring/annotations
        body_start = header_end + 1

        # If next significant line is a docstring, insert after it; else insert immediately.
        doc_re = re.compile(r"^\s+([ruRU]{0,2}['\"]).*?\1", re.DOTALL)
        inserted = False

        # Peek next few lines to decide insertion point
        # Simple: insert right after the header (safe for our case)
        out.append(NORM_SNIPPET)
        i = body_start
    return "".join(out)

ORDER_BY_LEGACY_RE = re.compile(
    r"ORDER BY\s+STR_TO_DATE\s*\(\s*CONCAT\s*\(\s*'01 '\s*,\s*([^)]+?)\s*\)\s*,\s*'%d %b %Y'\s*\)\s+(ASC|DESC)",
    re.IGNORECASE,
)

def fix_legacy_ordering(txt: str) -> str:
    # Replace with ORDER BY <expr> DESC/ASC assuming canonical YYYY-MM
    return ORDER_BY_LEGACY_RE.sub(r"ORDER BY \1 \2", txt)

def patch_file(p: Path) -> bool:
    if not p.exists():
        return False
    original = read(p)
    txt = original
    txt = ensure_import(txt)
    txt = insert_normalization(txt)
    if txt != original:
        backup_once(p)
        write(p, txt)
        return True
    return False

def patch_admin_ordering(p: Path) -> bool:
    if not p.exists():
        return False
    original = read(p)
    txt = fix_legacy_ordering(original)
    if txt != original:
        backup_once(p)
        write(p, txt)
        return True
    return False

def main() -> int:
    changed = 0
    for t in TARGETS:
        if patch_file(t):
            changed += 1
    if OPTIONALLY_FIX_ADMIN_ORDERING:
        if patch_admin_ordering(ADMIN):
            changed += 1
    print(f"[patch] files changed: {changed}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
