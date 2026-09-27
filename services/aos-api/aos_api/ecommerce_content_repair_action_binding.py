"""Fail-closed entry for a human-RETURN Action binding.

The positive producer must revalidate the current ReturnDecision, queued
attempt, frozen Brief, installation and budget in the same Action transaction.
Until that producer exists, no RETURN-specific proposal can be persisted.
"""

from __future__ import annotations

from typing import Any

from aos_api.aip_action_policy import RiskDecision, classify_action_risk
from aos_api.aip_action_store import AipActionTransitionBlocked
from aos_api.aip_contracts import ActionRiskLevel


ACTION_TYPE = "ecommerce_growth_content_generate"
_REPAIR_KEYS = frozenset({
    "returnDecisionRef", "briefRef", "priorArtifactRef",
    "installationBindingRef", "capabilityRef", "budgetUpperBoundMinor",
})


def require_repair_action_request(body: Any, action_snapshot: dict[str, Any],
                                  risk: RiskDecision) -> None:
    """Reject a repair-looking request unless a current authority producer owns it."""
    if body.action_type_id != ACTION_TYPE and action_snapshot.get("id") != ACTION_TYPE:
        return
    payload = body.payload
    if type(payload) is not dict or not (_REPAIR_KEYS & payload.keys()):
        return
    current = classify_action_risk(body.action_type_id, action_snapshot,
                                   payload, body.risk_hint)
    policy = current.approval_policy
    if (body.action_type_id != action_snapshot.get("id") or risk != current
            or current.level not in (ActionRiskLevel.R2, ActionRiskLevel.R3)
            or policy.get("makerChecker") is not True
            or policy.get("draftOnly") is not False
            or policy.get("executionAllowed") is not True
            or type(policy.get("minimumApprovals")) is not int
            or policy["minimumApprovals"] < 1):
        raise AipActionTransitionBlocked("REPAIR_ACTION_EXECUTABLE_REVIEW_REQUIRED")
    if set(payload) != _REPAIR_KEYS or body.impact_preview_ref is not None:
        raise AipActionTransitionBlocked("REPAIR_ACTION_EXACT_PAYLOAD_REQUIRED")
    raise AipActionTransitionBlocked("REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED")


def require_repair_action_proposal(row: Any) -> None:
    """An old or direct-insert proposal is never grandfathered into a decision."""
    if row["action_type_id"] != ACTION_TYPE and row["action_type_snapshot"].get("id") != ACTION_TYPE:
        return
    payload = row["payload"]
    if type(payload) is not dict:
        raise AipActionTransitionBlocked("REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED")
    if _REPAIR_KEYS & payload.keys():
        raise AipActionTransitionBlocked("REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED")
