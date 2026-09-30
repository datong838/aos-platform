"""A real PostgreSQL clone proves the precheck never activates a policy."""

from datetime import UTC, datetime, timedelta
import os
import uuid

import psycopg
from psycopg.rows import dict_row
import pytest

from aos_api.aip_action_models import DecideActionProposalRequest, WithdrawActionProposalRequest
from aos_api.aip_action_store import AipActionStore
from aos_api.aip_network_policy_action_producer import (
    propose_network_activation, decide_network_activation as _decide_network_activation,
)
from aos_api.aip_network_policy_approval_consumer import (
    NetworkApprovalConsumptionBlocked, precheck_network_activation,
)
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_runtime_guard_policy_contracts import EgressPolicyRevisionCreate
from aos_api.auth import Principal
from aos_api.db import connect, get_dsn
from aos_api.tenant_scope import TenantScope
from tests.aip._runtime_guard_history_fixture import seed_historical_runtime_guard


CLONE = "aos_bg00bx_cutover_testonly_20260930"
SCOPE = TenantScope("org-org", "dev-project")


def decide_network_activation(*args, **kwargs):
    # Historical a0v_117 synthetic clone proof only; not a formal issuer service.
    return _decide_network_activation(*args, connect_factory=connect, **kwargs)


def test_only_exact_approval_consumption_precheck(monkeypatch):
    if os.environ.get("AOS_BG00CA_TEST_DATABASE") != CLONE:
        pytest.skip("explicit BG00ca disposable clone required")
    with psycopg.connect(get_dsn(), row_factory=dict_row) as owner:
        assert owner.info.dbname == CLONE
        assert owner.execute("SELECT version_num FROM alembic_version").fetchone()["version_num"] == "a0v_117"
        for subject, role in (("bg00ca-maker", "owner"), ("bg00ca-checker", "admin"),
                              ("bg00ca-revoker", "admin")):
            owner.execute(
                "INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES(%s,%s,%s,%s) "
                "ON CONFLICT (org_id,project_id,subject) DO NOTHING",
                (*SCOPE.key, subject, role),
            )
    suffix = uuid.uuid4().hex[:10]
    now = datetime.now(UTC)
    egress = seed_historical_runtime_guard(SCOPE, "bg00ca-test", EgressPolicyRevisionCreate(
        policyId=f"bg00ca-egress-{suffix}", revision=1, environment="development",
        allowedSchemes=["https"], allowedHosts=["api.agnes-ai.cn"], allowedPorts=[443],
        allowPublicFallback=False, unknownDestinationBehavior="block",
        regionState="confirmed", region="cn-test-only", effectiveFrom=now - timedelta(hours=1),
        effectiveUntil=now + timedelta(days=1), owner="bg00ca-test", approvalRef="test-only",
        lifecycle="active",
    ))
    candidate = NetworkPolicyRevisionCreate(
        policyId=f"bg00ca-network-{suffix}", revision=1, allowedSchemes=["https"],
        allowedHosts=["api.agnes-ai.cn"], allowedPorts=[443], tlsRequired=True,
        publicFallbackAllowed=False,
        egressPolicyRef={"assetType": "EgressPolicyRevision", "assetId": egress.policy_id,
                         "revision": egress.revision, "contentHash": egress.content_hash},
        effectiveFrom=now, effectiveUntil=now + timedelta(hours=12), owner="bg00ca-maker",
        approvalRef="text-only-test", lifecycle="active",
    )
    maker = Principal(subject="bg00ca-maker", org_id=SCOPE.org_id,
                      project_id=SCOPE.project_id, roles=["owner"], token_kind="oidc")
    checker = Principal(subject="bg00ca-checker", org_id=SCOPE.org_id,
                        project_id=SCOPE.project_id, roles=["admin"], token_kind="oidc")
    expiry = datetime.now(UTC) + timedelta(minutes=10)
    proposed = propose_network_activation(
        maker, candidate, expected_version=0, idempotency_key=f"propose-{suffix}", expires_at=expiry,
    )
    decision = DecideActionProposalRequest.model_validate({
        "expectedProposalVersion": proposed.proposal.version,
        "expectedProposalHash": proposed.proposal.proposal_hash,
        "decision": "approved", "reason": "isolated precheck proof",
        "approvalExpiresAt": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
    })
    approved = decide_network_activation(checker, proposed.proposal.id, f"approve-{suffix}", decision)
    assert approved.proposal.version == approved.approvals[0].proposal_version + 1
    approval_id = approved.approvals[0].id
    with connect(SCOPE) as conn:
        proof = precheck_network_activation(conn, SCOPE, proposed.proposal.id, approval_id)
        assert proof.proposal_id == proposed.proposal.id
        assert proof.approval_event_id == approval_id
        assert proof.policy_id == candidate.policy_id
        assert proof.revision == 1 and proof.consumption_key == proposed.proposal.id
        conn.rollback()
    with connect(SCOPE) as conn:
        with pytest.raises(NetworkApprovalConsumptionBlocked, match="APPROVAL_UNAVAILABLE"):
            precheck_network_activation(conn, SCOPE, proposed.proposal.id, "wrong-approval")
        conn.rollback()
    with connect(TenantScope("dev-org", "dev-project")) as conn:
        with pytest.raises(NetworkApprovalConsumptionBlocked, match="PROPOSAL_UNAVAILABLE"):
            precheck_network_activation(conn, TenantScope("dev-org", "dev-project"),
                                        proposed.proposal.id, approval_id)
        conn.rollback()
    with connect(SCOPE) as conn:
        conn.execute(
            "INSERT INTO aip_network_policy_receipt(org_id,project_id,receipt_id,operation,"
            "idempotency_key,request_hash,result_ref,created_by) "
            "VALUES(%s,%s,%s,'network_policy.activate',%s,%s,'{}'::jsonb,'test-only')",
            (*SCOPE.key, f"bg00ca-receipt-{suffix}", proposed.proposal.id, "a" * 64),
        )
        with pytest.raises(NetworkApprovalConsumptionBlocked, match="ALREADY_RECORDED"):
            precheck_network_activation(conn, SCOPE, proposed.proposal.id, approval_id)
        conn.rollback()
    with psycopg.connect(get_dsn()) as owner:
        owner.execute(
            "INSERT INTO aip_network_policy_head(org_id,project_id,policy_id,current_revision,version) "
            "VALUES(%s,%s,%s,1,1)", (*SCOPE.key, candidate.policy_id),
        )
    try:
        with connect(SCOPE) as conn:
            with pytest.raises(NetworkApprovalConsumptionBlocked, match="CURRENT_BINDING_DRIFTED"):
                precheck_network_activation(conn, SCOPE, proposed.proposal.id, approval_id)
            conn.rollback()
    finally:
        with psycopg.connect(get_dsn()) as owner:
            owner.execute("DELETE FROM aip_network_policy_head WHERE org_id=%s AND project_id=%s "
                          "AND policy_id=%s", (*SCOPE.key, candidate.policy_id))
    with psycopg.connect(get_dsn()) as owner:
        owner.execute("DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s",
                      (*SCOPE.key, checker.subject))
    try:
        with connect(SCOPE) as conn:
            with pytest.raises(NetworkApprovalConsumptionBlocked, match="CURRENT_BINDING_DRIFTED"):
                precheck_network_activation(conn, SCOPE, proposed.proposal.id, approval_id)
            conn.rollback()
    finally:
        with psycopg.connect(get_dsn()) as owner:
            owner.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) "
                          "VALUES(%s,%s,%s,'admin') ON CONFLICT DO NOTHING",
                          (*SCOPE.key, checker.subject))
    with psycopg.connect(get_dsn()) as owner:
        owner.execute("UPDATE aip_action_approval_event SET proposal_hash=%s WHERE org_id=%s "
                      "AND project_id=%s AND approval_event_id=%s",
                      ("b" * 64, *SCOPE.key, approval_id))
    try:
        with connect(SCOPE) as conn:
            with pytest.raises(NetworkApprovalConsumptionBlocked, match="APPROVAL_BINDING_DRIFTED"):
                precheck_network_activation(conn, SCOPE, proposed.proposal.id, approval_id)
            conn.rollback()
    finally:
        with psycopg.connect(get_dsn()) as owner:
            owner.execute("UPDATE aip_action_approval_event SET proposal_hash=%s WHERE org_id=%s "
                          "AND project_id=%s AND approval_event_id=%s",
                          (approved.proposal.proposal_hash, *SCOPE.key, approval_id))
    import aos_api.aip_runtime_guard_policy_store as guard_store
    real_guard_datetime = datetime
    class ExpiredEgressDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return real_guard_datetime.now(tz) + timedelta(days=2)
    monkeypatch.setattr(guard_store, "datetime", ExpiredEgressDatetime)
    with connect(SCOPE) as conn:
        with pytest.raises(NetworkApprovalConsumptionBlocked, match="CURRENT_BINDING_DRIFTED"):
            precheck_network_activation(conn, SCOPE, proposed.proposal.id, approval_id)
        conn.rollback()
    monkeypatch.undo()
    import aos_api.aip_network_policy_approval_consumer as consumer
    real_datetime = datetime
    class FutureDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime.now(tz) + timedelta(minutes=20)
    monkeypatch.setattr(consumer, "datetime", FutureDatetime)
    with connect(SCOPE) as conn:
        with pytest.raises(NetworkApprovalConsumptionBlocked, match="EXPIRED"):
            precheck_network_activation(conn, SCOPE, proposed.proposal.id, approval_id)
        conn.rollback()
    monkeypatch.undo()
    revoker = Principal(subject="bg00ca-revoker", org_id=SCOPE.org_id,
                        project_id=SCOPE.project_id, roles=["admin"], token_kind="oidc")
    rejection = DecideActionProposalRequest.model_validate({
        "expectedProposalVersion": approved.proposal.version,
        "expectedProposalHash": approved.proposal.proposal_hash,
        "decision": "rejected", "reason": "isolation revocation proof",
    })
    decide_network_activation(revoker, proposed.proposal.id, f"reject-{suffix}", rejection)
    with connect(SCOPE) as conn:
        with pytest.raises(NetworkApprovalConsumptionBlocked, match="PROPOSAL_NOT_APPROVED"):
            precheck_network_activation(conn, SCOPE, proposed.proposal.id, approval_id)
        conn.rollback()
    withdrawn_candidate = candidate.model_copy(update={"policy_id": f"bg00ca-withdraw-{suffix}"})
    withdrawn_proposal = propose_network_activation(
        maker, withdrawn_candidate, expected_version=0,
        idempotency_key=f"withdraw-propose-{suffix}", expires_at=expiry,
    )
    withdrawn_decision = decision.model_copy(update={
        "expected_proposal_version": withdrawn_proposal.proposal.version,
        "expected_proposal_hash": withdrawn_proposal.proposal.proposal_hash,
    })
    withdrawn_approved = decide_network_activation(
        checker, withdrawn_proposal.proposal.id, f"withdraw-approve-{suffix}", withdrawn_decision,
    )
    AipActionStore().withdraw(
        SCOPE, maker.subject, withdrawn_proposal.proposal.id, f"withdraw-{suffix}",
        WithdrawActionProposalRequest.model_validate({
            "expectedProposalVersion": withdrawn_approved.proposal.version,
            "expectedProposalHash": withdrawn_approved.proposal.proposal_hash,
            "reason": "isolated maker withdrawal",
        }),
    )
    with connect(SCOPE) as conn:
        with pytest.raises(NetworkApprovalConsumptionBlocked, match="PROPOSAL_NOT_APPROVED"):
            precheck_network_activation(conn, SCOPE, withdrawn_proposal.proposal.id,
                                        withdrawn_approved.approvals[0].id)
        conn.rollback()
    with connect(SCOPE) as conn:
        for table in ("aip_network_policy_head", "aip_network_policy_revision", "aip_network_policy_receipt"):
            assert conn.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"] == 0
