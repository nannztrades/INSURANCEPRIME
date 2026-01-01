# src/api/uploads_secure.py
from __future__ import annotations
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request
from typing import Dict, Any

# ✅ switched from PyPDF2 to pypdf
from pypdf import PdfReader

from src.services.auth_service import decode_token, TOKEN_COOKIE_NAME

router = APIRouter(prefix="/api/uploads-secure", tags=["Uploads Secure"])


def _read_text(pdf_bytes: bytes, max_pages: int = 2) -> str:
    import io
    buf = io.BytesIO(pdf_bytes)
    reader = PdfReader(buf)
    pages = min(max_pages, len(reader.pages))
    text = []
    for i in range(pages):
        try:
            # pypdf's extract_text API mirrors PyPDF2
            page_text = reader.pages[i].extract_text() or ""
            text.append(page_text)
        except Exception:
            # Be lenient: skip unreadable pages
            pass
    return "\n".join(text).lower()


def _markers_for(file_type: str):
    if file_type == "statement":
        return ["policy", "premium", "commission", "pay date"]
    if file_type == "schedule":
        return ["net commission", "total deductions", "commission batch", "income"]
    if file_type == "terminated":
        return ["termination", "reason", "status", "policy"]
    return []


def _require_uploader(request: Request, agent_code: str):
    tok = request.cookies.get(TOKEN_COOKIE_NAME)
    u = decode_token(tok) if tok else None
    if not u:
        raise HTTPException(status_code=403, detail="Authentication required")
    role = str((u.get("role") or "")).lower()
    if role == "agent":
        if str(u.get("agent_code") or "") != str(agent_code):
            raise HTTPException(
                status_code=403,
                detail="Agents may only upload for their own agent_code",
            )
    elif role in ("admin", "superuser"):
        return
    else:
        raise HTTPException(status_code=403, detail="Role not permitted to upload")


@router.post("/{file_type}")
async def validate_upload(
    file_type: str,
    agent_code: str = Form(...),
    month_year: str = Form(...),
    file: UploadFile = File(...),
    request: Request = ...,
) -> Dict[str, Any]:
    _require_uploader(request, agent_code)

    ft = file_type.lower().strip()
    if ft not in {"statement", "schedule", "terminated"}:
        raise HTTPException(status_code=400, detail="Invalid file_type")

    if file.content_type not in {"application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="Only PDF uploads are allowed")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5 MB
        raise HTTPException(status_code=413, detail="File too large (max 5MB)")

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
        "size_bytes": len(content),
        "markers_matched": matched,
    }