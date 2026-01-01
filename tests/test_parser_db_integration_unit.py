
# tests/test_parser_db_integration_unit.py
from __future__ import annotations
from pathlib import Path
import pytest

pytestmark = pytest.mark.unit

def test_parser_db_integration_handles_db_down(monkeypatch):
    from src.ingestion import parser_db_integration as pdi

    # Simulate DB down: get_conn raises
    monkeypatch.setattr("src.ingestion.db.get_conn", lambda: (_ for _ in ()).throw(Exception("DB down")))

    rows = [
        {"policy_no": "P001", "holder": "John Doe", "MONTH_YEAR": "Jun 2025", "premium": "10.00"},
        {"policy_no": "P002", "holder": "Jane Doe", "MONTH_YEAR": "Jun 2025", "premium": "20.00"},
    ]

    summary = pdi.ParserDBIntegration().process(
        doc_type_key="statement",
        agent_code="9518",
        agent_name="Agent 9518",
        df_rows=rows,
        file_path=Path("D:/PROJECT/INSURANCELOCAL/data/incoming/statement.pdf"),
        month_year_hint="Jun 2025",
    )

    assert summary["status"] == "success"
    assert summary["doc_type"] == "STATEMENT"
    assert summary["agent_code"] == "9518"
    assert summary["month_year"] == "Jun 2025"
    assert summary["upload_id"] is None or isinstance(summary["upload_id"], int)
    assert summary["rows_inserted"] == len(rows)
