
# tests/test_auth_csrf_requirements.py
from __future__ import annotations
from http import HTTPStatus

def test_login_agent_missing_csrf_is_rejected(client):
    r = client.post("/api/auth/login/agent", data={"agent_code": "AG001", "password": "pass123"})
    assert r.status_code in (HTTPStatus.FORBIDDEN, HTTPStatus.UNPROCESSABLE_ENTITY)

def test_login_agent_ok_with_csrf_header(client):
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    r = client.post(
        "/api/auth/login/agent",
        headers={"X-CSRF-Token": csrf},
        data={"agent_code": "AG001", "password": "pass123"},
    )
    assert r.status_code == HTTPStatus.OK
