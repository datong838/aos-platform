"""M2 frozen error-code contract tests."""

from __future__ import annotations

import pytest

from aos_api.asset_registry.errors import (
    ERROR_HTTP_STATUS,
    AssetRegistryError,
    AssetRegistryErrorCode,
    CurrentInstallationStaleError,
    EvidenceIntegrityCorruptError,
    EvidenceReferenceInvalidError,
    IdempotencyKeyRequiredError,
    InstallationStateConflictError,
    LockIntegrityCorruptError,
    LockIntegrityInvalidError,
    PreconditionInvalidError,
    PreconditionRequiredError,
    RegistrySnapshotStaleError,
    ResolutionLimitExceededError,
)


@pytest.mark.parametrize(
    ("error_type", "code", "status"),
    [
        (
            RegistrySnapshotStaleError,
            AssetRegistryErrorCode.REGISTRY_SNAPSHOT_STALE,
            409,
        ),
        (
            CurrentInstallationStaleError,
            AssetRegistryErrorCode.CURRENT_INSTALLATION_STALE,
            409,
        ),
        (
            ResolutionLimitExceededError,
            AssetRegistryErrorCode.RESOLUTION_LIMIT_EXCEEDED,
            422,
        ),
        (
            InstallationStateConflictError,
            AssetRegistryErrorCode.INSTALLATION_STATE_CONFLICT,
            409,
        ),
        (
            LockIntegrityInvalidError,
            AssetRegistryErrorCode.LOCK_INTEGRITY_INVALID,
            409,
        ),
        (
            IdempotencyKeyRequiredError,
            AssetRegistryErrorCode.IDEMPOTENCY_KEY_REQUIRED,
            400,
        ),
        (
            PreconditionRequiredError,
            AssetRegistryErrorCode.PRECONDITION_REQUIRED,
            428,
        ),
        (
            PreconditionInvalidError,
            AssetRegistryErrorCode.PRECONDITION_INVALID,
            400,
        ),
    ],
)
def test_m2_typed_errors_match_frozen_codes_and_statuses(
    error_type: type[AssetRegistryError],
    code: AssetRegistryErrorCode,
    status: int,
) -> None:
    error = error_type("frozen M2 error", details={"safe": True})

    assert error.code is code
    assert error.http_status == status
    assert error.details == {"safe": True}
    assert ERROR_HTTP_STATUS[code] == status


def test_every_error_code_has_an_http_status() -> None:
    assert set(ERROR_HTTP_STATUS) == set(AssetRegistryErrorCode)


def test_persisted_lock_corruption_error_cannot_leak_raw_content() -> None:
    error = LockIntegrityCorruptError()

    assert error.code is AssetRegistryErrorCode.LOCK_INTEGRITY_CORRUPT
    assert error.http_status == 500
    assert str(error) == "stored composition lock failed integrity verification"
    assert error.details is None

    with pytest.raises(TypeError):
        LockIntegrityCorruptError(  # type: ignore[call-arg]
            "raw lock payload",
            details={"lockPayload": {"resolved": ["secret"]}},
        )


def test_m4_evidence_errors_are_stable_and_do_not_leak_persisted_content() -> None:
    invalid = EvidenceReferenceInvalidError()
    assert invalid.code is AssetRegistryErrorCode.EVIDENCE_REFERENCE_INVALID
    assert invalid.http_status == 422
    assert invalid.details is None

    corrupt = EvidenceIntegrityCorruptError()
    assert corrupt.code is AssetRegistryErrorCode.EVIDENCE_INTEGRITY_CORRUPT
    assert corrupt.http_status == 500
    assert corrupt.details is None
    assert str(corrupt) == "stored Integration Evidence failed integrity verification"

    with pytest.raises(TypeError):
        EvidenceIntegrityCorruptError(  # type: ignore[call-arg]
            "raw Evidence",
        )
