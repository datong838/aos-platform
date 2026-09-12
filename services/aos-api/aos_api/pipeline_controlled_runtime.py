"""Server-owned schedule execution using independent runtime database identities."""
from contextlib import contextmanager
from datetime import datetime, timezone
from dataclasses import dataclass
from functools import partial

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from aos_api.ec_ingress_claim import claim_failed_run
from aos_api.ecom_consistency_store import EcomConsistencyStore
from aos_api.extension_runtime.consumer_connection import consumer_connection
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict,RuntimeRevisionConflict
from aos_api.extension_runtime.runtime_connections import runtime_worker_connection,runtime_worker_dsn
from aos_api.pipeline_control_service import PipelineControlServices
from aos_api.pipeline_controlled_executor import ControlledSnapshotExecutor
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.pipeline_schedule_control_owner import PipelineScheduleControlOwner,ScheduleControlBinding
from aos_api.pipeline_source_claim_owner import PipelineSourceClaimOwner


@contextmanager
def _authoritative_store():
    # Open inside the execution thread. A caller timing out must not dispose
    # resources before the actual worker has stopped.
    dsn=runtime_worker_dsn()
    engine=create_engine('postgresql+psycopg://',creator=lambda:psycopg.connect(dsn),poolclass=NullPool)
    try:yield EcomConsistencyStore(engine)
    finally:engine.dispose()


@dataclass(frozen=True)
class ControlledScheduleExecution:
    service: PipelineControlServices
    binding: ScheduleControlBinding
    eng: object
    recovery: bool = False

    def __post_init__(self):
        if (type(self.service) is not PipelineControlServices or type(self.binding) is not ScheduleControlBinding
                or type(self.service.claims) is not PipelineSourceClaimOwner or type(self.recovery) is not bool):
            raise TypeError('exact server-owned controlled schedule dependencies required')
        if self.service.scope!=self.binding.scope:raise PermissionError('schedule execution tenant differs')

    def _with_current_schedule(self, execute):
        scope=self.service.scope
        owner=PipelineScheduleControlOwner(controls=self.service.controls)
        with consumer_connection(runtime_worker_connection,dict(org_id=scope.org_id,project_id=scope.project_id)) as conn:
            def check(draft,spec):
                if owner.read_latest(conn,scope=scope,schedule_id=self.binding.schedule_id)!=self.binding:
                    raise RuntimeRevisionConflict('schedule binding was superseded')
                row=conn.execute('SELECT pipeline_id,enabled,ingest FROM meta_schedule WHERE org_id=%s AND project_id=%s AND id=%s FOR SHARE',
                    (*scope.key,self.binding.schedule_id)).fetchone()
                if row is None:raise LookupError('schedule unavailable')
                ingest=row['ingest'] or {}
                if (row['enabled'] is not True or row['pipeline_id']!=self.binding.pipeline_id
                        or type(ingest) is not dict or ingest.get('kind')!='pipeline-live-v1'
                        or ingest.get('pipelineId')!=self.binding.pipeline_id):
                    raise RuntimeConflict('schedule is not currently enabled and bound')
                return execute(conn, draft)
            return self.service.controls.run_current(conn,scope=scope,ref=self.binding.control_ref,actor=self.binding.actor,execute=check)

    def validate_current(self):
        return self._with_current_schedule(lambda conn, draft: None)

    def snapshot(self):
        from aos_api.ec_ingress_journal import _digest
        from aos_api.phase5_pipeline_engine import Pipeline, PipelineNode

        def build(conn, draft):
            row = conn.execute("""SELECT payload, revision FROM phase5_pipeline_graph
                WHERE org_id=%s AND project_id=%s AND pipeline_id=%s FOR SHARE""",
                (*self.service.scope.key, self.binding.pipeline_id)).fetchone()
            if row is None:
                raise LookupError('approved pipeline graph unavailable')
            graph = row['payload']
            if (type(graph) is not dict or row['revision'] != draft.graph_revision
                    or _digest(graph) != draft.graph_hash or graph.get('pipeline_id') != draft.pipeline_id
                    or graph.get('write_mode') != 'SNAPSHOT'):
                raise RuntimeRevisionConflict('approved execution graph differs')
            nodes = [PipelineNode.model_validate(node) for node in graph.get('nodes', [])]
            if not nodes or any(node.pipeline_id != draft.pipeline_id for node in nodes):
                raise RuntimeConflict('approved execution nodes differ')
            timeout = min(300.0, (draft.expires_at - datetime.now(timezone.utc)).total_seconds())
            if timeout <= 0:
                raise RuntimeConflict('approved execution window expired')
            pipeline = Pipeline(id=draft.pipeline_id, name=str(graph.get('name') or draft.pipeline_id),
                pipeline_type=str(graph.get('pipeline_type') or 'Batch'), write_mode='SNAPSHOT',
                executor_id='ec-live-v1', execution_mode='controlled', execution_timeout_seconds=timeout)
            return pipeline, nodes
        return self._with_current_schedule(build)

    def _executor(self,store):
        return ControlledSnapshotExecutor(claims=self.service.claims,store=store,connect=runtime_worker_connection,
            eng=self.eng,schedule_binding=self.binding)

    def claim_recovery(self,*,run_id,claim_id):
        if not self.recovery:raise ValueError('saved recovery mode required')
        self.validate_current()
        with _authoritative_store() as store:
            executor=self._executor(store)
            journal=ControlledIngressJournal(claims=self.service.claims,scope=self.service.scope,run_id=run_id,
                control_ref=self.binding.control_ref,actor=self.binding.actor,saved_recovery=True)
            return claim_failed_run(partial(executor._ingress._run_transaction,run_id=run_id),self.service.scope,
                run_id,claim_id,journal=journal,expected_schedule_id=self.binding.schedule_id)

    def invoke(self,*,pipeline,nodes,node_id,sample_input,execution_kind,scope,run_id,
               deadline,cancel_event,run_started_at,durable_ingress=False):
        if (scope!=self.service.scope or pipeline.id!=self.binding.pipeline_id
                or pipeline.executor_id!='ec-live-v1' or pipeline.execution_mode!='controlled'
                or pipeline.write_mode!='SNAPSHOT' or durable_ingress is not True
                or node_id is not None or sample_input!={} or execution_kind!='direct_sync'):
            raise ValueError('controlled schedule dispatch context differs')
        with _authoritative_store() as store:
            executor=self._executor(store)
            operation=executor.resume_saved if self.recovery else executor.execute
            return operation(scope=scope,run_id=run_id,control_ref=self.binding.control_ref,
                actor=self.binding.actor,deadline=deadline,cancel_event=cancel_event)


def resolve_schedule_execution(scope, schedule_id, pipeline_id, *, control_factory, recovery):
    from aos_api.pipeline_control_service import PipelineControlServiceFactory
    from aos_api.pipeline_schedule_claim import read_schedule_binding
    from aos_api.phase5_pipeline_engine import get_engine

    binding = read_schedule_binding(scope, schedule_id)
    if binding is None:
        return None
    if type(control_factory) is not PipelineControlServiceFactory:
        raise RuntimeError('controlled schedule service unavailable')
    if binding.scope != scope or binding.schedule_id != schedule_id or binding.pipeline_id != pipeline_id:
        raise RuntimeConflict('schedule control pipeline differs')
    execution = ControlledScheduleExecution(control_factory.build(scope), binding, get_engine(), recovery)
    execution.validate_current()
    return execution
