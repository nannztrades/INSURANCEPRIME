# src/services/periods.py
"""
Canonical period normalization module.
Enforces YYYY-MM format across the entire application.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

# Strict YYYY-MM
_RE_YYYY_MM = re.compile(r"^\s*(\d{4})-(0[1-9]|1[0-2])\s*$")
# Compact YYYYMM
_RE_YYYYMM = re.compile(r"^\s*(\d{4})(0[1-9]|1[0-2])\s*$")
# COM_ / COM- prefix
_RE_COM_PREFIX = re.compile(r"^\s*COM[_-]?", re.IGNORECASE)

MONTH_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def canonicalize_period(value: Optional[str]) -> Optional[str]:
    """
    Convert any common period format to strict 'YYYY-MM'.

    Supported inputs (examples):
        '2025-06'        -> '2025-06'
        '2025/06'        -> '2025-06'
        '202506'         -> '2025-06'
        'Jun 2025'       -> '2025-06'
        'June 2025'      -> '2025-06'
        'COM_2025-06'    -> '2025-06'
        'COM_JUN_2025'   -> '2025-06'
        'COM-June-2025'  -> '2025-06'

    Returns:
        'YYYY-MM' or None if unparseable.
    """
    if value is None:
        return None

    s = str(value).strip()
    if not s:
        return None

    # Strip COM_ / COM- prefix
    s = _RE_COM_PREFIX.sub("", s).strip()

    # Already strict YYYY-MM
    m = _RE_YYYY_MM.match(s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Compact YYYYMM
    m = _RE_YYYYMM.match(s)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # YYYY/MM or YYYY/M
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            y, m_num = parts[0], int(parts[1])
            if len(y) == 4 and 1 <= m_num <= 12:
                return f"{y}-{m_num:02d}"

    # Month word formats: 'Jun 2025', 'June 2025'
    for fmt in ("%b %Y", "%B %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return f"{dt.year:04d}-{dt.month:02d}"
        except ValueError:
            pass

    # COM_JUN_2025 and similar that slipped through
    parts = re.split(r"[_\s-]+", s)
    if len(parts) >= 2:
        # last token year, previous token month word
        if parts[-1].isdigit() and len(parts[-1]) == 4:
            year = parts[-1]
            month_word = parts[-2].lower()
            if month_word in MONTH_MAP:
                return f"{year}-{MONTH_MAP[month_word]:02d}"

    # YYYY-M or YYYY-M (single digit month)
    dash_parts = s.split("-")
    if len(dash_parts) == 2 and dash_parts[0].isdigit() and dash_parts[1].isdigit():
        y, m_num = dash_parts[0], int(dash_parts[1])
        if len(y) == 4 and 1 <= m_num <= 12:
            return f"{y}-{m_num:02d}"

    return None


def is_yyyy_mm(s: Optional[str]) -> bool:
    """Return True if s is strictly 'YYYY-MM'."""
    if s is None:
        return False
    return bool(_RE_YYYY_MM.match(s))


def sort_key(period: str) -> str:
    """
    Return a key for sorting periods. Prefer canonical 'YYYY-MM';
    fall back to the raw string (or empty string) if unparseable.
    """
    c = canonicalize_period(period)
    return c if c is not None else str(period or "")


def to_period_key(value: str) -> str:
    """
    Legacy alias for older imports.

    Returns canonical 'YYYY-MM' if possible; otherwise returns the original
    value (or empty string). Prefer canonicalize_period() in new code.
    """
    c = canonicalize_period(value)
    return c if c is not None else (value or "")