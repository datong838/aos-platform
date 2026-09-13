"""Scoped ecommerce execution connections with no Web-identity fallback."""
from contextlib import contextmanager

from psycopg import IsolationLevel
from psycopg.pq import TransactionStatus

from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
from aos_api.extension_runtime.storage_ports import require_runtime_role
from aos_api.tenant_scope import TenantScope, apply_transaction_scope


@contextmanager
def _connect(scope: TenantScope, *, read_only: bool):
    if type(scope) is not TenantScope:
        raise TypeError("trusted TenantScope required")
    with runtime_worker_connection() as conn:
        if conn.autocommit or conn.info.transaction_status != TransactionStatus.IDLE:
            raise RuntimeError("ecommerce runtime connection must start idle and transactional")
        conn.isolation_level = (
            IsolationLevel.REPEATABLE_READ if read_only else IsolationLevel.SERIALIZABLE
        )
        conn.read_only = read_only
        apply_transaction_scope(conn, scope)
        conn.execute("SET LOCAL statement_timeout = '30s'")
        conn.execute("SET LOCAL lock_timeout = '5s'")
        require_runtime_role(
            conn, org_id=scope.org_id, project_id=scope.project_id,
            protected_tables=(
                "public.extension_operation_dispatch_binding",
                "public.extension_runtime_binding",
            ),
        )
        # The host commits only after its same-transaction Receipt readback.
        # Do not wrap this yield in an explicit psycopg transaction context.
        yield conn


def connect_serializable(scope: TenantScope):
    return _connect(scope, read_only=False)


def connect_read_only(scope: TenantScope):
    return _connect(scope, read_only=True)
