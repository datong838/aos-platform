"""Real Action drafts under current bootstrap guards; no live approvals."""
import pytest
from uuid import uuid4
from test_analysis_bootstrap_binding_pg import (
    preview_case,preview,compilation_case,publications,context_publication,context_case,startup_case,
    analysis_case,consumer_case,host_case,control_governed,governed,service_case,stored,pair,body,
)
from test_analysis_bootstrap_authority_pg import review_identity


def create(data,prepared,execute=lambda value:value):
    from aos_api.ecommerce_analysis_bootstrap_action import AnalysisBootstrapActionPreparation
    from aos_api.ecommerce_analysis_bootstrap_authority import AnalysisBootstrapCurrentBinding
    conn,analysis,claimed,_,_=data
    return AnalysisBootstrapActionPreparation(AnalysisBootstrapCurrentBinding(analysis)).run_current(
        conn,claimed=claimed,intent=prepared['bootstrapIntent'],preview_ref=prepared['startupPreviewRef'],execute=execute)


def test_bootstrap_creates_actual_draft_and_replays(preview_case,review_identity):
    def prepared(value):
        first=create(preview_case,value)
        assert create(preview_case,value)==first
        return first
    result=preview(preview_case,execute=prepared)
    conn,analysis,_,_,_=preview_case
    row=conn.execute('SELECT status,risk_level,policy_snapshot FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                     (*analysis.scope.key,result.proposal.id)).fetchone()
    assert row['status']=='drafted' and row['risk_level']=='R1' and row['policy_snapshot']['draftOnly'] is True


@pytest.mark.parametrize('fault',['callback','maker-revoked'])
def test_bootstrap_action_failure_rolls_back(preview_case,review_identity,fault):
    conn,analysis,_,_,_=preview_case
    def fail(bundle):
        if fault=='callback':raise RuntimeError('after bootstrap proposal')
        conn.execute('RESET ROLE')
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',(*analysis.scope.key,analysis.source.actor))
        conn.execute('SET LOCAL ROLE aos_runtime')
        return bundle
    with pytest.raises((RuntimeError,PermissionError)),conn.transaction():
        preview(preview_case,execute=lambda value:create(preview_case,value,execute=fail))
    assert conn.execute("SELECT count(*) AS n FROM aip_action_proposal WHERE action_type_id='ecommerce_analysis_bootstrap'").fetchone()['n']==0


@pytest.mark.parametrize('fault',['generic','risk','approve'])
def test_bootstrap_action_cannot_bypass_guard_or_policy(preview_case,review_identity,fault):
    from aos_api.aip_action_store import AipActionStore,AipActionTransitionBlocked
    from aos_api.aip_action_models import CreateActionProposalRequest,DecideActionProposalRequest
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_contracts import ApprovalDecision
    from aos_api.ecommerce_analysis_bootstrap_action import _BootstrapActionGuard
    from aos_api.ecommerce_analysis_bootstrap_authority import AnalysisBootstrapCurrentBinding
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from test_w2d_action_binding import _risk
    conn,analysis,claimed,_,_=preview_case
    def prepared(value):
        guard=_BootstrapActionGuard(AnalysisBootstrapCurrentBinding(analysis),conn,claimed,value['bootstrapIntent'],value['startupPreviewRef'])
        store=AipActionStore(TransactionBoundConnectFactory(HostTransaction(conn),analysis.scope),
                             bootstrap_guard=None if fault=='generic' else guard)
        snapshot=store.action_type_snapshot(analysis.scope,'ecommerce_analysis_bootstrap')
        body=CreateActionProposalRequest(actionTypeId='ecommerce_analysis_bootstrap',taskId=value['compilationReceipt']['taskId'],
            purpose='fixture guarded initialization',payload={'bootstrapIntent':value['bootstrapIntent']},
            impactPreviewRef=value['startupPreviewRef'],expiresAt=value['startupPreview']['expiresAt'])
        if fault=='approve':
            bundle=create(preview_case,value)
            with pytest.raises(AipActionTransitionBlocked,match='EXECUTION_POLICY_NOT_ENABLED'):
                store.decide(analysis.scope,'fixture-approver',bundle.proposal.id,uuid4().hex,
                    DecideActionProposalRequest(expectedProposalVersion=bundle.proposal.version,
                        expectedProposalHash=bundle.proposal.proposal_hash,decision=ApprovalDecision.APPROVED))
        else:
            risk=_risk() if fault=='risk' else classify_action_risk(body.action_type_id,snapshot,body.payload,None)
            with pytest.raises(AipActionTransitionBlocked,match='GUARD_REQUIRED|RISK_DRIFTED'):
                store.create_proposal(analysis.scope,analysis.source.actor,uuid4().hex,body,snapshot,risk)
    preview(preview_case,execute=prepared)
