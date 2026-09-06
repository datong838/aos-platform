"""Database-bound runtime assignment directory with stable in-process revisions."""
from __future__ import annotations

import inspect
from psycopg.pq import TransactionStatus

from aos_api.tenant_scope import TenantScope
from .runtime_host import RuntimeTenantAssignment


class PostgresRuntimeTenantDirectory:
    def __init__(self, *, connect, build_assignment):
        if not callable(connect) or not callable(build_assignment):
            raise ValueError("trusted runtime directory dependencies required")
        if inspect.iscoroutinefunction(connect) or inspect.iscoroutinefunction(build_assignment):
            raise ValueError("runtime directory dependencies must be synchronous")
        self._connect = connect
        self._build = build_assignment
        self._cache: dict[tuple[str, str], tuple[int, RuntimeTenantAssignment]] = {}

    def __call__(self) -> tuple[RuntimeTenantAssignment, ...]:
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
        current: dict[tuple[str, str], tuple[int, RuntimeTenantAssignment]] = {}
        for row in rows:
            org_id = row["org_id"] if isinstance(row, dict) else row[0]
            project_id = row["project_id"] if isinstance(row, dict) else row[1]
            revision = row["assignment_revision"] if isinstance(row, dict) else row[2]
            scope = TenantScope(org_id=org_id, project_id=project_id)
            if type(revision) is not int or revision < 1:
                raise TypeError("invalid runtime assignment revision")
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
