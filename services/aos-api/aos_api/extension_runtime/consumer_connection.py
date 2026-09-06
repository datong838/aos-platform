"""Owned consumer transaction, never a caller transaction or privileged session."""
from contextlib import contextmanager
from psycopg.pq import TransactionStatus
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from .lifecycle_store import _values,RuntimeConflict
from .storage_ports import require_runtime_role


@contextmanager
def consumer_connection(connect,scope):
    with connect() as conn:
        if conn.info.transaction_status!=TransactionStatus.IDLE:
            raise RuntimeConflict('consumer requires an independent idle connection')
        with conn.transaction():
            apply_asset_transaction_scope(conn,**scope)
            if _values(conn.execute('SELECT current_user AS role').fetchone(),('role',))[0]!='aos_runtime':
                raise RuntimeConflict('consumer requires adopted runtime role')
            require_runtime_role(conn,**scope,protected_tables=('extension_runtime_operation','extension_runtime_outbox','extension_runtime_event'))
            conn.execute("SET LOCAL lock_timeout='1s'")
            conn.execute("SET LOCAL statement_timeout='10s'")
            yield conn
