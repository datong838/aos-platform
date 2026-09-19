"""Serial server-owned snapshot execution; no application startup side effects."""
from datetime import datetime
import asyncio
from math import isfinite
import re
from threading import Event
from time import monotonic
from psycopg.pq import TransactionStatus
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ec_ingress_recovery import _check_active
from aos_api.pipeline_snapshot_schedule_claim import _group_id
from aos_api.pipeline_snapshot_schedule_dispatch import PipelineSnapshotScheduleDispatch
from aos_api.pipeline_snapshot_schedule_runtime import PipelineSnapshotScheduleRuntime
from aos_api.pipeline_snapshot_group_recovery_runtime import PipelineSnapshotGroupRecoveryRuntime
from aos_api.pipeline_snapshot_group_recovery_receipt import read_recovery_receipt
from aos_api.tenant_scope import TenantScope
from aos_api.logging_facade import get_logger


log = get_logger('aos-api.snapshot-schedule-worker')
_SAVED_RECOVERY_TIMEOUT_SECONDS = 300.0
_SAFE_ORIGIN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]{0,79}$')
_SAFE_REASONS = {
    'recovery receipt is not current':'RECOVERY_RECEIPT_NOT_CURRENT',
    'recovery definition is not current':'RECOVERY_DEFINITION_NOT_CURRENT',
    'recovery original schedule members differ':'RECOVERY_ORIGINAL_SCHEDULE_MEMBERS_DIFFER',
    'snapshot recovery receipt is not current':'SNAPSHOT_RECOVERY_RECEIPT_NOT_CURRENT',
    'recovery original authority differs':'RECOVERY_ORIGINAL_AUTHORITY_DIFFERS',
    'recovery definition is not current enabled authority':'RECOVERY_DEFINITION_NOT_CURRENT_ENABLED',
    'saved-only recovery definition required':'SAVED_ONLY_RECOVERY_DEFINITION_REQUIRED',
    'saved recovery transfer authority differs':'SAVED_RECOVERY_TRANSFER_AUTHORITY_DIFFERS',
    'recovery definition actor or policy differs':'RECOVERY_DEFINITION_ACTOR_OR_POLICY_DIFFERS',
    'recovery bindings are not current':'RECOVERY_BINDINGS_NOT_CURRENT',
    'recovery requires complete exact current control and original run pairs':'RECOVERY_CONTROL_RUN_PAIRS_DIFFER',
    'recovery current schedule membership differs':'RECOVERY_SCHEDULE_MEMBERSHIP_DIFFERS',
    'recovery current control unavailable':'RECOVERY_CURRENT_CONTROL_UNAVAILABLE',
    'recovery execution control differs':'RECOVERY_EXECUTION_CONTROL_DIFFERS',
    'canonical recovery mappings required':'CANONICAL_RECOVERY_MAPPINGS_REQUIRED',
    'saved recovery mapping differs':'SAVED_RECOVERY_MAPPING_DIFFERS',
    'current recovery facts changed during consumption':'RECOVERY_FACTS_CHANGED',
    'source claim loop identity differs or expired':'SOURCE_CLAIM_LOOP_IDENTITY_DIFFERS_OR_EXPIRED',
    'source claim loop transaction changed':'SOURCE_CLAIM_LOOP_TRANSACTION_CHANGED',
    'source claim loop original members differ':'SOURCE_CLAIM_LOOP_ORIGINAL_MEMBERS_DIFFER',
    'source claim loop member differs':'SOURCE_CLAIM_LOOP_MEMBER_DIFFERS',
    'source claim loop group differs':'SOURCE_CLAIM_LOOP_GROUP_DIFFERS',
    'runtime control reference differs':'RUNTIME_CONTROL_REFERENCE_DIFFERS',
    'runtime control was superseded':'RUNTIME_CONTROL_WAS_SUPERSEDED',
    'source call claim unavailable':'SOURCE_CALL_CLAIM_UNAVAILABLE',
    'saved recovery requires original input':'SAVED_RECOVERY_REQUIRES_ORIGINAL_INPUT',
    'saved recovery control family differs':'SAVED_RECOVERY_CONTROL_FAMILY_DIFFERS',
    'original control unavailable':'ORIGINAL_CONTROL_UNAVAILABLE',
    'saved recovery context differs':'SAVED_RECOVERY_CONTEXT_DIFFERS',
    'source claim current binding differs':'SOURCE_CLAIM_CURRENT_BINDING_DIFFERS',
    'snapshot group claim unavailable':'SNAPSHOT_GROUP_CLAIM_UNAVAILABLE',
    'SNAPSHOT_GROUP_BINDING_DIFFERS':'SNAPSHOT_GROUP_BINDING_DIFFERS',
    'SNAPSHOT_GROUP_MEMBERS_DIFFER':'SNAPSHOT_GROUP_MEMBERS_DIFFER',
    'canonical object required':'CANONICAL_RELATIONSHIP_OBJECT_REQUIRED',
    'exact original parent pipelines required':'EXACT_ORIGINAL_PARENT_PIPELINES_REQUIRED',
    'current and original parent pipelines differ':'CURRENT_AND_ORIGINAL_PARENT_PIPELINES_DIFFER',
    'runtime request is not currently admitted':'RUNTIME_REQUEST_NOT_CURRENTLY_ADMITTED',
}


def _safe_origin_name(name):
    return name if type(name) is str and _SAFE_ORIGIN.fullmatch(name) else 'unknown'


def _error_origin(exc):
    traceback = exc.__traceback__
    if traceback is None:
        return 'unknown'
    while traceback.tb_next is not None:
        traceback = traceback.tb_next
    name = traceback.tb_frame.f_code.co_name
    return _safe_origin_name(name)


def _error_reason(exc):
    if len(exc.args) == 1 and type(exc.args[0]) is str and exc.args[0] in _SAFE_REASONS:
        return _SAFE_REASONS[exc.args[0]]
    return type(exc).__name__.upper()


class PipelineSnapshotScheduleWorker:
    def __init__(self,*,scope,runtime,recovery):
        if (type(scope) is not TenantScope or type(runtime) is not PipelineSnapshotScheduleRuntime
                or type(recovery) is not PipelineSnapshotGroupRecoveryRuntime
                or runtime._claims._groups._controls is not recovery._controls
                or runtime._connect is not recovery._connect
                or runtime._completion._store is not recovery._store):
            raise TypeError('shared original worker runtimes required')
        self.scope,self._runtime,self._recovery=scope,runtime,recovery
        self._dispatch=PipelineSnapshotScheduleDispatch(definitions=runtime._definitions,claims=runtime._claims)
        self.status='STOPPED'
        self.last_outcomes=[]
        self.last_error=None
        self._serving=False
        self.active_definition_id=None

    async def serve(self,stop,*,host_ready,interval=15):
        if (not callable(host_ready) or type(interval) not in (int,float)
                or not isfinite(interval) or interval<=0):
            raise ValueError('bounded worker polling configuration required')
        if getattr(self,'_serving',False):raise RuntimeError('snapshot worker already serving')
        self._serving=True
        self.status='IDLE';self.last_outcomes=[];self.last_error=None
        cancel=Event();active=None;cancelled=False
        try:
            while not stop.is_set() and host_ready():
                self.status='RUNNING'
                active=asyncio.create_task(asyncio.to_thread(self.tick,cancel_event=cancel))
                while not active.done():
                    if stop.is_set() or not host_ready():
                        self.status='STOPPING';cancel.set()
                        break
                    # wait does not propagate cancellation into the thread task.
                    await asyncio.wait({active},timeout=.05)
                if cancel.is_set():break
                try:
                    self.last_outcomes=active.result();self.last_error=None
                except Exception:
                    self.last_error='SNAPSHOT_TICK_UNCONFIRMED'
                active=None;self.status='IDLE'
                try:await asyncio.wait_for(stop.wait(),timeout=interval)
                except TimeoutError:pass
        except asyncio.CancelledError:
            cancelled=True
        finally:
            self.status='STOPPING';cancel.set()
            if active is not None:
                while not active.done():
                    try:await asyncio.shield(active)
                    except asyncio.CancelledError:cancelled=True
                    except Exception:break
                if not active.cancelled():
                    try:active.result()
                    except Exception:self.last_error='SNAPSHOT_TICK_UNCONFIRMED'
            self.status='STOPPED';self._serving=False
        if cancelled:raise asyncio.CancelledError

    def run_definition(self,definition_id,*,deadline=None,cancel_event=None):
        definition_id=_group_id(definition_id)
        active=dict(deadline=deadline,cancel_event=cancel_event)
        _check_active(**active)
        key='aos:snapshot-worker:'+canonical_sha256([*self.scope.key,definition_id])
        with self._runtime._connect() as lock:
            if lock.info.transaction_status!=TransactionStatus.IDLE:
                raise ValueError('independent worker session required')
            # No transaction locks are held while invoking source/Store Owners.
            locked=lock.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0)) AS locked',(key,)).fetchone()['locked']
            if locked is not True:return dict(status='busy',definitionId=definition_id)
            try:
                _check_active(**active)
                with self._runtime._transaction(self.scope) as conn:
                    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                    candidate=self._dispatch.inspect(conn,scope=self.scope,definition_id=definition_id,now=now)
                    recovery=None
                    if candidate['status']=='original_group_pending' and len(candidate['groupIds'])==1:
                        saved=read_recovery_receipt(conn,scope=self.scope,group_id=candidate['groupIds'][0])
                        if saved is not None and saved['body']['currentDefinitionRef']==candidate['definitionRef']:
                            recovery=saved
                _check_active(**active)
                if recovery is not None:
                    # The immutable approval is the durable routing intent.
                    # The original fixed Authority rechecks every permission,
                    # window and saved-input fact before any Store operation.
                    recovery_deadline=monotonic()+_SAVED_RECOVERY_TIMEOUT_SECONDS
                    if deadline is not None:
                        recovery_deadline=min(deadline,recovery_deadline)
                    recovery_active=dict(deadline=recovery_deadline,cancel_event=cancel_event)
                    _check_active(**recovery_active)
                    self.active_definition_id=definition_id
                    return self._recovery.resume_saved(scope=self.scope,actor=recovery['body']['executor'],
                        recovery_ref=recovery['ref'],**recovery_active)
                if candidate['status']!='due':return candidate
                self.active_definition_id=definition_id
                return self._runtime.execute(scope=self.scope,definition_ref=candidate['definitionRef'],
                    group_id=candidate['groupId'],actor=candidate['actor'],
                    scheduled_for=datetime.fromisoformat(candidate['scheduledFor']),trigger='cron',**active)
            finally:
                self.active_definition_id=None
                lock.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))',(key,))

    def tick(self,*,deadline=None,cancel_event=None):
        active=dict(deadline=deadline,cancel_event=cancel_event)
        _check_active(**active)
        with self._runtime._transaction(self.scope) as conn:
            rows=conn.execute('''SELECT definition_id FROM public.pipeline_snapshot_schedule_definition_head
                WHERE org_id=%s AND project_id=%s AND state='enabled' ORDER BY definition_id''',self.scope.key).fetchall()
        outcomes=[]
        for row in rows:
            _check_active(**active)
            identifier=str(row['definition_id'])
            try:
                result=self.run_definition(identifier,**active)
            except Exception as exc:
                # Original Runtime preserves its durable claim/unknown facts.
                # No synthetic failed/stopped row and no raw exception leakage.
                _check_active(**active)
                log.warning('snapshot_execution_unconfirmed definition_id=%s error_type=%s error_origin=%s reason_code=%s',
                    identifier,type(exc).__name__,_error_origin(exc),_error_reason(exc))
                result=dict(status='unknown',errorCode='SNAPSHOT_EXECUTION_UNCONFIRMED')
            outcomes.append(dict(result,definitionId=identifier))
        return outcomes
