
# src/common/date_rules.py
from __future__ import annotations

from datetime import datetime, date
from typing import Optional, Union, Tuple
import calendar


def month_range(y: int, m: int) -> Tuple[datetime, datetime]:
    """
    Return the inclusive [start, end] datetime range for a given year-month.
    End is 23:59:59 on the last day to simplify “in-month” comparisons.
    """
    first = datetime(y, m, 1, 0, 0, 0)
    last_day = calendar.monthrange(y, m)[1]
    last = datetime(y, m, last_day, 23, 59, 59)  # inclusive end
    return first, last


def is_paydate_in_period_month(
    pay_date: Optional[Union[date, datetime]],
    period_date: Optional[Union[date, datetime]],
) -> bool:
    """
    True if pay_date falls within the same month (calendar) as period_date.
    Missing dates are treated as 'False' to count as disparities upstream.
    """
    if not pay_date or not period_date:
        return False  # treat missing/invalid as "not in month" -> disparity

    # Normalize to datetime
    if isinstance(pay_date, date) and not isinstance(pay_date, datetime):
        pay_date = datetime(pay_date.year, pay_date.month, pay_date.day)
    if isinstance(period_date, date) and not isinstance(period_date, datetime):
        period_date = datetime(period_date.year, period_date.month, period_date.day)

    start, end = month_range(period_date.year, period_date.month)
    return start <= pay_date <= end
