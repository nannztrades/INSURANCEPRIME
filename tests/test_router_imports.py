
# tests/test_router_imports.py
# Ensure all API modules import cleanly and expose a router.

import importlib
import pytest

MODULES = [
    "src.api.admin_reports",
    "src.api.agent_api",
    "src.api.superuser_api",
    "src.api.uploads",
    "src.api.uploads_secure",
    "src.api.ingestion_api",
    "src.api.agent_reports",
    "src.api.agent_missing",
    "src.api.disparities",
    "src.api.ui_pages",
    "src.api.admin_users",
    "src.api.admin_agents",
    "src.api.auth_api",
]

@pytest.mark.parametrize("modname", MODULES)
def test_import_module_has_router(modname):
    mod = importlib.import_module(modname)
    assert hasattr(mod, "router"), f"{modname} should export 'router'"
