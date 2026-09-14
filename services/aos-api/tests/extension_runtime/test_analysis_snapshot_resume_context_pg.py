"""Twelve original snapshot owners; initialization/Pending still named fixtures."""
from copy import deepcopy
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS

import psycopg
from psycopg.rows import dict_row
import pytest

from test_analysis_snapshot_fulfillment_pg import (
    database,pytestmark,ledger,owner_case,claim_case,executor_case,group_claim_case,
    prepared_case,assessment_case,journal_case,object_case,completed_group,
    business_case,fact_case,evidence_case,query_case,quality_case,business_evidence_case,
    readiness_case,receipt_case,fulfillment_case,
)
from test_analysis_snapshot_context_pg import bridge_case as original_bridge
from tests.test_data_requirement_store import requirement
from tests.test_aip_business_investigation_evidence import runtime
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
from aos_api.ecommerce_analysis_pending_data_context import AnalysisPendingDataContext
from aos_api.ecommerce_analysis_snapshot_resume_context import AnalysisSnapshotResumeContext
from aos_api.ecommerce_growth_runtime_adapters import _analysis_command_hash


def exact(kind,identity,*,receipt=False):
    value=dict(resourceType=kind,resourceId=identity,revision=1,contentHash='sha256:'+'a'*64)
    if receipt:value['receiptId']=identity
    return value


@pytest.fixture
def bridge_case(completed_group,monkeypatch):
    case=original_bridge.__wrapped__(completed_group,monkeypatch)
    conn,args,state,context,_,call=case
    req=requirement();rt=runtime()
    prior=exact('AnalysisRuntimeReceipt','named-original-analysis',receipt=True)
    context['analysisReceipt'].update(receiptRef=prior,
        occurrenceRef=exact('AutomationOccurrence','named-occurrence'),
        caseRef=req.case_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
        runRef=req.run_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
        profileRef=exact('InvestigationProfileRevision','named-profile'),
        planRef=dict(resourceType='PlanRevision',resourceId=rt.plan_ref.resource_id,
            revision=rt.plan_ref.revision,contentHash='sha256:'+rt.plan_ref.content_hash),
        taskRunRef=dict(resourceType='TaskRun',resourceId=rt.task_run_ref.resource_id,
            revision=rt.task_run_ref.version,contentHash='sha256:'+rt.binding_hash))
    call['receipt_ref']=prior
    def current(self,db,*,receipt_ref,execute):
        assert db is conn and receipt_ref==prior
        state['context_calls']=state.get('context_calls',0)+1
        return execute(deepcopy(context))
    monkeypatch.setattr(AnalysisContinuationContext,'run_current',current)
    return case


@pytest.fixture
def resume_case(fulfillment_case,bridge_case,monkeypatch):
    conn,state,fulfillment,call=fulfillment_case
    schema=fulfillment.source._schema
    path=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_049_data_requirement_current_lock.py'
    spec=importlib.util.spec_from_file_location('resume_head_lock_ddl',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    conn.execute('RESET ROLE')
    migration.op=NS(execute=lambda statement:conn.execute(statement.replace('public.data_requirement_head',f'"{schema}".data_requirement_head')))
    migration.upgrade();conn.execute('SET ROLE aos_runtime')
    saved=fulfillment.put_current(conn,**call)
    root=deepcopy(bridge_case[3]['analysisReceipt'])
    origin=AnalysisContinuationOrigin(AnalysisContinuationContext(fulfillment.source.analysis))
    def current_origin(self,db,*,receipt_ref,execute):
        assert db is conn and receipt_ref==root['receiptRef']
        if state.get('origin_denied'):raise ValueError('named original initialization revoked')
        value=dict(context=deepcopy(bridge_case[3]),analysisReceipt=deepcopy(root),
            initializationEvidenceRef=exact('Evidence','named-initialization'))
        answer=execute(value)
        if state.get('origin_denied'):raise ValueError('named original initialization revoked')
        return answer
    monkeypatch.setattr(AnalysisContinuationOrigin,'run_current',current_origin)
    import aos_api.ecommerce_analysis_snapshot_resume_context as target
    import aos_api.ecommerce_analysis_snapshot_business_evidence as original
    monkeypatch.setattr(target,'HostTransaction',original.HostTransaction)
    cmd=dict(operation='runtime.analysis.resume_snapshot',idempotencyKey='named-snapshot-resume',
        occurrenceRef=root['occurrenceRef'],caseRef=root['caseRef'],profileRef=root['profileRef'],
        cutoffAt=saved.cutoff_at.isoformat(),priorReceiptRef=root['receiptRef'],
        requirementRef=saved.requirement_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
        fulfillmentRef=fulfillment.reference(saved).model_dump(mode='json',by_alias=True,exclude_none=True),
        checkpointRef=requirement().checkpoint_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
        priorPlanRef=root['planRef'],sourceReadinessRef=saved.source_readiness_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
        evidenceRefs=[call['bundle_ref'].model_dump(mode='json',by_alias=True,exclude_none=True)],
        observedAt=saved.fulfilled_at.isoformat(),
        businessEvidenceRef=call['business_ref'].model_dump(mode='json',by_alias=True,exclude_none=True),
        readinessPolicyRef=call['policy_ref'].model_dump(mode='json',by_alias=True,exclude_none=True))
    cmd['requestHash']=_analysis_command_hash(cmd)
    return conn,state,AnalysisSnapshotResumeContext(fulfillment,origin),cmd


def test_phase_b_does_not_reenter_old_pending_state_and_stage_expires(resume_case,monkeypatch):
    conn,state,owner,cmd=resume_case
    original=AnalysisPendingDataContext.run_current
    observed=[]
    def pending(*args,**kwargs):
        assert not state.get('phase_b'), 'old Pending reentered after the transition boundary'
        state['pending_checks']=state.get('pending_checks',0)+1
        return original(*args,**kwargs)
    monkeypatch.setattr(AnalysisPendingDataContext,'run_current',pending)
    def consume(stage):
        stage.assert_current(conn,owner.scope)
        assert stage.runtime.task_run_status.value=='paused'
        state['phase_b']=True
        conn.execute("INSERT INTO readiness_test_probe VALUES('phase-b')")
        observed.append(stage)
        return 'inspected'
    assert owner.run_current(conn,command=cmd,execute=consume)=='inspected'
    assert state['pending_checks']>0 and state['calls']==1
    assert conn.execute('SELECT count(*) AS n FROM readiness_test_probe').fetchone()['n']==1
    with pytest.raises(PermissionError):observed[0].assert_current(conn,owner.scope)
    assert conn.execute("SELECT status FROM aip_task WHERE task_id='task-1'").fetchone()['status']=='paused'


@pytest.mark.parametrize('fault',['command','scope','binding','quality','business','policy','origin','deferred','transaction'])
def test_phase_b_late_dependency_change_rolls_back_probe(resume_case,fault):
    conn,state,owner,cmd=resume_case
    def consume(stage):
        conn.execute("INSERT INTO readiness_test_probe VALUES('must-roll-back')")
        if fault=='command':stage._command['idempotencyKey']='tampered'
        elif fault=='scope':conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
        elif fault=='binding':state['binding_denied']=True
        elif fault in {'quality','business'}:
            from test_analysis_snapshot_source_evidence_pg import revoke
            ref=InvestigationExactRef.model_validate(cmd['businessEvidenceRef'])
            if fault=='quality':ref=InvestigationExactRef.model_validate(owner.business._record(conn,ref)['selection']['qualityRef'])
            revoke(conn,owner.source,ref)
        elif fault=='policy':state['readiness_raw']=b'{}'
        elif fault=='origin':state['origin_denied']=True
        elif fault=='deferred':return (item for item in [1])
        elif fault=='transaction':
            with psycopg.connect(host='127.0.0.1',port=18432,user='postgres',dbname='postgres',row_factory=dict_row) as other:
                stage.assert_current(other,owner.scope)
    with pytest.raises((ValueError,PermissionError,LookupError)):
        owner.run_current(conn,command=cmd,execute=consume)
    assert conn.execute('SELECT count(*) AS n FROM readiness_test_probe').fetchone()['n']==0
