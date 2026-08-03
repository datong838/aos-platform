"""M4-0 frozen Integration Case operation, role, scope, and marking policy."""

from __future__ import annotations

import pytest

from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    DutySeparationRequiredError,
)
from aos_api.asset_registry.integration_policy import (
    CREATE_CASE_OPERATION,
    GET_CASE_OPERATION,
    INTEGRATION_CASE_COMMAND_OPERATIONS,
    INTEGRATION_CASE_OPERATION_ROLES,
    INTEGRATION_CASE_OPERATIONS,
    LIST_CASES_OPERATION,
    LIST_TIMELINE_OPERATION,
    PROJECT_CASE_OPERATION,
    READ_CASE_ROLES,
    require_integration_case_role,
    require_integration_case_visibility,
    validate_integration_case_scope,
)

_READ_OPERATIONS = {
    LIST_CASES_OPERATION,
    GET_CASE_OPERATION,
    LIST_TIMELINE_OPERATION,
}


def test_five_operations_and_two_commands_are_exact() -> None:
    assert INTEGRATION_CASE_OPERATIONS == _READ_OPERATIONS | {
        CREATE_CASE_OPERATION,
        PROJECT_CASE_OPERATION,
    }
    assert INTEGRATION_CASE_COMMAND_OPERATIONS == {
        CREATE_CASE_OPERATION,
        PROJECT_CASE_OPERATION,
    }


def test_operation_role_matrix_is_dedicated_and_fail_closed() -> None:
    assert INTEGRATION_CASE_OPERATION_ROLES == {
        LIST_CASES_OPERATION: READ_CASE_ROLES,
        CREATE_CASE_OPERATION: frozenset({"integration-case-maker"}),
        GET_CASE_OPERATION: READ_CASE_ROLES,
        PROJECT_CASE_OPERATION: frozenset({"integration-case-projector"}),
        LIST_TIMELINE_OPERATION: READ_CASE_ROLES,
    }

    require_integration_case_role(
        roles=["integration-case-maker"], operation=CREATE_CASE_OPERATION
    )
    require_integration_case_role(
        roles=["integration-case-projector"], operation=PROJECT_CASE_OPERATION
    )
    for operation in _READ_OPERATIONS:
        for role in READ_CASE_ROLES:
            require_integration_case_role(roles=[role], operation=operation)

    with pytest.raises(DutySeparationRequiredError):
        require_integration_case_role(roles=["admin"], operation=CREATE_CASE_OPERATION)
    with pytest.raises(DutySeparationRequiredError):
        require_integration_case_role(
            roles=["integration-case-maker"], operation=PROJECT_CASE_OPERATION
        )
    with pytest.raises(DutySeparationRequiredError):
        require_integration_case_role(roles=["viewer"], operation=GET_CASE_OPERATION)
    with pytest.raises(ValueError, match="unknown integration case operation"):
        require_integration_case_role(roles=["admin"], operation="unknown")


@pytest.mark.parametrize("roles", ["admin", [" admin"], ["admin\n"], [1], []])
def test_malformed_or_unprivileged_roles_fail_closed(roles: object) -> None:
    with pytest.raises(DutySeparationRequiredError):
        require_integration_case_role(
            roles=roles,  # type: ignore[arg-type]
            operation=CREATE_CASE_OPERATION,
        )


def test_scope_is_exact_and_cannot_be_coerced() -> None:
    assert validate_integration_case_scope("current") == "current"
    assert validate_integration_case_scope("reference") == "reference"
    for value in ("", "CURRENT", " current", "reference ", "tenant", "live"):
        with pytest.raises(ValueError, match="integration case scope is invalid"):
            validate_integration_case_scope(value)


def test_case_visibility_conceals_marking_names_without_admin_bypass() -> None:
    require_integration_case_visibility(
        principal_markings=["public", "region-cn"],
        target_markings=["public"],
    )

    with pytest.raises(AssetNotFoundError) as hidden:
        require_integration_case_visibility(
            principal_markings=["public"],
            target_markings=["secret-customer"],
        )
    assert hidden.value.details is None
    assert "secret-customer" not in str(hidden.value)

    with pytest.raises(AssetNotFoundError):
        require_integration_case_visibility(
            principal_markings=["public"],
            target_markings=["public", "secret-customer"],
        )
