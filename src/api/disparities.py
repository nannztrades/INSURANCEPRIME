
# src/api/disparities.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List
from datetime import datetime, date
from calendar import monthrange
import csv, io
from src.ingestion.db import get_conn

router = APIRouter(prefix="/api/disparities", tags=["Disparities"])

def _parse_month_year(label: str) -> date:
    parts = (label or "").split()
    months = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,"Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    if len(parts) != 2 or parts[0] not in months:
        raise ValueError("Month label not recognized. Use 'Mon YYYY', e.g. 'Jun 2025'.")
    y = int(parts[1]); m = months[parts[0]]
    return date(y, m, 1)

@router.get("/pay-date")
def pay_date_disparities(agent_code: str, month_year: str) -> Dict[str, Any]:
    try:
        start = _parse_month_year(month_year)
        end = date(start.year, start.month, monthrange(start.year, start.month)[1])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT `policy_no`,`holder`,`pay_date`,`premium`,`MONTH_YEAR`
                FROM `statement`
                WHERE `agent_code`=%s AND `MONTH_YEAR`=%s
                ORDER BY `pay_date` DESC
            """, (agent_code, month_year))
            rows = cur.fetchall() or []

        disparities: List[Dict[str, Any]] = []
        total_premium_affected = 0.0
        future_dated_count = 0
        past_dated_count = 0

        for r in rows:
            pay_val = r.get('pay_date')
            pd: date
            try:
                if isinstance(pay_val, date):
                    pd = pay_val
                else:
                    s = str(pay_val or "")
                    if "-" in s:
                        pd = datetime.strptime(s[:10], "%Y-%m-%d").date()
                    elif "/" in s:
                        pd = datetime.strptime(s[:10], "%d/%m/%Y").date()
                    else:
                        continue
            except Exception:
                continue

            if not (start <= pd <= end):
                days_diff = (pd - end).days
                prem = float(r.get('premium') or 0.0)
                total_premium_affected += prem
                if days_diff > 0: future_dated_count += 1
                else: past_dated_count += 1
                disparities.append({
                    "policy_no": r.get('policy_no'),
                    "holder_name": r.get('holder'),
                    "premium": prem,
                    "expected_month": month_year,
                    "pay_date": pd.isoformat(),
                    "days_difference": days_diff
                })

        return {
            "summary": {
                "total_disparities": len(disparities),
                "future_dated_count": future_dated_count,
                "past_dated_count": past_dated_count,
                "total_premium_affected": round(total_premium_affected, 2)
            },
            "disparities": disparities
        }
    finally:
        conn.close()

@router.get("/pay-date.csv")
def pay_date_disparities_csv(agent_code: str, month_year: str):
    try:
        start = _parse_month_year(month_year)
        end = date(start.year, start.month, monthrange(start.year, start.month)[1])
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT `policy_no`,`holder`,`pay_date`,`premium`,`MONTH_YEAR`
                FROM `statement`
                WHERE `agent_code`=%s AND `MONTH_YEAR`=%s
                ORDER BY `pay_date` DESC
            """, (agent_code, month_year))
            rows = cur.fetchall() or []

        disparities: List[Dict[str, Any]] = []
        for r in rows:
            pay_val = r.get('pay_date')
            pd: date
            try:
                if isinstance(pay_val, date):
                    pd = pay_val
                else:
                    s = str(pay_val or "")
                    if "-" in s:
                        pd = datetime.strptime(s[:10], "%Y-%m-%d").date()
                    elif "/" in s:
                        pd = datetime.strptime(s[:10], "%d/%m/%Y").date()
                    else:
                        continue
            except Exception:
                continue

            if not (start <= pd <= end):
                days_diff = (pd - end).days
                prem = float(r.get('premium') or 0.0)
                disparities.append({
                    "policy_no": r.get('policy_no'),
                    "holder_name": r.get('holder'),
                    "premium": prem,
                    "expected_month": month_year,
                    "pay_date": pd.isoformat(),
                    "days_difference": days_diff
                })

        buf = io.StringIO()
        headers = ["policy_no","holder_name","premium","expected_month","pay_date","days_difference"]
        writer = csv.DictWriter(buf, fieldnames=headers)
        writer.writeheader()
        for d in disparities:
            writer.writerow(d)
        buf.seek(0)
        return StreamingResponse(buf, media_type="text/csv")
    finally:
        conn.close()
