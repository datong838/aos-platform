import pytest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_contracts import ActionRiskLevel


@pytest.mark.parametrize('kind',['ecommerce_growth_cutover','ecommerce_growth_cutover_rollback'])
@pytest.mark.parametrize('hint',[None,ActionRiskLevel.R0,ActionRiskLevel.R3,ActionRiskLevel.R4])
def test_internal_control_requires_independent_review(kind,hint):
    decision=classify_action_risk(kind,{}, {},hint)
    assert decision.floor is ActionRiskLevel.R2
    assert decision.level is (hint if hint in (ActionRiskLevel.R3,ActionRiskLevel.R4) else ActionRiskLevel.R2)
    assert decision.approval_policy['makerChecker'] is True
    assert decision.approval_policy['executionAllowed'] is (hint is not ActionRiskLevel.R4)
    assert decision.approval_policy['draftOnly'] is (hint is ActionRiskLevel.R4)
    assert decision.approval_policy['minimumApprovals']==(2 if hint in (ActionRiskLevel.R3,ActionRiskLevel.R4) else 1)


@pytest.mark.parametrize('kind,payload,expected',[('query',{},ActionRiskLevel.R0),('ordinary',{},ActionRiskLevel.R1),('send',{},ActionRiskLevel.R2),('price',{},ActionRiskLevel.R3),('refund',{},ActionRiskLevel.R4)])
def test_other_action_floors_unchanged(kind,payload,expected):
    assert classify_action_risk(kind,{},payload,None).floor is expected
