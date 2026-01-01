# src/reports/monthly_reports.py
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal

# --- Python 3.8 shim: strip 'usedforsecurity' kwarg for hashlib.md5 ---
import hashlib as _hashlib
_md5_orig = _hashlib.md5
def _md5_shim(*args, **kwargs):
    kwargs.pop('usedforsecurity', None)
    return _md5_orig(*args, **kwargs)
_hashlib.md5 = _md5_shim
# ----------------------------------------------------------------------

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics import renderPDF
from reportlab.lib.units import cm

from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import mm

from src.ingestion.db import get_conn

MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

def _period_key_from_month_year(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip()
    import re
    m = re.search(r'COM_([A-Za-z]{3})_(\d{4})', s, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'([A-Za-z]{3,9})\s+(\d{4})', s, flags=re.IGNORECASE)
    if m:
        mon = m.group(1)[:3].lower()
        yr = int(m.group(2))
        mm = MONTHS.get(mon)
        if mm:
            return f"{yr:04d}-{mm:02d}"
    return ""

# --------------------------- Upload resolution helpers ---------------------------

def _active_upload_id(agent_code: str, month_year: str) -> Optional[int]:
    """
    Latest ACTIVE statement upload_id for agent+month.
    Falls back to latest (even if uploads table missing doc_type/is_active).
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Prefer ACTIVE in uploads
            cur.execute("""
                SELECT MAX(u.`UploadID`) AS max_upload
                FROM `uploads` u
                WHERE u.`agent_code`=%s AND u.`month_year`=%s
                  AND u.`doc_type`='STATEMENT' AND u.`is_active`=1
            """, (agent_code, month_year))
            r = cur.fetchone() or {}
            val = r.get('max_upload')
            if val is None:
                # Fallback: compute from statement directly
                cur.execute("""
                    SELECT MAX(`upload_id`) AS max_upload
                    FROM `statement`
                    WHERE `agent_code`=%s AND `MONTH_YEAR`=%s
                """, (agent_code, month_year))
                r = cur.fetchone() or {}
                val = r.get('max_upload')
            if isinstance(val, int):
                return val
            if isinstance(val, str):
                try:
                    return int(val)
                except ValueError:
                    return None
            return None
    finally:
        conn.close()

def _latest_terminated_upload_id(agent_code: str, month_year: str) -> Optional[int]:
    """
    Latest ACTIVE terminated upload_id up to (and including) month_year.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT MAX(u.`UploadID`) AS max_upload
                FROM `uploads` u
                WHERE u.`agent_code`=%s AND u.`month_year`<=%s
                  AND u.`doc_type`='TERMINATED' AND u.`is_active`=1
            """, (agent_code, month_year))
            r = cur.fetchone() or {}
            val = r.get('max_upload')
            if val is None:
                # Fallback: compute from terminated directly
                cur.execute("""
                    SELECT MAX(`upload_id`) AS max_upload
                    FROM `terminated`
                    WHERE `agent_code`=%s AND `month_year`<=%s
                """, (agent_code, month_year))
                r = cur.fetchone() or {}
                val = r.get('max_upload')
            if isinstance(val, int):
                return val
            if isinstance(val, str):
                try:
                    return int(val)
                except ValueError:
                    return None
            return None
    finally:
        conn.close()

def _latest_schedule_upload_id(agent_code: str, month_year: str) -> Optional[int]:
    """
    Latest ACTIVE schedule upload_id for the month.
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT MAX(u.`UploadID`) AS max_upload
                FROM `uploads` u
                WHERE u.`agent_code`=%s AND u.`month_year`=%s
                  AND u.`doc_type`='SCHEDULE' AND u.`is_active`=1
            """, (agent_code, month_year))
            r = cur.fetchone() or {}
            val = r.get('max_upload')
            if val is None:
                # Fallback: compute from schedule directly
                cur.execute("""
                    SELECT MAX(`upload_id`) AS max_upload
                    FROM `schedule`
                    WHERE `agent_code`=%s AND `month_year`=%s
                """, (agent_code, month_year))
                r = cur.fetchone() or {}
                val = r.get('max_upload')
            if isinstance(val, int):
                return val
            if isinstance(val, str):
                try:
                    return int(val)
                except ValueError:
                    return None
            return None
    finally:
        conn.close()

# --------------------------- Summary ---------------------------

def compute_month_summary(agent_code: str, month_year: str) -> Dict[str, Any]:
    """
    Summary numbers only (counts/totals). Lists are fetched via helper functions below.
    """
    conn = get_conn()
    try:
        out = {
            'agent_code': agent_code,
            'month_year': month_year,
            'policies_reported': 0,
            'total_premium': 0.0,
            'total_commission_reported': 0.0,
            'total_commission_expected': 0.0,
            'missing_policies_count': 0,
            'terminated_policies_count': 0,
            'commission_mismatches_count': 0
        }

        period_key = _period_key_from_month_year(month_year)
        active_id = _active_upload_id(agent_code, month_year)

        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) AS cnt, SUM(`premium`) AS prem, SUM(`com_amt`) AS comm
                FROM `statement`
                WHERE `agent_code`=%s AND `MONTH_YEAR`=%s
            """, (agent_code, month_year))
            r = cur.fetchone() or {}
            out['policies_reported'] = int(r.get('cnt') or 0)

            prem = r.get('prem')
            comm = r.get('comm')
            out['total_premium'] = float(Decimal(str(prem)) if prem is not None else Decimal("0.00"))
            out['total_commission_reported'] = float(Decimal(str(comm)) if comm is not None else Decimal("0.00"))

            if active_id is not None:
                cur.execute("""
                    SELECT SUM(`expected_amount`) AS exp
                    FROM `expected_commissions`
                    WHERE `agent_code`=%s AND `upload_id`=%s
                """, (agent_code, active_id))
            elif period_key:
                cur.execute("""
                    SELECT SUM(`expected_amount`) AS exp
                    FROM `expected_commissions`
                    WHERE `agent_code`=%s AND `period`=%s
                """, (agent_code, period_key))
            else:
                cur.execute("""
                    SELECT SUM(`expected_amount`) AS exp
                    FROM `expected_commissions`
                    WHERE `agent_code`=%s AND `period`=%s
                """, (agent_code, month_year))
            r2 = cur.fetchone() or {}
            exp = r2.get('exp')
            out['total_commission_expected'] = float(Decimal(str(exp)) if exp is not None else Decimal("0.00"))

            # Missing policies count (latest statement membership vs historical active/terminated)
            term_latest_id = _latest_terminated_upload_id(agent_code, month_year)
            if active_id is not None:
                cur.execute("""
                    SELECT COUNT(*) AS missing_cnt FROM (
                      SELECT DISTINCT s.`policy_no`
                      FROM `statement` s
                      WHERE s.`agent_code`=%s AND s.`MONTH_YEAR`<=%s
                        AND s.`policy_no` NOT IN (
                          SELECT t.`policy_no`
                          FROM `terminated` t
                          WHERE t.`agent_code`=%s AND t.`month_year`<=%s
                          {term_filter}
                        )
                    ) ap
                    WHERE ap.`policy_no` NOT IN (
                      SELECT s2.`policy_no` FROM `statement` s2
                      WHERE s2.`agent_code`=%s AND s2.`MONTH_YEAR`=%s AND s2.`upload_id`=%s
                    )
                """.format(
                    term_filter=f"AND t.`upload_id`={term_latest_id}" if term_latest_id is not None else ""
                ), (agent_code, month_year, agent_code, month_year, agent_code, month_year, active_id))
            else:
                cur.execute("""
                    SELECT COUNT(*) AS missing_cnt FROM (
                      SELECT DISTINCT s.`policy_no`
                      FROM `statement` s
                      WHERE s.`agent_code`=%s AND s.`MONTH_YEAR`<=%s
                        AND s.`policy_no` NOT IN (
                          SELECT t.`policy_no`
                          FROM `terminated` t
                          WHERE t.`agent_code`=%s AND t.`month_year`<=%s
                        )
                    ) ap
                    WHERE ap.`policy_no` NOT IN (
                      SELECT s2.`policy_no` FROM `statement` s2
                      WHERE s2.`agent_code`=%s AND s2.`MONTH_YEAR`=%s
                    )
                """, (agent_code, month_year, agent_code, month_year, agent_code, month_year))
            r3 = cur.fetchone() or {}
            out['missing_policies_count'] = int(r3.get('missing_cnt') or 0)

            # Terminated in the month (latest terminated view)
            term_latest_id = _latest_terminated_upload_id(agent_code, month_year)
            cur.execute("""
                SELECT COUNT(*) AS term_cnt
                FROM `terminated`
                WHERE `agent_code`=%s AND `month_year`=%s
                {term_filter}
            """.format(
                term_filter=f"AND `upload_id`={term_latest_id}" if term_latest_id is not None else ""
            ), (agent_code, month_year))
            r4 = cur.fetchone() or {}
            out['terminated_policies_count'] = int(r4.get('term_cnt') or 0)

        return out
    finally:
        conn.close()

# --------------------------- Fetch sections ---------------------------

def _fetch_schedule_commission(agent_code: str, month_year: str) -> Optional[float]:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            try:
                sched_latest_id = _latest_schedule_upload_id(agent_code, month_year)
                cur.execute("""
                    SELECT SUM(`net_commission`) AS scheduled
                    FROM `schedule`
                    WHERE `agent_code`=%s AND `month_year`=%s
                    {sched_filter}
                """.format(
                    sched_filter=f"AND `upload_id`={sched_latest_id}" if sched_latest_id is not None else ""
                ), (agent_code, month_year))
                r = cur.fetchone() or {}
                scheduled = r.get('scheduled')
                return float(Decimal(str(scheduled)) if scheduled is not None else Decimal("0.00"))
            except Exception:
                return None
    finally:
        conn.close()

def _fetch_terminated_policies(agent_code: str, month_year: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        term_latest_id = _latest_terminated_upload_id(agent_code, month_year)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT `policy_no`, `termination_date`, `month_year`
                FROM `terminated`
                WHERE `agent_code`=%s AND `month_year`=%s
                {term_filter}
                ORDER BY `termination_date` ASC
            """.format(
                term_filter=f"AND `upload_id`={term_latest_id}" if term_latest_id is not None else ""
            ), (agent_code, month_year))
            rows = cur.fetchall() or []
            out: List[Dict[str, Any]] = []
            for r in rows:
                out.append({
                    "policy_no": r.get("policy_no"),
                    "termination_date": r.get("termination_date"),
                    "month_year": r.get("month_year"),
                })
            return out
    finally:
        conn.close()

def _fetch_missing_policies(agent_code: str, month_year: str) -> List[Dict[str, Any]]:
    conn = get_conn()
    try:
        active_id = _active_upload_id(agent_code, month_year)
        term_latest_id = _latest_terminated_upload_id(agent_code, month_year)
        with conn.cursor() as cur:
            cur.execute("""
                SELECT ap.`policy_no`,
                       MAX(ap.`MONTH_YEAR`) AS last_seen_month,
                       MAX(ap.`premium`) AS last_premium
                FROM `statement` ap
                WHERE ap.`agent_code`=%s AND ap.`MONTH_YEAR`<=%s
                  AND ap.`policy_no` NOT IN (
                    SELECT t.`policy_no`
                    FROM `terminated` t
                    WHERE t.`agent_code`=%s AND t.`month_year`<=%s
                    {term_filter}
                  )
                  AND ap.`policy_no` NOT IN (
                    SELECT s2.`policy_no`
                    FROM `statement` s2
                    WHERE s2.`agent_code`=%s AND s2.`MONTH_YEAR`=%s
                    {stmt_filter}
                  )
                GROUP BY ap.`policy_no`
                ORDER BY last_seen_month ASC
            """.format(
                term_filter=f"AND t.`upload_id`={term_latest_id}" if term_latest_id is not None else "",
                stmt_filter=f"AND s2.`upload_id`={active_id}" if active_id is not None else ""
            ), (agent_code, month_year, agent_code, month_year, agent_code, month_year))
            rows = cur.fetchall() or []
            out: List[Dict[str, Any]] = []
            for r in rows:
                out.append({
                    "policy_no": r.get("policy_no"),
                    "last_seen_month": r.get("last_seen_month"),
                    "last_premium": r.get("last_premium"),
                })
            return out
    finally:
        conn.close()

def _fetch_discrepancies_multiple_entries(agent_code: str, month_year: str) -> List[Dict[str, Any]]:
    """
    Same policy_no appears multiple times in the latest statement upload for the month.
    """
    conn = get_conn()
    try:
        active_id = _active_upload_id(agent_code, month_year)
        if active_id is None:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.`policy_no`, COUNT(*) AS entries
                FROM `statement` s
                WHERE s.`agent_code`=%s AND s.`MONTH_YEAR`=%s AND s.`upload_id`=%s
                GROUP BY s.`policy_no`
                HAVING COUNT(*) > 1
                ORDER BY entries DESC
            """, (agent_code, month_year, active_id))
            rows = cur.fetchall() or []
            return [{"policy_no": r.get("policy_no"), "entries": r.get("entries")} for r in rows]
    finally:
        conn.close()

def _fetch_discrepancies_inception_vs_first_seen(agent_code: str, month_year: str) -> List[Dict[str, Any]]:
    """
    Inception later than first_seen_date or in the future relative to period date.
    Requires active_policies table.
    """
    conn = get_conn()
    try:
        active_id = _active_upload_id(agent_code, month_year)
        if active_id is None:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.`policy_no`, s.`inception`, ap.`first_seen_date`
                FROM `statement` s
                LEFT JOIN `active_policies` ap ON ap.`policy_no`=s.`policy_no`
                WHERE s.`agent_code`=%s AND s.`MONTH_YEAR`=%s AND s.`upload_id`=%s
                  AND (
                    (s.`inception` IS NOT NULL AND ap.`first_seen_date` IS NOT NULL AND s.`inception` > ap.`first_seen_date`)
                    OR (s.`inception` IS NOT NULL AND s.`inception` > STR_TO_DATE(CONCAT('28 ', %s), '%%d %%b %%Y'))
                  )
            """, (agent_code, month_year, active_id, month_year))
            rows = cur.fetchall() or []
            out: List[Dict[str, Any]] = []
            for r in rows:
                out.append({
                    "policy_no": r.get("policy_no"),
                    "inception": r.get("inception"),
                    "first_seen": r.get("first_seen_date"),
                })
            return out
    finally:
        conn.close()

def _fetch_discrepancies_arrears(agent_code: str, month_year: str) -> List[Dict[str, Any]]:
    """
    Arrears suspects: 2+ entries for the same policy in the month with similar or multiple premiums.
    """
    conn = get_conn()
    try:
        active_id = _active_upload_id(agent_code, month_year)
        if active_id is None:
            return []
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.`policy_no`, COUNT(*) AS entries, SUM(s.`premium`) AS total_premium
                FROM `statement` s
                WHERE s.`agent_code`=%s AND s.`MONTH_YEAR`=%s AND s.`upload_id`=%s
                GROUP BY s.`policy_no`
                HAVING COUNT(*) >= 2
                ORDER BY total_premium DESC
            """, (agent_code, month_year, active_id))
            rows = cur.fetchall() or []
            return [{"policy_no": r.get("policy_no"), "entries": r.get("entries"), "total_premium": r.get("total_premium")} for r in rows]
    finally:
        conn.close()

def _fetch_should_be_terminated(agent_code: str, month_year: str) -> List[Dict[str, Any]]:
    """
    Policies that have a termination prior to or in this month but still appear after termination.
    """
    conn = get_conn()
    try:
        term_latest_id = _latest_terminated_upload_id(agent_code, month_year)
        with conn.cursor() as cur:
            # Find policies terminated by or before the month, but present in latest statement month membership.
            active_id = _active_upload_id(agent_code, month_year)
            if active_id is None:
                return []
            cur.execute("""
                SELECT DISTINCT s.`policy_no`
                FROM `statement` s
                WHERE s.`agent_code`=%s AND s.`MONTH_YEAR`=%s AND s.`upload_id`=%s
                  AND s.`policy_no` IN (
                    SELECT t.`policy_no`
                    FROM `terminated` t
                    WHERE t.`agent_code`=%s AND t.`month_year`<=%s
                    {term_filter}
                  )
            """.format(
                term_filter=f"AND t.`upload_id`={term_latest_id}" if term_latest_id is not None else ""
            ), (agent_code, month_year, active_id, agent_code, month_year))
            rows = cur.fetchall() or []
            return [{"policy_no": r.get("policy_no")} for r in rows]
    finally:
        conn.close()

# --------------------------- (Old) Canvas-based rendering ---------------------------
# NOTE: We are no longer using the canvas-based render for agent reports. Kept for reference.

def _render_bar_chart_net_across_months(
    c: canvas.Canvas,
    agent_code: str,
    month_year: str,
    y: float,
    months_back: int = 6
) -> float:
    conn = get_conn()
    try:
        labels: List[str] = []
        values: List[float] = []
        pk = _period_key_from_month_year(month_year)
        if not pk:
            return y - 10
        base_year = int(pk.split("-")[0]); base_mon = int(pk.split("-")[1])
        for i in range(months_back - 1, -1, -1):
            yr = base_year
            mon = base_mon - i
            while mon <= 0:
                mon += 12; yr -= 1
            while mon > 12:
                mon -= 12; yr += 1
            label = f"{yr}-{mon:02d}"
            labels.append(label)
        with conn.cursor() as cur:
            for label in labels:
                month_text = datetime.strptime(label + "-01", "%Y-%m-%d").strftime("%b %Y")
                sched_latest = _latest_schedule_upload_id(agent_code, month_text)
                net_val = None
                if sched_latest is not None:
                    try:
                        cur.execute("""
                            SELECT SUM(`net_commission`) AS net
                            FROM `schedule`
                            WHERE `agent_code`=%s AND `month_year`=%s AND `upload_id`=%s
                        """, (agent_code, month_text, sched_latest))
                        r = cur.fetchone() or {}
                        net_val = r.get("net")
                    except Exception:
                        net_val = None
                if net_val is None:
                    cur.execute("""
                        SELECT `total_commission_reported` AS rep
                        FROM `monthly_reports`
                        WHERE `agent_code`=%s AND `report_period`=%s
                        ORDER BY `report_id` DESC
                        LIMIT 1
                    """, (agent_code, label))
                    r2 = cur.fetchone() or {}
                    net_val = r2.get("rep")
                values.append(float(Decimal(str(net_val or 0.0))))
    finally:
        conn.close()

    c.setFont("Helvetica-Bold", 13)
    c.drawString(50, y, "Net earnings across months")
    y -= 24

    d = Drawing(400, 180)
    bc = VerticalBarChart()
    bc.x = 30; bc.y = 30
    bc.height = 120; bc.width = 340
    bc.data = [values]
    bc.barWidth = 10
    bc.strokeColor = colors.black
    bc.valueAxis.valueMin = 0
    bc.valueAxis.labelTextFormat = "%.0f"
    bc.categoryAxis.categoryNames = labels
    bc.categoryAxis.labels.boxAnchor = 'n'
    bc.categoryAxis.labels.angle = 30
    bc.categoryAxis.labels.dx = 0
    bc.categoryAxis.labels.dy = -15
    bc.bars[0].fillColor = colors.darkblue

    d.add(bc)
    renderPDF.draw(d, c, 50, y - 160)
    return y - 180

# --------------------------- Platypus-based compact PDF ---------------------------

def local_and_gcs(agent_code: str, agent_name: str, month_year: str, out_dir: Path, user_id: Optional[int]) -> dict:
    """
    Render a compact monthly PDF report for an agent (Platypus).
    - Removes the "Active policies" section (as requested).
    - Polishes styling and headings.
    - Uses variance = Actual - Expected for intuitive interpretation.
    - FETCHES lists directly from DB helpers (terminated, missing, discrepancies).
    """
    # Ensure output folder
    period_key = _period_key_from_month_year(month_year) or month_year.replace('COM_', '').replace(' ', '-')
    folder = out_dir / agent_code / period_key
    folder.mkdir(parents=True, exist_ok=True)

    # Pull summary + details
    summary = compute_month_summary(agent_code, month_year)
    total_reported = Decimal(str(summary.get('total_commission_reported', 0.0)))
    total_expected = Decimal(str(summary.get('total_commission_expected', 0.0)))
    variance_amount = total_reported - total_expected
    variance_pct = Decimal("0.00")
    if total_expected != Decimal("0.00"):
        variance_pct = (variance_amount / total_expected * Decimal("100")).quantize(Decimal("0.01"))

    # Build PDF doc
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"report_{ts}.pdf"
    pdf_path = folder / filename
    doc = SimpleDocTemplate(str(pdf_path), pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleBig', fontSize=18, leading=22, spaceAfter=8))
    styles.add(ParagraphStyle(name='H2', fontSize=12, leading=16, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#1f6feb")))
    styles.add(ParagraphStyle(name='Body', fontSize=10, leading=14, spaceAfter=2))

    content = []
    content.append(Paragraph(f"Monthly Report — {agent_name} ({agent_code})", styles['TitleBig']))
    content.append(Paragraph(f"Period: {month_year}", styles['Body']))
    content.append(Paragraph(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Body']))
    content.append(Spacer(1, 8))

    # Key metrics table
    metrics = [
        ["Policies reported", str(int(summary.get('policies_reported', 0)))],
        ["Total premium", f"{float(summary.get('total_premium', 0.0)):.2f}"],
        ["Commission (actual)", f"{float(total_reported):.2f}"],
        ["Commission (expected)", f"{float(total_expected):.2f}"],
        ["Variance (Actual - Expected)", f"{float(variance_amount):.2f}"],
        ["Variance (%)", f"{float(variance_pct):.2f}%"],
        ["Missing policies", str(int(summary.get('missing_policies_count', 0)))],
        ["Terminated policies", str(int(summary.get('terminated_policies_count', 0)))],
        ["Commission mismatches", str(int(summary.get('commission_mismatches_count', 0)))],
    ]
    tbl = Table(metrics, colWidths=[90*mm, 70*mm])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('LINEABOVE', (0,0), (-1,0), 0.5, colors.HexColor("#e5e7eb")),
        ('LINEBELOW', (0,-1), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#e5e7eb")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    content.append(Paragraph("Schedule vs Actual vs Expected", styles['H2']))
    content.append(tbl)
    content.append(Spacer(1, 8))

    # Terminated policies (compact list)
    content.append(Paragraph("Terminated policies", styles['H2']))
    term_rows = _fetch_terminated_policies(agent_code, month_year)
    if term_rows:
        term_table = [["Policy No.", "Termination Date", "Month"]]
        for r in term_rows[:30]:
            td = r.get("termination_date")
            td_str = td.strftime("%Y-%m-%d") if td else ""
            term_table.append([str(r.get("policy_no")), td_str, str(r.get("month_year"))])
        t = Table(term_table, colWidths=[50*mm, 40*mm, 40*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#e5e7eb")),
        ]))
        content.append(t)
    else:
        content.append(Paragraph("None", styles['Body']))
    content.append(Spacer(1, 8))

    # Missing policies section
    content.append(Paragraph("Missing policies (historically active but absent in latest upload)", styles['H2']))
    miss_rows = _fetch_missing_policies(agent_code, month_year)
    if miss_rows:
        miss_table = [["Policy No.", "Last seen month", "Last premium"]]
        for r in miss_rows[:30]:
            lp = r.get("last_premium")
            miss_table.append([str(r.get("policy_no")), str(r.get("last_seen_month")), f"{Decimal(str(lp or 0.0)):.2f}"])
        mt = Table(miss_table, colWidths=[50*mm, 40*mm, 40*mm])
        mt.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
            ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#e5e7eb")),
        ]))
        content.append(mt)
    else:
        content.append(Paragraph("None", styles['Body']))
    content.append(Spacer(1, 8))

    # Discrepancies / Data quality checks
    content.append(Paragraph("Discrepancies / Data quality checks", styles['H2']))
    sections = [
        ("Multiple entries in latest upload",
         _fetch_discrepancies_multiple_entries(agent_code, month_year),
         ["Policy No.", "Entries"],
         lambda r: [str(r.get("policy_no")), str(r.get("entries"))]),
        ("Inception vs first_seen inconsistencies",
         _fetch_discrepancies_inception_vs_first_seen(agent_code, month_year),
         ["Policy No.", "Inception", "First seen"],
         lambda r: [str(r.get("policy_no")), str(r.get("inception")), str(r.get("first_seen"))]),
        ("Arrears suspects",
         _fetch_discrepancies_arrears(agent_code, month_year),
         ["Policy No.", "Entries", "Total premium"],
         lambda r: [str(r.get("policy_no")), str(r.get("entries")), f'{float(r.get("total_premium", 0.0)):.2f}']),
        ("Should‑be‑terminated (appears after termination)",
         _fetch_should_be_terminated(agent_code, month_year),
         ["Policy No."],
         lambda r: [str(r.get("policy_no"))]),
    ]
    for title, rows, headers, row_map in sections:
        content.append(Paragraph(title, styles['Body']))
        if rows:
            table = [headers]
            for r in rows[:30]:
                table.append(row_map(r))
            tt = Table(table)
            tt.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
                ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e5e7eb")),
                ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor("#e5e7eb")),
            ]))
            content.append(tt)
        else:
            content.append(Paragraph("None", styles['Body']))
        content.append(Spacer(1, 4))

    doc.build(content)

    return {
        "pdf_path": str(pdf_path),
        "period_folder": str(folder),
        "period_key": period_key,
    }
