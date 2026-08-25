"""W5-07 canonical Action Kill and bounded Canary acceptance tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from aos_api.aip_action_adapters import ACTION_ADAPTERS, AdapterOutcome
from aos_api.aip_action_canary_models import (
    DecideCanaryPlanRequest,
    DecideKillPolicyRequest,
    EvaluateKillPolicyRequest,
    ProposeCanaryPlanRequest,
    ProposeKillPolicyRequest,
    SimulateKillDrillRequest,
)
from aos_api.aip_action_canary_service import (
    AipActionCanaryConflict,
    AipActionCanaryForbidden,
    AipActionCanaryService,
)
from aos_api.auth import Principal, require_principal
from aos_api.db import connect

from test_aip3b_action_execution import SCOPE, _create_approved, _headers, _lease

HASH = "a" * 64


def _principal(subject: str) -> Principal:
    return Principal(subject, SCOPE.org_id, SCOPE.project_id, ["aip_policy_admin"])


def _ref(resource_type: str, resource_id: str) -> dict:
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": 1,
        "contentHash": HASH,
    }


def _activate(
    service: AipActionCanaryService,
    *,
    policy_id: str,
    level: str = "action_type",
    action_type_id: str | None = None,
    account_ref: dict | None = None,
    reason: str = "W5_07_TEST_KILL",
) -> object:
    now = datetime.now(timezone.utc)
    proposed = service.propose_kill_policy(
        _principal("policy-maker"),
        f"propose-{uuid.uuid4().hex}",
        ProposeKillPolicyRequest(
            policyId=policy_id,
            expectedHeadVersion=0,
            level=level,
            killEnabled=True,
            reasonCode=reason,
            actionTypeId=action_type_id,
            accountBindingRef=account_ref,
            validFrom=now - timedelta(minutes=1),
            expiresAt=now + timedelta(hours=1),
        ),
    )
    return service.decide_kill_policy(
        _principal("policy-checker"),
        policy_id,
        proposed.revision,
        f"approve-{uuid.uuid4().hex}",
        DecideKillPolicyRequest(
            expectedHeadVersion=0,
            expectedContentHash=proposed.content_hash,
            decision="approved",
            reason="bounded test approval",
        ),
    )


def test_kill_policy_is_immutable_maker_checker_cas_and_idempotent() -> None:
    service = AipActionCanaryService()
    policy_id = f"kill-{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    request = ProposeKillPolicyRequest(
        policyId=policy_id,
        expectedHeadVersion=0,
        level="action_type",
        killEnabled=True,
        reasonCode="TEST_KILL",
        actionTypeId="aip.action.w5-07.test",
        validFrom=now,
        expiresAt=now + timedelta(hours=1),
    )
    first = service.propose_kill_policy(_principal("maker"), "same-proposal", request)
    replay = service.propose_kill_policy(_principal("maker"), "same-proposal", request)
    assert replay.content_hash == first.content_hash
    with pytest.raises(AipActionCanaryConflict):
        service.propose_kill_policy(
            _principal("maker"),
            "same-proposal",
            request.model_copy(update={"reason_code": "DRIFT"}),
        )
    decision = DecideKillPolicyRequest(
        expectedHeadVersion=0,
        expectedContentHash=first.content_hash,
        decision="approved",
        reason="maker checker",
    )
    with pytest.raises(AipActionCanaryForbidden):
        service.decide_kill_policy(_principal("maker"), policy_id, 1, "maker-decision", decision)
    approved = service.decide_kill_policy(
        _principal("checker"), policy_id, 1, "checker-decision", decision
    )
    assert approved.active is True
    assert approved.head_version == 1
    with connect(SCOPE) as conn:
        assert conn.execute(
            """SELECT COUNT(*) AS n FROM aip_action_kill_policy_revision
               WHERE org_id=%s AND project_id=%s AND policy_id=%s""",
            (*SCOPE.key, policy_id),
        ).fetchone()["n"] == 1


def test_effective_policy_is_exact_layered_and_expiry_fail_closed() -> None:
    service = AipActionCanaryService()
    account = _ref("AccountBindingRevision", f"account-{uuid.uuid4().hex}")
    _activate(
        service,
        policy_id=f"kill-{uuid.uuid4().hex}",
        level="account",
        account_ref=account,
        reason="ACCOUNT_STOP",
    )
    unrelated = service.evaluate(
        _principal("reader"),
        EvaluateKillPolicyRequest(
            actionTypeId="aip.action.other",
            accountBindingRef=_ref("AccountBindingRevision", "another-account"),
        ),
    )
    assert unrelated.blocked is False
    exact = service.evaluate(
        _principal("reader"),
        EvaluateKillPolicyRequest(actionTypeId="aip.action.other", accountBindingRef=account),
    )
    assert exact.blocked is True
    assert exact.reason_codes == ["ACCOUNT_STOP"]
    assert exact.policy_refs[0].resource_type == "KillPolicyRevision"

    expired_id = f"kill-expired-{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    expired = service.propose_kill_policy(
        _principal("expired-maker"),
        f"expired-propose-{uuid.uuid4().hex}",
        ProposeKillPolicyRequest(
            policyId=expired_id,
            expectedHeadVersion=0,
            level="action_type",
            killEnabled=True,
            reasonCode="EXPIRED_STOP",
            actionTypeId="expired.action",
            validFrom=now - timedelta(hours=2),
            expiresAt=now - timedelta(hours=1),
        ),
    )
    service.decide_kill_policy(
        _principal("expired-checker"),
        expired_id,
        1,
        f"expired-approve-{uuid.uuid4().hex}",
        DecideKillPolicyRequest(
            expectedHeadVersion=0,
            expectedContentHash=expired.content_hash,
            decision="approved",
            reason="expired test authority",
        ),
    )
    assert service.evaluate(
        _principal("reader"), EvaluateKillPolicyRequest(actionTypeId="expired.action")
    ).blocked is False


def test_reset_is_a_new_approved_revision_and_never_mutates_prior_fact() -> None:
    service = AipActionCanaryService()
    action_id = f"reset-action-{uuid.uuid4().hex}"
    policy_id = f"kill-reset-{uuid.uuid4().hex}"
    active = _activate(service, policy_id=policy_id, action_type_id=action_id)
    now = datetime.now(timezone.utc)
    reset = service.propose_kill_policy(
        _principal("reset-maker"),
        f"reset-propose-{uuid.uuid4().hex}",
        ProposeKillPolicyRequest(
            policyId=policy_id,
            expectedHeadVersion=1,
            level="action_type",
            killEnabled=False,
            reasonCode="CONTROLLED_RESET",
            actionTypeId=action_id,
            validFrom=now,
        ),
    )
    assert reset.revision == 2
    cleared = service.decide_kill_policy(
        _principal("reset-checker"),
        policy_id,
        2,
        f"reset-approve-{uuid.uuid4().hex}",
        DecideKillPolicyRequest(
            expectedHeadVersion=1,
            expectedContentHash=reset.content_hash,
            decision="approved",
            reason="controlled reset",
        ),
    )
    assert cleared.active is True
    assert cleared.kill_enabled is False
    assert service.evaluate(
        _principal("reader"), EvaluateKillPolicyRequest(actionTypeId=action_id)
    ).blocked is False
    with connect(SCOPE) as conn:
        rows = conn.execute(
            """SELECT revision,kill_enabled FROM aip_action_kill_policy_revision
               WHERE org_id=%s AND project_id=%s AND policy_id=%s ORDER BY revision""",
            (*SCOPE.key, policy_id),
        ).fetchall()
    assert [(row["revision"], row["kill_enabled"]) for row in rows] == [(1, True), (2, False)]
    assert active.content_hash != cleared.content_hash


class _NeverCalledAdapter:
    calls = 0

    def execute(self, *, payload, idempotency_key):
        self.calls += 1
        return AdapterOutcome("applied", "must-not-run", {})

    def reconcile(self, *, provider_request_id, request_fingerprint):
        raise AssertionError("reconcile must not run")


class _AcceptedAdapter:
    calls = 0

    def execute(self, *, payload, idempotency_key):
        self.calls += 1
        return AdapterOutcome("accepted", f"provider-{idempotency_key[-12:]}", {"queued": True})

    def reconcile(self, *, provider_request_id, request_fingerprint):
        raise AssertionError("simulation must not reconcile provider")


def test_active_kill_blocks_before_attempt_outbox_provider_or_usage(client) -> None:
    action_id = f"w5_07_killed_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    lease = _lease(client, proposal)["lease"]
    service = AipActionCanaryService()
    _activate(service, policy_id=f"kill-{uuid.uuid4().hex}", action_type_id=action_id)
    adapter = _NeverCalledAdapter()
    ACTION_ADAPTERS.register(action_id, adapter)
    try:
        with connect(SCOPE) as conn:
            outbox_before = conn.execute(
                "SELECT COUNT(*) AS n FROM aip_action_dispatch_outbox WHERE org_id=%s AND project_id=%s",
                SCOPE.key,
            ).fetchone()["n"]
        response = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers=_headers(f"execute-{uuid.uuid4().hex}"),
            json={"expectedProposalHash": proposal["proposalHash"]},
        )
        assert response.status_code == 422, response.text
        assert "canonical Action kill policy" in response.text
        assert adapter.calls == 0
        with connect(SCOPE) as conn:
            assert conn.execute(
                """SELECT COUNT(*) AS n FROM aip_action_execution_attempt
                   WHERE org_id=%s AND project_id=%s AND lease_id=%s""",
                (*SCOPE.key, lease["id"]),
            ).fetchone()["n"] == 0
            assert conn.execute(
                "SELECT COUNT(*) AS n FROM aip_action_dispatch_outbox WHERE org_id=%s AND project_id=%s",
                SCOPE.key,
            ).fetchone()["n"] == outbox_before
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_canary_plan_is_bounded_maker_checker_and_has_no_execute_route(client) -> None:
    service = AipActionCanaryService()
    plan_id = f"canary-{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    proposed = service.propose_canary_plan(
        _principal("canary-maker"),
        f"canary-propose-{uuid.uuid4().hex}",
        ProposeCanaryPlanRequest(
            planId=plan_id,
            actionTypeRevisionRef=_ref("ActionTypeRevision", "action"),
            capabilityBindingRef=_ref("CapabilityBindingRevision", "capability"),
            accountBindingRef=_ref("AccountBindingRevision", "account"),
            adapterRevisionRef=_ref("AdapterCapabilityRevision", "adapter"),
            objectRef={"resourceType": "Order", "resourceId": "synthetic-1", "authority": "test"},
            maxQuantity=3,
            maxBudget="10.00",
            currency="cny",
            windowStartsAt=now,
            windowEndsAt=now + timedelta(minutes=20),
            operatorId="operator-1",
            stopConditions=["ANY_UNKNOWN", "BUDGET_EXCEEDED"],
        ),
    )
    assert proposed.status == "awaiting_approval"
    assert proposed.currency == "CNY"
    with pytest.raises(AipActionCanaryForbidden):
        service.decide_canary_plan(
            _principal("canary-maker"), plan_id, 1, "maker-canary-decision",
            DecideCanaryPlanRequest(
                expectedContentHash=proposed.content_hash,
                decision="approved",
                reason="not allowed",
            ),
        )
    approved = service.decide_canary_plan(
        _principal("canary-checker"), plan_id, 1, "checker-canary-decision",
        DecideCanaryPlanRequest(
            expectedContentHash=proposed.content_hash,
            decision="approved",
            reason="bounded plan only",
        ),
    )
    assert approved.status == "approved"
    response = client.post(
        f"/v1/aip/action-canary-plans/{plan_id}/revisions/1/execute",
        headers=_headers(f"execute-canary-{uuid.uuid4().hex}"),
        json={},
    )
    assert response.status_code == 404


def test_kill_drill_is_simulation_only_idempotent_and_zero_side_effect() -> None:
    service = AipActionCanaryService()
    active = _activate(
        service,
        policy_id=f"kill-{uuid.uuid4().hex}",
        action_type_id=f"action-{uuid.uuid4().hex}",
    )
    request = SimulateKillDrillRequest(
        policyRef={
            "resourceType": "KillPolicyRevision",
            "resourceId": active.policy_id,
            "revision": active.revision,
            "contentHash": active.content_hash,
        },
        syntheticNewDispatchIds=["synthetic-dispatch-1", "synthetic-dispatch-2"],
        inflightAttemptIds=[],
    )
    first = service.simulate_kill_drill(_principal("drill-operator"), "same-drill", request)
    replay = service.simulate_kill_drill(_principal("drill-operator"), "same-drill", request)
    assert replay.receipt_id == first.receipt_id
    assert first.simulation_only is True
    assert first.result == "passed"
    assert first.invariants == {
        "newDispatchAttemptRowsCreated": False,
        "inflightClaimedCancelled": False,
        "reconcileRequiredCount": 0,
        "externalProviderCalled": False,
        "reservationOrUsageMutated": False,
    }


def test_kill_drill_marks_existing_inflight_for_reconcile_without_cancelling(client) -> None:
    action_id = f"w5_07_inflight_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    lease = _lease(client, proposal)["lease"]
    adapter = _AcceptedAdapter()
    ACTION_ADAPTERS.register(action_id, adapter)
    try:
        executed = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers=_headers(f"execute-{uuid.uuid4().hex}"),
            json={"expectedProposalHash": proposal["proposalHash"]},
        )
        assert executed.status_code == 200, executed.text
        attempt_id = executed.json()["attempt"]["id"]
        assert executed.json()["attempt"]["status"] == "accepted"
        service = AipActionCanaryService()
        active = _activate(
            service,
            policy_id=f"kill-{uuid.uuid4().hex}",
            action_type_id=action_id,
        )
        receipt = service.simulate_kill_drill(
            _principal("drill-operator"),
            f"drill-{uuid.uuid4().hex}",
            SimulateKillDrillRequest(
                policyRef={
                    "resourceType": "KillPolicyRevision",
                    "resourceId": active.policy_id,
                    "revision": active.revision,
                    "contentHash": active.content_hash,
                },
                syntheticNewDispatchIds=["synthetic-new"],
                inflightAttemptIds=[attempt_id],
            ),
        )
        assert receipt.inflight_reconcile_attempts == [attempt_id]
        assert receipt.invariants["inflightClaimedCancelled"] is False
        assert receipt.invariants["reconcileRequiredCount"] == 1
        assert adapter.calls == 1
        with connect(SCOPE) as conn:
            assert conn.execute(
                """SELECT status FROM aip_action_execution_attempt
                   WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                (*SCOPE.key, attempt_id),
            ).fetchone()["status"] == "accepted"
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_router_exposes_policy_control_without_side_effect(client) -> None:
    suffix = uuid.uuid4().hex
    response = client.post(
        "/v1/aip/action-kill-policies",
        headers={**_headers(f"route-{suffix}"), "Idempotency-Key": f"route-{suffix}"},
        json={
            "policyId": f"route-policy-{suffix}",
            "expectedHeadVersion": 0,
            "level": "project",
            "killEnabled": True,
            "reasonCode": "ROUTE_TEST",
            "validFrom": datetime.now(timezone.utc).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["active"] is False
