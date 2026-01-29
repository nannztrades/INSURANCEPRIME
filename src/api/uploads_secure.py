
# src/api/uploads_secure.py
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from typing import Dict, Any
import os
import io
import re
from pypdf import PdfReader
from pypdf.errors import PdfStreamError
from src.services.auth_service import decode_token, TOKEN_COOKIE_NAME

router = APIRouter(prefix="/api/uploads-secure", tags=["Uploads Secure"])

UPLOAD_MAX_BYTES: int = int(os.getenv("UPLOAD_MAX_BYTES", str(5 * 1024 * 1024)))
_YYYY_MM = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _read_text(pdf_bytes: bytes, max_pages: int = 2) -> str:
    """Best‑effort PDF text extraction for cheap validation."""
    try:
        buf = io.BytesIO(pdf_bytes)
        reader = PdfReader(buf)
        pages = min(max_pages, len(reader.pages))
        chunks = []
        for i in range(pages):
            try:
                page_text = reader.pages[i].extract_text() or ""
                chunks.append(page_text)
            except Exception:
                continue
        return "\n".join(chunks).lower()
    except PdfStreamError:
        return ""
    except Exception:
        return ""


def _markers_for(file_type: str):
    ft = file_type.lower()
    if ft == "statement":
        return ["policy", "premium", "commission", "pay date"]
    if ft == "schedule":
        return ["net commission", "total deductions", "commission batch", "income"]
    if ft == "terminated":
        return ["termination", "reason", "status", "policy"]
    return []


def _require_uploader(request: Request, agent_code: str) -> None:
    """Agents may upload only for themselves; admin/superuser can upload for anyone."""
    tok = request.cookies.get(TOKEN_COOKIE_NAME)
    u = decode_token(tok) if tok else None
    if not u:
        raise HTTPException(status_code=403, detail="Authentication required")
    role = str((u.get("role") or "")).lower()
    if role == "agent":
        if str(u.get("agent_code") or "") != str(agent_code):
            raise HTTPException(status_code=403, detail="Agents may only upload for their own agent_code")
        return
    if role in ("admin", "superuser"):
        return
    raise HTTPException(status_code=403, detail="Role not permitted to upload")


@router.post("/{file_type}")
async def validate_upload(
    file_type: str,
    agent_code: str = Form(...),
    month_year: str = Form(..., description="YYYY-MM"),
    file: UploadFile = File(...),
    request: Request = ...,
) -> Dict[str, Any]:
    """
    Lightweight validation endpoint:
    - Enforces role + agent_code gating.
    - Validates month_year is YYYY-MM (422 on failure).
    - Enforces content-type = PDF and max size.
    - Runs cheap marker-based heuristics on first pages.
    """
    _require_uploader(request, agent_code)
    ft = file_type.lower().strip()
    if ft not in {"statement", "schedule", "terminated"}:
        raise HTTPException(status_code=400, detail="Invalid file_type")

    if not _YYYY_MM.fullmatch(str(month_year).strip()):
        raise HTTPException(status_code=422, detail="month_year must be YYYY-MM")

    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only PDF uploads are allowed")

    content = await file.read()
    size = len(content)

    if size > UPLOAD_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {UPLOAD_MAX_BYTES // (1024 * 1024)}MB)",
        )

    text = _read_text(content, max_pages=2)
    markers = _markers_for(ft)
    matched = sum(1 for m in markers if m in text)
    if matched < 2:
        raise HTTPException(
            status_code=400,
            detail=f"Uploaded PDF does not look like a {ft} document. No ingestion performed.",
        )

    return {
        "status": "VALIDATED",
        "validated": True,
        "agent_code": agent_code,
        "month_year": month_year,
        "file_type": ft,
        "size_bytes": size,
        "markers_expected": markers,
        "markers_matched": matched,
        "marker_match_ratio": matched / max(len(markers), 1),
    }
