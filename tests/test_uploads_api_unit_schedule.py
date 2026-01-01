
# tests/test_uploads_api_unit_schedule.py
from __future__ import annotations
import io
import pandas as pd
import pytest

pytestmark = pytest.mark.unit

def _fake_df(d: dict) -> pd.DataFrame:
    return pd.DataFrame(d)

def test_upload_schedule_happy_path(client, monkeypatch):
    import src.api.uploads as uploads_api
    # bypass cookie auth
    monkeypatch.setattr(uploads_api, "_require_uploader", lambda req, ac: None, raising=True)
    # patch the symbol imported into uploads_api
    monkeypatch.setattr(
        uploads_api,
        "extract_schedule_data",
        lambda path: _fake_df({
            "agent_code": ["9518"], "agent_name": ["Agent 9518"],
            "commission_batch_code": ["COM_JUN_2025"],
            "total_premiums": [100.0], "income": [15.0],
            "total_deductions": [2.0], "net_commission": [13.0],
            "month_year": ["Jun 2025"],
        }),
        raising=True,
    )

    import src.ingestion.parser_db_integration as pdi
    def _fake_process(self, doc_type_key, agent_code, agent_name, df_rows, file_path, month_year_hint):
        return {
            "status": "success",
            "doc_type": "SCHEDULE",
            "agent_code": agent_code or "9518",
            "agent_name": agent_name or "Agent 9518",
            "month_year": month_year_hint or "Jun 2025",
            "upload_id": 456,
            "rows_inserted": len(df_rows or []),
            "moved_to": None,
        }
    monkeypatch.setattr(pdi.ParserDBIntegration, "process", _fake_process, raising=True)

    pdf_bytes = b"%PDF-1.4\n%EOF\n"  # content doesn't matter; parser is mocked
    files = {"file": ("schedule.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {"agent_code": "9518", "month_year": "Jun 2025", "agent_name": "Agent 9518"}

    resp = client.post("/api/pdf-enhanced/upload/schedule", files=files, data=data)
    assert resp.status_code == 200, resp.text
    j = resp.json()
    assert j["status"] == "success"
    assert j["doc_type"] == "SCHEDULE"
    assert j["agent_code"] == "9518"
    assert j["month_year"] == "Jun 2025"
    assert j["upload_id"] == 456
    assert j.get("records_count") == 1
