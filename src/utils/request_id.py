from __future__ import annotations

import time
import uuid
from typing import Callable, Awaitable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Attach a unique X-Request-ID header to every response and emit a simple
    structured log line for each request.

    You can later swap the print() for a proper logger without changing the
    middleware contract.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = str(uuid.uuid4())
        start = time.perf_counter()

        # Optionally expose it to downstream handlers via state if needed
        request.state.request_id = request_id

        response: Response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        # Propagate the ID to the client
        response.headers["X-Request-ID"] = request_id

        # Minimal structured log; replace with your own logger if desired
        print(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
            }
        )

        return response