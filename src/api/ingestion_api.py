
# pyright: reportCallIssue=false
# src/api/ingestion_api.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from src.ingestion.parser_db_integration import ParserDBIntegration
from src.ingestion.run_logger import RunLogger
from src.ingestion.commission import compute_expected_for_upload_dynamic, insert_expected_rows

# Import the parser module once; resolve and call inside a wrapper.
import src.parser.parser_db_ready_fixed_Version4 as parser_v4

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])


def _as_int(value: Any) -> Optional[int]:
    """Safely convert to int for values that may be Any | None."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    try:
        return int(value)
    except Exception:
        return None


def _parse_with_v4(func_name: str, path: str) -> Any:
    """
    Resolve a symbol from parser_v4 and call it.
    Encapsulating the call here prevents Pylance from flagging 'module is not callable' at call sites.
    """
    obj = getattr(parser_v4, func_name, None)
    if obj is None or not callable(obj):
        raise HTTPException(
            status_code=500,
            detail=f"Parser function '{func_name}' not available or not callable in parser_v4."
        )
    return obj(path)


@router.get("/health")
def ingestion_health() -> Dict[str, Any]:
    return {"status": "ok", "module": "ingestion_api"}


@router.post("/one")
async def ingest_one(
    doc_type: str = Form(...),  # 'statement' | 'schedule' | 'terminated'
    file: UploadFile = File(...),
    agent_code: Optional[str] = Form(None),
    agent_name: Optional[str] = Form(None),
    month_year_hint: Optional[str] = Form(None),
    dry_run: bool = Form(False),
) -> Dict[str, Any]:
    try:
        project_root = Path(__file__).resolve().parents[2]
        logger = RunLogger(project_root)

        content = await file.read()
        tmp = project_root / "tmp_ingestion_upload"
        tmp.mkdir(parents=True, exist_ok=True)
        filename = file.filename or "upload.pdf"
        target = tmp / filename
        with target.open("wb") as f:
            f.write(content)

        # Parse to DataFrame based on doc_type via wrapper
        doc = doc_type.lower().strip()
        if doc == "statement":
            df = _parse_with_v4("extract_statement_data", str(target))
        elif doc == "schedule":
            df = _parse_with_v4("extract_schedule_data", str(target))
        elif doc == "terminated":
            df = _parse_with_v4("extract_terminated_data", str(target))
        else:
            raise HTTPException(status_code=400, detail="Invalid doc_type")

        rows_raw: List[Dict[str, Any]] = [] if df is None else df.to_dict(orient="records")  # type: ignore[attr-defined]
        # Normalize keys to str so type is precisely List[Dict[str, Any]]
        rows: List[Dict[str, Any]] = [{str(k): v for k, v in r.items()} for r in rows_raw]

        integ = ParserDBIntegration()
        summary = integ.process(
            doc_type_key=doc,
            agent_code=str(agent_code or ""),
            agent_name=agent_name or None,
            df_rows=rows,
            file_path=target,
            month_year_hint=month_year_hint or None,
        )
        summary.setdefault("status", "success")
        logger.log_json(summary)
        logger.log_csv(summary)

        # If statement & not dry_run, compute dynamic expected commissions
        if (not dry_run) and summary.get("doc_type") == "STATEMENT" and summary.get("upload_id") is not None:
            upid = _as_int(summary.get("upload_id"))
            if upid is not None:
                rows_exp = compute_expected_for_upload_dynamic(upload_id=upid)
                inserted = insert_expected_rows(rows_exp)
                summary["expected_rows_inserted"] = inserted

        return summary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bulk")
async def ingest_bulk_dir(
    dir_path: str = Form(...),  # e.g., "data/incoming"
    override_agent_code: Optional[str] = Form(None),
    override_agent_name: Optional[str] = Form(None),
    dry_run: bool = Form(False),
) -> Dict[str, Any]:
    try:
        project_root = Path(__file__).resolve().parents[2]
        base = Path(dir_path)
        if not base.exists() or not base.is_dir():
            raise HTTPException(status_code=404, detail=f"Directory not found: {base}")

        logger = RunLogger(project_root)
        integ = ParserDBIntegration()
        results: List[Dict[str, Any]] = []

        for p in sorted(base.iterdir()):
            if not p.is_file():
                continue
            name = p.name.lower()

            # Resolve & call parser inside wrapper
            if "statement" in name:
                doc = "statement"
                df = _parse_with_v4("extract_statement_data", str(p))
            elif "schedule" in name:
                doc = "schedule"
                df = _parse_with_v4("extract_schedule_data", str(p))
            elif "terminat" in name:
                doc = "terminated"
                df = _parse_with_v4("extract_terminated_data", str(p))
            else:
                continue

            try:
                rows_raw: List[Dict[str, Any]] = [] if df is None else df.to_dict(orient="records")  # type: ignore[attr-defined]
                rows: List[Dict[str, Any]] = [{str(k): v for k, v in r.items()} for r in rows_raw]
                summary = integ.process(
                    doc_type_key=doc,
                    agent_code=str(override_agent_code or ""),
                    agent_name=override_agent_name or None,
                    df_rows=rows,
                    file_path=p,
                    month_year_hint=None,
                )
                summary.setdefault("status", "success")
                results.append(summary)
                logger.log_json(summary)
                logger.log_csv(summary)

                if (not dry_run) and doc == "statement" and summary.get("upload_id") is not None:
                    upid = _as_int(summary.get("upload_id"))
                    if upid is not None:
                        rows_exp = compute_expected_for_upload_dynamic(upload_id=upid)
                        inserted = insert_expected_rows(rows_exp)
                        logger.log_csv({
                            'type': 'EXPECTED_COMMISSIONS',
                            'file': p.name,
                            'rows_parsed': len(rows_exp),
                            'agent_code': summary.get('agent_code','') or (override_agent_code or ''),
                            'agent_name': summary.get('agent_name','') or (override_agent_name or ''),
                            'upload_id': summary.get('upload_id',''),
                            'rows_inserted': inserted,
                            'moved_to': summary.get('moved_to',''),
                            'status': 'success',
                            'error': ''
                        })
            except Exception as e:
                err = {
                    'type': 'ERROR',
                    'file': p.name,
                    'rows_parsed': '',
                    'agent_code': override_agent_code or '',
                    'agent_name': override_agent_name or '',
                    'upload_id': '',
                    'rows_inserted': '',
                    'moved_to': '',
                    'status': 'failure',
                    'error': str(e)
                }
                results.append(err)
                logger.log_csv(err)
                logger.log_json(err)

        return {"status": "OK", "count": len(results), "results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
