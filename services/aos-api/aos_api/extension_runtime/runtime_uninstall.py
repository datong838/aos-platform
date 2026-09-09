"""One-shot runtime resource cleanup after exact disable/detach authority."""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from psycopg.pq import TransactionStatus

from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.tenant_scope import TenantScope
from .lifecycle_store import RuntimeConflict,_values
from .reconciler import ResourceJournal
from .storage_ports import require_runtime_role


class RuntimeUninstallBusy(RuntimeConflict):
    pass


@dataclass(frozen=True)
class RuntimeUninstallPage:
    results: tuple[tuple[UUID,str],...]
    cursor: UUID | None


class RuntimeUninstallCleanupExecutor:
    """Commit an uncertain checkpoint before touching exactly one owned resource."""
    def __init__(self,*,connect,driver):
        if not callable(connect):raise ValueError('trusted connection factory required')
        self.connect=connect
        self.driver=driver

    @contextmanager
    def _idle(self):
        with self.connect() as conn:
            if conn.info.transaction_status!=TransactionStatus.IDLE:
                raise RuntimeConflict('runtime uninstall requires an independent idle connection')
            yield conn

    @contextmanager
    def _transaction(self,conn,scope):
        with conn.transaction():
            apply_asset_transaction_scope(conn,**scope)
            if _values(conn.execute('SELECT current_user AS role').fetchone(),('role',))[0]!='aos_runtime':
                raise RuntimeConflict('runtime uninstall requires adopted runtime role')
            require_runtime_role(conn,**scope,protected_tables=(
                'extension_runtime_operation','extension_runtime_binding',
                'extension_runtime_resource_lease','extension_dispatch_lifecycle_operation'))
            conn.execute("SET LOCAL lock_timeout='1s'")
            conn.execute("SET LOCAL statement_timeout='10s'")
            yield

    def run_batch(self,*,org_id,project_id,installation_id,generation,limit=100,after=None):
        TenantScope(org_id,project_id)
        installation_id=UUID(str(installation_id));generation=UUID(str(generation))
        if type(limit) is not int or not 1<=limit<=100:
            raise ValueError('resource scan limit must be 1..100')
        after=UUID(str(after)) if after is not None else None
        scope=dict(org_id=org_id,project_id=project_id)
        journal=ResourceJournal()
        with self._idle() as conn:
            with self._transaction(conn,scope):
                candidates=journal.uninstall_candidates(conn,**scope,
                    installation_id=installation_id,generation=generation,
                    engine_context=self.driver.context,limit=limit,after=after)
        results=[]
        for resource_id in candidates:
            try:
                state=self.run_one(**scope,installation_id=installation_id,
                    generation=generation,resource_id=resource_id)
            except RuntimeUninstallBusy:
                state='busy'
            results.append((resource_id,state))
        return RuntimeUninstallPage(tuple(results),candidates[-1] if candidates else after)

    def run_one(self,*,org_id,project_id,installation_id,generation,resource_id):
        TenantScope(org_id,project_id)
        installation_id=UUID(str(installation_id));generation=UUID(str(generation))
        resource_id=UUID(str(resource_id));scope=dict(org_id=org_id,project_id=project_id)
        key=int.from_bytes(sha256(json.dumps([org_id,project_id,str(resource_id)],
            separators=(',',':')).encode()).digest()[:8],signed=True)
        journal=ResourceJournal()
        with self._idle() as conn:
            locked=False
            try:
                with self._transaction(conn,scope):
                    locked=_values(conn.execute('SELECT pg_try_advisory_lock(%s) AS locked',(key,)).fetchone(),('locked',))[0]
                    if locked is not True:raise RuntimeUninstallBusy('resource already cleaning')
                    intent,container,status=journal.begin_uninstall_cleanup(conn,**scope,
                        installation_id=installation_id,generation=generation,
                        resource_id=resource_id,engine_context=self.driver.context)
                if status in ('released','uncertain'):return status
                try:
                    self.driver.require_isolation()
                    removed=self.driver.remove_owned(intent.identity.name,intent.identity.owner,
                        expected_container_id=container)
                except Exception:
                    return 'uncertain'
                if removed is not True:return 'uncertain'
                with self._transaction(conn,scope):
                    return journal.record_cleanup(conn,**scope,intent=intent,removed=True)
            finally:
                if locked:
                    with self._transaction(conn,scope):
                        conn.execute('SELECT pg_advisory_unlock(%s)',(key,))


__all__=['RuntimeUninstallBusy','RuntimeUninstallCleanupExecutor','RuntimeUninstallPage']
