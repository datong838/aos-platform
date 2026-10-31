"""Reserved Judge-call action cannot inherit generic draft/execution authority."""
import pytest
from aos_api.aip_action_models import CreateActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.tenant_scope import TenantScope

ACTION='aip_request_model_judge_call'
SCOPE=TenantScope('org-org','dev-project')

@pytest.mark.parametrize('hint',[None,ActionRiskLevel.R3,ActionRiskLevel.R4])
def test_judge_call_has_independent_checker_and_no_generic_execution(hint):
    risk=classify_action_risk(ACTION,{'id':ACTION}, {'requestId':'judge-request','requestHash':'a'*64},hint)
    assert risk.floor is ActionRiskLevel.R2
    assert risk.approval_policy['makerChecker'] is True
    assert risk.approval_policy['executionAllowed'] is False

@pytest.mark.parametrize('request_id,snapshot_id',[(ACTION,ACTION),(ACTION,'another'),('another',ACTION)])
def test_judge_call_request_requires_dedicated_producer(request_id,snapshot_id):
    body=CreateActionProposalRequest(actionTypeId=request_id,purpose='model-judge-call',payload={'requestId':'j','requestHash':'a'*64})
    snapshot={'id':snapshot_id}
    risk=classify_action_risk(request_id,snapshot,body.payload,None)
    with pytest.raises(AipActionTransitionBlocked,match='MODEL_JUDGE_ACTION_PRODUCER_REQUIRED'):
        AipActionStore()._internal_request_binding(None,SCOPE,'maker',body,snapshot,risk)

@pytest.mark.parametrize('checker',[False,True])
@pytest.mark.parametrize('request_id,snapshot_id',[(ACTION,ACTION),(ACTION,'another'),('another',ACTION)])
def test_judge_call_proposal_replay_and_checker_require_dedicated_producer(checker,request_id,snapshot_id):
    row={'action_type_id':request_id,'action_type_snapshot':{'id':snapshot_id}}
    with pytest.raises(AipActionTransitionBlocked,match='MODEL_JUDGE_ACTION_PRODUCER_REQUIRED'):
        AipActionStore()._internal_proposal_guard(None,SCOPE,'checker' if checker else 'maker',row,checker=checker)

@pytest.mark.parametrize('request_id,snapshot_id',[(ACTION,ACTION),(ACTION,'another'),('another',ACTION)])
def test_judge_call_cannot_reach_generic_executor(request_id,snapshot_id):
    with pytest.raises(AipActionTransitionBlocked,match='MODEL_JUDGE_DEDICATED_OWNER_REQUIRED'):
        AipActionExecutionService._reject_bootstrap_action({'action_type_id':request_id,'action_type_snapshot':{'id':snapshot_id}})
