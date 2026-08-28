"""Explicit, inactive-by-default Provider Health maintenance assembly."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

from aos_api.aip_action_adapters import ACTION_ADAPTERS, ActionAdapterRegistry
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_action_store import AipActionStore, AipActionStoreError
from aos_api.aip_adapter_conformance import AdapterConformanceReport
from aos_api.aip_adapter_contracts import AdapterCapabilityRevision
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_provider_health_action import (
    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
    ProviderHealthProbeActionAdapter,
)
from aos_api.aip_provider_health_action_authority import (
    provider_health_action_type_snapshot,
    register_provider_health_action_adapter,
)
from aos_api.aip_provider_health_maintenance import AipTextProviderHealthMaintainer
from aos_api.aip_provider_health_maintenance_inbox import (
    ProviderHealthMaintenanceLeaseInbox,
    ProviderHealthMaintenanceLeaseRunner,
)
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope


class ProviderHealthRuntimeAssemblyError(RuntimeError):
    """Stable assembly failure without persistence or Provider details."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _legacy_refresh_disabled() -> dict[str, Any]:
    raise ProviderHealthRuntimeAssemblyError(
        "LEGACY_PROVIDER_HEALTH_REFRESH_DISABLED"
    )


@dataclass(frozen=True)
class ProviderHealthMaintenanceRuntime:
    maintainer: AipTextProviderHealthMaintainer
    registry: ActionAdapterRegistry
    adapter: ProviderHealthProbeActionAdapter
    adapter_revision: AdapterCapabilityRevision
    conformance_report: AdapterConformanceReport
    action_type_snapshot: dict[str, Any]


def build_provider_health_maintenance_runtime(
    *,
    principal: Principal,
    refresh_health: Callable[[], dict[str, Any]],
    refresh_readiness: Callable[..., dict[str, Any]],
    model_runtime_store: AipModelRuntimeStore | None = None,
    action_store: AipActionStore | None = None,
    registry: ActionAdapterRegistry | None = None,
    clock: Callable[[], datetime] | None = None,
) -> ProviderHealthMaintenanceRuntime:
    """Build but do not start one exact-authority maintenance runtime."""
    inbox = ProviderHealthMaintenanceLeaseInbox(principal)
    store = action_store or AipActionStore()
    expected_action = provider_health_action_type_snapshot()
    try:
        installed_action = store.action_type_snapshot(
            TenantScope(principal.org_id, principal.project_id),
            PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
        )
    except AipActionStoreError as exc:
        raise ProviderHealthRuntimeAssemblyError(
            "PROVIDER_HEALTH_ACTION_TYPE_NOT_INSTALLED"
        ) from exc
    if installed_action != expected_action:
        raise ProviderHealthRuntimeAssemblyError(
            "PROVIDER_HEALTH_ACTION_TYPE_REVISION_DRIFTED"
        )
    isolated_registry = registry or ActionAdapterRegistry()
    if isolated_registry is ACTION_ADAPTERS:
        raise ProviderHealthRuntimeAssemblyError(
            "GLOBAL_ACTION_ADAPTER_REGISTRY_FORBIDDEN"
        )
    adapter, revision, report = register_provider_health_action_adapter(
        isolated_registry, refresh_health
    )
    if not report.green or adapter.adapter_revision_ref != revision.exact_ref():
        raise ProviderHealthRuntimeAssemblyError(
            "PROVIDER_HEALTH_ADAPTER_CONFORMANCE_NOT_GREEN"
        )
    service = AipActionExecutionService(store, isolated_registry)
    runner = ProviderHealthMaintenanceLeaseRunner(inbox, service)
    maintainer = AipTextProviderHealthMaintainer(
        store=model_runtime_store,
        refresh_health=_legacy_refresh_disabled,
        refresh_readiness=refresh_readiness,
        execute_authorized_refresh=runner,
        clock=clock,
    )
    return ProviderHealthMaintenanceRuntime(
        maintainer=maintainer,
        registry=isolated_registry,
        adapter=adapter,
        adapter_revision=revision,
        conformance_report=report,
        action_type_snapshot=installed_action,
    )
__all__ = [
    "ProviderHealthMaintenanceRuntime",
    "ProviderHealthRuntimeAssemblyError",
    "build_provider_health_maintenance_runtime",
]
