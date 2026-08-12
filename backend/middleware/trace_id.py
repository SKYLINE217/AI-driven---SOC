"""
SOC Triager — Trace ID middleware.

Generates a UUID4 trace_id for every request, binds it to the structlog
context, and adds it as X-Trace-Id in the response header.
This makes every log line for a given request correlatable.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or str(uuid.uuid4())

        # Bind trace_id to structlog context for this coroutine scope
        with structlog.contextvars.bound_contextvars(trace_id=trace_id):
            response = await call_next(request)

        response.headers["X-Trace-Id"] = trace_id
        return response
