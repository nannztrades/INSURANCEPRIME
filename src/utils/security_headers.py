from __future__ import annotations

from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add a baseline set of security headers to every response.

    - HSTS (Strict-Transport-Security)
    - X-Frame-Options
    - X-Content-Type-Options
    - Referrer-Policy
    - Permissions-Policy
    - Content-Security-Policy (configurable)
    """

    def __init__(self, app: ASGIApp, *, csp: Optional[str] = None) -> None:
        super().__init__(app)
        # Very conservative default CSP; you can relax as needed.
        self._csp = (
            csp
            or "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline';"
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # Only set headers if not already present, so per-route overrides still work.
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains; preload",
        )
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=()",
        )
        response.headers.setdefault("Content-Security-Policy", self._csp)

        return response