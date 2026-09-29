"""Fixed ActionType identities for future formally approved policy activation.

These identities do not register ActionTypes or authorize any active policy write.
"""

from types import MappingProxyType

from aos_api.aip_contracts import ActionRiskLevel


POLICY_ACTIVATION_ACTION_RISK = MappingProxyType({
    "aip_activate_egress_policy": ActionRiskLevel.R2,
    "aip_activate_data_policy": ActionRiskLevel.R2,
    "aip_activate_network_policy": ActionRiskLevel.R2,
    "aip_activate_quota_policy": ActionRiskLevel.R2,
    "aip_activate_budget_policy": ActionRiskLevel.R3,
})
