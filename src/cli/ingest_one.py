
# src/cli/ingest_one.py
from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.ingestion.parser_db_integration import ParserDBIntegration
from src.ingestion.run_logger import RunLogger
from src.parser.parser_db_ready_fixed_Version4 import (
    extract_statement_data,
    extract_schedule_data,
    extract_terminated_data,
)


def _normalize_rows(df) -> List[Dict[str, Any]]:
    """
    Convert a pandas DataFrame to List[Dict[str, Any]] with all keys coerced to str,
    satisfying Pylance's invariance for List[Dict[str, Any]].
    """
    rows_raw = [] if df is None else df.to_dict(orient="records")
    rows: List[Dict[str, Any]] = [{str(k): v for k, v in r.items()} for r in rows_raw]
    return rows


def _parse_to_rows(doc_type: str, path: Path) -> List[Dict[str, Any]]:
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


def cli_main():
    ap = argparse.ArgumentParser(
        description="Ingest one insurance file (parse → df_rows → ParserDBIntegration.process)"
    )
    ap.add_argument("--type", "-t", required=True, choices=["statement", "schedule", "terminated"],
                    help="Document type to parse & insert")
    ap.add_argument("--file", "-f", required=True, help="Path to PDF or text/CSV dump")
    ap.add_argument("--agent-code", help="Agent code (override). If omitted, parser output in rows is used.")
    ap.add_argument("--agent-name", help="Agent name (override)")
    ap.add_argument("--month-year", help="Month label hint (e.g., 'Jun 2025' or 'COM_JUN_2025')")
    ap.add_argument("--dry-run", action="store_true", help="Parse only—do NOT write to DB")
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[2]
    logger = RunLogger(project_root)

    p = Path(args.file)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {p}")

    # Parse → normalized df_rows
    rows = _parse_to_rows(args.type, p)

    # DRY-RUN path: do not call process(), only log a simulated summary
    if args.dry_run:
        summary = {
            "type": args.type.upper(),
            "file": p.name,
            "rows_parsed": len(rows),
            "agent_code": args.agent_code or "",
            "agent_name": args.agent_name or "",
            "upload_id": "",
            "rows_inserted": 0,
            "moved_to": "",
            "status": "DRY_RUN",
            "error": ""
        }
        logger.log_csv(summary)
        logger.log_json(summary)
        print("\n=== Ingestion (DRY-RUN) Summary ===")
        for k, v in summary.items():
            print(f"{k}: {v}")
        print("==============================\n")
        return

    # Real ingestion: call integration.process with df_rows
    integ = ParserDBIntegration()
    try:
        result = integ.process(
            doc_type_key=args.type.lower().strip(),
            agent_code=str(args.agent_code or ""),
            agent_name=args.agent_name or None,
            df_rows=rows,
            file_path=p,
            month_year_hint=args.month_year or None,
        )

        # Standardize and log
        summary = {
            "type": args.type.upper(),
            "file": p.name,
            "rows_parsed": len(rows),
            "agent_code": result.get("agent_code") or (args.agent_code or ""),
            "agent_name": result.get("agent_name") or (args.agent_name or ""),
            "upload_id": result.get("upload_id", ""),
            "rows_inserted": result.get("rows_inserted", 0),
            "moved_to": result.get("moved_to", ""),
            "status": "success",
            "error": ""
        }
        logger.log_csv(summary)
        logger.log_json(summary)

        print("\n=== Ingestion Summary ===")
        for k, v in result.items():
            print(f"{k}: {v}")
        print("=========================\n")

    except Exception as e:
        err = {
            "type": args.type.upper(),
            "file": p.name,
            "rows_parsed": len(rows),
            "agent_code": args.agent_code or "",
            "agent_name": args.agent_name or "",
            "upload_id": "",
            "rows_inserted": 0,
            "moved_to": "",
            "status": "failure",
            "error": str(e)
        }
        logger.log_csv(err)
        logger.log_json(err)
        print("\n[ERROR] Ingestion failed:", e, "\n")
        raise


if __name__ == "__main__":
    cli_main()
