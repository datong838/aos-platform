"""Actual original Task/Run owners; snapshot stage explicitly remains a fixture."""
from datetime import timedelta
from types import SimpleNamespace

import pytest

from test_analysis_data_resume_pg import (
    resume_case,pytestmark,data_case,formal_case,preview_case,review_identity,compilation_case,
    publications,context_publication,context_case,startup_case,analysis_case,consumer_case,
    host_case,control_governed,governed,service_case,stored,pair,body,
)
from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_analysis_snapshot_resume import _AnalysisSnapshotResumeSession
from aos_api.ecommerce_analysis_snapshot_resume_context import AnalysisSnapshotResumeContext, _CurrentSnapshotResumeStage
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory, DataRequirementRequestHostService
from tests.test_analysis_snapshot_resume_contracts import ref,seal


@pytest.fixture
def snapshot_case(resume_case,monkeypatch):
    conn,analysis,old,run,runtime,requirement=resume_case
    context=object.__new__(AnalysisSnapshotResumeContext)
    context.scope=analysis.scope
    command=old.command
    command['operation']='runtime.analysis.resume_snapshot'
    del command['mappingRef']
    command['businessEvidenceRef']=ref('Evidence','named-snapshot-business')
    command['readinessPolicyRef']=ref('SnapshotReadinessPolicy','named-policy',revision='1.22.0')
    for field in ('fulfillmentRef','sourceReadinessRef'):
        command[field]['receiptId']=command[field]['resourceId']
    command['evidenceRefs']=command['evidenceRefs'][:1]
    seal(command)

    def named_snapshot_current(self,db,*,command,execute):
        assert self is context and db is conn
        # The whole snapshot stage is named, not claimed as twelve-source proof.
        with conn.transaction():
            stage=_CurrentSnapshotResumeStage(conn,analysis.scope,command,requirement=requirement,
                runtime=runtime,fulfillment=requirement,bundle=requirement,readiness=requirement,
                deadline=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']+timedelta(minutes=5))
            stage._active=True
            try:return execute(stage)
            finally:stage._active=False
    monkeypatch.setattr(AnalysisSnapshotResumeContext,'run_current',named_snapshot_current)
    session=_AnalysisSnapshotResumeSession(context,conn,command)
    tx=HostTransaction(conn)
    _,runs,*_=DataRequirementRequestHostService._components(tx,analysis.scope)
    tasks=AipTaskStore(TransactionBoundConnectFactory(tx,analysis.scope))
    return conn,analysis,session,run,runtime,requirement,tasks,runs


def test_original_task_and_domain_resume_once_under_snapshot_session(snapshot_case):
    conn,analysis,session,run,runtime,requirement,tasks,runs=snapshot_case
    with pytest.raises(PermissionError):session._resume_states()
    result=session.run_current(lambda current:current._resume_states())
    assert result.task_run_ref.resource_id==runtime.task_run_ref.resource_id
    assert result.task_run_ref.version==runtime.task_run_ref.version+1
    assert result.task_ref.version==runtime.task_ref.version+1
    assert tasks.get_run(analysis.scope,runtime.task_run_ref.resource_id).status.value=='running'
    after=runs.get_verified(analysis.scope,run.authority.run_id)
    assert after.state.version==run.state.version+1 and after.state.lifecycle.value=='PREPARING'
    assert after.state.pending_requirement_ref is None
    assert not tasks.timeline(analysis.scope,runtime.task_run_ref.resource_id).steps
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE source_ref=%s",
        ('run-control:resume:'+session.control_key,)).fetchone()['n']==1
    from aos_api.ecommerce_growth_runtime_adapters import _strict_resume_control_receipt
    saved_control=conn.execute("SELECT payload FROM aip_evidence WHERE source_ref=%s",
        ('run-control:resume:'+session.control_key,)).fetchone()['payload']
    assert _strict_resume_control_receipt(saved_control)
    # A second first-transition request must not emit another transition.
    with pytest.raises(ValueError):session.run_current(lambda current:current._resume_states())
    assert runs.get_verified(analysis.scope,run.authority.run_id).state==after.state


@pytest.mark.parametrize('fault',['domain-failure','returned-result','post-failure'])
def test_both_original_state_changes_rollback(snapshot_case,monkeypatch,fault):
    conn,analysis,session,run,runtime,requirement,tasks,runs=snapshot_case
    if fault=='domain-failure':
        monkeypatch.setattr(type(runs),'resume_after_data',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('named domain failure')))
    elif fault=='returned-result':
        original=AipTaskStore.resume_run
        def changed(*args,**kwargs):
            result=original(*args,**kwargs)
            return result.model_copy(update={'run':result.run.model_copy(update={'version':result.run.version+1})})
        monkeypatch.setattr(AipTaskStore,'resume_run',changed)
    def consume(current):
        result=current._resume_states()
        if fault=='post-failure':raise RuntimeError('named post-transition failure')
        return result
    with pytest.raises((ValueError,RuntimeError)):session.run_current(consume)
    assert tasks.get_run(analysis.scope,runtime.task_run_ref.resource_id).status.value=='paused'
    assert runs.get_verified(analysis.scope,run.authority.run_id).state==run.state
    assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE source_ref=%s",
        ('run-control:resume:'+session.control_key,)).fetchone()['n']==0


def test_legacy_resume_verifier_reads_actual_original_control_hash(resume_case,monkeypatch):
    from aos_api.business_investigation_shared_contracts import InvestigationExactRef
    from aos_api.aip_business_investigation_fulfillment_saga import RESUME_REASON
    from aos_api.ecommerce_growth_runtime_adapters import (
        AnalysisAdvanceHostService,_AnalysisRunAndTaskResumer,_HostAnalysisReceiptStore,_strict_analysis_command,
    )
    from aos_api import ecommerce_growth_host_composition as composition
    conn,analysis,session,run,runtime,requirement=resume_case
    tx=HostTransaction(conn)
    _,runs,compilations,*_=DataRequirementRequestHostService._components(tx,analysis.scope)
    tasks=AipTaskStore(TransactionBoundConnectFactory(tx,analysis.scope),_analysis_resume_session=session)
    # Only legacy data-readiness is named. Original state writes and verifier are real.
    monkeypatch.setattr(AnalysisAdvanceHostService,'_resume_authorities',
        lambda *a,**kw:(None,None,None,runtime,None,None,None,None,None))
    resumer=_AnalysisRunAndTaskResumer(runs,tasks,InvestigationExactRef.model_validate(session.command['requirementRef']),run.authority.run_id,
        run.state.version,conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
    def invoke():
        return resumer.resume_run(analysis.scope,runtime.task_run_ref.resource_id,
            expected_run_version=runtime.task_run_ref.version,expected_task_version=runtime.task_ref.version,
            actor=AnalysisAdvanceHostService.executor_identity,idempotency_key='bi-fulfillment-resume-native-verifier',
            reason=RESUME_REASON)
    monkeypatch.setattr(composition,'build_ecommerce_growth_host_ports',lambda *a,**kw:
        SimpleNamespace(runtime_port=SimpleNamespace(commit=lambda **kw:invoke())))
    session.resume()
    host=AnalysisAdvanceHostService()
    prior=_HostAnalysisReceiptStore(tx,analysis.scope).read_exact(session.command['priorReceiptRef'])
    compilation=compilations.get_for_run(analysis.scope,requirement.run_ref)
    resumed=host._runtime_binding_for_task_run(analysis.scope,compilation,
        runs.get_verified(analysis.scope,run.authority.run_id),tasks,runtime.task_run_ref.resource_id)
    payload=host._running_receipt(session.command,prior,resumed,analysis.scope,session.command['idempotencyKey'])
    assert host._verify_resume_commit(transaction=tx,scope=analysis.scope,command=session.command,
        parsed=_strict_analysis_command(session.command),receipt=payload)==payload
