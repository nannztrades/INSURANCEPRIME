
# src/api/ingestion_api.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Annotated, Callable, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from src.ingestion.parser_db_integration import ParserDBIntegration
from src.ingestion.run_logger import RunLogger
from src.ingestion.commission import (
    compute_expected_for_upload_dynamic,
    insert_expected_rows,
)

# Import the parser module once; resolve callable names at runtime.
import src.parser.parser_db_ready_fixed_Version4 as parser_v4

from src.services.security import require_csrf

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])

# Parameter-level dependency (editor-friendly)
CSRF = Annotated[None, Depends(require_csrf)]


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
    Encapsulating the call here prevents 'module is not callable' and offers
    a single error path if the symbol isn't exposed.
    """
    obj = getattr(parser_v4, func_name, None)
    if obj is None or not callable(obj):
        raise HTTPException(
            status_code=500,
            detail=f"Parser function '{func_name}' not available or not callable in parser_v4.",
        )
    return obj(path)


def _get_ingest_callable(pdb: ParserDBIntegration) -> Callable[..., Dict[str, Any]]:
    """
    Fetch the ingestion method in a type-checker-friendly way.
    Supports either 'ingest_dataframe' or 'ingest_df'.
    """
    fn = getattr(pdb, "ingest_dataframe", None)
    if not callable(fn):
        fn = getattr(pdb, "ingest_df", None)
    if not callable(fn):
        raise HTTPException(status_code=500, detail="No ingestion method found on ParserDBIntegration")
    return cast(Callable[..., Dict[str, Any]], fn)


def _log_error(logger: Any, msg: str) -> None:
    """Log without tripping Pylance if the concrete API varies."""
    for name in ("log_error", "error", "log"):
        fn = getattr(logger, name, None)
        if callable(fn):
            try:
                fn(msg)
                return
            except Exception:
                pass
    try:
        print(f"[ingestion] {msg}")
    except Exception:
        pass


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
    _csrf_ok: CSRF = Depends(),
) -> Dict[str, Any]:
    project_root = Path(__file__).resolve().parents[2]
    logger = RunLogger(project_root)

    filename = file.filename or "upload.pdf"
    try:
        content = await file.read()
        tmp = project_root / "tmp_ingestion_upload"
        tmp.mkdir(parents=True, exist_ok=True)
        target = tmp / filename
        with target.open("wb") as f:
            f.write(content)

        # Parse to DataFrame based on doc_type via wrapper
        doc = (doc_type or "").lower().strip()
        if doc == "statement":
            df = _parse_with_v4("extract_statement_data", str(target))
        elif doc == "schedule":
            df = _parse_with_v4("extract_schedule_data", str(target))
        elif doc == "terminated":
            df = _parse_with_v4("extract_terminated_data", str(target))
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported doc_type: {doc_type}")

        # Persist using a DB integration helper (Pylance-safe)
        pdb = ParserDBIntegration()
        ingest = _get_ingest_callable(pdb)
        res = ingest(
            df=df,
            doc_type=doc,
            source_filename=filename,
            agent_code=agent_code,
            agent_name=agent_name,
            month_year_hint=month_year_hint,
            dry_run=dry_run,
        )
        upload_id = _as_int(res.get("upload_id"))

        # Compute expected commissions & insert (Statements only, not dry_run)
        if upload_id and not dry_run and doc == "statement":
            # ✅ Correct signatures (keyword for compute; single-arg for insert)
            expected_rows = compute_expected_for_upload_dynamic(upload_id=upload_id)
            inserted = insert_expected_rows(expected_rows)  # noqa: F841

        # Minimal structured response
        return {
            "status": "SUCCESS",
            "doc_type": doc,
            "upload_id": upload_id,
            "dry_run": bool(dry_run),
            "rows": _as_int(res.get("rows")) or 0,
            "agent_code": agent_code,
            "agent_name": agent_name,
            "month_year_hint": month_year_hint,
        }

    except HTTPException:
        raise
    except Exception as e:
        _log_error(logger, f"ingest_one failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
