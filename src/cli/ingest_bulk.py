
# src/cli/ingest_bulk.py
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Dict, Any

from src.ingestion.parser_db_integration import ParserDBIntegration
from src.ingestion.run_logger import RunLogger
from src.ingestion.commission import compute_expected_for_upload_dynamic, insert_expected_rows
from src.parser.parser_db_ready_fixed_Version4 import (
    extract_statement_data,
    extract_schedule_data,
    extract_terminated_data,
)


# ---- Filename token detection ------------------------------------------------

TOKEN_MAP = {
    "statement": ["statement"],
    "schedule": ["schedule"],
    "terminated": ["terminated", "termination"],
}

def detect_type_from_name(name: str) -> str:
    """Detect doc type by filename tokens (case-insensitive)."""
    n = name.lower()
    for key, tokens in TOKEN_MAP.items():
        for t in tokens:
            if t in n:
                return key
    # Common fallback for "terminat..." fragments
    if re.search(r"terminat", n):
        return "terminated"
    raise ValueError(f"Cannot detect type from filename: {name}")


# ---- Parse helpers (Pylance-safe rows) --------------------------------------

def _normalize_rows(df) -> List[Dict[str, Any]]:
    """
    Convert a pandas DataFrame to List[Dict[str, Any]] with all keys coerced to str,
    satisfying Pylance's invariance for List[Dict[str, Any]].
    """
    rows_raw = [] if df is None else df.to_dict(orient="records")
    rows: List[Dict[str, Any]] = [{str(k): v for k, v in r.items()} for r in rows_raw]
    return rows

def _parse_to_rows(doc_type: str, path: Path) -> List[Dict[str, Any]]:
    """Dispatch to the correct extractor and return normalized rows."""
    doc = doc_type.lower().strip()
    if doc == "statement":
        df = extract_statement_data(str(path))
    elif doc == "schedule":
        df = extract_schedule_data(str(path))
    elif doc == "terminated":
        df = extract_terminated_data(str(path))
    else:
        raise ValueError(f"Unknown doc_type: {doc_type}")
    return _normalize_rows(df)


# ---- CLI entry ---------------------------------------------------------------

def cli_main():
    ap = argparse.ArgumentParser(
        description="Bulk ingest files (parse → df_rows → ParserDBIntegration.process)"
    )
    ap.add_argument("--dir", "-d", required=True,
                    help="Directory containing files to ingest (e.g., data/incoming)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Parse only—do NOT write to DB")
    ap.add_argument("--agent-code", help="Override agent code for all files (optional)")
    ap.add_argument("--agent-name", help="Override agent name for all files (optional)")
    ap.add_argument("--month-year", help="Month label hint for all files (optional)")
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    logger = RunLogger(project_root)
    base = Path(args.dir)

    if not base.exists() or not base.is_dir():
        raise FileNotFoundError(f"Directory not found: {base}")

    summaries: List[Dict[str, Any]] = []
    integ = ParserDBIntegration()  # current __init__ takes no arguments

    for p in sorted(base.iterdir()):
        if not p.is_file():
            continue

        try:
            # Detect doc type from filename, then parse → normalized rows
            doc_type = detect_type_from_name(p.name)
            rows = _parse_to_rows(doc_type, p)

            if args.dry_run:
                # Simulated summary—no DB writes
                summary = {
                    "type": doc_type.upper(),
                    "file": p.name,
                    "rows_parsed": len(rows),
                    "agent_code": args.agent_code or "",
                    "agent_name": args.agent_name or "",
                    "upload_id": "",
                    "rows_inserted": 0,
                    "moved_to": "",
                    "status": "DRY_RUN",
                    "error": "",
                }
                summaries.append(summary)
                logger.log_csv(summary)
                logger.log_json(summary)
                continue

            # Real ingestion via integration.process (df_rows path)
            result = integ.process(
                doc_type_key=doc_type,
                agent_code=str(args.agent_code or ""),
                agent_name=args.agent_name or None,
                df_rows=rows,
                file_path=p,
                month_year_hint=args.month_year or None,
            )

            # Standardize and log
            summary = {
                "type": doc_type.upper(),
                "file": p.name,
                "rows_parsed": len(rows),
                "agent_code": result.get("agent_code") or (args.agent_code or ""),
                "agent_name": result.get("agent_name") or (args.agent_name or ""),
                "upload_id": result.get("upload_id", ""),
                "rows_inserted": result.get("rows_inserted", 0),
                "moved_to": result.get("moved_to", ""),
                "status": "success",
                "error": "",
            }
            summaries.append(summary)
            logger.log_csv(summary)
            logger.log_json(summary)

            # Dynamic expected commissions (Statements only, not dry-run)
            if doc_type == "statement" and result.get("upload_id"):
                rows_exp = compute_expected_for_upload_dynamic(upload_id=int(result["upload_id"]))
                inserted = insert_expected_rows(rows_exp)
                logger.log_csv({
                    "type": "EXPECTED_COMMISSIONS",
                    "file": p.name,
                    "rows_parsed": len(rows_exp),
                    "agent_code": summary.get("agent_code", ""),
                    "agent_name": summary.get("agent_name", ""),
                    "upload_id": summary.get("upload_id", ""),
                    "rows_inserted": inserted,
                    "moved_to": summary.get("moved_to", ""),
                    "status": "success",
                    "error": "",
                })

        except Exception as e:
            err = {
                "type": "ERROR",
                "file": p.name,
                "rows_parsed": "",
                "agent_code": args.agent_code or "",
                "agent_name": args.agent_name or "",
                "upload_id": "",
                "rows_inserted": "",
                "moved_to": "",
                "status": "failure",
                "error": str(e),
            }
            summaries.append(err)
            logger.log_csv(err)
            logger.log_json(err)

    # Console report
    print("\n=== Bulk Ingestion Report ===")
    total = len(summaries)
    ok = sum(1 for s in summaries if s.get("status") in ("success", "DRY_RUN"))
    fail = total - ok
    print(f"Files processed: {total} | success/DRY_RUN: {ok} | failed: {fail}")
    for s in summaries:
        print(f"- {s.get('type')}: file={s.get('file')} upload_id={s.get('upload_id')} "
              f"rows_inserted={s.get('rows_inserted')} status={s.get('status')}")
    print("============================\n")


if __name__ == "__main__":
    cli_main()
