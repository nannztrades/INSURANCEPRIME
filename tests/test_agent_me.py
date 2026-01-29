
# tests/test_agent_me.py
from __future__ import annotations
from http import HTTPStatus

def test_agent_me_reports_agent_identity(client):
    r = client.get("/api/agent/me")
    assert r.status_code == HTTPStatus.OK
    j = r.json()
    assert j["status"] == "OK"
    assert j["role"] == "agent"
    assert j["agent_code"] == "AG001"
