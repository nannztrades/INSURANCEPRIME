
# tests/test_auth_flow.py
# Validates CSRF issuance and happy-path logins for agent and admin.

from src.services.auth_service import TOKEN_COOKIE_NAME

def test_csrf_endpoint_sets_cookie(client):
    r = client.get("/api/auth/csrf")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "OK"
    assert "csrf_token" in j
    # Cookie should be present
    assert any(c.name == "csrf_token" for c in client.cookies.jar)

def test_agent_login_happy_path(client):
    # First fetch CSRF
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    # Attempt login
    r = client.post(
        "/api/auth/login/agent",
        headers={"X-CSRF-Token": csrf},
        data={"agent_code": "AG001", "password": "pass123"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "OK"
    assert j["role"] == "agent"
    # Cookie with token should be set
    assert any(c.name == TOKEN_COOKIE_NAME for c in client.cookies.jar)

def test_admin_login_happy_path(client):
    csrf = client.get("/api/auth/csrf").json()["csrf_token"]
    r = client.post(
        "/api/auth/login/user",
        headers={"X-CSRF-Token": csrf},
        data={"user_id": 201, "password": "pass123"},
    )
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "OK"
    assert j["role"] in ("admin", "superuser")  # per fake decode we return admin for id 201
    assert any(c.name == TOKEN_COOKIE_NAME for c in client.cookies.jar)
