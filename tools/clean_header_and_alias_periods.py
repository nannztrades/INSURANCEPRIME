
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
1) Remove invisible/unexpected Unicode and common HTML-entity artifacts from src/reports/monthly_reports.py.
2) Ensure src/services/periods.py exposes a legacy shim: to_period_key().
"""

from __future__ import annotations
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[1]
MONTHLY = REPO / "src" / "reports" / "monthly_reports.py"
SERV_PERIODS = REPO / "src" / "services" / "periods.py"

# Characters to strip globally (Zero Width, BOM, directional marks, word joiners)
# \ufeff = BOM; \u200b..u200f = ZW*; \u202a..u202e bidi; \u2060..u206f word-joiners/controls
_BAD_CHARS_RE = re.compile(
    "[" + "".join([
        "\ufeff",                     # BOM
        "\u200b", "\u200c", "\u200d", "\u200e", "\u200f",
        "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
        "\u2060", "\u2061", "\u2062", "\u2063", "\u2064", "\u2066", "\u2067", "\u2068", "\u2069",
    ]) + "]"
)

def _backup_once(p: Path) -> None:
    b = p.with_suffix(p.suffix + ".bak2")
    if p.exists() and not b.exists():
        b.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")

def clean_monthly_reports() -> str:
    if not MONTHLY.exists():
        return "monthly_reports.py: missing (skipped)"

    txt = MONTHLY.read_text(encoding="utf-8")

    # 1) Strip invisible controls across entire file
    new = _BAD_CHARS_RE.sub("", txt)

    # 2) Fix common HTML entities conservatively in the first ~200 lines only
    lines = new.splitlines()
    head = "\n".join(lines[:200])
    head = (head
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&amp;", "&")
            .replace("–", "-")      # en-dash to hyphen
            .replace("—", "-"))     # em-dash to hyphen
    # Specific arrow artifact sometimes appears
    head = head.replace("-&gt;", "->")
    new = head + ("\n" if not head.endswith("\n") else "") + "\n".join(lines[200:])

    if new != txt:
        _backup_once(MONTHLY)
        MONTHLY.write_text(new, encoding="utf-8")
        return "monthly_reports.py: cleaned header/unicode artifacts"
    return "monthly_reports.py: no changes"

def ensure_to_period_key_alias() -> str:
    if not SERV_PERIODS.exists():
        return "services/periods.py: missing (skipped)"
    s = SERV_PERIODS.read_text(encoding="utf-8")

    has_alias = re.search(r"^\s*def\s+to_period_key\s*\(", s, flags=re.M)
    if has_alias:
        return "services/periods.py: to_period_key exists (no changes)"

    # We assume canonicalize_period(raw) -> Optional[str] exists
    alias = r'''

# ---- Legacy shim for older imports ----
def to_period_key(value: str) -> str:
    """
    Legacy alias: return canonical 'YYYY-MM' if possible; otherwise return the input as-is (or empty string).
    """
    try:
        c = canonicalize_period(value)
    except Exception:
        c = None
    return c if c is not None else (value or "")
'''
    _backup_once(SERV_PERIODS)
    SERV_PERIODS.write_text(s.rstrip() + alias + "\n", encoding="utf-8")
    return "services/periods.py: added to_period_key shim"

def main() -> int:
    print("[fix] ", clean_monthly_reports())
    print("[fix] ", ensure_to_period_key_alias())
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
