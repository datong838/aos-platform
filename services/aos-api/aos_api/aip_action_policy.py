"""Server-side Action risk floor; client hints can only raise risk."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aos_api.aip_contracts import ActionRiskLevel

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
    if any(word in text for word in ("refund", "payment", "pay_", "inventory", "permission", "退款", "支付", "库存", "权限")):
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
    return RiskDecision(level, floor, tuple(reasons), approval_policy)
