
# tests/test_agent_and_superuser_endpoints.py
# Exercise endpoints that depend on agent/superuser identity.

from src.services.auth_service import TOKEN_COOKIE_NAME

def test_agent_statements_uses_agent_context(client):
    # Simulate agent cookie; our decode_token() returns an agent identity
    client.cookies.set(TOKEN_COOKIE_NAME, "agent-token", path="/")
    r = client.get("/api/agent/statements", params={"month_year": "Jun 2025"})
    assert r.status_code == 200
    assert r.json()["count"] == 0

def test_superuser_audit_flags_empty(client):
    client.cookies.set(TOKEN_COOKIE_NAME, "superuser-token", path="/")
    r = client.get("/api/superuser/audit-flags", params={"agent_code": "AG001"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
