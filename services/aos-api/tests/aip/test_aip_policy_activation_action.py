import pytest

from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_contracts import ActionRiskLevel


@pytest.mark.parametrize("action_type_id,expected", [
    ("aip_activate_egress_policy", ActionRiskLevel.R2),
    ("aip_activate_data_policy", ActionRiskLevel.R2),
    ("aip_activate_network_policy", ActionRiskLevel.R2),
    ("aip_activate_quota_policy", ActionRiskLevel.R2),
    ("aip_activate_budget_policy", ActionRiskLevel.R3),
])
def test_fixed_policy_activation_requires_independent_review(action_type_id, expected):
    decision = classify_action_risk(action_type_id, {}, {}, ActionRiskLevel.R0)
    assert decision.floor is expected
    assert decision.level is expected
    assert decision.approval_policy["makerChecker"] is True
    assert decision.approval_policy["draftOnly"] is False
    assert decision.approval_policy["minimumApprovals"] == (2 if expected is ActionRiskLevel.R3 else 1)


def test_similar_unregistered_action_does_not_inherit_policy_floor():
    decision = classify_action_risk("aip_activate_egress_policy_v2", {}, {}, None)
    assert decision.floor is ActionRiskLevel.R1
    assert decision.approval_policy["draftOnly"] is True


def test_client_may_only_raise_policy_activation_risk():
    decision = classify_action_risk("aip_activate_egress_policy", {}, {}, ActionRiskLevel.R4)
    assert decision.floor is ActionRiskLevel.R2
    assert decision.level is ActionRiskLevel.R4
    assert decision.approval_policy["executionAllowed"] is False
