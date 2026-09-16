"""Serial server-owned snapshot execution; no application startup side effects."""
from datetime import datetime
import asyncio
from math import isfinite
from threading import Event
from psycopg.pq import TransactionStatus
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ec_ingress_recovery import _check_active
from aos_api.pipeline_snapshot_schedule_claim import _group_id
from aos_api.pipeline_snapshot_schedule_dispatch import PipelineSnapshotScheduleDispatch
from aos_api.pipeline_snapshot_schedule_runtime import PipelineSnapshotScheduleRuntime
from aos_api.pipeline_snapshot_group_recovery_runtime import PipelineSnapshotGroupRecoveryRuntime
from aos_api.pipeline_snapshot_group_recovery_receipt import read_recovery_receipt
from aos_api.tenant_scope import TenantScope


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
                    self.active_definition_id=definition_id
                    return self._recovery.resume_saved(scope=self.scope,actor=recovery['body']['executor'],
                        recovery_ref=recovery['ref'],**active)
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
            except Exception:
                # Original Runtime preserves its durable claim/unknown facts.
                # No synthetic failed/stopped row and no raw exception leakage.
                _check_active(**active)
                result=dict(status='unknown',errorCode='SNAPSHOT_EXECUTION_UNCONFIRMED')
            outcomes.append(dict(result,definitionId=identifier))
        return outcomes
