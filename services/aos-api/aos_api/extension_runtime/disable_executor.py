"""Trusted synchronous disable worker with a durable fence before drain.

connect must create an independently owned transaction context that commits on
normal exit. It must never lend a caller's already-open business transaction.
"""
from contextlib import contextmanager
from uuid import UUID
from psycopg.pq import TransactionStatus

from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from .disable_commit import begin_disable,finish_disable
from .lifecycle_store import _values,RuntimeConflict,RuntimeRevisionConflict


class RuntimeDisableExecutor:
    def __init__(self, *, connect, installation_store, check_current_permission, check_drained):
        if not all(callable(v) for v in (connect,check_current_permission,check_drained)):
            raise ValueError('trusted connection, current permission and drain readers required')
        self.connect=connect
        self.store=installation_store
        self.permission=check_current_permission
        self.drain=check_drained

    @contextmanager
    def _connection(self,scope):
        with self.connect() as conn:
            if conn.info.transaction_status!=TransactionStatus.IDLE:
                raise RuntimeConflict('disable requires an independent idle connection')
            with conn.transaction():
                apply_asset_transaction_scope(conn,**scope)
                if _values(conn.execute('SELECT current_user AS role').fetchone(),('role',))[0]!='aos_runtime':
                    raise RuntimeConflict('disable requires adopted runtime role')
                yield conn

    def execute(self, *, org_id,project_id,operation_id,expected_revision):
        scope=dict(org_id=org_id,project_id=project_id)
        args=dict(**scope,operation_id=operation_id,expected_revision=expected_revision,
            installation_store=self.store,check_current_permission=self.permission)
        with self._connection(scope) as conn:
            row=conn.execute('''SELECT kind,phase,revision FROM extension_runtime_operation
                WHERE org_id=%s AND project_id=%s AND operation_id=%s''',
                (org_id,project_id,UUID(str(operation_id)))).fetchone()
            if row is None:raise LookupError('disable operation not found')
            kind,phase,revision=_values(row,('kind','phase','revision'))
            if type(expected_revision) is not int or revision!=expected_revision:
                raise RuntimeRevisionConflict('disable operation changed; read current operation')
            if kind!='disable' or phase not in ('accepted','fencing'):
                raise RuntimeConflict('disable requires accepted or fenced operation')
            if phase=='accepted':
                args['expected_revision']=begin_disable(conn,**args).revision
        # The first connection context has committed before this one is opened.
        with self._connection(scope) as conn:
            return finish_disable(conn,**args,check_drained=self.drain)
