
# tests/test_admin_agents_csrf.py
from __future__ import annotations
from http import HTTPStatus

def test_admin_create_agent_rejects_without_csrf(client):
    r = client.post(
        "/api/admin/agents",
        json={"agent_code": "AGX", "agent_name": "Agent X", "is_active": 1},
    )
    assert r.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.UNPROCESSABLE_ENTITY)

def test_admin_create_agent_ok_with_csrf(client):
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    r = client.post(
        "/api/admin/agents",
        json={"agent_code": "AGX", "agent_name": "Agent X", "is_active": 1},
        headers={"X-CSRF-Token": csrf},
    )
    assert r.status_code == HTTPStatus.OK
    j = r.json()
    assert j["status"] == "SUCCESS"
    assert j["agent_code"] == "AGX"
