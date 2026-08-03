"""Stable, transport-neutral errors for the asset registry."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class AssetRegistryErrorCode(StrEnum):
    MANIFEST_INVALID = "MANIFEST_INVALID"
    VERSION_INVALID = "VERSION_INVALID"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    TRUST_ROOT_UNAVAILABLE = "TRUST_ROOT_UNAVAILABLE"
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
    REGISTRY_SNAPSHOT_STALE = "REGISTRY_SNAPSHOT_STALE"
    CURRENT_INSTALLATION_STALE = "CURRENT_INSTALLATION_STALE"
    RESOLUTION_LIMIT_EXCEEDED = "RESOLUTION_LIMIT_EXCEEDED"
    INSTALLATION_STATE_CONFLICT = "INSTALLATION_STATE_CONFLICT"
    LOCK_INTEGRITY_INVALID = "LOCK_INTEGRITY_INVALID"
    LOCK_INTEGRITY_CORRUPT = "LOCK_INTEGRITY_CORRUPT"
    IDEMPOTENCY_KEY_REQUIRED = "IDEMPOTENCY_KEY_REQUIRED"
    PRECONDITION_REQUIRED = "PRECONDITION_REQUIRED"
    PRECONDITION_INVALID = "PRECONDITION_INVALID"
    MARKING_ACCESS_DENIED = "MARKING_ACCESS_DENIED"
    REGISTRY_INTEGRITY_CORRUPT = "REGISTRY_INTEGRITY_CORRUPT"
    NOT_FOUND = "NOT_FOUND"


ERROR_HTTP_STATUS: dict[AssetRegistryErrorCode, int] = {
    AssetRegistryErrorCode.MANIFEST_INVALID: 400,
    AssetRegistryErrorCode.VERSION_INVALID: 400,
    AssetRegistryErrorCode.SIGNATURE_INVALID: 400,
    AssetRegistryErrorCode.TRUST_ROOT_UNAVAILABLE: 503,
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
    AssetRegistryErrorCode.REGISTRY_SNAPSHOT_STALE: 409,
    AssetRegistryErrorCode.CURRENT_INSTALLATION_STALE: 409,
    AssetRegistryErrorCode.RESOLUTION_LIMIT_EXCEEDED: 422,
    AssetRegistryErrorCode.INSTALLATION_STATE_CONFLICT: 409,
    AssetRegistryErrorCode.LOCK_INTEGRITY_INVALID: 409,
    AssetRegistryErrorCode.LOCK_INTEGRITY_CORRUPT: 500,
    AssetRegistryErrorCode.IDEMPOTENCY_KEY_REQUIRED: 400,
    AssetRegistryErrorCode.PRECONDITION_REQUIRED: 428,
    AssetRegistryErrorCode.PRECONDITION_INVALID: 400,
    AssetRegistryErrorCode.MARKING_ACCESS_DENIED: 403,
    AssetRegistryErrorCode.REGISTRY_INTEGRITY_CORRUPT: 500,
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
        super().__init__(
            AssetRegistryErrorCode.VERSION_INVALID, message, details=details
        )


class SignatureInvalidError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.SIGNATURE_INVALID, message, details=details
        )


class TrustRootUnavailableError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.TRUST_ROOT_UNAVAILABLE,
            message,
            details=details,
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
        super().__init__(
            AssetRegistryErrorCode.APPROVAL_STALE, message, details=details
        )


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


class RegistrySnapshotStaleError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.REGISTRY_SNAPSHOT_STALE,
            message,
            details=details,
        )


class CurrentInstallationStaleError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.CURRENT_INSTALLATION_STALE,
            message,
            details=details,
        )


class ResolutionLimitExceededError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.RESOLUTION_LIMIT_EXCEEDED,
            message,
            details=details,
        )


class InstallationStateConflictError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.INSTALLATION_STATE_CONFLICT,
            message,
            details=details,
        )


class LockIntegrityInvalidError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.LOCK_INTEGRITY_INVALID,
            message,
            details=details,
        )


class LockIntegrityCorruptError(AssetRegistryError):
    def __init__(self) -> None:
        super().__init__(
            AssetRegistryErrorCode.LOCK_INTEGRITY_CORRUPT,
            "stored composition lock failed integrity verification",
        )


class IdempotencyKeyRequiredError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.IDEMPOTENCY_KEY_REQUIRED,
            message,
            details=details,
        )


class PreconditionRequiredError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.PRECONDITION_REQUIRED,
            message,
            details=details,
        )


class PreconditionInvalidError(AssetRegistryError):
    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            AssetRegistryErrorCode.PRECONDITION_INVALID,
            message,
            details=details,
        )


class MarkingAccessDeniedError(AssetRegistryError):
    """Fail a control-plane write without disclosing missing markings."""

    def __init__(self) -> None:
        super().__init__(
            AssetRegistryErrorCode.MARKING_ACCESS_DENIED,
            "asset marking access denied",
        )


class RegistryIntegrityCorruptError(AssetRegistryError):
    """Safe failure for malformed persisted Registry projections."""

    def __init__(self) -> None:
        super().__init__(
            AssetRegistryErrorCode.REGISTRY_INTEGRITY_CORRUPT,
            "stored Registry data failed integrity verification",
        )


class AssetNotFoundError(AssetRegistryError):
    def __init__(self, message: str = "asset registry resource not found") -> None:
        super().__init__(AssetRegistryErrorCode.NOT_FOUND, message)
