
# tests/test_uploads_secure_roles.py
from __future__ import annotations
import io
import pytest

pytestmark = pytest.mark.unit

def test_admin_can_upload_for_other_agent(client, monkeypatch):
    import src.api.uploads_secure as us
    # Simulate admin cookie
    monkeypatch.setattr(us, "decode_token", lambda tok: {"role": "admin"}, raising=True)
    client.cookies.set(us.TOKEN_COOKIE_NAME, "fake-token")
    # Mock text extraction: return enough markers
    monkeypatch.setattr(us, "_read_text", lambda b, max_pages=2: "policy premium commission", raising=True)

    files = {"file": ("s.pdf", io.BytesIO(b"%PDF-1.4\n%EOF\n"), "application/pdf")}
    # agent_code mismatch doesn't matter for admin
    data = {"agent_code": "AG-OTHER", "month_year": "Jun 2025"}
    r = client.post("/api/uploads-secure/statement", files=files, data=data)
    assert r.status_code == 200
    assert r.json().get("validated") is True

def test_superuser_can_upload_for_other_agent(client, monkeypatch):
    import src.api.uploads_secure as us
    monkeypatch.setattr(us, "decode_token", lambda tok: {"role": "superuser"}, raising=True)
    client.cookies.set(us.TOKEN_COOKIE_NAME, "fake-token")
    monkeypatch.setattr(us, "_read_text", lambda b, max_pages=2: "net commission total deductions income", raising=True)

    files = {"file": ("sched.pdf", io.BytesIO(b"%PDF-1.4\n%EOF\n"), "application/pdf")}
    data = {"agent_code": "AG-OTHER", "month_year": "Jun 2025"}
    r = client.post("/api/uploads-secure/schedule", files=files, data=data)
    assert r.status_code == 200
    assert r.json().get("validated") is True
