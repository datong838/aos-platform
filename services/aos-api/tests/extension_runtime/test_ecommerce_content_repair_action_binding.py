"""RETURN Action proposals must not inherit the generic draft-only path."""

from __future__ import annotations

import pytest

from aos_api.aip_action_models import CreateActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
ACTION = {"id": "ecommerce_growth_content_generate", "name": "content generate",
          "objectType": "Task", "parameters": [], "requiredMarkings": [],
          "submissionCriteria": [], "revisionHash": "a" * 64}


def _request(*, risk_hint: ActionRiskLevel | None, payload: dict):
    return CreateActionProposalRequest(
        actionTypeId=ACTION["id"], taskId="task-1", runId="run-1",
        purpose="human RETURN content repair", riskHint=risk_hint, payload=payload,
    )


def test_return_action_rejects_draft_only_r1_before_any_database_read():
    body = _request(risk_hint=None, payload={"returnDecisionRef": {}})
    risk = classify_action_risk(body.action_type_id, ACTION, body.payload, body.risk_hint)
    assert risk.approval_policy["draftOnly"] is True
    with pytest.raises(AipActionTransitionBlocked, match="REPAIR_ACTION_EXECUTABLE_REVIEW_REQUIRED"):
        AipActionStore()._internal_request_binding(object(), SCOPE, "maker-1", body, ACTION, risk)


def test_return_action_rejects_incomplete_payload_even_when_r2():
    body = _request(risk_hint=ActionRiskLevel.R2, payload={"returnDecisionRef": {}})
    risk = classify_action_risk(body.action_type_id, ACTION, body.payload, body.risk_hint)
    assert risk.approval_policy["draftOnly"] is False
    with pytest.raises(AipActionTransitionBlocked, match="REPAIR_ACTION_EXACT_PAYLOAD_REQUIRED"):
        AipActionStore()._internal_request_binding(object(), SCOPE, "maker-1", body, ACTION, risk)


def test_exact_return_payload_stays_fenced_until_current_authority_producer():
    payload = {key: {} for key in (
        "returnDecisionRef", "briefRef", "priorArtifactRef",
        "installationBindingRef", "capabilityRef", "budgetUpperBoundMinor",
    )}
    body = _request(risk_hint=ActionRiskLevel.R2, payload=payload)
    risk = classify_action_risk(body.action_type_id, ACTION, body.payload, body.risk_hint)
    with pytest.raises(AipActionTransitionBlocked, match="REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED"):
        AipActionStore()._internal_request_binding(object(), SCOPE, "maker-1", body, ACTION, risk)


def test_legacy_inserted_return_proposal_cannot_be_decided():
    row = {"action_type_id": ACTION["id"], "action_type_snapshot": ACTION,
           "payload": {"returnDecisionRef": {}}, "policy_snapshot": {}}
    with pytest.raises(AipActionTransitionBlocked, match="REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED"):
        AipActionStore()._internal_proposal_guard(object(), SCOPE, "checker-1", row,
                                                   checker=True)
