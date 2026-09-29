"""Disposable clone only: synthetic metadata and actor prove code path, not live approval."""
from datetime import UTC, datetime, timedelta
import json
import os
import uuid

import psycopg
from psycopg.rows import dict_row
import pytest

from aos_api.aip_action_store import AipActionConflict, AipActionIdempotencyConflict, AipActionStore, AipActionTransitionBlocked
from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_network_policy_action_producer import (
    NetworkPolicyProducerBlocked, _ACTION, _OBJECT, propose_network_activation,
    decide_network_activation,
)
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevisionCreate
from aos_api.auth import Principal
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope
from tests.aip._runtime_guard_history_fixture import seed_historical_runtime_guard


CLONE = "aos_bg00br_producer_testonly_20260929"
SCOPE = TenantScope("org-org", "dev-project")


def test_only_clone_produces_exact_drafted_proposal_and_no_policy_write():
    if os.environ.get("AOS_BG00BR_TEST_DATABASE") != CLONE:
        pytest.skip("explicit BG00br disposable database required")
    with psycopg.connect(get_dsn(), row_factory=dict_row) as owner:
        assert owner.info.dbname == CLONE
        owner.execute(
            "INSERT INTO meta_object_type(id,name,description,published,properties,required_markings) "
            "VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb) ON CONFLICT (id) DO NOTHING",
            (_OBJECT["id"], _OBJECT["name"], _OBJECT["description"], _OBJECT["published"],
             json.dumps(_OBJECT["properties"]), json.dumps(_OBJECT["requiredMarkings"])),
        )
        owner.execute(
            "INSERT INTO meta_action_type(id,name,object_type,parameters,required_markings,submission_criteria) "
            "VALUES(%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb) ON CONFLICT (id) DO NOTHING",
            (_ACTION["id"], _ACTION["name"], _ACTION["objectType"],
             json.dumps(_ACTION["parameters"]), json.dumps(_ACTION["requiredMarkings"]),
             json.dumps(_ACTION["submissionCriteria"])),
        )
        owner.execute(
            "INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,%s) "
            "ON CONFLICT (org_id,project_id,subject) DO NOTHING",
            (*SCOPE.key, "bg00br-test-maker", "owner"),
        )
        for subject in ("bg00bs-test-checker", "bg00bs-test-revoker"):
            owner.execute(
                "INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT (org_id,project_id,subject) DO NOTHING",
                (*SCOPE.key, subject, "admin"),
            )
    now = datetime.now(UTC)
    suffix = uuid.uuid4().hex[:8]
    egress = seed_historical_runtime_guard(SCOPE, "bg00br-test", EgressPolicyRevisionCreate(
        policyId=f"bg00br-test-egress-{suffix}", revision=1, environment="development",
        allowedSchemes=["https"], allowedHosts=["api.agnes-ai.cn"], allowedPorts=[443],
        allowPublicFallback=False, unknownDestinationBehavior="block",
        regionState="confirmed", region="cn-test-only", effectiveFrom=now - timedelta(hours=1),
        effectiveUntil=now + timedelta(days=1), owner="bg00br-test", approvalRef="test-only",
        lifecycle="active",
    ))
    candidate = NetworkPolicyRevisionCreate(
        policyId=f"bg00br-test-network-{suffix}", revision=1, allowedSchemes=["https"],
        allowedHosts=["api.agnes-ai.cn"], allowedPorts=[443], tlsRequired=True,
        publicFallbackAllowed=False,
        egressPolicyRef={"assetType": "EgressPolicyRevision", "assetId": egress.policy_id,
                         "revision": egress.revision, "contentHash": egress.content_hash},
        effectiveFrom=now, effectiveUntil=now + timedelta(hours=12), owner="bg00br-test-maker",
        approvalRef="text-only-test", lifecycle="active",
    )
    principal = Principal(subject="bg00br-test-maker", org_id=SCOPE.org_id,
                          project_id=SCOPE.project_id, roles=["owner"], token_kind="oidc")
    expiry = datetime.now(UTC) + timedelta(minutes=10)
    key = f"bg00br-test-key-{suffix}"
    first = propose_network_activation(principal, candidate, expected_version=0,
                                       idempotency_key=key, expires_at=expiry)
    assert first.proposal.status.value == "drafted"
    assert first.proposal.action_binding_hash is not None
    assert propose_network_activation(principal, candidate, expected_version=0,
                                      idempotency_key=key, expires_at=expiry).proposal.id == first.proposal.id
    with pytest.raises(AipActionIdempotencyConflict):
        propose_network_activation(principal, candidate.model_copy(update={"owner": "other-owner"}),
                                    expected_version=0, idempotency_key=key, expires_at=expiry)
    with pytest.raises(NetworkPolicyProducerBlocked, match="OWNER_REQUIRED"):
        propose_network_activation(Principal(subject="unknown-maker", org_id=SCOPE.org_id,
            project_id=SCOPE.project_id, token_kind="oidc"), candidate, expected_version=0,
            idempotency_key=f"unknown-{suffix}", expires_at=expiry)
    with pytest.raises(NetworkPolicyProducerBlocked, match="HEAD_VERSION_DRIFTED"):
        propose_network_activation(principal, candidate, expected_version=1,
                                    idempotency_key=f"stale-{suffix}", expires_at=expiry)
    with pytest.raises(NetworkPolicyProducerBlocked, match="TARGET_OR_EGRESS_INVALID"):
        propose_network_activation(principal, candidate.model_copy(update={
            "egress_policy_ref": candidate.egress_policy_ref.model_copy(update={"content_hash": "b" * 64})}),
            expected_version=0, idempotency_key=f"egress-{suffix}", expires_at=expiry)
    with pytest.raises(NetworkPolicyProducerBlocked, match="OWNER_REQUIRED"):
        propose_network_activation(Principal(subject="bg00br-test-maker", org_id="dev-org",
            project_id=SCOPE.project_id, token_kind="oidc"), candidate,
            expected_version=0, idempotency_key=f"canary-{suffix}", expires_at=expiry)
    with connect(SCOPE) as conn:
        proposal = conn.execute(
            "SELECT status,risk_level,action_binding_hash FROM aip_action_proposal "
            "WHERE org_id=%s AND project_id=%s AND proposal_id=%s", (*SCOPE.key, first.proposal.id),
        ).fetchone()
        assert proposal["status"] == "drafted" and proposal["risk_level"] == "R2"
        assert proposal["action_binding_hash"] == first.proposal.action_binding_hash
        for table in ("aip_network_policy_head", "aip_network_policy_revision", "aip_network_policy_receipt"):
            assert conn.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"] == 0
    with pytest.raises(AipActionTransitionBlocked, match="CHECKER_UNWIRED"):
        AipActionStore()._internal_proposal_guard(None, SCOPE, "bg00br-test-checker",
            {"action_type_id": _ACTION["id"], "action_type_snapshot": {"id": _ACTION["id"]},
             "payload": {}}, checker=True)
    checker = Principal(subject="bg00bs-test-checker", org_id=SCOPE.org_id,
                        project_id=SCOPE.project_id, roles=["admin"], token_kind="oidc")
    approve = DecideActionProposalRequest.model_validate({
        "expectedProposalVersion": first.proposal.version,
        "expectedProposalHash": first.proposal.proposal_hash,
        "decision": "approved", "reason": "isolated path proof",
        "approvalExpiresAt": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    })
    with pytest.raises(NetworkPolicyProducerBlocked, match="MAKER_CHECKER_SEPARATION"):
        decide_network_activation(principal, first.proposal.id, f"maker-check-{suffix}", approve)
    with pytest.raises(NetworkPolicyProducerBlocked, match="CURRENT_CHECKER_REQUIRED"):
        decide_network_activation(Principal(subject="unknown-checker", org_id=SCOPE.org_id,
            project_id=SCOPE.project_id, roles=["admin"], token_kind="oidc"),
            first.proposal.id, f"unknown-check-{suffix}", approve)
    with pytest.raises(AipActionConflict):
        decide_network_activation(checker, first.proposal.id, f"stale-check-{suffix}",
            approve.model_copy(update={"expected_proposal_version": first.proposal.version + 1}))
    approved = decide_network_activation(checker, first.proposal.id, f"approve-{suffix}", approve)
    assert approved.proposal.status.value == "approved"
    assert len(approved.approvals) == 1
    assert approved.approvals[0].action_binding_hash == first.proposal.action_binding_hash
    assert decide_network_activation(checker, first.proposal.id,
        f"approve-{suffix}", approve).proposal.id == first.proposal.id
    with pytest.raises(AipActionIdempotencyConflict):
        decide_network_activation(checker, first.proposal.id, f"approve-{suffix}",
            approve.model_copy(update={"reason": "changed"}))
    revoker = Principal(subject="bg00bs-test-revoker", org_id=SCOPE.org_id,
                        project_id=SCOPE.project_id, roles=["admin"], token_kind="oidc")
    second_approve = approve.model_copy(update={"expected_proposal_version": approved.proposal.version})
    with pytest.raises(NetworkPolicyProducerBlocked, match="ALREADY_APPROVED"):
        decide_network_activation(revoker, first.proposal.id, f"second-approve-{suffix}", second_approve)
    reject = DecideActionProposalRequest.model_validate({
        "expectedProposalVersion": approved.proposal.version,
        "expectedProposalHash": approved.proposal.proposal_hash,
        "decision": "rejected", "reason": "isolated revocation proof",
    })
    rejected = decide_network_activation(revoker, first.proposal.id, f"revoke-{suffix}", reject)
    assert rejected.proposal.status.value == "rejected"
    assert decide_network_activation(revoker, first.proposal.id,
        f"revoke-{suffix}", reject).proposal.id == first.proposal.id
    drifted = candidate.model_copy(update={"policy_id": f"bg00by-drift-{suffix}"})
    drifted_proposal = propose_network_activation(
        principal, drifted, expected_version=0,
        idempotency_key=f"drift-propose-{suffix}", expires_at=expiry,
    )
    with psycopg.connect(get_dsn()) as owner:
        owner.execute(
            "INSERT INTO aip_network_policy_head(org_id,project_id,policy_id,current_revision,version) "
            "VALUES(%s,%s,%s,1,1)", (*SCOPE.key, drifted.policy_id),
        )
    try:
        drifted_decision = DecideActionProposalRequest.model_validate({
            "expectedProposalVersion": drifted_proposal.proposal.version,
            "expectedProposalHash": drifted_proposal.proposal.proposal_hash,
            "decision": "approved", "reason": "head changed after proposal",
        })
        with pytest.raises(NetworkPolicyProducerBlocked, match="CHECKER_BINDING_DRIFTED"):
            decide_network_activation(checker, drifted_proposal.proposal.id,
                f"drift-decide-{suffix}", drifted_decision)
        with connect(SCOPE) as conn:
            assert conn.execute(
                "SELECT count(*) AS n FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s "
                "AND proposal_id=%s", (*SCOPE.key, drifted_proposal.proposal.id),
            ).fetchone()["n"] == 0
    finally:
        with psycopg.connect(get_dsn()) as owner:
            owner.execute("DELETE FROM aip_network_policy_head WHERE org_id=%s AND project_id=%s "
                          "AND policy_id=%s", (*SCOPE.key, drifted.policy_id))
    with connect(SCOPE) as conn:
        for table in ("aip_network_policy_head", "aip_network_policy_revision", "aip_network_policy_receipt"):
            assert conn.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"] == 0
