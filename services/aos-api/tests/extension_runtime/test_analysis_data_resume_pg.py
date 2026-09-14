"""Actual state owners; positive state-composition tests name their data-readiness fixture."""
from datetime import datetime
from types import SimpleNamespace
import pytest
from test_analysis_data_preparation_pg import (
    data_case,prepare,formal_case,preview_case,review_identity,compilation_case,publications,context_publication,
    context_case,startup_case,analysis_case,consumer_case,host_case,control_governed,governed,
    service_case,stored,pair,body,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    TransactionBoundConnectFactory,_HostAnalysisReceiptStore,_analysis_command_hash,
    DataRequirementRequestHostService,AnalysisAdvanceHostService,_AnalysisRunAndTaskResumer,
)
from aos_api.automation_occurrence_store import AutomationOccurrenceStore
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.aip_task_store import AipTaskStore,AipTaskTransitionBlocked
from aos_api.aip_business_investigation_fulfillment_saga import RESUME_REASON

pytestmark=[pytest.mark.parametrize('startup_case',['defer-host'],indirect=True),
            pytest.mark.parametrize('stored',['qualified-runtime'],indirect=True)]


@pytest.fixture
def resume_case(data_case):
    from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
    from aos_api.ecommerce_analysis_continuation_origin import AnalysisContinuationOrigin
    from aos_api.ecommerce_analysis_data_resume import _AnalysisDataResumeSession
    from test_ecommerce_analysis_advance_host import resume_command
    conn,analysis,claimed,spec=data_case
    pending=prepare(data_case)
    tx=HostTransaction(conn)
    root=_HostAnalysisReceiptStore(tx,analysis.scope).read(claimed.target_idempotency_key)
    cases,runs,receipts,binder,data,_=DataRequirementRequestHostService._components(tx,analysis.scope)
    requirement=data.get_exact(analysis.scope,InvestigationExactRef.model_validate(pending['requirementRef']))
    run=runs.get_verified(analysis.scope,root['runRef']['resourceId'])
    compilation=receipts.get_for_run(analysis.scope,InvestigationExactRef.model_validate(root['runRef']))
    runtime=binder.bind_receipt(analysis.scope,compilation,run)
    AutomationOccurrenceStore(TransactionBoundConnectFactory(tx,analysis.scope)).record_target_receipt(
        analysis.scope,occurrence_id=claimed.occurrence_id,owner=claimed.claim_owner,receipt_ref=root['receiptRef'],
        occurred_at=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'].replace(microsecond=0))
    command=resume_command(**{k:root[k] for k in ('occurrenceRef','caseRef','profileRef','cutoffAt')},
        priorReceiptRef=root['receiptRef'],priorPlanRef=root['planRef'],requirementRef=pending['requirementRef'],
        checkpointRef=requirement.checkpoint_ref.model_dump(mode='json',by_alias=True,exclude_none=True),
        observedAt=spec.cutoff_at.isoformat())
    command['requestHash']=_analysis_command_hash({k:v for k,v in command.items() if k!='requestHash'})
    session=_AnalysisDataResumeSession(AnalysisContinuationOrigin(AnalysisContinuationContext(analysis)),conn,root['receiptRef'],command)
    return conn,analysis,session,run,runtime,requirement


def test_actual_missing_fulfillment_still_blocks_session(resume_case):
    with pytest.raises(TypeError):AipTaskStore(_analysis_resume_session=True)
    conn,analysis,session,run,runtime,requirement=resume_case
    with pytest.raises(ValueError,match='fulfillment authority drifted'):session.resume()
    tasks=AipTaskStore(TransactionBoundConnectFactory(HostTransaction(conn),analysis.scope))
    assert tasks.get_run(analysis.scope,runtime.task_run_ref.resource_id).status.value=='paused'


@pytest.mark.parametrize('fault',[None,'domain-failure','actor'])
def test_state_composition_with_explicit_data_readiness_fixture(resume_case,monkeypatch,fault):
    conn,analysis,session,run,runtime,requirement=resume_case
    # Only data fulfillment validation is a named fixture here. It is NOT a real
    # fulfillment acceptance; previous test exercises the actual missing-data gate.
    def fixture_current_data(self,**kwargs):
        assert kwargs['scope']==analysis.scope and kwargs['command']==session.command
        return (None,None,None,runtime,None,None,None,None,None)
    monkeypatch.setattr(AnalysisAdvanceHostService,'_resume_authorities',fixture_current_data)
    tx=HostTransaction(conn)
    _,runs,*_=DataRequirementRequestHostService._components(tx,analysis.scope)
    tasks=AipTaskStore(TransactionBoundConnectFactory(tx,analysis.scope),_analysis_resume_session=session)
    resumer=_AnalysisRunAndTaskResumer(runs,tasks,InvestigationExactRef.model_validate(session.command['requirementRef']),
        run.authority.run_id,run.state.version,conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
    if fault=='domain-failure':
        monkeypatch.setattr(runs,'resume_after_data',lambda *a,**kw:(_ for _ in ()).throw(RuntimeError('fixture domain failure')))
    def invoke():return resumer.resume_run(analysis.scope,runtime.task_run_ref.resource_id,
        expected_run_version=runtime.task_run_ref.version,expected_task_version=runtime.task_ref.version,
        actor=analysis.source.actor if fault=='actor' else AnalysisAdvanceHostService.executor_identity,
        idempotency_key='bi-fulfillment-resume-fixture',reason=RESUME_REASON)
    with pytest.raises(PermissionError,match='enclosing'):invoke()
    # The sealed dispatch response is outside this state-owner composition test.
    # Actual sealed dispatch with absent fulfillment is exercised above.
    from aos_api import ecommerce_growth_host_composition as composition
    monkeypatch.setattr(composition,'build_ecommerce_growth_host_ports',lambda *a,**kw:
        SimpleNamespace(runtime_port=SimpleNamespace(commit=lambda **kw:invoke())))
    if fault:
        with pytest.raises((ValueError,PermissionError,RuntimeError)):session.resume()
        assert tasks.get_run(analysis.scope,runtime.task_run_ref.resource_id).status.value=='paused'
    else:
        result=session.resume()
        assert result.run.status.value=='running' and resumer.run_state.lifecycle.value=='PREPARING'
        assert not tasks.timeline(analysis.scope,runtime.task_run_ref.resource_id).steps

