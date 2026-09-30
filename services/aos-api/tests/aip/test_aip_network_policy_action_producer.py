from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_action_models import CreateActionProposalRequest, DecideActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore, AipActionTransitionBlocked, canonical_hash
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_network_policy_action_producer import (
    NetworkPolicyActivationGuard,
    NetworkPolicyProducerBlocked,
    propose_network_activation,
)
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope


def _candidate():
    now = datetime(2026, 9, 29, tzinfo=UTC)
    return NetworkPolicyRevisionCreate.model_validate({
        "policyId": "network-1", "revision": 1,
        "allowedSchemes": ["https"], "allowedHosts": ["api.agnes-ai.cn"],
        "allowedPorts": [443], "tlsRequired": True, "publicFallbackAllowed": False,
        "egressPolicyRef": {"assetType": "EgressPolicyRevision", "assetId": "egress-1",
                            "revision": 1, "contentHash": "a" * 64},
        "effectiveFrom": now, "effectiveUntil": now + timedelta(days=1),
        "owner": "owner-1", "approvalRef": "text-is-not-approval", "lifecycle": "active",
    })


def _snapshot():
    return {"id": "aip_activate_network_policy", "name": "激活网络策略",
            "objectType": "NetworkPolicyRevision", "parameters": [],
            "requiredMarkings": [], "submissionCriteria": [], "revisionHash": "a" * 64}


def test_dev_identity_cannot_enter_dedicated_producer_before_database():
    principal = Principal(subject="user:dev", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="dev")
    with pytest.raises(NetworkPolicyProducerBlocked, match="OIDC"):
        propose_network_activation(principal, _candidate(), expected_version=0,
                                   idempotency_key="key-1", expires_at=datetime.now(UTC) + timedelta(minutes=10),
                                   connect_factory=lambda *_: 1)


def test_direct_action_store_cannot_create_unbound_system_policy_proposal():
    store = AipActionStore(connect_factory=lambda *_: (_ for _ in ()).throw(AssertionError("DB read forbidden")))
    body = CreateActionProposalRequest(actionTypeId="aip_activate_network_policy", purpose="activate")
    snapshot = _snapshot()
    risk = classify_action_risk(body.action_type_id, snapshot, body.payload, None)
    with pytest.raises(AipActionTransitionBlocked, match="PRODUCER_REQUIRED"):
        store.create_proposal(TenantScope("org-org", "dev-project"), "owner-1", "key-1", body, snapshot, risk)


def test_generic_checker_cannot_approve_system_policy_proposal():
    store = AipActionStore(connect_factory=lambda *_: (_ for _ in ()).throw(AssertionError("DB read forbidden")))
    row = {"action_type_id": "aip_activate_network_policy", "action_type_snapshot": _snapshot(),
           "payload": {}}
    with pytest.raises(AipActionTransitionBlocked, match="CHECKER_UNWIRED"):
        store._internal_proposal_guard(None, TenantScope("org-org", "dev-project"),
                                       "checker-1", row, checker=True)


@pytest.mark.parametrize("action_id,snapshot_id", [
    ("aip_activate_network_policy", "other"),
    ("other", "aip_activate_network_policy"),
])
def test_generic_executor_cannot_lease_or_execute_system_policy_proposal(action_id, snapshot_id):
    proposal = {"action_type_id": action_id, "action_type_snapshot": {"id": snapshot_id}}
    with pytest.raises(AipActionTransitionBlocked, match="POLICY_ACTION_EXECUTOR_UNWIRED"):
        AipActionExecutionService._reject_bootstrap_action(proposal)


def test_live_route_rejects_dev_identity_before_policy_database(client):
    response = client.post(
        "/v1/aip/runtime-guard-policies/networks/activation-proposals",
        headers={"Authorization": "Bearer dev", "X-Org-Id": "org-org",
                 "X-Project-Id": "dev-project", "If-Match": "0", "Idempotency-Key": "test-producer"},
        json={"candidate": _candidate().model_dump(mode="json", by_alias=True),
              "expiresAt": (datetime.now(UTC) + timedelta(minutes=10)).isoformat()},
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "OIDC_POLICY_MAKER_REQUIRED"


def test_dedicated_checker_rejects_dev_identity_before_database():
    from aos_api.aip_network_policy_action_producer import decide_network_activation
    principal = Principal(subject="checker", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="dev")
    body = DecideActionProposalRequest.model_validate({
        "expectedProposalVersion": 1, "expectedProposalHash": "a" * 64,
        "decision": "approved", "reason": "test-only",
    })
    with pytest.raises(NetworkPolicyProducerBlocked, match="OIDC"):
        decide_network_activation(principal, "proposal-1", "key-1", body,
                                  connect_factory=lambda *_: (_ for _ in ()).throw(AssertionError("DB read forbidden")))


def test_oidc_checker_without_independent_issuer_cannot_use_api_database(monkeypatch):
    import aos_api.aip_network_policy_action_producer as producer
    principal = Principal(subject="checker", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    body = DecideActionProposalRequest.model_validate({
        "expectedProposalVersion": 1, "expectedProposalHash": "a" * 64,
        "decision": "approved", "reason": "isolated no-effect gate",
    })
    monkeypatch.setattr(producer, "db_connect", lambda *_: (_ for _ in ()).throw(
        AssertionError("ordinary API DB connection forbidden")))
    with pytest.raises(NetworkPolicyProducerBlocked, match="NETWORK_ISSUER_SERVICE_REQUIRED"):
        producer.decide_network_activation(principal, "proposal-1", "key-1", body)


def test_generic_checker_remains_unwired_for_network_proposal():
    store = AipActionStore(connect_factory=lambda *_: (_ for _ in ()).throw(AssertionError("DB read forbidden")))
    row = {"action_type_id": "aip_activate_network_policy", "action_type_snapshot": _snapshot(), "payload": {}}
    with pytest.raises(AipActionTransitionBlocked, match="CHECKER_UNWIRED"):
        store._internal_proposal_guard(None, TenantScope("org-org", "dev-project"),
                                       "checker", row, checker=True)


def test_live_decision_route_rejects_dev_identity_before_database(client):
    response = client.post(
        "/v1/aip/runtime-guard-policies/networks/activation-proposals/proposal-1/decision",
        headers={"Authorization": "Bearer dev", "X-Org-Id": "org-org",
                 "X-Project-Id": "dev-project", "Idempotency-Key": "test-checker"},
        json={"expectedProposalVersion": 1, "expectedProposalHash": "a" * 64,
              "decision": "approved", "reason": "test-only"},
    )
    assert response.status_code == 403, response.text
    assert response.json()["code"] == "OIDC_POLICY_CHECKER_REQUIRED"


def test_checker_requires_timezone_aware_approval_expiry_before_database():
    from aos_api.aip_network_policy_action_producer import decide_network_activation
    principal = Principal(subject="checker", org_id="org-org", project_id="dev-project",
                          roles=["admin"], token_kind="oidc")
    body = DecideActionProposalRequest.model_validate({
        "expectedProposalVersion": 1, "expectedProposalHash": "a" * 64,
        "decision": "approved", "approvalExpiresAt": "2026-10-01T00:00:00",
    })
    with pytest.raises(NetworkPolicyProducerBlocked, match="EXPIRY_INVALID"):
        decide_network_activation(principal, "proposal-1", "key-1", body,
            connect_factory=lambda *_: (_ for _ in ()).throw(AssertionError("DB read forbidden")))


def test_checker_replay_rechecks_current_target_and_dependencies(monkeypatch):
    scope = TenantScope("org-org", "dev-project")
    candidate = _candidate()
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    guard = NetworkPolicyActivationGuard(
        scope=scope, actor="owner-1", candidate=candidate,
        expected_version=0, expires_at=expires_at,
    )
    snapshot = _snapshot()
    payload = {"candidate": candidate.model_dump(mode="json", by_alias=True),
               "expectedHeadVersion": 0}
    risk = classify_action_risk("aip_activate_network_policy", snapshot, payload, None)
    policy = {"floor": risk.floor.value, "reasons": list(risk.reasons), **risk.approval_policy}
    row = {
        "created_by": "owner-1", "status": "drafted", "task_id": None, "run_id": None,
        "impact_preview_id": None, "object_ref": None, "diff": {}, "evidence_refs": [],
        "purpose": "activate", "payload": payload, "expires_at": expires_at,
        "action_type_snapshot": snapshot, "risk_level": risk.level.value,
        "policy_snapshot": policy, "approval_policy_hash": canonical_hash(policy),
        "action_binding_hash": "a" * 64,
    }
    def drifted(*_args):
        raise NetworkPolicyProducerBlocked("LIVE_DEPENDENCY_DRIFTED")
    monkeypatch.setattr(guard, "check_request", drifted)
    with pytest.raises(NetworkPolicyProducerBlocked, match="LIVE_DEPENDENCY_DRIFTED"):
        guard.check_replay(object(), scope, "owner-1", row)
