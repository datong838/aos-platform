"""One-resource restart reconciliation. Never recreates or enables resources.

Trusted host owns connect/driver and must await this synchronous work to settle.
The connection is dedicated: its session lock survives the fence transaction,
then disappears on close even if the recovery process crashes.
"""
from contextlib import contextmanager
from hashlib import sha256
import json
from uuid import UUID

from psycopg.pq import TransactionStatus
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.tenant_scope import TenantScope
from .lifecycle_store import RuntimeConflict,_values
from .reconciler import ResourceJournal
from .storage_ports import require_runtime_role


class ExpiredResourceRecovery:
    def __init__(self,*,connect,driver):
        if not callable(connect):raise ValueError('trusted connection factory required')
        self.connect=connect
        self.driver=driver

    @contextmanager
    def _transaction(self,conn,scope):
        with conn.transaction():
            apply_asset_transaction_scope(conn,**scope)
            if _values(conn.execute('SELECT current_user AS role').fetchone(),('role',))[0]!='aos_runtime':
                raise RuntimeConflict('recovery requires adopted runtime role')
            require_runtime_role(conn,**scope,protected_tables=('extension_runtime_operation','extension_runtime_binding','extension_runtime_resource_lease'))
            conn.execute("SET LOCAL lock_timeout='1s'")
            conn.execute("SET LOCAL statement_timeout='10s'")
            yield

    def run_one(self,*,org_id,project_id,resource_id):
        TenantScope(org_id,project_id)
        resource_id=UUID(str(resource_id))
        scope=dict(org_id=org_id,project_id=project_id)
        key=int.from_bytes(sha256(json.dumps([org_id,project_id,str(resource_id)],separators=(',',':')).encode()).digest()[:8],signed=True)
        journal=ResourceJournal()
        with self.connect() as conn:
            if conn.info.transaction_status!=TransactionStatus.IDLE:
                raise RuntimeConflict('recovery requires an independent idle connection')
            locked=False
            try:
                with self._transaction(conn,scope):
                    locked=_values(conn.execute('SELECT pg_try_advisory_lock(%s) AS locked',(key,)).fetchone(),('locked',))[0]
                    if locked is not True:raise RuntimeConflict('resource already recovering')
                    intent,container,status=journal.begin_recovery(conn,**scope,resource_id=resource_id,engine_context=self.driver.context)
                # Top-level transaction exited before any engine call.
                if status=='released':return status
                try:
                    self.driver.require_isolation()
                    removed=self.driver.remove_owned(intent.identity.name,intent.identity.owner,expected_container_id=container)
                except Exception:
                    # Fixed persisted failure state; never store engine errors/secrets.
                    return 'uncertain'
                if removed is not True:return 'uncertain'
                with self._transaction(conn,scope):
                    return journal.record_cleanup(conn,**scope,intent=intent,removed=True)
            finally:
                if locked:
                    with self._transaction(conn,scope):
                        conn.execute('SELECT pg_advisory_unlock(%s)',(key,))
