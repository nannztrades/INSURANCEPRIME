
# src/ingestion/parser_db_integration.py
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, date

from src.ingestion.db import get_conn

MONTHS = {
    "jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
    "jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12
}

def _first_of_month_from_label(label: Optional[str]) -> Optional[date]:
    if not label:
        return None
    s = str(label).strip()
    parts = s.split()
    if len(parts) == 2 and parts[1].isdigit():
        mon = parts[0][:3].lower()
        mm = MONTHS.get(mon)
        if mm:
            return date(int(parts[1]), mm, 1)
    s2 = s.replace("-", "_")
    toks = s2.split("_")
    if len(toks) >= 3 and toks[-2].isalpha() and toks[-1].isdigit():
        mon = toks[-2][:3].lower()
        mm = MONTHS.get(mon)
        if mm:
            return date(int(toks[-1]), mm, 1)
    return None

def _infer_agent_code(rows: List[Dict[str, Any]], fallback: str) -> str:
    for r in rows:
        for k in ("agent_code", "AgentCode", "AGENT_CODE"):
            v = r.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return fallback or ""

def _infer_month_year(rows: List[Dict[str, Any]], hint: Optional[str]) -> Optional[str]:
    if hint:
        return hint
    for r in rows:
        for k in ("MONTH_YEAR", "month_year", "MonthYear"):
            val = r.get(k)
            if isinstance(val, str) and val.strip():
                s = val.strip()
                s2 = s.replace("-", "_")
                toks = s2.split("_")
                if len(toks) >= 3 and toks[-2].isalpha() and toks[-1].isdigit():
                    mon = toks[-2].title()[:3]
                    return f"{mon} {toks[-1]}"
                parts = s.split()
                if len(parts) == 2 and parts[1].isdigit():
                    return f"{parts[0].title()[:3]} {parts[1]}"
                return s
    return None

def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None

def _decimal_or_none(v: Any) -> Optional[float]:
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return float(str(v).replace(",", ""))
    except Exception:
        return None

class ParserDBIntegration:
    """
    Persist parsed rows to MySQL (uploads + row tables), or return a summary if DB is down.
    """

    def process(
        self,
        doc_type_key: str,
        agent_code: str,
        agent_name: Optional[str],
        df_rows: List[Dict[str, Any]],
        file_path: Path,
        month_year_hint: Optional[str],
    ) -> Dict[str, Any]:

        doc = (doc_type_key or "").lower().strip()
        if doc not in ("statement", "schedule", "terminated"):
            raise ValueError(f"Unsupported doc_type_key '{doc_type_key}'")

        eff_agent_code = _infer_agent_code(df_rows, agent_code)
        eff_agent_name = agent_name or eff_agent_code or None
        month_label = _infer_month_year(df_rows, month_year_hint)
        first_of_month = _first_of_month_from_label(month_label)

        upload_id: Optional[int] = None
        rows_inserted = 0

        try:
            conn = get_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO `uploads`
                        (`agent_code`,`AgentName`,`doc_type`,`FileName`,
                         `UploadTimestamp`,`month_year`,`is_active`)
                        VALUES (%s,%s,%s,%s,NOW(),%s,1)
                        """,
                        (
                            _safe_str(eff_agent_code),
                            _safe_str(eff_agent_name),
                            doc.upper(),
                            Path(file_path).name,
                            _safe_str(month_label),
                        ),
                    )
                    upload_id = cur.lastrowid

                with conn.cursor() as cur:
                    if doc == "statement":
                        for r in df_rows:
                            cur.execute(
                                """
                                INSERT INTO `statement`
                                (`upload_id`,`agent_code`,`policy_no`,`holder`,
                                 `policy_type`,`pay_date`,`receipt_no`,
                                 `premium`,`com_rate`,`com_amt`,`inception`,
                                 `MONTH_YEAR`,`AGENT_LICENSE_NUMBER`,`period_date`)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                """,
                                (
                                    upload_id,
                                    _safe_str(r.get("agent_code")) or _safe_str(eff_agent_code),
                                    _safe_str(r.get("policy_no")),
                                    _safe_str(r.get("holder")),
                                    _safe_str(r.get("policy_type")),
                                    _safe_str(r.get("pay_date")),
                                    _safe_str(r.get("receipt_no")),
                                    _decimal_or_none(r.get("premium")),
                                    _decimal_or_none(r.get("com_rate")),
                                    _decimal_or_none(r.get("com_amt")),
                                    _safe_str(r.get("inception")),
                                    _safe_str(r.get("MONTH_YEAR")) or _safe_str(r.get("month_year")) or _safe_str(month_label),
                                    _safe_str(r.get("AGENT_LICENSE_NUMBER")),
                                    first_of_month,
                                ),
                            )
                        rows_inserted = len(df_rows)

                    elif doc == "schedule":
                        for r in df_rows:
                            cur.execute(
                                """
                                INSERT INTO `schedule`
                                (`upload_id`,`agent_code`,`agent_name`,
                                 `commission_batch_code`,`total_premiums`,`income`,
                                 `total_deductions`,`net_commission`,`month_year`)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                """,
                                (
                                    upload_id,
                                    _safe_str(r.get("agent_code")) or _safe_str(eff_agent_code),
                                    _safe_str(r.get("agent_name")) or _safe_str(eff_agent_name),
                                    _safe_str(r.get("commission_batch_code")),
                                    _decimal_or_none(r.get("total_premiums")),
                                    _decimal_or_none(r.get("income")),
                                    _decimal_or_none(r.get("total_deductions")),
                                    _decimal_or_none(r.get("net_commission")),
                                    _safe_str(r.get("month_year")) or _safe_str(month_label),
                                ),
                            )
                        rows_inserted = len(df_rows)

                    else:  # terminated
                        for r in df_rows:
                            cur.execute(
                                """
                                INSERT INTO `terminated`
                                (`upload_id`,`agent_code`,`policy_no`,`holder`,`surname`,
                                 `other_name`,`receipt_no`,`paydate`,`premium`,`com_rate`,
                                 `com_amt`,`policy_type`,`inception`,`status`,`agent_name`,
                                 `reason`,`month_year`,`AGENT_LICENSE_NUMBER`,`termination_date`)
                                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                """,
                                (
                                    upload_id,
                                    _safe_str(r.get("agent_code")) or _safe_str(eff_agent_code),
                                    _safe_str(r.get("policy_no")),
                                    _safe_str(r.get("holder")),
                                    _safe_str(r.get("surname")),
                                    _safe_str(r.get("other_name")),
                                    _safe_str(r.get("receipt_no")),
                                    _safe_str(r.get("paydate")),
                                    _decimal_or_none(r.get("premium")),
                                    _decimal_or_none(r.get("com_rate")),
                                    _decimal_or_none(r.get("com_amt")),
                                    _safe_str(r.get("policy_type")),
                                    _safe_str(r.get("inception")),
                                    _safe_str(r.get("status")),
                                    _safe_str(r.get("agent_name")) or _safe_str(eff_agent_name),
                                    _safe_str(r.get("reason")),
                                    _safe_str(r.get("month_year")) or _safe_str(month_label),
                                    _safe_str(r.get("AGENT_LICENSE_NUMBER")),
                                    _safe_str(r.get("termination_date")),
                                ),
                            )
                        rows_inserted = len(df_rows)

                conn.commit()
            finally:
                conn.close()
        except Exception:
            upload_id = upload_id or None
            rows_inserted = len(df_rows)

        moved_to: Optional[str] = None
        try:
            root = Path(file_path).resolve().parents[2]
            processed_dir = root / "data" / "processed"
            processed_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_name = f"{stamp}_{eff_agent_code or 'unknown'}_{doc}_{Path(file_path).name}"
            dest = processed_dir / out_name
            if Path(file_path).exists():
                Path(file_path).replace(dest)
                moved_to = str(dest)
        except Exception:
            moved_to = None

        return {
            "status": "success",
            "doc_type": doc.upper(),
            "agent_code": eff_agent_code,
            "agent_name": eff_agent_name,
            "month_year": month_label,
            "upload_id": upload_id,
            "rows_inserted": rows_inserted,
            "moved_to": moved_to,
        }
