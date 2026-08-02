"""Stable, transport-neutral errors for the asset registry."""
from __future__ import annotations

from enum import StrEnum
from typing import Any


class AssetRegistryErrorCode(StrEnum):
    MANIFEST_INVALID = "MANIFEST_INVALID"
    VERSION_INVALID = "VERSION_INVALID"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    BUNDLE_VERSION_IMMUTABLE = "BUNDLE_VERSION_IMMUTABLE"
    DEPENDENCY_CONFLICT = "DEPENDENCY_CONFLICT"
    DEPENDENCY_CYCLE = "DEPENDENCY_CYCLE"
    REVISION_CONFLICT = "REVISION_CONFLICT"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    APPROVAL_STALE = "APPROVAL_STALE"
    DUTY_SEPARATION_REQUIRED = "DUTY_SEPARATION_REQUIRED"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    ROLLBACK_BLOCKED = "ROLLBACK_BLOCKED"
    NOT_FOUND = "NOT_FOUND"


ERROR_HTTP_STATUS: dict[AssetRegistryErrorCode, int] = {
    AssetRegistryErrorCode.MANIFEST_INVALID: 400,
    AssetRegistryErrorCode.VERSION_INVALID: 400,
    AssetRegistryErrorCode.SIGNATURE_INVALID: 400,
    AssetRegistryErrorCode.BUNDLE_VERSION_IMMUTABLE: 409,
    AssetRegistryErrorCode.DEPENDENCY_CONFLICT: 409,
    AssetRegistryErrorCode.DEPENDENCY_CYCLE: 409,
    AssetRegistryErrorCode.REVISION_CONFLICT: 409,
    AssetRegistryErrorCode.IDEMPOTENCY_CONFLICT: 409,
    AssetRegistryErrorCode.APPROVAL_STALE: 409,
    AssetRegistryErrorCode.DUTY_SEPARATION_REQUIRED: 403,
    AssetRegistryErrorCode.PREFLIGHT_FAILED: 422,
    AssetRegistryErrorCode.VERIFICATION_FAILED: 422,
    AssetRegistryErrorCode.ROLLBACK_BLOCKED: 409,
    AssetRegistryErrorCode.NOT_FOUND: 404,
}


class AssetRegistryError(RuntimeError):
    """Safe application error; routers may map it without importing FastAPI here."""

    def __init__(
        self,
        code: AssetRegistryErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        if not message or message != message.strip():
            raise ValueError("error message must be non-blank and normalized")
        self.code = code
        self.http_status = ERROR_HTTP_STATUS[code]
        self.details = details
        super().__init__(message)


class ManifestInvalidError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.MANIFEST_INVALID, message, details=details
        )


class VersionInvalidError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(AssetRegistryErrorCode.VERSION_INVALID, message, details=details)


class SignatureInvalidError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.SIGNATURE_INVALID, message, details=details
        )


class BundleVersionImmutableError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.BUNDLE_VERSION_IMMUTABLE,
            message,
            details=details,
        )


class DependencyConflictError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.DEPENDENCY_CONFLICT, message, details=details
        )


class DependencyCycleError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.DEPENDENCY_CYCLE, message, details=details
        )


class RevisionConflictError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.REVISION_CONFLICT, message, details=details
        )


class IdempotencyConflictError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.IDEMPOTENCY_CONFLICT, message, details=details
        )


class ApprovalStaleError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(AssetRegistryErrorCode.APPROVAL_STALE, message, details=details)


class DutySeparationRequiredError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.DUTY_SEPARATION_REQUIRED,
            message,
            details=details,
        )


class PreflightFailedError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.PREFLIGHT_FAILED, message, details=details
        )


class VerificationFailedError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.VERIFICATION_FAILED, message, details=details
        )


class RollbackBlockedError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.ROLLBACK_BLOCKED, message, details=details
        )


class AssetNotFoundError(AssetRegistryError):
    def __init__(self, message: str = "asset registry resource not found") -> None:
        super().__init__(AssetRegistryErrorCode.NOT_FOUND, message)
