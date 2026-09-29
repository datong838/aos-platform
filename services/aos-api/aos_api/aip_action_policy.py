"""Server-side Action risk floor; client hints can only raise risk."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aos_api.aip_contracts import ActionRiskLevel
from aos_api.aip_provider_health_action import (
    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
)
from aos_api.aip_policy_activation_action import POLICY_ACTIVATION_ACTION_RISK

ACTION_APPROVAL_ROLES = frozenset({'admin', 'approver', 'aip_approver'})

_ORDER = {level: index for index, level in enumerate(ActionRiskLevel)}


@dataclass(frozen=True)
class RiskDecision:
    level: ActionRiskLevel
    floor: ActionRiskLevel
    reasons: tuple[str, ...]
    approval_policy: dict[str, Any]


def classify_action_risk(
    action_type_id: str,
    action_snapshot: dict[str, Any],
    payload: dict[str, Any],
    client_hint: ActionRiskLevel | None,
) -> RiskDecision:
    text = " ".join(
        [
            action_type_id,
            str(action_snapshot.get("name") or ""),
            str(action_snapshot.get("objectType") or ""),
            " ".join(str(key) for key in payload),
        ]
    ).lower()
    reasons: list[str] = []
    floor = ActionRiskLevel.R1
    if action_type_id in POLICY_ACTIVATION_ACTION_RISK:
        floor = POLICY_ACTIVATION_ACTION_RISK[action_type_id]
        reasons.append("formal_policy_activation")
    elif action_type_id in {"ecommerce_growth_cutover", "ecommerce_growth_cutover_rollback",
                          "ecommerce_dispatch_configuration_refresh"}:
        floor = ActionRiskLevel.R2
        reasons.append("internal_runtime_configuration_refresh" if action_type_id.endswith('_refresh')
                       else "internal_runtime_cutover")
    elif action_type_id == 'ecommerce_analysis_bootstrap':
        floor = ActionRiskLevel.R1
        reasons.append('internal_analysis_initial_pause_only')
    elif action_type_id in {'ecommerce_growth_event_control', 'ecommerce_growth_event_dispatch'}:
        floor = ActionRiskLevel.R2
        reasons.append('internal_event_dispatch_control' if action_type_id.endswith('_dispatch')
                       else 'internal_event_binding_control')
    elif action_type_id == 'ecommerce_growth_schedule_put':
        floor = ActionRiskLevel.R2
        reasons.append('internal_schedule_authority_change')
    elif action_type_id == PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID:
        floor = ActionRiskLevel.R2
        reasons.append("provider_external_health_probe")
    elif any(word in text for word in ("refund", "payment", "pay_", "inventory", "permission", "退款", "支付", "库存", "权限")):
        floor = ActionRiskLevel.R4
        reasons.append("irreversible_or_financial")
    elif any(word in text for word in ("price", "discount", "commission", "bulk", "livestream", "价格", "优惠", "佣金", "批量", "直播")):
        floor = ActionRiskLevel.R3
        reasons.append("public_or_bulk_commercial_effect")
    elif any(word in text for word in ("publish", "send", "contact", "cancel_order", "shipping", "发布", "触达", "取消", "发货")):
        floor = ActionRiskLevel.R2
        reasons.append("single_external_effect")
    elif any(word in text for word in ("query", "read", "inspect", "search", "查询", "读取", "检查")) and not payload:
        floor = ActionRiskLevel.R0
        reasons.append("read_only")
    else:
        reasons.append("draft_only_default")
    level = floor
    if client_hint is not None and _ORDER[client_hint] > _ORDER[level]:
        level = client_hint
        reasons.append("client_hint_raised_risk")
    approval_policy = {
        "makerChecker": level in {ActionRiskLevel.R2, ActionRiskLevel.R3, ActionRiskLevel.R4},
        "minimumApprovals": 2 if level in {ActionRiskLevel.R3, ActionRiskLevel.R4} else 1,
        "executionAllowed": level is not ActionRiskLevel.R4,
        "draftOnly": level in {ActionRiskLevel.R1, ActionRiskLevel.R4},
    }
    if action_type_id == 'ecommerce_analysis_bootstrap' and level is ActionRiskLevel.R1:
        approval_policy.update(makerChecker=True, draftOnly=False, controlledSourceInitialization=True)
    return RiskDecision(level, floor, tuple(reasons), approval_policy)
