"""Stable error body — T-API §1 / §3."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aos_api.logging_facade import get_logger, get_trace_id

log = get_logger("aos-api.errors")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None
    traceId: str


class ApiError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def error_payload(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return ErrorBody(
        code=code,
        message=message,
        details=details,
        traceId=trace_id or get_trace_id(),
    ).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        log.warning(
            "api_error code=%s status=%s msg=%s",
            exc.code,
            exc.status_code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(
                code=exc.code,
                message=exc.message,
                details=exc.details,
            ),
        )

    @app.exception_handler(HTTPException)
    async def _http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "traceId" in detail:
            body = detail
        else:
            code = "AUTH_REQUIRED" if exc.status_code == 401 else "HTTP_ERROR"
            body = error_payload(
                code=code,
                message=str(detail),
            )
        log.warning("http_error status=%s code=%s", exc.status_code, body.get("code"))
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        log.info("validation_error errors=%s", exc.errors())
        return JSONResponse(
            status_code=400,
            content=error_payload(
                code="VALIDATION",
                message="request validation failed",
                details={"errors": exc.errors()},
            ),
        )
