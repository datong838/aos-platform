"""Unique non-HTTP dispatch service for ecommerce growth operations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from aos_api.db import connect_read_only, connect_serializable
from aos_api.ecommerce_growth_host_composition import (
    ECOMMERCE_GROWTH_OPERATIONS,
    EcommerceGrowthHostAdapterRegistry,
    EcommerceGrowthHostPorts,
    build_ecommerce_growth_host_ports,
)
from aos_api.ecommerce_growth_host_ports import (
    ConnectFactory,
    EcommerceGrowthHostBlocked,
    LockedEcommerceGrowthHostPort,
)
from aos_api.tenant_scope import TenantScope


_ISSUE_SQL = """SELECT operation_id, handler_kind, installation_id, generation,
                      execution_epoch, operation_fence, revision, cutover_group_id,
                      cutover_group_revision
                 FROM extension_operation_dispatch_binding
                WHERE org_id=%s AND project_id=%s AND operation_id=%s"""

_PORT_ATTRS = {
    "ecommerce_growth_investigation_describe": "describe_port",
    "ecommerce_growth_case_put": "write_port",
    "ecommerce_growth_schedule_put": "write_port",
    "ecommerce_growth_schedule_trigger": "occurrence_port",
    "ecommerce_growth_data_fulfill": "data_port",
    "ecommerce_growth_analysis_advance": "runtime_port",
    "ecommerce_growth_review_advance": "review_port",
    "ecommerce_growth_content_generate": "capability_port",
    "ecommerce_growth_content_review": "content_review_port",
}

LegacyCompatService = Callable[..., Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class IssuedDispatchRef:
    org_id: str
    project_id: str
    operation_id: str
    handler_kind: str
    dispatch_revision: int
    installation_id: str | None
    generation: str | None
    execution_epoch: int | None
    cutover_group_id: str
    cutover_group_revision: int


def _canonical_uuid(value: Any, name: str) -> str:
    try:
        parsed = UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise EcommerceGrowthHostBlocked(f"current dispatch {name} is not executable") from exc
    return str(parsed)


class EcommerceGrowthCanonicalRouter:
    """Issue a short-lived DispatchRef, then commit only through sealed host ports."""

    def __init__(
        self,
        registry: EcommerceGrowthHostAdapterRegistry,
        *,
        connect_factory: ConnectFactory | None = None,
        issue_connect_factory: ConnectFactory | None = None,
        legacy_compat: Mapping[str, LegacyCompatService] | None = None,
    ) -> None:
        if type(registry) is not EcommerceGrowthHostAdapterRegistry:
            raise TypeError("canonical router requires the sealed ecommerce growth registry")
        host_connect = connect_factory if connect_factory is not None else connect_serializable
        self._issue_connect = (
            issue_connect_factory
            if issue_connect_factory is not None
            else connect_factory if connect_factory is not None else connect_read_only
        )
        self._ports: EcommerceGrowthHostPorts = build_ecommerce_growth_host_ports(
            registry,
            connect_factory=host_connect,
        )
        self._legacy_compat = dict(legacy_compat) if legacy_compat else {}

    def dispatch(
        self,
        *,
        scope: TenantScope,
        operation_id: str,
        command: Mapping[str, Any],
        occurred_at: datetime | None = None,
    ) -> Mapping[str, Any]:
        if type(scope) is not TenantScope:
            raise TypeError("canonical router requires a trusted TenantScope")
        if type(operation_id) is not str or operation_id not in ECOMMERCE_GROWTH_OPERATIONS:
            raise EcommerceGrowthHostBlocked("unknown operation")
        if type(command) is not dict:
            raise TypeError("command must be a strict mapping")
        dispatch_ref = self._issue(scope, operation_id)
        if dispatch_ref.handler_kind == "legacy":
            compat = self._legacy_compat.get(operation_id)
            if compat is None:
                raise EcommerceGrowthHostBlocked("legacy dispatch has no registered compatibility service")
            return compat(scope=scope, dispatch_ref=dispatch_ref, command=command)
        return self._port_for(operation_id).commit(
            dispatch_ref=dispatch_ref,
            command=command,
            occurred_at=occurred_at,
        )

    def _port_for(self, operation_id: str) -> LockedEcommerceGrowthHostPort:
        return getattr(self._ports, _PORT_ATTRS[operation_id])

    def _issue(self, scope: TenantScope, operation_id: str) -> IssuedDispatchRef:
        with self._issue_connect(scope) as conn:
            row = conn.execute(_ISSUE_SQL, (*scope.key, operation_id)).fetchone()
        if row is None:
            raise EcommerceGrowthHostBlocked("current dispatch authority is unavailable")
        if row.get("operation_fence") is not False:
            raise EcommerceGrowthHostBlocked("current dispatch is not executable")
        handler_kind = row.get("handler_kind")
        if handler_kind == "legacy":
            return IssuedDispatchRef(
                org_id=scope.org_id,
                project_id=scope.project_id,
                operation_id=operation_id,
                handler_kind="legacy",
                dispatch_revision=row["revision"],
                installation_id=None,
                generation=None,
                execution_epoch=None,
                cutover_group_id=_canonical_uuid(row["cutover_group_id"], "cutover group"),
                cutover_group_revision=row["cutover_group_revision"],
            )
        if handler_kind != "extension":
            raise EcommerceGrowthHostBlocked("current dispatch is not executable")
        return IssuedDispatchRef(
            org_id=scope.org_id,
            project_id=scope.project_id,
            operation_id=operation_id,
            handler_kind="extension",
            dispatch_revision=row["revision"],
            installation_id=_canonical_uuid(row["installation_id"], "installation"),
            generation=_canonical_uuid(row["generation"], "generation"),
            execution_epoch=row["execution_epoch"],
            cutover_group_id=_canonical_uuid(row["cutover_group_id"], "cutover group"),
            cutover_group_revision=row["cutover_group_revision"],
        )


__all__ = [
    "EcommerceGrowthCanonicalRouter",
    "IssuedDispatchRef",
]
