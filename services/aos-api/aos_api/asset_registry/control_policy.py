"""Shared M2-B role, marking, idempotency, and strong-ETag policy."""

from __future__ import annotations

import re
from collections.abc import Collection

from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    DutySeparationRequiredError,
    IdempotencyKeyRequiredError,
    MarkingAccessDeniedError,
    PreconditionInvalidError,
    PreconditionRequiredError,
)

RESOLVE_OPERATION = "bundle_compositions.resolve"
CREATE_INSTALLATION_OPERATION = "bundle_installations.create"
SUBMIT_INSTALLATION_OPERATION = "bundle_installations.submit"
APPROVE_INSTALLATION_OPERATION = "bundle_installations.approve"
REJECT_INSTALLATION_OPERATION = "bundle_installations.reject"
APPLY_INSTALLATION_OPERATION = "bundle_installations.apply"
VERIFY_INSTALLATION_OPERATION = "bundle_installations.verify"
ROLLBACK_INSTALLATION_OPERATION = "bundle_installations.rollback"
UNINSTALL_INSTALLATION_OPERATION = "bundle_installations.uninstall"

CONTROL_COMMAND_OPERATIONS = frozenset(
    {
        RESOLVE_OPERATION,
        CREATE_INSTALLATION_OPERATION,
        SUBMIT_INSTALLATION_OPERATION,
        APPROVE_INSTALLATION_OPERATION,
        REJECT_INSTALLATION_OPERATION,
        APPLY_INSTALLATION_OPERATION,
        VERIFY_INSTALLATION_OPERATION,
        ROLLBACK_INSTALLATION_OPERATION,
        UNINSTALL_INSTALLATION_OPERATION,
    }
)

_CREATE_SUBMIT_ROLES = frozenset({"admin", "developer", "asset-installer"})
_APPROVAL_ROLES = frozenset({"admin", "asset-install-approver"})
_APPLY_ROLES = frozenset({"admin", "asset-installer"})
READ_CONTROL_ROLES = frozenset(
    {"admin", "developer", "asset-installer", "asset-install-approver"}
)
CONTROL_OPERATION_ROLES = {
    RESOLVE_OPERATION: _CREATE_SUBMIT_ROLES,
    CREATE_INSTALLATION_OPERATION: _CREATE_SUBMIT_ROLES,
    SUBMIT_INSTALLATION_OPERATION: _CREATE_SUBMIT_ROLES,
    APPROVE_INSTALLATION_OPERATION: _APPROVAL_ROLES,
    REJECT_INSTALLATION_OPERATION: _APPROVAL_ROLES,
    APPLY_INSTALLATION_OPERATION: _APPLY_ROLES,
    VERIFY_INSTALLATION_OPERATION: _APPLY_ROLES,
    ROLLBACK_INSTALLATION_OPERATION: _APPLY_ROLES,
    UNINSTALL_INSTALLATION_OPERATION: _APPLY_ROLES,
}

_STRONG_ETAG = re.compile(r'^"([1-9][0-9]*)"$')
_MAX_IDEMPOTENCY_KEY_LENGTH = 160
_MAX_POSTGRES_BIGINT = 9_223_372_036_854_775_807


def require_control_role(*, roles: Collection[str], operation: str) -> None:
    """Require the exact frozen operation role set."""

    allowed = CONTROL_OPERATION_ROLES.get(operation)
    if allowed is None:
        raise ValueError("unknown asset control operation")
    if not _normalized_values(roles).intersection(allowed):
        raise DutySeparationRequiredError(
            "asset control operation requires an authorized role"
        )


def require_control_read_role(*, roles: Collection[str]) -> None:
    """Allow every M2-B participant role to review immutable plans."""

    if not _normalized_values(roles).intersection(READ_CONTROL_ROLES):
        raise DutySeparationRequiredError(
            "asset control read requires an authorized role"
        )


def require_target_markings(
    *,
    principal_markings: Collection[str],
    target_markings: Collection[str],
    conceal: bool = False,
) -> None:
    """Enforce target subset without the platform's legacy admin bypass."""

    principal = _normalized_values(principal_markings)
    target = _normalized_target_markings(target_markings)
    if target.issubset(principal):
        return
    if conceal:
        raise AssetNotFoundError()
    raise MarkingAccessDeniedError()


def validate_idempotency_key(value: str | None) -> str:
    """Return a normalized M2 command key or its stable 400 error."""

    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or "\x00" in value
        or len(value) > _MAX_IDEMPOTENCY_KEY_LENGTH
        or not value.isprintable()
    ):
        raise IdempotencyKeyRequiredError("a valid Idempotency-Key header is required")
    return value


def parse_strong_if_match(value: str | None) -> tuple[str, int]:
    """Parse the sole accepted If-Match representation."""

    if value is None:
        raise PreconditionRequiredError("If-Match header is required")
    if not isinstance(value, str):
        raise PreconditionInvalidError("If-Match header is invalid")
    match = _STRONG_ETAG.fullmatch(value)
    if match is None:
        raise PreconditionInvalidError("If-Match header is invalid")
    digits = match.group(1)
    if len(digits) > 19:
        raise PreconditionInvalidError("If-Match header is invalid")
    version = int(digits)
    if version > _MAX_POSTGRES_BIGINT:
        raise PreconditionInvalidError("If-Match header is invalid")
    return value, version


def strong_etag(version: int) -> str:
    """Render one positive installation ETag."""

    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or version < 1
        or version > _MAX_POSTGRES_BIGINT
    ):
        raise ValueError("ETag version must be a positive integer")
    return f'"{version}"'


def _normalized_values(values: Collection[str]) -> set[str]:
    if isinstance(values, (str, bytes)):
        return set()
    normalized: set[str] = set()
    try:
        items = list(values)
    except TypeError:
        return set()
    for value in items:
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or "\x00" in value
        ):
            continue
        normalized.add(value)
    return normalized


def _normalized_target_markings(values: Collection[str]) -> set[str]:
    if isinstance(values, (str, bytes)):
        raise TypeError("target markings must be a collection of strings")
    try:
        items = list(values)
    except TypeError as exc:
        raise TypeError("target markings must be a collection of strings") from exc
    for value in items:
        if not isinstance(value, str):
            raise TypeError("target markings must contain only strings")
        if (
            not value
            or value != value.strip()
            or "\x00" in value
            or not value.isprintable()
        ):
            raise ValueError("target markings contain an invalid value")
    return set(items)
