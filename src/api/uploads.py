
# src/api/uploads.py
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request

from src.ingestion.parser_db_integration import ParserDBIntegration
from src.services.auth_service import decode_token, TOKEN_COOKIE_NAME
from src.parser.parser_db_ready_fixed_Version4 import (
    extract_statement_data,
    extract_schedule_data,
    extract_terminated_data,
)

router = APIRouter(prefix="/api", tags=["Uploads"])

ALLOWED_DOC_TYPES = {"statement", "schedule", "terminated"}

def _safe_filename(orig: str | None, agent_code: str, doc_type: str) -> str:
    """
    Build a safe filename:
    - If orig is None or empty, generate: {timestamp}_{agent_code}_{doc_type}.pdf
    - Strip any path components; keep basename only.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not orig:
        return f"{ts}_{agent_code}_{doc_type}.pdf"
    name = Path(orig).name
    if not name.strip():
        return f"{ts}_{agent_code}_{doc_type}.pdf"
    return name

def _require_uploader(request: Request, agent_code: str) -> None:
    """
    Gate uploads by role:
    - Agents may only upload for their own agent_code.
    - Admin/Superuser may upload for anyone.
    """
    tok = request.cookies.get(TOKEN_COOKIE_NAME)
    u = decode_token(tok) if tok else None
    if not u:
        raise HTTPException(status_code=403, detail="Authentication required")
    role = str((u.get("role") or "")).lower()
    if role == "agent":
        if str(u.get("agent_code") or "") != str(agent_code):
            raise HTTPException(status_code=403, detail="Agents may only upload for their own agent_code")
    elif role in ("admin", "superuser"):
        return
    else:
        raise HTTPException(status_code=403, detail="Role not permitted to upload")

@router.post("/pdf-enhanced/upload/{doc_type}")
async def upload_and_ingest(
    request: Request,
    doc_type: str,
    file: UploadFile = File(...),
    agent_code: str = Form(...),
    month_year: str = Form(...),
    agent_name: str = Form(""),
) -> Dict[str, Any]:
    """
    Accept a PDF upload, parse it, and persist via ParserDBIntegration.
    doc_type: statement | schedule | terminated
    """
    # Auth guard
    _require_uploader(request, agent_code)

    # Validate doc type
    doc_type_norm = doc_type.lower().strip()
    if doc_type_norm not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported doc_type '{doc_type}'. Use one of {sorted(ALLOWED_DOC_TYPES)}"
        )

    # Save incoming file
    project_root = Path(__file__).resolve().parents[2]
    incoming = project_root / "data" / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)

    filename = file.filename or "upload.pdf"
    safe_name = _safe_filename(filename, agent_code, doc_type_norm)
    target = incoming / safe_name

    contents = await file.read()
    with target.open("wb") as f:
        f.write(contents)

    # Parse to DataFrame -> rows list[dict] with str keys (Pylance-safe)
    try:
        if doc_type_norm == "statement":
            df = extract_statement_data(str(target))
        elif doc_type_norm == "schedule":
            df = extract_schedule_data(str(target))
        else:  # terminated
            df = extract_terminated_data(str(target))

        rows_raw = [] if df is None else df.to_dict(orient="records")
        # Normalize keys to str so type is precisely List[Dict[str, Any]]
        rows: List[Dict[str, Any]] = [{str(k): v for k, v in r.items()} for r in rows_raw]

        integ = ParserDBIntegration()
        summary = integ.process(
            doc_type_key=doc_type_norm,
            agent_code=str(agent_code or ""),
            agent_name=agent_name or None,
            df_rows=rows,
            file_path=target,
            month_year_hint=month_year or None,
        )

        return {
            "status": "success",
            "message": "PDF uploaded and processed.",
            "upload_id": summary.get("upload_id"),
            "records_count": summary.get("rows_inserted"),
            "agent_code": summary.get("agent_code") or agent_code,
            "doc_type": summary.get("doc_type"),
            "month_year": summary.get("month_year"),
            "file_saved_as": safe_name,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))