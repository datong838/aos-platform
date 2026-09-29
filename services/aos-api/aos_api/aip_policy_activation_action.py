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


class PolicyActivationActionTypeReserved(ValueError):
    """A system policy action cannot be registered through generic editors."""


def require_generic_action_type_mutable(action_type_id: str) -> None:
    if action_type_id in POLICY_ACTIVATION_ACTION_RISK:
        raise PolicyActivationActionTypeReserved("system policy action type is reserved")
