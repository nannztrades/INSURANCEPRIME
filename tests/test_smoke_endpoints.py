
# tests/test_smoke_endpoints.py
from __future__ import annotations
import pytest

pytestmark = pytest.mark.unit

def test_ui_landing(client):
    r = client.get("/ui/")
    assert r.status_code == 200

def test_ui_login_agent(client):
    r = client.get("/ui/login/agent")
    assert r.status_code == 200

def test_ui_login_admin(client):
    r = client.get("/ui/login/admin")
    assert r.status_code == 200

def test_ui_login_superuser(client):
    r = client.get("/ui/login/superuser")
    assert r.status_code == 200
