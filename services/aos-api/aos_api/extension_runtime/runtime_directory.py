"""Database-bound runtime assignment directory with stable in-process revisions."""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from psycopg.pq import TransactionStatus

from aos_api.tenant_scope import TenantScope
from .runtime_host import RuntimeTenantAssignment


@dataclass(frozen=True, slots=True)
class RuntimeTenantDescriptor:
    scope: TenantScope
    assignment_revision: int

    def __post_init__(self) -> None:
        if type(self.scope) is not TenantScope:
            raise TypeError("runtime descriptor requires TenantScope")
        if type(self.assignment_revision) is not int or self.assignment_revision < 1:
            raise TypeError("invalid runtime assignment revision")


class PostgresRuntimeTenantDirectory:
    def __init__(self, *, connect, build_assignment):
        if not callable(connect) or not callable(build_assignment):
            raise ValueError("trusted runtime directory dependencies required")
        if inspect.iscoroutinefunction(connect) or inspect.iscoroutinefunction(build_assignment):
            raise ValueError("runtime directory dependencies must be synchronous")
        self._connect = connect
        self._build = build_assignment
        self._cache: dict[tuple[str, str], tuple[int, RuntimeTenantAssignment]] = {}

    def read_descriptors(self) -> tuple[RuntimeTenantDescriptor, ...]:
        with self._connect() as conn:
            if conn.info.transaction_status != TransactionStatus.IDLE:
                raise RuntimeError("runtime directory requires an independent idle connection")
            with conn.transaction():
                rows = conn.execute(
                    "SELECT org_id,project_id,assignment_revision "
                    "FROM extension_runtime_read_host_assignments()"
                ).fetchall()
        if len(rows) > 1000:
            raise RuntimeError("runtime directory assignment limit exceeded")
        current: dict[tuple[str, str], RuntimeTenantDescriptor] = {}
        for row in rows:
            org_id = row["org_id"] if isinstance(row, dict) else row[0]
            project_id = row["project_id"] if isinstance(row, dict) else row[1]
            revision = row["assignment_revision"] if isinstance(row, dict) else row[2]
            scope = TenantScope(org_id=org_id, project_id=project_id)
            descriptor = RuntimeTenantDescriptor(
                scope=scope, assignment_revision=revision
            )
            if scope.key in current:
                raise ValueError("duplicate runtime tenant assignment")
            current[scope.key] = descriptor
        return tuple(current.values())

    def materialize(
        self, descriptors: tuple[RuntimeTenantDescriptor, ...]
    ) -> tuple[RuntimeTenantAssignment, ...]:
        if type(descriptors) is not tuple or len(descriptors) > 1000 or any(
            type(value) is not RuntimeTenantDescriptor for value in descriptors
        ):
            raise TypeError("bounded runtime tenant descriptors required")
        current: dict[tuple[str, str], tuple[int, RuntimeTenantAssignment]] = {}
        for descriptor in descriptors:
            scope = descriptor.scope
            revision = descriptor.assignment_revision
            if scope.key in current:
                raise ValueError("duplicate runtime tenant assignment")
            cached = self._cache.get(scope.key)
            if cached is not None and cached[0] == revision:
                assignment = cached[1]
            else:
                assignment = self._build(scope=scope, assignment_revision=revision)
                if inspect.isawaitable(assignment):
                    close = getattr(assignment, "close", None)
                    if callable(close):
                        close()
                    raise TypeError("runtime assignment factory must be synchronous")
                if type(assignment) is not RuntimeTenantAssignment or assignment.scope != scope:
                    raise TypeError("runtime assignment factory returned a mismatched assignment")
            current[scope.key] = (revision, assignment)
        self._cache = current
        return tuple(value[1] for _, value in sorted(current.items()))

    def __call__(self) -> tuple[RuntimeTenantAssignment, ...]:
        return self.materialize(self.read_descriptors())
