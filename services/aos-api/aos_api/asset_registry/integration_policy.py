"""Frozen M4 Integration Case authorization and operation policy."""

from __future__ import annotations

from collections.abc import Collection
from typing import Final, Literal

from aos_api.asset_registry.control_policy import require_target_markings
from aos_api.asset_registry.errors import DutySeparationRequiredError

LIST_CASES_OPERATION: Final = "integration_cases.list"
CREATE_CASE_OPERATION: Final = "integration_cases.create"
GET_CASE_OPERATION: Final = "integration_cases.get"
PROJECT_CASE_OPERATION: Final = "integration_cases.project"
LIST_TIMELINE_OPERATION: Final = "integration_cases.timeline.list"

INTEGRATION_CASE_OPERATIONS = frozenset(
    {
        LIST_CASES_OPERATION,
        CREATE_CASE_OPERATION,
        GET_CASE_OPERATION,
        PROJECT_CASE_OPERATION,
        LIST_TIMELINE_OPERATION,
    }
)
INTEGRATION_CASE_COMMAND_OPERATIONS = frozenset(
    {CREATE_CASE_OPERATION, PROJECT_CASE_OPERATION}
)

READ_CASE_ROLES = frozenset(
    {
        "admin",
        "developer",
        "integration-case-reader",
        "integration-case-maker",
        "integration-case-projector",
    }
)
INTEGRATION_CASE_OPERATION_ROLES = {
    LIST_CASES_OPERATION: READ_CASE_ROLES,
    CREATE_CASE_OPERATION: frozenset({"integration-case-maker"}),
    GET_CASE_OPERATION: READ_CASE_ROLES,
    PROJECT_CASE_OPERATION: frozenset({"integration-case-projector"}),
    LIST_TIMELINE_OPERATION: READ_CASE_ROLES,
}

IntegrationCaseScope = Literal["current", "reference"]


def require_integration_case_role(*, roles: Collection[str], operation: str) -> None:
    """Require the dedicated frozen role for an M4 operation."""

    allowed = INTEGRATION_CASE_OPERATION_ROLES.get(operation)
    if allowed is None:
        raise ValueError("unknown integration case operation")
    if not _normalized_roles(roles).intersection(allowed):
        raise DutySeparationRequiredError(
            "integration case operation requires an authorized role"
        )


def validate_integration_case_scope(value: str) -> IntegrationCaseScope:
    """Accept only the two public, mutually isolated Case scopes."""

    if value == "current":
        return "current"
    if value == "reference":
        return "reference"
    raise ValueError("integration case scope is invalid")


def require_integration_case_visibility(
    *,
    principal_markings: Collection[str],
    target_markings: Collection[str],
) -> None:
    """Conceal a Case when its markings are not fully visible."""

    require_target_markings(
        principal_markings=principal_markings,
        target_markings=target_markings,
        conceal=True,
    )


def _normalized_roles(values: Collection[str]) -> set[str]:
    if isinstance(values, (str, bytes)):
        return set()
    try:
        items = list(values)
    except TypeError:
        return set()
    return {
        value
        for value in items
        if isinstance(value, str)
        and value
        and value == value.strip()
        and "\x00" not in value
        and value.isprintable()
    }
