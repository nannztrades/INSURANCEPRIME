
# tests/test_ingestion_e2e_integration.py
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def ensure_active_agent(db_available: bool):
    if not db_available:
        return
    from src.ingestion.db import get_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO `agents` (`agent_code`,`agent_name`,`is_active`)
                VALUES (%s,%s,1)
                ON DUPLICATE KEY UPDATE `is_active`=1, `agent_name`=VALUES(`agent_name`)
                """,
                ("AG123", "Test Agent"),
            )
        conn.commit()
    finally:
        conn.close()

@pytest.fixture
def agent_cookie(client: TestClient, db_available: bool, ensure_active_agent):
    if not db_available:
        pytest.skip("DB not available; skipping integration test")
    r = client.post("/api/auth/login/agent", data={"agent_code": "AG123"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.cookies

# ...rest of your integration tests...
