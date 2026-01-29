
# src/services/roles.py
from __future__ import annotations
from typing import Callable, Set
from fastapi import Request, HTTPException, status

from src.services.auth_service import decode_token, TOKEN_COOKIE_NAME


def _current_user(request: Request) -> dict | None:
    tok = request.cookies.get(TOKEN_COOKIE_NAME)
    return decode_token(tok) if tok else None


def require_role(*allowed: str) -> Callable[[Request], dict]:
    """
    Dependency factory for role-based access control.

    Use like:
        Depends(require_role("admin"))
        Depends(require_role("admin", "superuser"))
    """
    allowed_set: Set[str] = {r.lower() for r in allowed}

    def _dep(request: Request) -> dict:
        user = _current_user(request)
        role = str((user or {}).get("role") or "").lower()
        if not user or (allowed_set and role not in allowed_set):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return user

    return _dep


# Convenience dependencies
require_admin = require_role("admin")
require_superuser = require_role("superuser")
require_admin_or_superuser = require_role("admin", "superuser")

# Export used by agent API
require_agent_user = require_role("agent")
