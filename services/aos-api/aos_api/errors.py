"""Stable error body — T-API §1 / §3."""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aos_api.logging_facade import get_logger, get_trace_id
from aos_api.public_contracts import redact_sensitive
from aos_api.aip_contracts import AIP_ERROR_STATUS

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


def aip_error(
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> ApiError:
    """Build a stable AIP error and reject unregistered public codes."""

    if code not in AIP_ERROR_STATUS:
        raise ValueError(f"unregistered AIP error code: {code}")
    return ApiError(
        code=code,
        message=message,
        status_code=AIP_ERROR_STATUS[code],
        details=details,
    )


def error_payload(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    return ErrorBody(
        code=code,
        message=str(redact_sensitive(message)),
        details=redact_sensitive(details),
        traceId=trace_id or get_trace_id(),
    ).model_dump()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_request: Request, exc: ApiError) -> JSONResponse:
        log.warning(
            "api_error code=%s status=%s",
            exc.code,
            exc.status_code,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=error_payload(
                code=exc.code,
                message=str(redact_sensitive(exc.message)),
                details=redact_sensitive(exc.details),
            ),
        )

    @app.exception_handler(HTTPException)
    async def _http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            safe_detail = redact_sensitive(detail)
            body = error_payload(
                code=str(safe_detail.get("code") or "HTTP_ERROR"),
                message=str(safe_detail.get("message") or "request failed"),
                details=safe_detail.get("details"),
                trace_id=safe_detail.get("traceId"),
            )
        else:
            code = "AUTH_REQUIRED" if exc.status_code == 401 else "HTTP_ERROR"
            body = error_payload(
                code=code,
                message=str(redact_sensitive(detail)),
            )
        log.warning("http_error status=%s code=%s", exc.status_code, body.get("code"))
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        safe_errors = redact_sensitive(exc.errors())
        log.info("validation_error count=%s", len(exc.errors()))
        return JSONResponse(
            status_code=400,
            content=error_payload(
                code="VALIDATION",
                message="request validation failed",
                details={"errors": safe_errors},
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, _exc: Exception) -> JSONResponse:
        log.error("unhandled_api_error type=%s", type(_exc).__name__)
        return JSONResponse(
            status_code=500,
            content=error_payload(
                code="INTERNAL_ERROR",
                message="internal server error",
            ),
        )
