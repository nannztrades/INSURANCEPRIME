
# tests/test_admin_reports_smoke.py
# Lightweight API smoke tests for list endpoints — DB is faked to return [].

def test_list_uploads_empty(client):
    r = client.get("/api/admin/uploads")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0
    assert isinstance(body["items"], list)

def test_list_statements_empty(client):
    r = client.get("/api/admin/statements", params={"agent_code": "AG001", "month_year": "Jun 2025"})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 0

def test_list_schedule_empty(client):
    r = client.get("/api/admin/schedule", params={"agent_code": "AG001"})
    assert r.status_code == 200
    assert r.json()["count"] == 0

def test_list_terminated_empty(client):
    r = client.get("/api/admin/terminated", params={"agent_code": "AG001"})
    assert r.status_code == 200
    assert r.json()["count"] == 0

def test_active_policies_empty(client):
    r = client.get("/api/admin/active-policies", params={"agent_code": "AG001"})
    assert r.status_code == 200
    assert r.json()["count"] == 0
