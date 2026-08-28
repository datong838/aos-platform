"""Provider Health canonical startup preflight acceptance."""
from __future__ import annotations

import pytest

from aos_api.aip_action_store import AipActionNotFound
from aos_api.aip_provider_health_action import PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
from aos_api.aip_provider_health_action_authority import (
    provider_health_action_type_snapshot,
)
from aos_api.aip_provider_health_maintenance_startup import (
    AUTHORITY_MODE_ENV,
    CANONICAL_AUTHORITY_MODE,
    CANONICAL_SCOPE,
    CANONICAL_SERVICE_SUBJECT,
    MAINTENANCE_ENABLED_ENV,
    ProviderHealthStartupPreflightError,
    SERVICE_ORG_ENV,
    SERVICE_PROJECT_ENV,
    SERVICE_SUBJECT_ENV,
    preflight_provider_health_maintenance_startup,
)


class SnapshotStore:
    def __init__(self, snapshot=None, error=None) -> None:
        self.snapshot = snapshot
        self.error = error
        self.calls = []

    def action_type_snapshot(self, scope, action_type_id):
        self.calls.append((scope, action_type_id))
        if self.error is not None:
            raise self.error
        return self.snapshot


def _enabled_env() -> dict[str, str]:
    return {
        MAINTENANCE_ENABLED_ENV: "true",
        AUTHORITY_MODE_ENV: CANONICAL_AUTHORITY_MODE,
        SERVICE_SUBJECT_ENV: CANONICAL_SERVICE_SUBJECT,
        SERVICE_ORG_ENV: CANONICAL_SCOPE.org_id,
        SERVICE_PROJECT_ENV: CANONICAL_SCOPE.project_id,
    }


def test_preflight_is_inactive_by_default_without_database_read() -> None:
    store = SnapshotStore(error=AssertionError("database must not be read"))
    result = preflight_provider_health_maintenance_startup(
        environ={}, action_store=store
    )
    assert result.status == "PROVIDER_HEALTH_MAINTENANCE_STARTUP_INACTIVE"
    assert result.enabled is False
    assert result.ready is False
    assert result.principal is None
    assert result.action_type_snapshot is None
    assert store.calls == []


@pytest.mark.parametrize(
    ("updates", "expected_code"),
    [
        (
            {AUTHORITY_MODE_ENV: ""},
            "CANONICAL_ACTION_LEASE_AUTHORITY_MODE_REQUIRED",
        ),
        (
            {AUTHORITY_MODE_ENV: "legacy-bool"},
            "CANONICAL_ACTION_LEASE_AUTHORITY_MODE_REQUIRED",
        ),
        (
            {SERVICE_SUBJECT_ENV: "service:other"},
            "EXACT_PROVIDER_HEALTH_SERVICE_SUBJECT_REQUIRED",
        ),
        (
            {SERVICE_ORG_ENV: "dev-org"},
            "EXACT_PROVIDER_HEALTH_SERVICE_TENANT_REQUIRED",
        ),
        (
            {SERVICE_PROJECT_ENV: "other-project"},
            "EXACT_PROVIDER_HEALTH_SERVICE_TENANT_REQUIRED",
        ),
    ],
)
def test_preflight_rejects_authority_or_identity_drift_before_database(
    updates, expected_code
) -> None:
    env = _enabled_env()
    env.update(updates)
    store = SnapshotStore(error=AssertionError("database must not be read"))
    with pytest.raises(ProviderHealthStartupPreflightError) as error:
        preflight_provider_health_maintenance_startup(
            environ=env, action_store=store
        )
    assert error.value.code == expected_code
    assert store.calls == []


def test_preflight_requires_exact_installed_action_type() -> None:
    missing = SnapshotStore(error=AipActionNotFound("missing"))
    with pytest.raises(ProviderHealthStartupPreflightError) as error:
        preflight_provider_health_maintenance_startup(
            environ=_enabled_env(), action_store=missing
        )
    assert error.value.code == "PROVIDER_HEALTH_ACTION_TYPE_NOT_INSTALLED"

    drifted_snapshot = {
        **provider_health_action_type_snapshot(),
        "name": "drifted",
    }
    drifted = SnapshotStore(snapshot=drifted_snapshot)
    with pytest.raises(ProviderHealthStartupPreflightError) as error:
        preflight_provider_health_maintenance_startup(
            environ=_enabled_env(), action_store=drifted
        )
    assert error.value.code == "PROVIDER_HEALTH_ACTION_TYPE_REVISION_DRIFTED"
    assert missing.calls == [
        (CANONICAL_SCOPE, PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID)
    ]
    assert drifted.calls == [
        (CANONICAL_SCOPE, PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID)
    ]


def test_preflight_green_returns_only_canonical_service_identity() -> None:
    snapshot = provider_health_action_type_snapshot()
    store = SnapshotStore(snapshot=snapshot)
    result = preflight_provider_health_maintenance_startup(
        environ=_enabled_env(), action_store=store
    )
    assert result.status == "PROVIDER_HEALTH_MAINTENANCE_STARTUP_PREFLIGHT_GREEN"
    assert result.enabled is True
    assert result.ready is True
    assert result.authority_mode == CANONICAL_AUTHORITY_MODE
    assert result.action_type_snapshot == snapshot
    assert result.principal is not None
    assert result.principal.subject == CANONICAL_SERVICE_SUBJECT
    assert (result.principal.org_id, result.principal.project_id) == (
        CANONICAL_SCOPE.org_id,
        CANONICAL_SCOPE.project_id,
    )
    assert result.principal.roles == ["aip_executor"]
    assert result.principal.markings == ["public", "restricted"]
    assert result.principal.token_kind == "service"
    assert store.calls == [
        (CANONICAL_SCOPE, PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID)
    ]
