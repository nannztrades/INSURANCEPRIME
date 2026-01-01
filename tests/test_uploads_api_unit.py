
# tests/test_uploads_api_unit.py
from __future__ import annotations
import io
import pandas as pd
import pytest

pytestmark = pytest.mark.unit

def _fake_df(d: dict) -> pd.DataFrame:
    return pd.DataFrame(d)

def test_upload_statement_happy_path(client, monkeypatch):
    """
    Unit: verify /api/pdf-enhanced/upload/statement returns a success summary
    without requiring real DB or auth.
    """

    # 1) bypass auth guard
    import src.api.uploads as uploads_api
    monkeypatch.setattr(uploads_api, "_require_uploader", lambda req, ac: None, raising=True)

    # 2) mock the EXACT symbol the route uses (imported into uploads_api)
    monkeypatch.setattr(
        uploads_api,
        "extract_statement_data",
        lambda path: _fake_df({"policy_no": ["P001"], "MONTH_YEAR": ["Jun 2025"], "premium": [10.0]}),
        raising=True,
    )

    # 3) mock integration -> summary (no DB work)
    import src.ingestion.parser_db_integration as pdi
    def _fake_process(self, doc_type_key, agent_code, agent_name, df_rows, file_path, month_year_hint):
        return {
            "status": "success",
            "doc_type": doc_type_key.upper(),
            "agent_code": agent_code or "9518",
            "agent_name": agent_name or "Agent 9518",
            "month_year": month_year_hint or "Jun 2025",
            "upload_id": 123,
            "rows_inserted": len(df_rows or []),
            "moved_to": None,
        }
    monkeypatch.setattr(pdi.ParserDBIntegration, "process", _fake_process, raising=True)

    # 4) tiny (minimal) PDF payload; parser is mocked so content won't be read
    pdf_bytes = b"%PDF-1.4\n%EOF\n"
    files = {"file": ("statement.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"agent_code": "9518", "month_year": "Jun 2025", "agent_name": "Agent 9518"}

    # 5) call the endpoint
    resp = client.post("/api/pdf-enhanced/upload/statement", files=files, data=data)

    assert resp.status_code == 200, resp.text
    j = resp.json()
    assert j["status"] == "success"
    assert j["doc_type"] == "STATEMENT"
    assert j["agent_code"] == "9518"
    assert j["month_year"] == "Jun 2025"
    assert j["upload_id"] == 123
    # Final assertion updated:
    assert j.get("records_count") == 1  # we mocked one parsed row
