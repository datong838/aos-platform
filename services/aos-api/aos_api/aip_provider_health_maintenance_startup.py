"""Fail-closed startup preflight for canonical Provider Health maintenance."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from aos_api.aip_action_adapters import ActionAdapterRegistry
from aos_api.aip_action_store import AipActionStore, AipActionStoreError
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_provider_health_action import PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
from aos_api.aip_provider_health_action_authority import (
    provider_health_action_type_snapshot,
)
from aos_api.aip_provider_health_maintenance_runtime import (
    ProviderHealthMaintenanceRuntime,
    build_provider_health_maintenance_runtime,
)
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope

MAINTENANCE_ENABLED_ENV = "AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED"
AUTHORITY_MODE_ENV = "AOS_AIP_TEXT_HEALTH_CANONICAL_AUTHORITY_MODE"
SERVICE_SUBJECT_ENV = "AOS_AIP_TEXT_HEALTH_SERVICE_SUBJECT"
SERVICE_ORG_ENV = "AOS_AIP_TEXT_HEALTH_SERVICE_ORG_ID"
SERVICE_PROJECT_ENV = "AOS_AIP_TEXT_HEALTH_SERVICE_PROJECT_ID"

CANONICAL_AUTHORITY_MODE = "action-lease-v1"
CANONICAL_SERVICE_SUBJECT = "service:aip-provider-health-maintenance"
CANONICAL_SCOPE = TenantScope("org-org", "dev-project")
CANONICAL_SERVICE_ROLES = ["aip_executor"]
CANONICAL_SERVICE_MARKINGS = ["public", "restricted"]
CANONICAL_PLUGIN_ID = "provider-health-probe"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class ProviderHealthStartupPreflightError(RuntimeError):
    """Stable startup failure that contains no credential or Provider detail."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProviderHealthStartupPreflight:
    status: str
    enabled: bool
    ready: bool
    authority_mode: str | None = None
    principal: Principal | None = None
    plugin_snapshot: dict[str, Any] | None = None
    action_type_snapshot: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProviderHealthMaintenanceStartup:
    preflight: ProviderHealthStartupPreflight
    runtime: ProviderHealthMaintenanceRuntime | None = None


def _legacy_maintenance_enabled(environ: Mapping[str, str]) -> bool:
    return environ.get(MAINTENANCE_ENABLED_ENV, "false").strip().lower() in (
        _TRUE_VALUES
    )


def _default_plugin_catalog() -> dict[str, Any]:
    from aos_api.action_template_registry import DEFAULTS, KEY, SUBDIR
    from aos_api.aip_kv_store import get_payload
    from aos_api.plugin_disk import scan_disk
    from aos_api.tenant_scope import bind_tenant_scope

    with bind_tenant_scope(CANONICAL_SCOPE):
        state = get_payload(KEY) or {}
    raw_installed = state.get("installed")
    installed = (
        {str(item) for item in raw_installed}
        if isinstance(raw_installed, list)
        else set(DEFAULTS)
    )
    items = []
    for manifest in scan_disk(SUBDIR):
        if manifest.get("id") != CANONICAL_PLUGIN_ID:
            continue
        items.append(
            {
                "id": CANONICAL_PLUGIN_ID,
                "actionTypeId": manifest.get("actionTypeId"),
                "installed": CANONICAL_PLUGIN_ID in installed,
            }
        )
    return {"items": items}


def _canonical_plugin_snapshot(
    plugin_catalog: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    items = plugin_catalog().get("items") or []
    matches = [item for item in items if item.get("id") == CANONICAL_PLUGIN_ID]
    if len(matches) != 1:
        raise ProviderHealthStartupPreflightError(
            "PROVIDER_HEALTH_ACTION_PLUGIN_NOT_DISCOVERABLE"
        )
    snapshot = dict(matches[0])
    if snapshot.get("actionTypeId") != PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID:
        raise ProviderHealthStartupPreflightError(
            "PROVIDER_HEALTH_ACTION_PLUGIN_CONTRACT_DRIFTED"
        )
    if snapshot.get("installed") is not True:
        raise ProviderHealthStartupPreflightError(
            "PROVIDER_HEALTH_ACTION_PLUGIN_NOT_INSTALLED"
        )
    return snapshot


def preflight_provider_health_maintenance_startup(
    *,
    environ: Mapping[str, str] | None = None,
    action_store: AipActionStore | None = None,
    plugin_catalog: Callable[[], dict[str, Any]] | None = None,
) -> ProviderHealthStartupPreflight:
    """Validate wiring prerequisites without constructing or starting a runtime."""
    env = os.environ if environ is None else environ
    if not _legacy_maintenance_enabled(env):
        return ProviderHealthStartupPreflight(
            status="PROVIDER_HEALTH_MAINTENANCE_STARTUP_INACTIVE",
            enabled=False,
            ready=False,
        )

    authority_mode = env.get(AUTHORITY_MODE_ENV)
    if authority_mode != CANONICAL_AUTHORITY_MODE:
        raise ProviderHealthStartupPreflightError(
            "CANONICAL_ACTION_LEASE_AUTHORITY_MODE_REQUIRED"
        )
    if env.get(SERVICE_SUBJECT_ENV) != CANONICAL_SERVICE_SUBJECT:
        raise ProviderHealthStartupPreflightError(
            "EXACT_PROVIDER_HEALTH_SERVICE_SUBJECT_REQUIRED"
        )
    if (
        env.get(SERVICE_ORG_ENV) != CANONICAL_SCOPE.org_id
        or env.get(SERVICE_PROJECT_ENV) != CANONICAL_SCOPE.project_id
    ):
        raise ProviderHealthStartupPreflightError(
            "EXACT_PROVIDER_HEALTH_SERVICE_TENANT_REQUIRED"
        )

    principal = Principal(
        subject=CANONICAL_SERVICE_SUBJECT,
        org_id=CANONICAL_SCOPE.org_id,
        project_id=CANONICAL_SCOPE.project_id,
        roles=list(CANONICAL_SERVICE_ROLES),
        markings=list(CANONICAL_SERVICE_MARKINGS),
        token_kind="service",
    )
    plugin_snapshot = _canonical_plugin_snapshot(
        plugin_catalog or _default_plugin_catalog
    )
    store = action_store or AipActionStore()
    expected = provider_health_action_type_snapshot()
    try:
        installed = store.action_type_snapshot(
            CANONICAL_SCOPE,
            PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
        )
    except AipActionStoreError as exc:
        raise ProviderHealthStartupPreflightError(
            "PROVIDER_HEALTH_ACTION_TYPE_NOT_INSTALLED"
        ) from exc
    if installed != expected:
        raise ProviderHealthStartupPreflightError(
            "PROVIDER_HEALTH_ACTION_TYPE_REVISION_DRIFTED"
        )
    return ProviderHealthStartupPreflight(
        status="PROVIDER_HEALTH_MAINTENANCE_STARTUP_PREFLIGHT_GREEN",
        enabled=True,
        ready=True,
        authority_mode=authority_mode,
        principal=principal,
        plugin_snapshot=plugin_snapshot,
        action_type_snapshot=installed,
    )


def build_provider_health_maintenance_startup(
    *,
    environ: Mapping[str, str] | None = None,
    refresh_health: Callable[[], dict[str, Any]] | None = None,
    refresh_readiness: Callable[..., dict[str, Any]] | None = None,
    model_runtime_store: AipModelRuntimeStore | None = None,
    action_store: AipActionStore | None = None,
    plugin_catalog: Callable[[], dict[str, Any]] | None = None,
    registry: ActionAdapterRegistry | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ProviderHealthMaintenanceStartup:
    """Build, but never start, a canonical runtime after exact preflight."""
    env = os.environ if environ is None else environ
    if not _legacy_maintenance_enabled(env):
        return ProviderHealthMaintenanceStartup(
            preflight=preflight_provider_health_maintenance_startup(
                environ=env,
                action_store=action_store,
                plugin_catalog=plugin_catalog,
            )
        )

    store = action_store or AipActionStore()
    preflight = preflight_provider_health_maintenance_startup(
        environ=env,
        action_store=store,
        plugin_catalog=plugin_catalog,
    )
    if refresh_health is None or refresh_readiness is None:
        raise ProviderHealthStartupPreflightError(
            "EXPLICIT_PROVIDER_HEALTH_RUNTIME_CALLABLES_REQUIRED"
        )
    if preflight.principal is None:
        raise ProviderHealthStartupPreflightError(
            "PROVIDER_HEALTH_STARTUP_PRINCIPAL_UNAVAILABLE"
        )
    runtime = build_provider_health_maintenance_runtime(
        principal=preflight.principal,
        refresh_health=refresh_health,
        refresh_readiness=refresh_readiness,
        model_runtime_store=model_runtime_store,
        action_store=store,
        registry=registry,
        clock=clock,
    )
    return ProviderHealthMaintenanceStartup(
        preflight=preflight,
        runtime=runtime,
    )


__all__ = [
    "AUTHORITY_MODE_ENV",
    "CANONICAL_AUTHORITY_MODE",
    "CANONICAL_SCOPE",
    "CANONICAL_PLUGIN_ID",
    "CANONICAL_SERVICE_MARKINGS",
    "CANONICAL_SERVICE_ROLES",
    "CANONICAL_SERVICE_SUBJECT",
    "MAINTENANCE_ENABLED_ENV",
    "ProviderHealthStartupPreflight",
    "ProviderHealthStartupPreflightError",
    "ProviderHealthMaintenanceStartup",
    "SERVICE_ORG_ENV",
    "SERVICE_PROJECT_ENV",
    "SERVICE_SUBJECT_ENV",
    "build_provider_health_maintenance_startup",
    "preflight_provider_health_maintenance_startup",
]
