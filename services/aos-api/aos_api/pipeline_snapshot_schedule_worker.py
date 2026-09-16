"""Serial server-owned snapshot execution; no application startup side effects."""
from datetime import datetime
from psycopg.pq import TransactionStatus
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.ec_ingress_recovery import _check_active
from aos_api.pipeline_snapshot_schedule_claim import _group_id
from aos_api.pipeline_snapshot_schedule_dispatch import PipelineSnapshotScheduleDispatch
from aos_api.pipeline_snapshot_schedule_runtime import PipelineSnapshotScheduleRuntime
from aos_api.pipeline_snapshot_group_recovery_runtime import PipelineSnapshotGroupRecoveryRuntime
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
                _check_active(**active)
                if candidate['status']!='due':return candidate
                return self._runtime.execute(scope=self.scope,definition_ref=candidate['definitionRef'],
                    group_id=candidate['groupId'],actor=candidate['actor'],
                    scheduled_for=datetime.fromisoformat(candidate['scheduledFor']),trigger='cron',**active)
            finally:
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
