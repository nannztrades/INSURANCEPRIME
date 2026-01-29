
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fixes two things:
  1) Ensures 'from __future__ import ...' is at the very top of src/reports/monthly_reports.py
  2) Recreates src/util/periods.py (and __init__.py) with normalize_month_param()
Idempotent. Safe to run multiple times.
"""

from __future__ import annotations
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
MONTHLY = REPO / "src" / "reports" / "monthly_reports.py"
UTIL_DIR = REPO / "src" / "util"

_FUTURE_IMPORT_RE = re.compile(r"(?m)^\s*from\s+__future__\s+import\s+.+$")

def move_future_to_top(path: Path) -> str:
    if not path.exists():
        return "missing (skipped)"
    text = path.read_text(encoding="utf-8")
    futures = _FUTURE_IMPORT_RE.findall(text)
    if not futures:
        return "no __future__ import found (skipped)"

    lines = text.splitlines()
    # Preserve shebang/coding header if present
    header = []
    i = 0
    if i < len(lines) and lines[i].startswith("#!"):
        header.append(lines[i]); i += 1
    if i < len(lines) and (lines[i].startswith("# -*- coding:") or "coding:" in lines[i]):
        header.append(lines[i]); i += 1

    # Optional module docstring block
    j = i
    doc = []
    if j < len(lines) and re.match(r'^\s*[rubfRUBF]*("""|\'\'\')', lines[j]):
        q = '"""' if '"""' in lines[j] else "'''"
        doc.append(lines[j]); j += 1
        while j < len(lines):
            doc.append(lines[j])
            if lines[j].strip().endswith(q):
                j += 1
                break
            j += 1

    # Remove all future imports from the entire file body,
    # then rebuild with header + docstring + future(s) + rest
    body_wo_future = _FUTURE_IMPORT_RE.sub("", "\n".join(lines[j:])).lstrip("\n")
    new_text = ""
    if header:
        new_text += "\n".join(header) + "\n"
    if doc:
        new_text += "\n".join(doc) + "\n"
    new_text += "\n".join(futures) + "\n" + body_wo_future
    new_text = re.sub(r"\n{3,}", "\n\n", new_text).lstrip("\n") + "\n"

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return "moved __future__ to top"
    return "already correct (no changes)"

def ensure_util_periods() -> str:
    UTIL_DIR.mkdir(parents=True, exist_ok=True)
    initp = UTIL_DIR / "__init__.py"
    if not initp.exists():
        initp.write_text("__all__ = []\n", encoding="utf-8")

    periodsp = UTIL_DIR / "periods.py"
    code = r'''from __future__ import annotations
import re
from datetime import datetime
from typing import Optional

# Fast, robust normalizer used by tests
_RE_CANONICAL = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')         # YYYY-MM
_RE_YEAR_DASH_M = re.compile(r'^(\d{4})-(\d{1,2})$')           # YYYY-M
_RE_YEAR_SLASH_MM = re.compile(r'^(\d{4})/(0[1-9]|1[0-2])$')   # YYYY/MM
_RE_COM_PREFIX = re.compile(r'^COM_', re.IGNORECASE)

_MONTH_FMTS = ('%b %Y', '%B %Y')  # 'Jun 2025', 'June 2025'

def normalize_month_param(raw: Optional[str]) -> Optional[str]:
    """
    Convert many month inputs to canonical 'YYYY-MM'.
    Accepts: 'YYYY-MM', 'YYYY-M', 'YYYY/MM', 'YYYYMM', 'Mon YYYY', 'Month YYYY', with optional 'COM_' prefix.
    Returns None for empty/invalid input.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    # Drop prefixes like 'COM_'
    s = _RE_COM_PREFIX.sub('', s)

    # Already canonical
    if _RE_CANONICAL.fullmatch(s):
        return s

    # YYYY-M  -> YYYY-MM
    m = _RE_YEAR_DASH_M.fullmatch(s)
    if m:
        y, mm = int(m.group(1)), int(m.group(2))
        if 1 <= mm <= 12:
            return f'{y:04d}-{mm:02d}'

    # YYYY/MM -> YYYY-MM
    m = _RE_YEAR_SLASH_MM.fullmatch(s)
    if m:
        return f'{int(m.group(1)):04d}-{m.group(2)}'

    # Month words e.g., 'Jun 2025' or 'June 2025'
    for fmt in _MONTH_FMTS:
        try:
            return datetime.strptime(s, fmt).strftime('%Y-%m')
        except ValueError:
            pass

    # Compact YYYYMM
    if re.fullmatch(r'^\d{6}$', s):
        y, mm = int(s[:4]), int(s[4:])
        if 1 <= mm <= 12:
            return f'{y:04d}-{mm:02d}'

    return None
'''
    periodsp.write_text(code, encoding="utf-8")
    return "util.periods written"

if __name__ == "__main__":
    print("[fix] monthly_reports.py:", move_future_to_top(MONTHLY))
    print("[fix] src/util/periods.py:", ensure_util_periods())
