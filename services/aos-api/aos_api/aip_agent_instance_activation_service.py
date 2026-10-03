"""Governed AgentInstance activation backed by fresh tenant Binding evidence."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

from aos_api.aip_agent_control_contracts import ActivateAgentInstanceRequest, SuspendAgentInstanceRequest
from aos_api.aip_agent_registry_contracts import (
    AgentInstance,
    AgentInstanceStatus,
    RegistryReceipt,
    UpdateAgentInstanceRequest,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryStore,
    AipAgentRegistryTransitionBlocked,
)
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AipAgentInstanceActivationService:
    def __init__(
        self,
        *,
        connect_factory: ConnectFactory | None = None,
        store: AipAgentRegistryStore | None = None,
    ) -> None:
        self._connect_factory = connect_factory or db_connect
        self._store = store or AipAgentRegistryStore(connect_factory)

    def activate(
        self,
        scope: TenantScope,
        instance_id: str,
        request: ActivateAgentInstanceRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> tuple[AgentInstance, RegistryReceipt]:
        binding_ids = self._binding_ids(request.capability_binding_ids)
        current = self._store.get_instance(scope, instance_id)
        transition = UpdateAgentInstanceRequest(
            expected_version=request.expected_version,
            from_status=AgentInstanceStatus.PROVISIONING,
            to_status=AgentInstanceStatus.ACTIVE,
            overlay=current.overlay,
        )
        if current.status is AgentInstanceStatus.ACTIVE:
            return self._store.update_instance(
                scope,
                instance_id,
                transition,
                idempotency_key=idempotency_key,
                actor=actor,
                occurred_at=occurred_at,
            )
        if current.status is not AgentInstanceStatus.PROVISIONING:
            raise AipAgentRegistryTransitionBlocked(
                "only provisioning AgentInstance can be activated"
            )
        if current.version != request.expected_version:
            raise AipAgentRegistryTransitionBlocked(
                "AgentInstance version changed before activation"
            )
        self._require_exact_template_and_bindings(
            scope,
            current,
            binding_ids,
            evaluated_at=occurred_at,
        )
        return self._store.update_instance(
            scope,
            instance_id,
            transition,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
            before_update=lambda conn: self._require_exact_template_and_bindings(
                scope, current, binding_ids, evaluated_at=occurred_at,
                connection=conn, lock=True,
            ),
        )

    def suspend(
        self,
        scope: TenantScope,
        instance_id: str,
        request: SuspendAgentInstanceRequest,
        *,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> tuple[AgentInstance, RegistryReceipt]:
        current = self._store.get_instance(scope, instance_id)
        if current.status is not AgentInstanceStatus.ACTIVE:
            raise AipAgentRegistryTransitionBlocked(
                "only active AgentInstance can be suspended"
            )
        if current.version != request.expected_version:
            raise AipAgentRegistryTransitionBlocked(
                "AgentInstance version changed before suspension"
            )
        transition = UpdateAgentInstanceRequest(
            expected_version=request.expected_version,
            from_status=AgentInstanceStatus.ACTIVE,
            to_status=AgentInstanceStatus.SUSPENDED,
            overlay=current.overlay,
        )
        return self._store.update_instance(
            scope,
            instance_id,
            transition,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )

    @staticmethod
    def _binding_ids(values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned) or len(cleaned) != len(set(cleaned)):
            raise ValueError("capability binding ids must be unique and non-blank")
        return cleaned

    def _require_exact_template_and_bindings(
        self,
        scope: TenantScope,
        instance: AgentInstance,
        binding_ids: list[str],
        *,
        evaluated_at: datetime,
        connection: Any | None = None,
        lock: bool = False,
    ) -> None:
        if connection is None:
            with self._connect_factory(scope) as conn:
                return self._require_exact_template_and_bindings(
                    scope, instance, binding_ids, evaluated_at=evaluated_at,
                    connection=conn,
                )
        template = connection.execute(
            """SELECT lifecycle,content_hash FROM aip_agent_template_revision
               WHERE template_id=%s AND revision=%s"""
            + (" FOR SHARE" if lock else ""),
            (instance.template.asset_id, instance.template.revision),
        ).fetchone()
        if (
            template is None
            or template["lifecycle"] != "published"
            or template["content_hash"] != instance.template.content_hash
        ):
            raise AipAgentRegistryTransitionBlocked(
                "exact published AgentTemplate is required for activation"
            )
        rows = connection.execute(
            """SELECT binding_id,status,health,operational_readiness,
                      allow_degraded,dependency_snapshot_hash,readiness_expires_at
               FROM aip_capability_binding
               WHERE org_id=%s AND project_id=%s AND binding_id=ANY(%s)
               ORDER BY binding_id"""
            + (" FOR SHARE" if lock else ""),
            (*scope.key, binding_ids),
        ).fetchall()
        if len(rows) != len(binding_ids):
            raise AipAgentRegistryTransitionBlocked(
                "all activation CapabilityBindings must exist in tenant scope"
            )
        if lock:
            # Read the database clock after acquiring the row locks.  The
            # request timestamp may predate a lock wait and expired readiness.
            evaluated_at = max(
                evaluated_at,
                connection.execute("SELECT clock_timestamp() AS now").fetchone()["now"],
            )
        for row in rows:
            usable = row["operational_readiness"] == "available" or (
                row["operational_readiness"] == "degraded"
                and bool(row["allow_degraded"])
            )
            if (
                row["status"] != "active"
                or row["health"] != "healthy"
                or not usable
                or row["dependency_snapshot_hash"] is None
                or row["readiness_expires_at"] is None
                or row["readiness_expires_at"] <= evaluated_at
            ):
                raise AipAgentRegistryTransitionBlocked(
                    "fresh active CapabilityBinding is required for activation"
                )
