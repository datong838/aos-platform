import pytest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_contracts import ActionRiskLevel


@pytest.mark.parametrize('hint',[None,ActionRiskLevel.R0,ActionRiskLevel.R3,ActionRiskLevel.R4])
def test_schedule_save_has_executable_independent_review_floor(hint):
    risk=classify_action_risk('ecommerce_growth_schedule_put',{}, {'policyHash':'sha256:'+'a'*64},hint)
    assert risk.floor is ActionRiskLevel.R2
    assert risk.level is (hint if hint in (ActionRiskLevel.R3,ActionRiskLevel.R4) else ActionRiskLevel.R2)
    assert risk.approval_policy['makerChecker'] is True
    assert risk.approval_policy['draftOnly'] is (hint is ActionRiskLevel.R4)
    assert risk.approval_policy['executionAllowed'] is (hint is not ActionRiskLevel.R4)
