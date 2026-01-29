
# src/api/health.py
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from pathlib import Path
import os
import shutil
from src.ingestion.db import get_conn

router = APIRouter(prefix="", tags=["Health"])

def _dirs() -> List[Path]:
    ingest = Path(os.getenv("INGEST_DIR", "data/incoming"))
    tmp = Path(os.getenv("TMP_DIR", "tmp_ingestion_upload"))
    reports = Path(os.getenv("REPORTS_DIR", "data/reports"))
    return [ingest, tmp, reports]

@router.get("/healthz")
def healthz() -> Dict[str, Any]:
    # App is up
    return {"status": "ok", "service": "icrs"}

@router.get("/readyz")
def readyz() -> Dict[str, Any]:
    # DB ping
    try:
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                _ = cur.fetchone()
        finally:
            conn.close()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB ping failed: {e}")

    # Directories exist and writable
    failed: List[str] = []
    for p in _dirs():
        try:
            p.mkdir(parents=True, exist_ok=True)
            test = p / ".writable.tmp"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
        except Exception as e:
            failed.append(f"{p} ({e})")

    if failed:
        raise HTTPException(status_code=503, detail=f"Dir check failed: {', '.join(failed)}")

    # Disk space ≥ 1 GB free
    try:
        base = Path(".").resolve()
        total, used, free = shutil.disk_usage(base)
        if free < 1_000_000_000:
            raise HTTPException(status_code=503, detail="Insufficient disk space (<1 GB)")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Disk check failed: {e}")

    return {
        "status": "ok",
        "db": "ok",
        "dirs": [str(p) for p in _dirs()],
        "disk_free_bytes": free,
    }
