
# tests/test_uploads_secure_unit.py
from __future__ import annotations
import io
import pytest

pytestmark = pytest.mark.unit

def test_non_pdf_rejected(client, monkeypatch):
    import src.api.uploads_secure as us
    monkeypatch.setattr(us, "_require_uploader", lambda req, ac: None, raising=True)
    files = {"file": ("x.txt", io.BytesIO(b"hi"), "text/plain")}
    data  = {"agent_code": "9518", "month_year": "Jun 2025"}
    r = client.post("/api/uploads-secure/statement", files=files, data=data)
    assert r.status_code == 400
    assert "Only PDF uploads are allowed" in r.text

def test_oversize_rejected(client, monkeypatch):
    import src.api.uploads_secure as us
    monkeypatch.setattr(us, "_require_uploader", lambda req, ac: None, raising=True)
    big = b"%PDF-1.4\n" + b"x" * (5 * 1024 * 1024 + 1)
    files = {"file": ("big.pdf", io.BytesIO(big), "application/pdf")}
    data  = {"agent_code": "9518", "month_year": "Jun 2025"}
    r = client.post("/api/uploads-secure/statement", files=files, data=data)
    assert r.status_code == 413
    assert "File too large" in r.text

def test_marker_fail(client, monkeypatch):
    import src.api.uploads_secure as us
    monkeypatch.setattr(us, "_require_uploader", lambda req, ac: None, raising=True)
    monkeypatch.setattr(us, "_read_text", lambda b, max_pages=2: "noise only", raising=True)
   
