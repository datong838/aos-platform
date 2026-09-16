"""Bounded tenant-scoped discovery of pending preparation deliveries."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from aos_api.tenant_scope import TenantScope

from .consumer_connection import consumer_connection
from .live_installation_owner import LiveInstallationLifecycleOwner
from .live_job_directory import LivePreparedJobDirectory
from .preparation_consumer import PreparationConsumer
from .preparation_worker import PreparationWorker


@dataclass(frozen=True, slots=True)
class PendingPreparationDescriptor:
    scope: TenantScope
    installation_id: UUID
    mode: str = "pending"

    def __post_init__(self) -> None:
        if (type(self.scope) is not TenantScope or type(self.installation_id) is not UUID
                or self.mode not in {"pending", "rehydrate"}):
            raise TypeError("exact pending preparation descriptor required")


class PostgresPendingPreparationDirectory:
    """Reads routing facts only; it neither claims nor authorizes an operation."""

    LIMIT = 100

    def __init__(self, *, connect, scope: TenantScope) -> None:
        if not callable(connect) or type(scope) is not TenantScope:
            raise ValueError("trusted pending preparation directory inputs required")
        self.connect = connect
        self.scope = scope

    def _read_installations(self) -> tuple[object, ...]:
        tenant = {"org_id": self.scope.org_id, "project_id": self.scope.project_id}
        with consumer_connection(self.connect, tenant) as conn:
            rows = conn.execute(
                """SELECT DISTINCT ON (installation_id) installation_id,mode FROM (
                   SELECT DISTINCT o.installation_id,'pending'::text AS mode
                     FROM extension_runtime_outbox b
                     JOIN extension_runtime_event e
                       ON (e.org_id,e.project_id,e.event_id)=
                          (b.org_id,b.project_id,b.event_id)
                     JOIN extension_runtime_operation o
                       ON (o.org_id,o.project_id,o.operation_id)=
                          (e.org_id,e.project_id,e.operation_id)
                    WHERE b.org_id=%s AND b.project_id=%s
                      AND b.consumer_id='runtime-reconciler'
                      AND b.delivered_at IS NULL
                      AND o.kind='runtime-apply'
                    UNION ALL
                   SELECT b.installation_id,'rehydrate'::text AS mode
                     FROM extension_runtime_binding b
                     JOIN bundle_installation i
                       ON (i.org_id,i.project_id,i.installation_id)=
                          (b.org_id,b.project_id,b.installation_id)
                     JOIN bundle_installation_revision ir
                       ON ir.org_id=i.org_id AND ir.project_id=i.project_id
                      AND ir.installation_pk=i.installation_pk
                      AND ir.revision=i.active_revision
                     JOIN extension_runtime_operation o
                       ON o.org_id=b.org_id AND o.project_id=b.project_id
                      AND o.operation_id=(b.resource_handle_ref->>'preparationOperationId')::uuid
                    WHERE b.org_id=%s AND b.project_id=%s
                      AND ir.state='active' AND b.enabled AND NOT b.operation_fence
                      AND b.observed_state='ready' AND b.desired_state='enabled'
                      AND o.kind='runtime-apply' AND o.status='succeeded' AND o.phase='succeeded'
                      AND EXISTS (
                          SELECT 1 FROM extension_runtime_resource_lease r
                           WHERE r.org_id=b.org_id AND r.project_id=b.project_id
                             AND r.operation_id=o.operation_id AND r.generation=b.generation)
                      AND NOT EXISTS (
                          SELECT 1 FROM extension_runtime_resource_lease r
                           WHERE r.org_id=b.org_id AND r.project_id=b.project_id
                             AND r.operation_id=o.operation_id AND r.generation=b.generation
                             AND (r.observed_release OR r.cleanup_state<>'pending'
                                  OR r.expires_at<=clock_timestamp()))
                    ) candidates
                    ORDER BY installation_id,CASE mode WHEN 'pending' THEN 0 ELSE 1 END
                    LIMIT 101""",
                (*self.scope.key, *self.scope.key),
            ).fetchall()
        return tuple(rows)

    def read_descriptors(self) -> tuple[PendingPreparationDescriptor, ...]:
        rows = self._read_installations()
        if type(rows) is not tuple or len(rows) > self.LIMIT:
            raise RuntimeError("pending preparation directory limit exceeded")
        installations: list[UUID] = []
        modes: list[str] = []
        for row in rows:
            value = row.get("installation_id") if type(row) is dict else row[0]
            mode = (row.get("mode", "pending") if type(row) is dict
                    else row[1] if len(row)>1 else "pending")
            installation = UUID(str(value))
            if installation in installations:
                raise ValueError("duplicate pending preparation installation")
            installations.append(installation)
            if mode not in {"pending", "rehydrate"}:
                raise ValueError("pending preparation mode differs")
            modes.append(mode)
        if installations != sorted(installations):
            raise ValueError("pending preparation directory is not ordered")
        return tuple(
            PendingPreparationDescriptor(self.scope, installation, mode)
            for installation, mode in zip(installations, modes)
        )


class LiveInstallationOwnerFactory:
    """Creates an unstarted owner from server-assembled trusted dependencies."""

    def __init__(
        self,
        *,
        connect,
        scope: TenantScope,
        worker: PreparationWorker,
        live_directory: LivePreparedJobDirectory,
    ) -> None:
        if (
            not callable(connect)
            or type(scope) is not TenantScope
            or type(worker) is not PreparationWorker
            or type(live_directory) is not LivePreparedJobDirectory
        ):
            raise TypeError("exact live installation owner dependencies required")
        self.connect = connect
        self.scope = scope
        self.worker = worker
        self.live_directory = live_directory

    def __call__(
        self, descriptor: PendingPreparationDescriptor
    ) -> LiveInstallationLifecycleOwner:
        if (
            type(descriptor) is not PendingPreparationDescriptor
            or descriptor.scope != self.scope
        ):
            raise ValueError("pending preparation descriptor scope mismatch")
        consumer = PreparationConsumer(
            connect=self.connect,
            worker=self.worker,
            installation_id=descriptor.installation_id,
            org_id=self.scope.org_id,
            project_id=self.scope.project_id,
            live_directory=self.live_directory,
            rehydrate=descriptor.mode == "rehydrate",
        )
        return LiveInstallationLifecycleOwner(preparation=consumer)
