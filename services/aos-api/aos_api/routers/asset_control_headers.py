"""Raw ASGI header cardinality checks for the M2 control plane."""

from __future__ import annotations

from fastapi import Request

from aos_api.asset_registry.control_policy import (
    parse_strong_if_match,
    validate_idempotency_key,
)
from aos_api.asset_registry.errors import (
    IdempotencyKeyRequiredError,
    PreconditionInvalidError,
)


def require_idempotency_key(request: Request) -> str:
    values = _raw_header_values(request, b"idempotency-key")
    if len(values) != 1:
        raise IdempotencyKeyRequiredError(
            "exactly one valid Idempotency-Key header is required"
        )
    return validate_idempotency_key(values[0])


def require_if_match(request: Request) -> str:
    values = _raw_header_values(request, b"if-match")
    if not values:
        return parse_strong_if_match(None)[0]
    if len(values) != 1:
        raise PreconditionInvalidError("If-Match header is invalid")
    return parse_strong_if_match(values[0])[0]


def _raw_header_values(request: Request, name: bytes) -> list[str]:
    values: list[str] = []
    for raw_name, raw_value in request.scope.get("headers", []):
        if raw_name.lower() == name:
            try:
                values.append(raw_value.decode("latin-1"))
            except UnicodeDecodeError as exc:
                raise ValueError("request header is not decodable") from exc
    return values
