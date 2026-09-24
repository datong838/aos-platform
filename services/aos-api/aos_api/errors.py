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


def _json_safe(value: Any) -> Any:
    """Keep validation details inspectable without leaking unserializable objects."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(redact_sensitive(str(value)))


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

    def model_dump(self) -> dict[str, Any]:
        """Return the stable error body, for use as an ``HTTPException.detail``.

        ``ApiError`` is deliberately not a pydantic model — it is raised, not
        serialized — but routers consistently build their mapped
        ``HTTPException`` detail as ``ApiError(code=…, message=…).model_dump()``.
        That call used to raise ``AttributeError`` inside the error path itself,
        so every mapped 4xx surfaced as a 500 ``INTERNAL_ERROR``. Forwarding to
        :func:`error_payload` keeps the documented contract working and yields
        the same body shape every other error path produces.
        """

        return error_payload(code=self.code, message=self.message, details=self.details)


def is_not_found_code(code: str) -> bool:
    """判断领域错误码是否表达「资源不存在」语义（按其映射到 404）。

    平台的既有约定是「不存在的资源 → 404 + ``*_NOT_FOUND`` 码」：线上全量扫掠
    实测 **537 处 404 vs 7 处 400**，故把 400 的那几处视为映射缺陷而非约定差异。

    必须同时认两种形态，缺一即产生「404 分支从写下那天就是死代码」：
    - 后缀式 ``MEDIA_SET_NOT_FOUND`` / ``ITEM_NOT_FOUND`` / ``SESSION_NOT_FOUND``；
    - **裸 ``NOT_FOUND``**（部分引擎直接发裸码，如 ``gantt.GanttError``）。

    不要用 ``code.endswith("NOT_FOUND")`` 代替：它会误收 ``XNOT_FOUND`` 这类拼写。
    """

    return code == "NOT_FOUND" or code.endswith("_NOT_FOUND")


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
        safe_errors = _json_safe(redact_sensitive(exc.errors()))
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
