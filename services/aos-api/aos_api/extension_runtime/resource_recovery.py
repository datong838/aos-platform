"""One-resource restart reconciliation. Never recreates or enables resources.

Trusted host owns connect/driver and must await this synchronous work to settle.
The connection is dedicated: its session lock survives the fence transaction,
then disappears on close even if the recovery process crashes.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import json
from uuid import UUID

from psycopg.pq import TransactionStatus
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.tenant_scope import TenantScope
from .lifecycle_store import RuntimeConflict,RuntimeOperationStore,_values
from .reconciler import ResourceJournal,ResourceStillLive
from .storage_ports import require_runtime_role


class ResourceRecoveryBusy(RuntimeConflict):
    """Another recovery worker owns this resource's reconciliation."""


@dataclass(frozen=True)
class RecoveryPage:
    results: tuple[tuple[UUID,str],...]
    cursor: UUID | None
    settled_operations: tuple[UUID,...] = ()


class ExpiredResourceRecovery:
    def __init__(self,*,connect,driver):
        if not callable(connect):raise ValueError('trusted connection factory required')
        self.connect=connect
        self.driver=driver

    @contextmanager
    def _idle(self):
        with self.connect() as conn:
            if conn.info.transaction_status!=TransactionStatus.IDLE:
                raise RuntimeConflict('recovery requires an independent idle connection')
            yield conn

    def run_batch(self,*,org_id,project_id,limit=100,after=None):
        TenantScope(org_id,project_id)
        if type(limit) is not int or not 1<=limit<=100:raise ValueError('resource scan limit must be 1..100')
        after=UUID(str(after)) if after is not None else None
        scope=dict(org_id=org_id,project_id=project_id)
        with self._idle() as conn:
            with self._transaction(conn,scope):
                candidates=ResourceJournal().expired(conn,**scope,engine_context=self.driver.context,limit=limit,after=after)
        results=[]
        for resource in candidates:
            try:state=self.run_one(**scope,resource_id=resource)
            except ResourceRecoveryBusy:state='busy'
            except ResourceStillLive:state='live'
            # Permission, DB, identity and other failures deliberately propagate.
            results.append((resource,state))
        settled=self._settle_committed_batch(scope,limit)
        return RecoveryPage(tuple(results),candidates[-1] if candidates else after,settled)

    def _settle_committed_batch(self,scope,limit):
        from .committed_cleanup import settle_committed_cleanup
        from .lifecycle_store import RuntimeRevisionConflict
        with self._idle() as conn:
            with self._transaction(conn,scope):
                rows=conn.execute('''SELECT o.operation_id,o.revision FROM extension_runtime_operation o
                    WHERE o.org_id=%s AND o.project_id=%s AND o.kind='runtime-apply'
                      AND o.phase='succeeded' AND o.status='needs_attention'
                      AND o.failure_code='RESOURCE_CLEANUP_UNCERTAIN'
                      AND EXISTS(SELECT 1 FROM extension_runtime_resource_lease r
                        WHERE r.org_id=o.org_id AND r.project_id=o.project_id AND r.operation_id=o.operation_id)
                      AND NOT EXISTS(SELECT 1 FROM extension_runtime_resource_lease r
                        WHERE r.org_id=o.org_id AND r.project_id=o.project_id AND r.operation_id=o.operation_id
                          AND (NOT r.observed_release OR r.cleanup_state<>'released' OR r.engine_context<>%s))
                    ORDER BY o.operation_id LIMIT %s''',
                    (scope['org_id'],scope['project_id'],self.driver.context,limit)).fetchall()
        settled=[]
        for row in rows:
            operation,revision=_values(row,('operation_id','revision'))
            try:
                with self._idle() as conn:
                    with self._transaction(conn,scope):
                        settle_committed_cleanup(conn,**scope,operation_id=operation,expected_revision=revision)
            except RuntimeRevisionConflict:
                continue
            settled.append(operation)
        return tuple(settled)

    def settle_preparation(self,*,org_id,project_id,operation_id,expected_revision):
        TenantScope(org_id,project_id)
        scope=dict(org_id=org_id,project_id=project_id)
        with self._idle() as conn:
            with self._transaction(conn,scope):
                return RuntimeOperationStore().settle_failed_preparation(conn,**scope,
                    operation_id=operation_id,expected_revision=expected_revision)

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
        with self._idle() as conn:
            locked=False
            try:
                with self._transaction(conn,scope):
                    locked=_values(conn.execute('SELECT pg_try_advisory_lock(%s) AS locked',(key,)).fetchone(),('locked',))[0]
                    if locked is not True:raise ResourceRecoveryBusy('resource already recovering')
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
