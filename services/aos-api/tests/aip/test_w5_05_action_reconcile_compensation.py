"""W5-05 typed reconciliation, manual authority and exact compensation policy tests."""
from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from aos_api.aip_action_adapters import ACTION_ADAPTERS, AdapterOutcome
from aos_api.auth import require_principal
from aos_api.db import connect

from test_aip3b_action_execution import (
    SCOPE,
    _create_approved,
    _headers,
    _lease,
    _principal,
)


class UnknownThenFailedAdapter:
    def __init__(self) -> None:
        self.reconcile_calls = 0

    def execute(self, *, payload, idempotency_key):
        error = TimeoutError("response lost")
        error.provider_request_id = f"provider-{idempotency_key[-12:]}"
        raise error

    def reconcile(self, *, provider_request_id, request_fingerprint):
        self.reconcile_calls += 1
        return AdapterOutcome("failed", provider_request_id, {"confirmed": "not_applied"})


class AcceptedThenAppliedAdapter:
    def __init__(self) -> None:
        self.reconcile_calls = 0

    def execute(self, *, payload, idempotency_key):
        return AdapterOutcome("accepted", f"provider-{idempotency_key[-12:]}", {"queued": True})

    def reconcile(self, *, provider_request_id, request_fingerprint):
        self.reconcile_calls += 1
        return AdapterOutcome("applied", provider_request_id, {"confirmed": True})


class UnknownWithoutProviderRefAdapter:
    def execute(self, *, payload, idempotency_key):
        raise TimeoutError("no stable provider reference")

    def reconcile(self, *, provider_request_id, request_fingerprint):
        raise AssertionError("manual-only unknown must not query provider")


class AppliedAdapter:
    def execute(self, *, payload, idempotency_key):
        return AdapterOutcome("applied", f"provider-{idempotency_key[-12:]}", {"appliedEffect": {"quantity": 1}})

    def reconcile(self, *, provider_request_id, request_fingerprint):
        return AdapterOutcome("applied", provider_request_id, {"confirmed": True})


def _execute(client, proposal: dict, adapter) -> dict:
    ACTION_ADAPTERS.register(proposal["actionType"]["actionTypeId"], adapter)
    lease = _lease(client, proposal)["lease"]
    response = client.post(
        f"/v1/aip/action-leases/{lease['id']}/execute",
        headers=_headers(f"execute-{uuid.uuid4().hex}"),
        json={"expectedProposalHash": proposal["proposalHash"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_reconciled_failed_is_typed_and_never_compensable(client) -> None:
    action_id = f"w5_05_failed_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    adapter = UnknownThenFailedAdapter()
    try:
        executed = _execute(client, proposal, adapter)
        initial = executed["receipts"][0]
        assert initial["providerOutcome"] == "unknown"
        assert initial["reconciliationStatus"] == "pending"
        response = client.post(
            f"/v1/aip/action-receipts/{initial['id']}/reconcile",
            headers=_headers(f"reconcile-{uuid.uuid4().hex}"),
            json={"reason": "verify final outcome"},
        )
        assert response.status_code == 200, response.text
        resolved = response.json()["receipts"][1]
        assert resolved["status"] == "reconciled"
        assert resolved["providerOutcome"] == "failed"
        assert resolved["reconciliationStatus"] == "automatic"
        assert resolved["resolutionQuality"] == "confirmed"
        compensation = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/compensation",
            headers=_headers(f"compensate-{uuid.uuid4().hex}"),
            json={
                "receiptId": resolved["id"],
                "purpose": "must stay blocked",
                "actionTypeId": action_id,
            },
        )
        assert compensation.status_code == 422
        assert adapter.reconcile_calls == 1
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_accepted_reconcile_is_claimed_once_under_concurrent_replay(client) -> None:
    action_id = f"w5_05_accepted_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    adapter = AcceptedThenAppliedAdapter()
    try:
        initial = _execute(client, proposal, adapter)["receipts"][0]
        headers = _headers(f"reconcile-{uuid.uuid4().hex}")
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(
                pool.map(
                    lambda _index: client.post(
                        f"/v1/aip/action-receipts/{initial['id']}/reconcile",
                        headers=headers,
                        json={"reason": "accepted polling"},
                    ),
                    range(2),
                )
            )
        assert [item.status_code for item in responses] == [200, 200]
        assert adapter.reconcile_calls == 1
        assert responses[0].json()["receipts"][-1]["providerOutcome"] == "applied"
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_missing_provider_ref_creates_manual_case_and_enforces_maker_checker(client) -> None:
    action_id = f"w5_05_manual_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    try:
        initial = _execute(client, proposal, UnknownWithoutProviderRefAdapter())["receipts"][0]
        response = client.post(
            f"/v1/aip/action-receipts/{initial['id']}/reconcile",
            headers=_headers(f"reconcile-{uuid.uuid4().hex}"),
            json={"reason": "missing provider ref"},
        )
        assert response.status_code == 200, response.text
        case = response.json()["manualReconcileCase"]
        assert response.json()["reconcileAttempt"]["status"] == "manual_required"
        assert case["status"] == "open"
        same_actor = client.post(
            f"/v1/aip/action-manual-reconcile-cases/{case['id']}/decisions",
            headers=_headers(f"decision-{uuid.uuid4().hex}"),
            json={"expectedVersion": 1, "decision": "confirmed_applied", "evidenceRefs": []},
        )
        assert same_actor.status_code == 422
        client.app.dependency_overrides[require_principal] = lambda: _principal("checker-b", "aip_executor")
        unresolved = client.post(
            f"/v1/aip/action-manual-reconcile-cases/{case['id']}/decisions",
            headers=_headers(f"decision-{uuid.uuid4().hex}"),
            json={"expectedVersion": 1, "decision": "unresolved", "evidenceRefs": []},
        )
        assert unresolved.status_code == 200, unresolved.text
        assert unresolved.json()["manualReconcileCase"]["status"] == "unresolved"
        resolved = client.post(
            f"/v1/aip/action-manual-reconcile-cases/{case['id']}/decisions",
            headers=_headers(f"decision-{uuid.uuid4().hex}"),
            json={
                "expectedVersion": 2,
                "decision": "confirmed_applied",
                "evidenceRefs": [{
                    "resourceType": "Evidence",
                    "resourceId": "provider-console-readback",
                    "revision": "1",
                    "authority": "aip_evidence",
                }],
                "appliedEffect": {"quantity": 1},
                "residualEffect": {"quantity": 1},
            },
        )
        assert resolved.status_code == 200, resolved.text
        receipt = resolved.json()["receipts"][-1]
        assert receipt["providerOutcome"] == "applied"
        assert receipt["reconciliationStatus"] == "manual"
        assert receipt["manualDecisionReceiptId"].startswith("manual-decision-")
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_exact_policy_generates_compensation_payload_and_duplicate_is_idempotent(client) -> None:
    action_id = f"w5_05_original_{uuid.uuid4().hex}"
    compensation_id = f"w5_05_reverse_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    try:
        applied = _execute(client, proposal, AppliedAdapter())["receipts"][0]
        policy_id = f"policy-{uuid.uuid4().hex}"
        policy_hash = uuid.uuid4().hex + uuid.uuid4().hex
        with connect(SCOPE) as conn:
            conn.execute(
                """INSERT INTO meta_action_type
                   (id,name,object_type,parameters,required_markings,submission_criteria)
                   VALUES (%s,'受控逆操作','WorkOrder','[]'::jsonb,'[]'::jsonb,'[]'::jsonb)""",
                (compensation_id,),
            )
            conn.execute(
                """INSERT INTO aip_action_compensation_policy_revision
                   (org_id,project_id,policy_id,revision,content_hash,lifecycle,
                    original_action_type_id,allowed_outcomes,compensation_action_type_id,
                    payload_template,effect_scope_schema,maximum_effect,risk_floor,valid_from,expires_at)
                   VALUES (%s,%s,%s,1,%s,'published',%s,'["applied","partial"]'::jsonb,
                           %s,'{"policyGenerated":true}'::jsonb,'{"allowedKeys":["quantity"]}'::jsonb,
                           '{"quantity":1}'::jsonb,'R1',NOW(),NOW()+INTERVAL '1 hour')""",
                (*SCOPE.key, policy_id, policy_hash, action_id, compensation_id),
            )
            conn.commit()
        request = {
            "receiptId": applied["id"],
            "purpose": "policy generated inverse action",
            "policyRevisionRef": {
                "resourceType": "CompensationPolicyRevision",
                "resourceId": policy_id,
                "revision": 1,
                "contentHash": policy_hash,
            },
            "effectDelta": {"quantity": 1},
        }
        excessive = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/compensation",
            headers=_headers(f"compensation-excess-{uuid.uuid4().hex}"),
            json={**request, "effectDelta": {"quantity": 2}},
        )
        assert excessive.status_code == 422
        first = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/compensation",
            headers=_headers(f"compensation-{uuid.uuid4().hex}"),
            json=request,
        )
        assert first.status_code == 201, first.text
        generated = first.json()["proposal"]
        assert generated["actionType"]["actionTypeId"] == compensation_id
        assert generated["payload"]["policyGenerated"] is True
        assert generated["payload"]["originalReceiptId"] == applied["id"]
        assert generated["compensationOriginalReceiptId"] == applied["id"]
        assert generated["compensationEffect"] == {"quantity": 1}
        assert generated["compensationResidualEffect"] == {"quantity": 1}
        second = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/compensation",
            headers=_headers(f"compensation-replay-{uuid.uuid4().hex}"),
            json=request,
        )
        assert second.status_code == 201
        assert second.json()["proposal"]["id"] == generated["id"]
        caller_override = client.post(
            f"/v1/aip/action-proposals/{proposal['id']}/compensation",
            headers=_headers(f"compensation-override-{uuid.uuid4().hex}"),
            json={**request, "actionTypeId": compensation_id, "payload": {"free": "form"}},
        )
        assert caller_override.status_code == 422
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)
