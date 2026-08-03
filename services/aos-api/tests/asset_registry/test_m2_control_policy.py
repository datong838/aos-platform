"""Frozen M2-B shared authorization and header policy tests."""

from __future__ import annotations

import pytest

from aos_api.asset_registry.control_policy import (
    CONTROL_COMMAND_OPERATIONS,
    CONTROL_OPERATION_ROLES,
    READ_CONTROL_ROLES,
    parse_strong_if_match,
    require_control_read_role,
    require_control_role,
    require_target_markings,
    strong_etag,
    validate_idempotency_key,
)
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    AssetRegistryError,
    AssetRegistryErrorCode,
    DutySeparationRequiredError,
    IdempotencyKeyRequiredError,
    MarkingAccessDeniedError,
    PreconditionInvalidError,
    PreconditionRequiredError,
    RegistryIntegrityCorruptError,
)

_EXPECTED_OPERATION_ROLES = {
    "bundle_compositions.resolve": {
        "admin",
        "developer",
        "asset-installer",
    },
    "bundle_installations.create": {
        "admin",
        "developer",
        "asset-installer",
    },
    "bundle_installations.submit": {
        "admin",
        "developer",
        "asset-installer",
    },
    "bundle_installations.approve": {"admin", "asset-install-approver"},
    "bundle_installations.reject": {"admin", "asset-install-approver"},
    "bundle_installations.apply": {"admin", "asset-installer"},
    "bundle_installations.verify": {"admin", "asset-installer"},
    "bundle_installations.rollback": {"admin", "asset-installer"},
}


def test_control_operation_role_matrix_is_exact_and_fail_closed() -> None:
    assert CONTROL_COMMAND_OPERATIONS == frozenset(_EXPECTED_OPERATION_ROLES)
    assert {
        operation: set(roles) for operation, roles in CONTROL_OPERATION_ROLES.items()
    } == _EXPECTED_OPERATION_ROLES

    for operation, allowed_roles in _EXPECTED_OPERATION_ROLES.items():
        for role in allowed_roles:
            require_control_role(roles=[role], operation=operation)
        with pytest.raises(DutySeparationRequiredError):
            require_control_role(roles=["viewer"], operation=operation)

    with pytest.raises(ValueError, match="unknown asset control operation"):
        require_control_role(roles=["admin"], operation="unknown")


def test_control_read_roles_are_the_frozen_union() -> None:
    assert READ_CONTROL_ROLES == frozenset(
        {"admin", "developer", "asset-installer", "asset-install-approver"}
    )
    for role in READ_CONTROL_ROLES:
        require_control_read_role(roles=[role])
    with pytest.raises(DutySeparationRequiredError):
        require_control_read_role(roles=["viewer"])


def test_target_markings_have_no_admin_bypass_and_do_not_leak_names() -> None:
    require_target_markings(
        principal_markings=["public", "region-cn"],
        target_markings=["public"],
    )
    require_target_markings(principal_markings=[], target_markings=[])

    with pytest.raises(MarkingAccessDeniedError) as denied:
        require_target_markings(
            principal_markings=["public"],
            target_markings=["public", "secret-customer"],
        )
    assert denied.value.code is AssetRegistryErrorCode.MARKING_ACCESS_DENIED
    assert denied.value.details is None
    assert "secret-customer" not in str(denied.value)

    with pytest.raises(AssetNotFoundError) as hidden:
        require_target_markings(
            principal_markings=["public"],
            target_markings=["secret-customer"],
            conceal=True,
        )
    assert hidden.value.code is AssetRegistryErrorCode.NOT_FOUND
    assert hidden.value.details is None


@pytest.mark.parametrize(
    "target_markings",
    [[""], [" secret"], ["secret "], ["secret\x00"], ["secret\n"], [1], "secret"],
)
def test_malformed_target_markings_fail_closed(target_markings: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        require_target_markings(
            principal_markings=["secret"],
            target_markings=target_markings,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [None, "", " ", " leading", "trailing ", "bad\x00key", "bad\nkey", "x" * 161],
)
def test_idempotency_key_rejects_missing_or_unsafe_values(value: str | None) -> None:
    with pytest.raises(IdempotencyKeyRequiredError):
        validate_idempotency_key(value)


def test_idempotency_key_preserves_valid_printable_value() -> None:
    value = "request-" + "x" * 152
    assert len(value) == 160
    assert validate_idempotency_key(value) == value


@pytest.mark.parametrize(
    "value",
    ["", "*", 'W/"1"', '"0"', '"01"', "1", '"1", "2"', '"1\n"'],
)
def test_if_match_rejects_every_non_strong_positive_single_etag(value: str) -> None:
    with pytest.raises(PreconditionInvalidError):
        parse_strong_if_match(value)


def test_if_match_requires_header_and_round_trips_positive_version() -> None:
    with pytest.raises(PreconditionRequiredError):
        parse_strong_if_match(None)
    assert parse_strong_if_match('"42"') == ('"42"', 42)
    assert strong_etag(42) == '"42"'


@pytest.mark.parametrize(
    "value",
    ['"9223372036854775808"', '"' + "9" * 5000 + '"'],
)
def test_if_match_rejects_values_outside_postgres_bigint(value: str) -> None:
    with pytest.raises(PreconditionInvalidError):
        parse_strong_if_match(value)


def test_if_match_accepts_postgres_bigint_maximum() -> None:
    value = '"9223372036854775807"'
    assert parse_strong_if_match(value) == (value, 9_223_372_036_854_775_807)
    assert strong_etag(9_223_372_036_854_775_807) == value


@pytest.mark.parametrize(
    "version",
    [True, False, 0, -1, 1.0, "1", 9_223_372_036_854_775_808],
)
def test_strong_etag_rejects_non_positive_integer_versions(version: object) -> None:
    with pytest.raises(ValueError):
        strong_etag(version)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("error", "code", "status", "message"),
    [
        (
            MarkingAccessDeniedError(),
            AssetRegistryErrorCode.MARKING_ACCESS_DENIED,
            403,
            "asset marking access denied",
        ),
        (
            RegistryIntegrityCorruptError(),
            AssetRegistryErrorCode.REGISTRY_INTEGRITY_CORRUPT,
            500,
            "stored Registry data failed integrity verification",
        ),
    ],
)
def test_new_control_errors_have_fixed_safe_envelopes(
    error: AssetRegistryError,
    code: AssetRegistryErrorCode,
    status: int,
    message: str,
) -> None:
    assert error.code is code
    assert error.http_status == status
    assert error.details is None
    assert str(error) == message
