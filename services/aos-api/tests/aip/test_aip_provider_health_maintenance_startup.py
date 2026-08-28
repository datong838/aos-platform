"""Provider Health canonical startup preflight acceptance."""
from __future__ import annotations

import pytest

from aos_api.aip_action_adapters import ACTION_ADAPTERS, ActionAdapterRegistry
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
    build_provider_health_maintenance_startup,
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


def _installed_catalog() -> dict:
    return {
        "items": [
            {
                "id": "provider-health-probe",
                "actionTypeId": PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
                "installed": True,
            }
        ]
    }


def test_preflight_is_inactive_by_default_without_database_read() -> None:
    store = SnapshotStore(error=AssertionError("database must not be read"))
    result = preflight_provider_health_maintenance_startup(
        environ={},
        action_store=store,
        plugin_catalog=lambda: (_ for _ in ()).throw(
            AssertionError("plugin catalog must not be read")
        ),
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
            environ=env,
            action_store=store,
            plugin_catalog=lambda: (_ for _ in ()).throw(
                AssertionError("plugin catalog must not be read")
            ),
        )
    assert error.value.code == expected_code
    assert store.calls == []


def test_preflight_requires_exact_installed_action_type() -> None:
    missing = SnapshotStore(error=AipActionNotFound("missing"))
    with pytest.raises(ProviderHealthStartupPreflightError) as error:
        preflight_provider_health_maintenance_startup(
            environ=_enabled_env(),
            action_store=missing,
            plugin_catalog=_installed_catalog,
        )
    assert error.value.code == "PROVIDER_HEALTH_ACTION_TYPE_NOT_INSTALLED"

    drifted_snapshot = {
        **provider_health_action_type_snapshot(),
        "name": "drifted",
    }
    drifted = SnapshotStore(snapshot=drifted_snapshot)
    with pytest.raises(ProviderHealthStartupPreflightError) as error:
        preflight_provider_health_maintenance_startup(
            environ=_enabled_env(),
            action_store=drifted,
            plugin_catalog=_installed_catalog,
        )
    assert error.value.code == "PROVIDER_HEALTH_ACTION_TYPE_REVISION_DRIFTED"
    assert missing.calls == [
        (CANONICAL_SCOPE, PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID)
    ]
    assert drifted.calls == [
        (CANONICAL_SCOPE, PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID)
    ]


@pytest.mark.parametrize(
    ("catalog", "expected_code"),
    [
        (
            {"items": []},
            "PROVIDER_HEALTH_ACTION_PLUGIN_NOT_DISCOVERABLE",
        ),
        (
            {
                "items": [
                    {
                        "id": "provider-health-probe",
                        "actionTypeId": PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
                        "installed": False,
                    }
                ]
            },
            "PROVIDER_HEALTH_ACTION_PLUGIN_NOT_INSTALLED",
        ),
        (
            {
                "items": [
                    {
                        "id": "provider-health-probe",
                        "actionTypeId": "OtherAction",
                        "installed": True,
                    }
                ]
            },
            "PROVIDER_HEALTH_ACTION_PLUGIN_CONTRACT_DRIFTED",
        ),
    ],
)
def test_preflight_requires_exact_installed_plugin_before_action_type_read(
    catalog, expected_code
) -> None:
    store = SnapshotStore(error=AssertionError("ActionType must not be read"))

    with pytest.raises(ProviderHealthStartupPreflightError) as error:
        preflight_provider_health_maintenance_startup(
            environ=_enabled_env(),
            action_store=store,
            plugin_catalog=lambda: catalog,
        )

    assert error.value.code == expected_code
    assert store.calls == []


def test_preflight_green_returns_only_canonical_service_identity() -> None:
    snapshot = provider_health_action_type_snapshot()
    store = SnapshotStore(snapshot=snapshot)
    result = preflight_provider_health_maintenance_startup(
        environ=_enabled_env(),
        action_store=store,
        plugin_catalog=_installed_catalog,
    )
    assert result.status == "PROVIDER_HEALTH_MAINTENANCE_STARTUP_PREFLIGHT_GREEN"
    assert result.enabled is True
    assert result.ready is True
    assert result.authority_mode == CANONICAL_AUTHORITY_MODE
    assert result.plugin_snapshot == _installed_catalog()["items"][0]
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


def test_startup_factory_inactive_requires_no_callable_or_database_read() -> None:
    store = SnapshotStore(error=AssertionError("database must not be read"))
    result = build_provider_health_maintenance_startup(
        environ={},
        action_store=store,
        plugin_catalog=lambda: (_ for _ in ()).throw(
            AssertionError("plugin catalog must not be read")
        ),
    )
    assert result.preflight.status == (
        "PROVIDER_HEALTH_MAINTENANCE_STARTUP_INACTIVE"
    )
    assert result.runtime is None
    assert store.calls == []


@pytest.mark.parametrize(
    ("refresh_health", "refresh_readiness"),
    [
        (None, lambda **_: {}),
        (lambda: {}, None),
        (None, None),
    ],
)
def test_startup_factory_requires_both_explicit_callables_after_preflight(
    refresh_health, refresh_readiness
) -> None:
    store = SnapshotStore(snapshot=provider_health_action_type_snapshot())
    with pytest.raises(ProviderHealthStartupPreflightError) as error:
        build_provider_health_maintenance_startup(
            environ=_enabled_env(),
            refresh_health=refresh_health,
            refresh_readiness=refresh_readiness,
            action_store=store,
            plugin_catalog=_installed_catalog,
        )
    assert error.value.code == (
        "EXPLICIT_PROVIDER_HEALTH_RUNTIME_CALLABLES_REQUIRED"
    )
    assert store.calls == [
        (CANONICAL_SCOPE, PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID)
    ]


def test_startup_factory_builds_isolated_runtime_without_calling_effects() -> None:
    store = SnapshotStore(snapshot=provider_health_action_type_snapshot())
    registry = ActionAdapterRegistry()
    calls = {"health": 0, "readiness": 0}

    def refresh_health():
        calls["health"] += 1
        raise AssertionError("construction must not call Provider refresh")

    def refresh_readiness(**_):
        calls["readiness"] += 1
        raise AssertionError("construction must not call readiness refresh")

    global_before = ACTION_ADAPTERS.get(PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID)
    result = build_provider_health_maintenance_startup(
        environ=_enabled_env(),
        refresh_health=refresh_health,
        refresh_readiness=refresh_readiness,
        action_store=store,
        plugin_catalog=_installed_catalog,
        registry=registry,
    )
    assert result.preflight.ready is True
    assert result.runtime is not None
    assert result.runtime.registry is registry
    assert result.runtime.conformance_report.green is True
    assert result.runtime.action_type_snapshot == provider_health_action_type_snapshot()
    assert calls == {"health": 0, "readiness": 0}
    assert ACTION_ADAPTERS.get(PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID) is global_before
    assert store.calls == [
        (CANONICAL_SCOPE, PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID),
        (CANONICAL_SCOPE, PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID),
    ]
