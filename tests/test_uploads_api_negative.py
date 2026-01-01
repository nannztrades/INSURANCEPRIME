
# tests/test_uploads_api_negative.py
from __future__ import annotations
import io
import pytest

pytestmark = pytest.mark.unit

def test_missing_file_statement(client):
    client.cookies.clear()
    # Missing file => FastAPI will raise 422 for required UploadFile
    data = {"agent_code": "9518", "month_year": "Jun 2025", "agent_name": "Agent 9518"}
    resp = client.post("/api/pdf-enhanced/upload/statement", data=data)
    assert resp.status_code == 422

def test_missing_agent_code_statement(client):
    client.cookies.clear()
    # Missing required Form field => 422
    pdf = b"%PDF-1.4\n%EOF\n"
    files = {"file": ("statement.pdf", io.BytesIO(pdf), "application/pdf")}
    data = {"month_year": "Jun 2025", "agent_name": "Agent 9518"}  # agent_code omitted
    resp = client.post("/api/pdf-enhanced/upload/statement", files=files, data=data)
    assert resp.status_code == 422

def test_invalid_doc_type_rejected(client, monkeypatch):
    client.cookies.clear()
    # Bypass auth to ensure we reach validation logic instead of 403 from auth guard
    import src.api.uploads as uploads_api
    monkeypatch.setattr(uploads_api, "_require_uploader", lambda req, ac: None, raising=True)

    pdf = b"%PDF-1.4\n%EOF\n"
    files = {"file": ("whatever.pdf", io.BytesIO(pdf), "application/pdf")}
    data = {"agent_code": "9518", "month_year": "Jun 2025", "agent_name": "Agent 9518"}
    resp = client.post("/api/pdf-enhanced/upload/not-a-type", files=files, data=data)
    assert resp.status_code == 400

def test_invalid_month_year_current_behavior(client, monkeypatch):
    client.cookies.clear()
    """
    NOTE: Today, invalid month_year is accepted by the backend (no strict format check).
    This test documents the current behavior: it still returns 200.

    If you later enforce a format (e.g., 'Mon YYYY'), update this assertion to expect 400.
    """
    import src.api.uploads as uploads_api
    # Bypass auth for a pure validation test
    monkeypatch.setattr(uploads_api, "_require_uploader", lambda req, ac: None, raising=True)
    # Avoid real parsing: return a tiny DF
    monkeypatch.setattr(
        uploads_api,
        "extract_statement_data",
        lambda path: __import__("pandas").DataFrame({"policy_no": ["P001"], "MONTH_YEAR": ["Bad"]}),
        raising=True,
    )
    # Mock integration summary
    import src.ingestion.parser_db_integration as pdi
    def _fake_process(self, doc_type_key, agent_code, agent_name, df_rows, file_path, month_year_hint):
        return {
            "status": "success",
            "doc_type": doc_type_key.upper(),
            "agent_code": agent_code or "9518",
            "agent_name": agent_name or "Agent 9518",
            "month_year": month_year_hint,  # "Bad"
            "upload_id": 999,
            "rows_inserted": len(df_rows or []),
            "moved_to": None,
        }
    monkeypatch.setattr(pdi.ParserDBIntegration, "process", _fake_process, raising=True)

    pdf = b"%PDF-1.4\n%EOF\n"
    files = {"file": ("statement.pdf", io.BytesIO(pdf), "application/pdf")}
    data = {"agent_code": "9518", "month_year": "Bad", "agent_name": "Agent 9518"}
    resp = client.post("/api/pdf-enhanced/upload/statement", files=files, data=data)
    assert resp.status_code == 200
    j = resp.json()
    assert j.get("month_year") == "Bad"
