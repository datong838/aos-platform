"""Actual isolated approval + gate + initial pause. No live reviewer or model calls."""
import pytest
from uuid import uuid4
from test_analysis_bootstrap_action_pg import (
    create,review_identity,preview_case,preview,compilation_case,publications,context_publication,context_case,
    startup_case,analysis_case,consumer_case,host_case,control_governed,governed,service_case,stored,pair,body,
)


@pytest.fixture
def start_case(preview_case,review_identity,request):
    from aos_api.ecommerce_analysis_bootstrap_start import _BootstrapProductionStartService
    from aos_api.ecommerce_analysis_bootstrap_action import _BootstrapActionGuard
    from aos_api.ecommerce_analysis_bootstrap_authority import AnalysisBootstrapCurrentBinding
    from aos_api.aip_action_store import AipActionStore
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_contracts import ApprovalDecision
    from aos_api.aip_production_contracts import ProductionStartRequest,ActionProposalExactRef
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    conn,analysis,claimed,_,_=preview_case
    value=preview(preview_case)
    draft=create(preview_case,value)
    guard=_BootstrapActionGuard(AnalysisBootstrapCurrentBinding(analysis),conn,claimed,value['bootstrapIntent'],value['startupPreviewRef'])
    actions=AipActionStore(TransactionBoundConnectFactory(HostTransaction(conn),analysis.scope),bootstrap_guard=guard)
    if getattr(request, 'param', 'independent') == 'source-controlled':
        approved=draft.proposal
    else:
        approved=actions.decide(analysis.scope,'fixture-approver',draft.proposal.id,uuid4().hex,
            DecideActionProposalRequest(expectedProposalVersion=draft.proposal.version,
                expectedProposalHash=draft.proposal.proposal_hash,decision=ApprovalDecision.APPROVED)).proposal
    receipt=guard.intent.compilation_receipt
    current=conn.execute('SELECT version FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s',
                         (*analysis.scope.key,receipt.task_id)).fetchone()
    request=ProductionStartRequest(taskId=receipt.task_id,expectedTaskVersion=current['version'],
        productionContextRef=guard.intent.compilation_binding.request.profile.production_context_ref,
        planRef=receipt.plan_ref,previewRef=guard.preview_ref,
        actionProposalRef=ActionProposalExactRef(proposalId=approved.id,version=approved.version,proposalHash=approved.proposal_hash),
        logicGraphId=receipt.logic_ref.resource_id,logicRevision=receipt.logic_ref.revision,logicGraphHash=receipt.logic_ref.content_hash)
    return conn,analysis,_BootstrapProductionStartService(guard),request,'bootstrap-start-'+uuid4().hex


def test_actual_bootstrap_commits_only_initial_pause_and_replays(start_case):
    conn,analysis,service,request,key=start_case
    result=service.start(analysis.scope,analysis.source.actor,key,request)
    assert result['run'].status.value=='paused'
    assert result['run'].last_checkpoint_id
    assert service.start(analysis.scope,analysis.source.actor,key,request)==result
    assert conn.execute('SELECT count(*) AS n FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s',
                        (*analysis.scope.key,result['run'].id)).fetchone()['n']==0


@pytest.mark.parametrize('when',['before','after'])
def test_bootstrap_pause_failure_rolls_back_start(start_case,monkeypatch,when):
    from aos_api.aip_task_store import AipTaskStore
    conn,analysis,service,request,key=start_case
    original=AipTaskStore.pause_run
    def fail(*args,**kwargs):
        if when=='after':original(*args,**kwargs)
        raise RuntimeError('fixture pause failure')
    monkeypatch.setattr(AipTaskStore,'pause_run',fail)
    with pytest.raises(RuntimeError,match='pause failure'):service.start(analysis.scope,analysis.source.actor,key,request)
    assert conn.execute('SELECT count(*) AS n FROM aip_task_run WHERE org_id=%s AND project_id=%s AND task_id=%s',
                        (*analysis.scope.key,request.task_id)).fetchone()['n']==0
    assert conn.execute('SELECT approval_status FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s',
                        (*analysis.scope.key,request.plan_ref.resource_id)).fetchone()['approval_status']=='draft'


def test_approved_bootstrap_still_cannot_use_generic_gate(start_case):
    from aos_api.aip_production_start_service import AipProductionStartService
    conn,analysis,service,request,key=start_case
    decision=AipProductionStartService(connect_factory=service._connect_factory).start(analysis.scope,analysis.source.actor,key,request)
    assert decision.task_run_ref is None
    assert 'ANALYSIS_BOOTSTRAP_SPECIALIZED_GATE_REQUIRED' in {b.code for b in decision.blockers}


def test_bootstrap_reviewer_withdrawal_blocks_start(start_case):
    conn,analysis,service,request,key=start_case
    conn.execute('RESET ROLE')
    conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'")
    conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises(PermissionError):service.start(analysis.scope,analysis.source.actor,key,request)


@pytest.mark.parametrize('fault',['archived','pointer'])
def test_bootstrap_requires_current_formal_logic_publication(start_case,fault):
    conn,analysis,service,request,key=start_case
    if fault=='archived':conn.execute("UPDATE aip_logic_graph SET status='archived' WHERE org_id=%s AND project_id=%s AND graph_id=%s",(*analysis.scope.key,request.logic_graph_id))
    else:conn.execute("UPDATE aip_logic_graph SET published_version=NULL WHERE org_id=%s AND project_id=%s AND graph_id=%s",(*analysis.scope.key,request.logic_graph_id))
    with pytest.raises(ValueError,match='LOGIC_GRAPH_NOT_PUBLISHED'):
        service.start(analysis.scope,analysis.source.actor,key,request)


def test_bootstrap_replay_payload_drift_rejected(start_case):
    from aos_api.aip_production_contract_store import ProductionContractIdempotencyConflict
    conn,analysis,service,request,key=start_case
    first=service.start(analysis.scope,analysis.source.actor,key,request)
    changed=request.model_copy(update={'expected_task_version':request.expected_task_version+1})
    with pytest.raises(ProductionContractIdempotencyConflict):service.start(analysis.scope,analysis.source.actor,key,changed)
    assert service._tasks.get_run(analysis.scope,first['run'].id)==first['run']


def test_generic_resume_cannot_turn_bootstrap_into_business_execution(start_case):
    from aos_api.aip_task_store import AipTaskTransitionBlocked
    conn,analysis,service,request,key=start_case
    result=service.start(analysis.scope,analysis.source.actor,key,request)
    run=result['run']
    version=conn.execute('SELECT version FROM aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s',
                         (*analysis.scope.key,request.task_id)).fetchone()['version']
    with pytest.raises(AipTaskTransitionBlocked,match='BOOTSTRAP_CONTINUATION_AUTHORITY_REQUIRED'):
        service._tasks.resume_run(analysis.scope,run.id,expected_run_version=run.version,expected_task_version=version,
            actor=analysis.source.actor,idempotency_key=key+'-unauthorized-resume')
    assert service._tasks.get_run(analysis.scope,run.id)==run


def test_bootstrap_approval_cannot_acquire_external_action_lease(start_case,monkeypatch):
    import aos_api.aip_action_execution as execution
    from aos_api.aip_action_adapters import ACTION_ADAPTERS
    from aos_api.aip_action_models import AcquireExecutionLeaseRequest
    from aos_api.aip_action_store import AipActionTransitionBlocked
    from aos_api.auth import Principal
    conn,analysis,service,request,key=start_case
    monkeypatch.setattr(execution,'connect',service._connect_factory)
    conn.execute('RESET ROLE')
    conn.execute('INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,%s)',(*analysis.scope.key,'fixture-bootstrap-executor','admin'))
    conn.execute('SET LOCAL ROLE aos_runtime')
    executor=Principal(subject='fixture-bootstrap-executor',roles=('admin',),markings=(),
                       org_id=analysis.scope.org_id,project_id=analysis.scope.project_id)
    with pytest.raises(AipActionTransitionBlocked,match='BOOTSTRAP_NOT_EXTERNAL_ACTION'):
        execution.AipActionExecutionService(service._actions,ACTION_ADAPTERS).acquire_lease(
            executor,request.action_proposal_ref.proposal_id,key+'-external',AcquireExecutionLeaseRequest(
                expectedProposalVersion=request.action_proposal_ref.version,expectedProposalHash=request.action_proposal_ref.proposal_hash))


@pytest.mark.parametrize('start_case',['source-controlled'],indirect=True)
def test_current_event_control_initializes_without_fabricating_human_review(start_case):
    conn,analysis,service,request,key=start_case
    result=service.start(analysis.scope,analysis.source.actor,key,request)
    assert result['run'].status.value=='paused'
    proposal=request.action_proposal_ref.proposal_id
    assert conn.execute('SELECT count(*) AS n FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                        (*analysis.scope.key,proposal)).fetchone()['n']==0
    assert conn.execute('SELECT status FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                        (*analysis.scope.key,proposal)).fetchone()['status']=='drafted'
    evidence=conn.execute("SELECT payload FROM aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_type='analysis-initialization-authority' AND source_ref=%s",(*analysis.scope.key,service._guard.intent.content_hash)).fetchall()
    assert len(evidence)==1 and evidence[0]['payload']['proof']['kind']=='current-event-control-initialization'
    assert evidence[0]['payload']['proof']['businessExecutionAuthorized'] is False
    assert service.start(analysis.scope,analysis.source.actor,key,request)==result


@pytest.mark.parametrize('start_case',['source-controlled'],indirect=True)
@pytest.mark.parametrize('fault',['rejected','source-revoked','action-snapshot'])
def test_source_derivation_cannot_bypass_current_denial(start_case,fault):
    from aos_api.aip_action_models import DecideActionProposalRequest
    from aos_api.aip_contracts import ApprovalDecision
    conn,analysis,service,request,key=start_case
    if fault=='rejected':
        service._actions.decide(analysis.scope,'fixture-approver',request.action_proposal_ref.proposal_id,uuid4().hex,
            DecideActionProposalRequest(expectedProposalVersion=request.action_proposal_ref.version,
                expectedProposalHash=request.action_proposal_ref.proposal_hash,decision=ApprovalDecision.REJECTED))
    else:
        conn.execute('RESET ROLE')
        if fault=='source-revoked':conn.execute("DELETE FROM meta_membership WHERE subject='fixture-approver'")
        else:conn.execute("UPDATE meta_action_type SET name='changed' WHERE id='ecommerce_analysis_bootstrap'")
        conn.execute('SET LOCAL ROLE aos_runtime')
    with pytest.raises((ValueError,PermissionError)):
        service.start(analysis.scope,analysis.source.actor,key,request)
    assert conn.execute('SELECT count(*) AS n FROM aip_task_run WHERE org_id=%s AND project_id=%s AND task_id=%s',(*analysis.scope.key,request.task_id)).fetchone()['n']==0


@pytest.mark.parametrize('start_case',['source-controlled'],indirect=True)
def test_revoked_initialization_authority_blocks_replay(start_case):
    conn,analysis,service,request,key=start_case
    first=service.start(analysis.scope,analysis.source.actor,key,request)
    ref=conn.execute("SELECT evidence_id,content_hash FROM aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_type='analysis-initialization-authority' AND source_ref=%s",
                      (*analysis.scope.key,service._guard.intent.content_hash)).fetchone()
    conn.execute("""INSERT INTO aip_evidence_revoke_event(org_id,project_id,event_id,evidence_id,revision,content_hash,reason,actor)
        VALUES(%s,%s,%s,%s,1,%s,'fixture revoke','fixture')""",(*analysis.scope.key,uuid4().hex,ref['evidence_id'],ref['content_hash']))
    with pytest.raises(ValueError,match='authority Evidence differs'):
        service.start(analysis.scope,analysis.source.actor,key,request)
    assert service._tasks.get_run(analysis.scope,first['run'].id)==first['run']
