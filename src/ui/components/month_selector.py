from __future__ import annotations

from datetime import datetime
from typing import List, Tuple


def generate_month_options(n_months: int = 36) -> List[Tuple[str, str]]:
    """
    Generate a list of (display, value) tuples for the last `n_months` months.

    - display: human-readable label, e.g. '2025-06'
    - value:   canonical YYYY-MM, same as display

    Latest month = current month; goes backwards n_months-1.
    """
    if n_months <= 0:
        return []

    now = datetime.utcnow()
    year = now.year
    month = now.month

    out: List[Tuple[str, str]] = []
    for _ in range(n_months):
        value = f"{year:04d}-{month:02d}"
        out.append((value, value))
        # decrement month
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    return out