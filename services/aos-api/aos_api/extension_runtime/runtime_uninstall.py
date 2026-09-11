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


class RuntimeUninstallGuard:
    """Invoke the only application-role command allowed to terminalize a runtime."""

    @staticmethod
    def before_uninstall(conn,*,org_id,project_id,installation_id,
                         expected_installation_revision,actor):
        if conn.info.transaction_status!=TransactionStatus.INTRANS:
            raise RuntimeError('runtime uninstall guard requires an explicit transaction')
        installation_id=UUID(str(installation_id))
        head=conn.execute('''SELECT r.state FROM bundle_installation i
            JOIN bundle_installation_revision r
              ON r.org_id=i.org_id AND r.project_id=i.project_id
             AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s
              AND i.current_revision=%s AND i.etag_version=%s FOR SHARE OF i,r''',
            (org_id,project_id,installation_id,expected_installation_revision,
             expected_installation_revision)).fetchone()
        if head is None:
            raise RuntimeConflict('current installation authority is unavailable')
        state=_values(head,('state',))[0]
        if state=='approved':
            row=conn.execute('''SELECT
              (SELECT count(*) FROM extension_runtime_binding b
                WHERE b.org_id=%s AND b.project_id=%s AND b.installation_id=%s) AS bindings,
              (SELECT count(*) FROM extension_runtime_operation o
                WHERE o.org_id=%s AND o.project_id=%s AND o.installation_id=%s
                  AND o.status NOT IN ('succeeded','failed','cancelled')) AS unresolved,
              (SELECT count(*) FROM extension_runtime_resource_lease r
                JOIN extension_runtime_operation o
                  ON o.org_id=r.org_id AND o.project_id=r.project_id
                 AND o.operation_id=r.operation_id
                WHERE o.org_id=%s AND o.project_id=%s AND o.installation_id=%s
                  AND (r.cleanup_state<>'released' OR r.observed_release IS NOT TRUE)) AS unsafe''',
                (org_id,project_id,installation_id,org_id,project_id,installation_id,
                 org_id,project_id,installation_id)).fetchone()
            if _values(row,('bindings','unresolved','unsafe'))!=(0,0,0):
                raise RuntimeConflict('approved runtime preparation is not clean for uninstall')
            return None
        row=conn.execute('''SELECT applied,receipt_data,content_hash
            FROM extension_runtime_uninstall_commit_ar2_018(%s,%s,%s)''',
            (installation_id,expected_installation_revision,actor)).fetchone()
        if row is None:
            raise RuntimeError('runtime uninstall command returned no result')
        applied,receipt,content_hash=_values(row,('applied','receipt_data','content_hash'))
        if applied is False and receipt is None and content_hash is None:
            return None
        authority=receipt.get('authorityData') if isinstance(receipt,dict) else None
        if (applied is not True or not isinstance(authority,dict)
                or authority.get('orgId')!=org_id or authority.get('projectId')!=project_id
                or authority.get('installationId')!=str(installation_id)
                or authority.get('installationRevision')!=expected_installation_revision
                or authority.get('actor')!=actor.strip()
                or not isinstance(receipt.get('receiptId'),str)
                or not isinstance(content_hash,str)):
            raise RuntimeError('runtime uninstall Receipt readback differs')
        verified=conn.execute('''SELECT content_hash=%s
                AND content_hash='sha256:'||encode(
                  sha256(convert_to(authority_data::text,'UTF8')),'hex') AS valid
            FROM extension_runtime_uninstall_receipt
            WHERE org_id=%s AND project_id=%s AND receipt_id=%s''',
            (content_hash,org_id,project_id,UUID(receipt['receiptId']))).fetchone()
        if verified is None or _values(verified,('valid',))[0] is not True:
            raise RuntimeError('runtime uninstall Receipt integrity failed')
        return receipt


__all__=['RuntimeUninstallBusy','RuntimeUninstallCleanupExecutor','RuntimeUninstallGuard',
         'RuntimeUninstallPage']
