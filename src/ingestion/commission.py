
# src/ingestion/commission.py
from __future__ import annotations

from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any, Union
from decimal import Decimal, ROUND_HALF_UP
import calendar

from src.ingestion.db import get_conn

Rule = Dict[str, Any]

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
}


def _parse_date(s: Optional[Union[str, date, datetime]]) -> Optional[datetime]:
    if s is None:
        return None
    if isinstance(s, datetime):
        return s
    if isinstance(s, date):
        return datetime(s.year, s.month, s.day)
    try:
        return datetime.strptime(str(s), '%Y-%m-%d')
    except Exception:
        return None


def _period_date_from_month_year(month_year: Optional[str]) -> Optional[datetime]:
    if not month_year:
        return None
    s = str(month_year).strip()
    import re
    m = re.search(r'COM_([A-Za-z]{3})_(\d{4})', s, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'([A-Za-z]{3,9})\s+(\d{4})', s, flags=re.IGNORECASE)
    if m:
        mon = m.group(1)[:3].lower()
        yr = int(m.group(2))
        mm = MONTHS.get(mon)
        if mm:
            last_day = calendar.monthrange(yr, mm)[1]
            return datetime(yr, mm, last_day)
    return None


def load_rules(conn) -> List[Dict[str, Any]]:
    rules: List[Dict[str, Any]] = []
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT `policy_type`,`policy_name`,`month_from`,`month_to`,
                   `commission_percent`,`effective_from`,`effective_to`
            FROM `commission_rules`
            ORDER BY `policy_type`,`month_from`
            """
        )
        for r in cur.fetchall():
            rules.append(r)
    return rules


def pick_percent_by_bucket(
    rules: List[Dict[str, Any]],
    policy_type: str,
    age_months: Optional[int],
    period_dt: Optional[datetime]
) -> Optional[float]:
    if not policy_type or age_months is None:
        return None
    for rule in rules:
        if str(rule.get('policy_type', '')).upper() != str(policy_type).upper():
            continue
        mf = int(rule.get('month_from') or 0)
        mt = int(rule.get('month_to') or 0)
        if not (mf <= age_months <= mt):
            continue
        ef = _parse_date(rule.get('effective_from'))
        et = _parse_date(rule.get('effective_to'))
        if period_dt is not None:
            if ef and period_dt < ef:
                continue
            if et and period_dt > et:
                continue
        return float(rule.get('commission_percent') or 0.0)
    return None


def bucket_percent_from_com_rate(
    rules: List[Dict[str, Any]],
    policy_type: str,
    com_rate: Optional[float],
    period_dt: Optional[datetime]
) -> Optional[float]:
    if com_rate is None:
        return None
    target = float(com_rate)
    for rule in rules:
        if str(rule.get('policy_type', '')).upper() != str(policy_type).upper():
            continue
        pct = float(rule.get('commission_percent') or 0.0)
        ef = _parse_date(rule.get('effective_from'))
        et = _parse_date(rule.get('effective_to'))
        if period_dt is not None:
            if ef and period_dt < ef:
                continue
            if et and period_dt > et:
                continue
        if abs(pct - target) < 1e-6:
            return pct
    return None


def months_between(inception_iso: Optional[Union[str, date, datetime]],
                   period_dt: Optional[datetime]) -> Optional[int]:
    inc = _parse_date(inception_iso)
    if not inc or not period_dt:
        return None
    if inc > period_dt:
        return None
    return (period_dt.year - inc.year) * 12 + (period_dt.month - inc.month) + 1


def _first_seen_cache(conn, policy_nos: List[str]) -> Dict[str, Optional[datetime]]:
    if not policy_nos:
        return {}
    uniq = list(set(policy_nos))
    placeholders = ",".join(["%s"] * len(uniq))
    sql = f"""
        SELECT `policy_no`,`first_seen_date`
        FROM `active_policies`
        WHERE `policy_no` IN ({placeholders})
    """
    cache: Dict[str, Optional[datetime]] = {p: None for p in uniq}
    with conn.cursor() as cur:
        cur.execute(sql, uniq)
        for r in cur.fetchall():
            fs = r.get('first_seen_date') if r else None
            cache[r.get('policy_no')] = _parse_date(fs) if fs else None
    return cache


def compute_expected_for_upload_dynamic(upload_id: int) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        rules = load_rules(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT `agent_code`,`policy_no`,`policy_type`,`premium`,`com_rate`,
                       `inception`,`MONTH_YEAR`,`period_date`
                FROM `statement`
                WHERE `upload_id`=%s
                """,
                (upload_id,)
            )
            rows = cur.fetchall()

        policy_nos = [str(r.get('policy_no')) for r in rows if r.get('policy_no') is not None]
        fs_cache = _first_seen_cache(conn, policy_nos)

        agg: Dict[Tuple[str, str], Decimal] = {}

        for r in rows:
            agent_code_val = r.get('agent_code')
            policy_no_val = r.get('policy_no')
            policy_type_val = r.get('policy_type')
            premium_val = r.get('premium')
            com_rate_val = r.get('com_rate')
            month_year_val = r.get('MONTH_YEAR')
            period_date_val = r.get('period_date')

            if agent_code_val is None or policy_no_val is None:
                continue
            if premium_val is None:
                continue

            agent_code = str(agent_code_val).strip()
            policy_no = str(policy_no_val).strip()
            policy_type = str(policy_type_val or "").strip()

            premium = Decimal(str(premium_val))
            com_rate: Optional[float] = float(com_rate_val) if com_rate_val is not None else None

            month_year_raw = str(month_year_val or "").strip()
            period_dt = _parse_date(period_date_val) or _period_date_from_month_year(month_year_raw)
            if period_dt is None:
                continue

            period_key = f"{period_dt.year:04d}-{period_dt.month:02d}"

            # A) via inception
            age_a = months_between(r.get('inception'), period_dt)
            pct_a = pick_percent_by_bucket(rules, policy_type, age_a, period_dt)

            # B) via com_rate
            pct_b = bucket_percent_from_com_rate(rules, policy_type, com_rate, period_dt)

            # C) via first_seen_date
            fs = fs_cache.get(policy_no)
            pct_c = None
            if fs is not None:
                age_c = (period_dt.year - fs.year) * 12 + (period_dt.month - fs.month) + 1
                pct_c = pick_percent_by_bucket(rules, policy_type, age_c, period_dt)

            if pct_a is not None:
                pct = Decimal(str(pct_a))
            elif pct_b is not None:
                pct = Decimal(str(pct_b))
            elif pct_c is not None:
                pct = Decimal(str(pct_c))
            else:
                pct = Decimal("0")

            expected_amt = (premium * pct / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            key = (agent_code, period_key)
            agg[key] = agg.get(key, Decimal("0.00")) + expected_amt

        out_rows: List[Dict[str, Any]] = []
        for (agent, period), amt in agg.items():
            out_rows.append({
                'agent_code': agent,
                'period': period,                  # canonical YYYY-MM
                'expected_amount': amt,            # Decimal for DECIMAL(12,2)
                'calc_basis': f'dynamic; rules={len(rules)}; upload_id={upload_id}',
                'upload_id': upload_id,
            })
        return out_rows
    finally:
        conn.close()


def insert_expected_rows(rows: List[Dict[str, Any]]) -> int:
    if not rows:
        return 0

    for r in rows:
        if not r.get('period') or r.get('upload_id') is None:
            raise ValueError(f"Row missing required keys: period={r.get('period')} upload_id={r.get('upload_id')}")

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            params = [
                (r['agent_code'], r['period'], r['expected_amount'], r.get('calc_basis'), r['upload_id'])
                for r in rows
            ]
            cur.executemany(
                """
                INSERT INTO `expected_commissions`
                (`agent_code`,`period`,`expected_amount`,`calc_basis`,`upload_id`)
                VALUES (%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  `expected_amount`=VALUES(`expected_amount`),
                  `calc_basis`=VALUES(`calc_basis`)
                """,
                params
            )
        conn.commit()
        return len(rows)
    finally:
        conn.close()
