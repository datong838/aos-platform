"""HTTP middleware: trace / org / project / request logging — T-CROSS §3.2 · TX.2 metrics."""
from __future__ import annotations

import time
import uuid
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from aos_api.errors import error_payload
from aos_api.logging_facade import get_logger, reset_context, set_context
from aos_api.metrics import parse_traceparent, record

log = get_logger("aos-api.http")


class TraceLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        trace_id = (
            request.headers.get("x-trace-id")
            or parse_traceparent(request.headers.get("traceparent"))
            or str(uuid.uuid4())
        )
        org_id = request.headers.get("x-org-id", "dev-org")
        project_id = request.headers.get("x-project-id", "dev-project")
        request.state.trace_id = trace_id
        request.state.org_id = org_id
        request.state.project_id = project_id
        set_context(trace_id=trace_id, org_id=org_id, project_id=project_id)
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            log.exception("unhandled_error path=%s", request.url.path)
            elapsed_ms = (time.perf_counter() - started) * 1000
            record(
                method=request.method,
                path=request.url.path,
                status=500,
                duration_ms=elapsed_ms,
            )
            reset_context()
            return JSONResponse(
                status_code=500,
                content=error_payload(
                    code="INTERNAL",
                    message="internal error",
                    trace_id=trace_id,
                ),
            )
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Trace-Id"] = trace_id
        record(
            method=request.method,
            path=request.url.path,
            status=status_code,
            duration_ms=elapsed_ms,
        )
        log.info(
            "request method=%s path=%s status=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            status_code,
            elapsed_ms,
        )
        reset_context()
        return response
