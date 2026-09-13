"""Concrete, phase-separated UI read consumer owned by one runtime assignment."""
from contextlib import contextmanager
from dataclasses import dataclass, field
import inspect
import threading
from uuid import UUID

from psycopg.pq import TransactionStatus
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from aos_api.asset_registry.canonical_json import canonical_json, canonical_sha256
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalog
from aos_api.tenant_scope import TenantScope
from .analyst_workspace_snapshot import read_host_analyst_workspace_snapshot
from .installed_package_invoker import CurrentInstalledPackageInvoker
from .lifecycle_store import RuntimeConflict, _values
from .live_job_directory import LivePreparedJobDirectory
from .storage_ports import require_runtime_role
from .ui_read_admission import require_current_catalog_read
from .ui_read_api_database import read_host_ui_principal
from .ui_read_contracts import UiReadRequest
from .ui_read_recovery import expire_ui_read_deliveries
from .ui_read_worker_store import UiReadClaim, claim_ui_read, complete_ui_read

_PROTECTED=('extension_runtime_ui_read_request','extension_runtime_execution_attempt','extension_runtime_binding',
            'ecommerce_investigation_case_head','ecommerce_investigation_case_revision',
            'ecommerce_investigation_run','ecommerce_investigation_run_state_head')


@dataclass(frozen=True, slots=True)
class PreparedUiRead:
    claim: UiReadClaim
    snapshot_hash: str
    snapshot: dict = field(repr=False)
    invoker: CurrentInstalledPackageInvoker = field(repr=False)


@dataclass(frozen=True, slots=True)
class UiReadInvocation:
    result: dict | None = field(default=None,repr=False)
    failure_code: str | None = None


@dataclass(frozen=True, slots=True)
class UiReadConsumerResult:
    request_id: UUID
    state: str


class RuntimeUiReadConsumer:
    def __init__(self,*,scope,connect,catalog,installation_store,live_directory,markings):
        if (type(scope) is not TenantScope or not callable(connect) or inspect.iscoroutinefunction(connect)
                or type(catalog) is not RuntimeWorkshopCatalog or type(installation_store) is not PostgresInstallationStore
                or type(live_directory) is not LivePreparedJobDirectory):
            raise TypeError('concrete scoped UI read dependencies required')
        if (type(markings) is not tuple or len(markings)>500 or len(set(markings))!=len(markings)
                or any(type(x) is not str or not x or not x.isprintable() or x!=x.strip() for x in markings)):
            raise ValueError('exact trusted UI read markings required')
        self.scope,self.connect,self.catalog=scope,connect,catalog
        self.store,self.directory,self.markings=installation_store,live_directory,tuple(sorted(markings))
        self._issued={}
        self._issued_lock=threading.Lock()

    @contextmanager
    def _connection(self,scope):
        if scope!=self.scope:raise RuntimeConflict('UI read assignment scope differs')
        with self.connect() as conn:
            if conn.info.transaction_status!=TransactionStatus.IDLE:
                raise RuntimeConflict('UI read consumer requires an idle owned connection')
            conn.row_factory=dict_row
            with conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
                apply_asset_transaction_scope(conn,org_id=scope.org_id,project_id=scope.project_id)
                if _values(conn.execute('SELECT current_user AS role').fetchone(),('role',))[0]!='aos_runtime':
                    raise RuntimeConflict('UI read consumer requires adopted runtime role')
                require_runtime_role(conn,org_id=scope.org_id,project_id=scope.project_id,protected_tables=_PROTECTED)
                conn.execute("SET LOCAL lock_timeout='1s'")
                conn.execute("SET LOCAL statement_timeout='10s'")
                yield conn

    def _gate(self,conn,subject,request):
        conn.execute("SELECT set_config('aos.subject',%s,true)",(subject,))
        principal=read_host_ui_principal(conn=conn,scope=self.scope,subject=subject,required_markings=self.markings)
        catalog=self.catalog.list_modules(org_id=self.scope.org_id,project_id=self.scope.project_id,
                                          roles=principal.roles,markings=principal.markings)
        entry=require_current_catalog_read(catalog=catalog,principal=principal,request=request)
        if entry.moduleRef.bundleId!='solution.ecommerce.growth':
            raise RuntimeConflict('fixed analyst package required')
        return entry

    def prepare_once(self,*,org_id,project_id):
        value=self._prepare_once(org_id=org_id,project_id=project_id)
        if type(value) is PreparedUiRead:
            with self._issued_lock:
                if value.claim.request_id in self._issued:raise RuntimeConflict('UI read already issued')
                self._issued[value.claim.request_id]=(value,False)
        return value

    def _prepare_once(self,*,org_id,project_id):
        if (org_id,project_id)!=self.scope.key:raise RuntimeConflict('UI read assignment scope differs')
        jobs=self.directory.jobs_for_scope(self.scope)
        targets=[{'installation_id':str(job.plan.installation_id),'generation':str(job.plan.generation)} for job in jobs]
        with self._connection(self.scope) as conn:
            expire_ui_read_deliveries(conn=conn,scope=self.scope)
            if not targets:return None
            rows=conn.execute('''SELECT q.request_id,q.subject,q.target_json,q.case_limit,q.run_limit
                FROM extension_runtime_ui_read_request q
                WHERE q.org_id=%s AND q.project_id=%s AND q.state='requested' AND q.deadline>clock_timestamp()
                  AND EXISTS(SELECT 1 FROM jsonb_to_recordset(%s::jsonb) AS j(installation_id uuid,generation uuid)
                    WHERE j.installation_id=q.installation_id AND j.generation=q.generation)
                ORDER BY q.created_at,q.request_id FOR UPDATE OF q SKIP LOCKED LIMIT 25''',
                (*self.scope.key,Jsonb(targets))).fetchall()
            for row in rows:
                try:
                    with conn.transaction():
                        request=UiReadRequest.model_validate(dict(schemaVersion='aos.runtime-ui-read-request/v1',
                            operationId='analyst_workspace_view_v1',moduleId='ecommerce.analyst',target=row['target_json'],
                            caseLimit=row['case_limit'],runLimit=row['run_limit']))
                        job=self.directory.resolve(scope=self.scope,installation_id=request.target.installationId,
                                                   generation=request.target.generation)
                        if not any(job is owned for owned in jobs):
                            raise RuntimeConflict('selected live job changed')
                        entry=self._gate(conn,row['subject'],request)
                        snapshot=read_host_analyst_workspace_snapshot(conn=conn,scope=self.scope,subject=row['subject'],
                            required_markings=self.markings,case_limit=request.caseLimit,run_limit=request.runLimit)
                        if len(canonical_json(snapshot))>900000:raise ValueError('bounded UI read snapshot required')
                        snapshot_hash=canonical_sha256(snapshot)
                        invoker=CurrentInstalledPackageInvoker(scope=self.scope,installation_id=request.target.installationId,
                            generation=request.target.generation,package_id='solution.ecommerce.growth',markings=self.markings,
                            connect_factory=self._connection,installation_store=self.store,live_directory=self.directory,expected_job=job)
                        current=invoker.read_current_in_transaction(HostTransaction(conn))
                        if current['package']['contentHash']!=entry.moduleRef.bundleContentHash:
                            raise RuntimeConflict('signed module package differs from installed package')
                        claim=claim_ui_read(conn=conn,scope=self.scope,request_id=row['request_id'],snapshot_hash=snapshot_hash)
                        if claim is None:raise RuntimeConflict('UI read already claimed')
                        prepared=PreparedUiRead(claim,snapshot_hash,snapshot,invoker)
                    return prepared
                except (RuntimeConflict,PermissionError,ValueError,LookupError):
                    # Roll back any partial Attempt before recording rejection.
                    rejected=conn.execute('''UPDATE extension_runtime_ui_read_request SET
                        state=CASE WHEN deadline<=statement_timestamp() THEN 'expired' ELSE 'denied' END,
                        failure_code=CASE WHEN deadline<=statement_timestamp() THEN 'READ_DEADLINE_EXPIRED' ELSE 'READ_ADMISSION_DENIED' END,
                        revision=revision+1,completed_at=clock_timestamp()
                        WHERE org_id=%s AND project_id=%s AND request_id=%s AND state='requested' RETURNING state''',
                        (*self.scope.key,row['request_id'])).fetchone()
                    if rejected is not None:return UiReadConsumerResult(row['request_id'],rejected['state'])
        return None

    def _check_prepared(self,prepared):
        if (type(prepared) is not PreparedUiRead or type(prepared.invoker) is not CurrentInstalledPackageInvoker
                or prepared.invoker.scope!=self.scope or prepared.invoker.directory is not self.directory
                or prepared.invoker.store is not self.store or prepared.invoker.expected_job is None
                or prepared.invoker.package_id!='solution.ecommerce.growth'
                or str(prepared.invoker.installation_id)!=prepared.claim.request.target.installationId
                or str(prepared.invoker.generation)!=prepared.claim.request.target.generation
                or prepared.snapshot.get('tenant')!={'orgId':self.scope.org_id,'projectId':self.scope.project_id}):
            raise TypeError('exact assignment prepared UI read required')
        with self._issued_lock:
            issued=self._issued.get(prepared.claim.request_id)
            if issued is None or issued[0] is not prepared:raise RuntimeConflict('UI read was not issued by this consumer')

    async def invoke_prepared(self,prepared):
        self._check_prepared(prepared)
        with self._issued_lock:
            issued=self._issued.get(prepared.claim.request_id)
            if issued is None or issued[0] is not prepared or issued[1]:raise RuntimeConflict('UI read invocation already consumed')
            self._issued[prepared.claim.request_id]=(prepared,True)
        if canonical_sha256(prepared.snapshot)!=prepared.snapshot_hash:
            return UiReadInvocation(failure_code='READ_RESULT_INVALID')
        try:
            result=await prepared.invoker('analyst_workspace_view_v1',{'snapshot':prepared.snapshot})
        except Exception:
            # Never retry an invocation whose response was not received.
            return UiReadInvocation(failure_code='READ_OUTCOME_UNKNOWN')
        return UiReadInvocation(result=result) if type(result) is dict else UiReadInvocation(failure_code='READ_RESULT_INVALID')

    def discard_prepared(self,prepared):
        self._check_prepared(prepared)
        with self._issued_lock:
            self._issued.pop(prepared.claim.request_id,None)

    def finish_prepared(self,prepared,invocation):
        self._check_prepared(prepared)
        if type(invocation) is not UiReadInvocation:
            raise TypeError('exact UI read completion required')
        with self._issued_lock:
            issued=self._issued.get(prepared.claim.request_id)
            if issued is None or issued[0] is not prepared or not issued[1]:raise RuntimeConflict('UI read invocation was not consumed')
        with self._connection(self.scope) as conn:
            failure=invocation.failure_code
            try:
                with conn.transaction():
                    self._gate(conn,prepared.claim.subject,prepared.claim.request)
            except (RuntimeConflict,PermissionError):failure='READ_ACCESS_REVOKED'
            if failure is None and not _valid_result(invocation.result,prepared):failure='READ_RESULT_INVALID'
            state=complete_ui_read(conn=conn,scope=self.scope,claim=prepared.claim,
                **({'failure_code':failure} if failure else {'result':invocation.result}))
        with self._issued_lock:
            self._issued.pop(prepared.claim.request_id,None)
        return UiReadConsumerResult(prepared.claim.request_id,state)


def _valid_result(result,prepared):
    try:
        request=prepared.claim.request
        if canonical_sha256(prepared.snapshot)!=prepared.snapshot_hash:return False
        if (type(result) is not dict or set(result)!={'schemaVersion','tenant','cutoffAt','cases','caseCount','runCount','truncated','executionAllowed'}
                or result['schemaVersion']!='aos.analyst-workspace-view/v1' or result['tenant']!=prepared.snapshot['tenant']
                or result['cutoffAt']!=prepared.snapshot['cutoffAt'] or result['executionAllowed'] is not False
                or type(result['truncated']) is not bool or result['truncated']!=prepared.snapshot['truncated'] or type(result['cases']) is not list
                or type(result['caseCount']) is not int or type(result['runCount']) is not int
                or result['caseCount']!=len(result['cases']) or result['caseCount']!=len(prepared.snapshot['cases']) or not 0<=result['caseCount']<=request.caseLimit):
            return False
        count=0
        for case in result['cases']:
            if type(case) is not dict or type(case.get('runs')) is not list or len(case['runs'])>request.runLimit:return False
            count+=len(case['runs'])
        return count==result['runCount']==sum(len(case['runs']) for case in prepared.snapshot['cases']) and len(canonical_json(result))<=900000
    except (ValueError,TypeError,KeyError):return False
