"""W5-04 durable execution intent and exact delivery bridge acceptance."""
from __future__ import annotations

import uuid

from aos_api.aip_action_adapters import ACTION_ADAPTERS, ActionAdapterRegistry, AdapterOutcome
from aos_api.aip_action_execution import AipActionExecutionService
from aos_api.aip_action_store import AipActionStore
from aos_api.aip_adapter_conformance import run_adapter_conformance
from aos_api.aip_eval_contracts import LineageRootType
from aos_api.aip_lineage_service import AipLineageService
from aos_api.auth import require_principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

from test_aip3b_action_execution import SCOPE, _create_approved, _lease, _principal
from test_w5_01_adapter_capability_contracts import (
    DeterministicAdapter,
    fixture as adapter_fixture,
    revision as adapter_revision,
)


class SensitiveAppliedAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, *, payload, idempotency_key):
        self.calls += 1
        return AdapterOutcome(
            "applied",
            f"provider-{idempotency_key[:12]}",
            {"result": payload, "token": "must-not-persist"},
        )

    def reconcile(self, *, provider_request_id, request_fingerprint):
        return AdapterOutcome("applied", provider_request_id, {"verified": True})


def test_exact_conformant_adapter_freezes_output_usage_and_redaction_schemas() -> None:
    item = adapter_revision(action_type_family="w5.04.demo")
    adapter = DeterministicAdapter(item)
    report = run_adapter_conformance(item, adapter, adapter_fixture(item))
    registry = ActionAdapterRegistry()
    registry.register_conformant(item, adapter, report)
    service = AipActionExecutionService(AipActionStore(), registry)
    resolved, binding = service._resolve_adapter(
        {"action_type_id": "w5.04.demo"},
        {
            "adapterRevisionRef": item.exact_ref().model_dump(
                mode="json", by_alias=True
            )
        },
    )
    assert resolved is adapter
    assert binding["outputSchemaRef"] == item.output_schema_ref.model_dump(
        mode="json", by_alias=True
    )
    assert binding["receiptSchemaRef"]["resourceType"] == "ReceiptSchemaRevision"
    assert binding["usageSchemaRef"]["resourceType"] == "UsageSchemaRevision"
    assert binding["redactionPolicyRef"]["resourceType"] == "RedactionPolicyRevision"


def test_execution_persists_intent_before_dispatch_and_bridges_exact_facts(client) -> None:
    action_id = f"w5_04_delivery_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    adapter = SensitiveAppliedAdapter()
    ACTION_ADAPTERS.register(action_id, adapter)
    try:
        lease = _lease(client, proposal)["lease"]
        response = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers={
                "Authorization": "Bearer dev",
                "X-Org-Id": SCOPE.org_id,
                "X-Project-Id": SCOPE.project_id,
                "Idempotency-Key": f"execute-{uuid.uuid4().hex}",
            },
            json={"expectedProposalHash": proposal["proposalHash"]},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["attempt"]["status"] == "applied"
        assert body["attempt"]["providerOutcome"] == "applied"
        assert body["attempt"]["usageSettlementStatus"] == "not_required"
        assert body["attempt"]["lineageProjectionStatus"] == "pending"
        receipt = body["receipts"][0]
        assert receipt["attemptId"] == body["attempt"]["id"]
        assert receipt["approvalSetHash"] == lease["approvalSetHash"]
        assert receipt["payload"]["token"] == "[REDACTED]"
        assert len(receipt["responseHash"]) == 64
        assert len(receipt["receiptContentHash"]) == 64
        assert receipt["usageReceiptRefs"][0]["resourceType"] == "UsageReceipt"
        with connect(SCOPE) as conn:
            attempt = conn.execute(
                "SELECT status,request_hash FROM aip_action_execution_attempt WHERE org_id=%s AND project_id=%s AND attempt_id=%s",
                (*SCOPE.key, body["attempt"]["id"]),
            ).fetchone()
            outbox = conn.execute(
                "SELECT status FROM aip_action_dispatch_outbox WHERE org_id=%s AND project_id=%s AND attempt_id=%s",
                (*SCOPE.key, body["attempt"]["id"]),
            ).fetchone()
            usage = conn.execute(
                "SELECT quantity,quality FROM aip_usage_receipt WHERE org_id=%s AND project_id=%s AND receipt_id=%s",
                (*SCOPE.key, receipt["usageReceiptRefs"][0]["resourceId"]),
            ).fetchone()
            assert attempt["status"] == "applied"
            assert attempt["request_hash"] == receipt["requestFingerprint"]
            assert outbox["status"] == "delivered"
            assert usage["quality"] == "unknown"
            assert usage["quantity"] is None
        with connect(TenantScope("dev-org", "dev-project")) as conn:
            assert conn.execute(
                "SELECT 1 FROM aip_action_execution_attempt WHERE attempt_id=%s",
                (body["attempt"]["id"],),
            ).fetchone() is None
        replay = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers={
                "Authorization": "Bearer dev",
                "X-Org-Id": SCOPE.org_id,
                "X-Project-Id": SCOPE.project_id,
                "Idempotency-Key": f"execute-replay-{uuid.uuid4().hex}",
            },
            json={"expectedProposalHash": proposal["proposalHash"]},
        )
        assert replay.status_code == 200
        assert adapter.calls == 1
        assert len(replay.json()["receipts"]) == 1
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_claimed_without_receipt_becomes_unknown_without_second_provider_call(client) -> None:
    action_id = f"w5_04_crash_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    adapter = SensitiveAppliedAdapter()
    ACTION_ADAPTERS.register(action_id, adapter)
    try:
        lease = _lease(client, proposal)["lease"]
        service = AipActionExecutionService(AipActionStore(), ACTION_ADAPTERS)
        principal = _principal("executor-a", "aip_executor")
        _proposal, _lease_row, attempt, _adapter = service._prepare_execution(
            principal, SCOPE, lease["id"], proposal["proposalHash"]
        )
        assert service._claim_dispatch(SCOPE, attempt["attempt_id"]) is True
        in_flight = service.execute(
            principal, lease["id"], proposal["proposalHash"]
        )
        assert in_flight.attempt is not None
        assert in_flight.attempt.status == "dispatch_claimed"
        assert in_flight.receipts == []
        assert adapter.calls == 0
        with connect(SCOPE) as conn:
            conn.execute(
                """UPDATE aip_action_execution_attempt
                   SET claimed_at=NOW()-INTERVAL '31 seconds'
                   WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                (*SCOPE.key, attempt["attempt_id"]),
            )
            conn.commit()

        view = service.execute(principal, lease["id"], proposal["proposalHash"])
        assert adapter.calls == 0
        assert view.attempt is not None and view.attempt.status == "unknown"
        assert view.receipts[0].status.value == "unknown"
        assert view.receipts[0].provider_request_id is None
        assert view.receipts[0].payload["errorType"] == "DISPATCH_STATE_AMBIGUOUS"
        with connect(SCOPE) as conn:
            assert conn.execute(
                "SELECT status FROM aip_action_dispatch_outbox WHERE org_id=%s AND project_id=%s AND attempt_id=%s",
                (*SCOPE.key, attempt["attempt_id"]),
            ).fetchone()["status"] == "unknown"
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)


def test_action_lineage_hash_covers_controlled_receipt_and_is_idempotent(client) -> None:
    action_id = f"w5_04_lineage_{uuid.uuid4().hex}"
    proposal = _create_approved(client, action_id)
    ACTION_ADAPTERS.register(action_id, SensitiveAppliedAdapter())
    try:
        lease = _lease(client, proposal)["lease"]
        service = AipActionExecutionService(AipActionStore(), ACTION_ADAPTERS)
        view = service.execute(
            _principal("executor-a", "aip_executor"), lease["id"], proposal["proposalHash"]
        )
        receipt_id = view.receipts[0].id
        lineage = AipLineageService()
        first = lineage.reconcile(SCOPE, LineageRootType.ACTION, proposal["id"])
        second = lineage.reconcile(SCOPE, LineageRootType.ACTION, proposal["id"])
        receipt_events = [event for event in first if event.source_id == receipt_id]
        assert len(receipt_events) == 1
        assert receipt_events[0].artifact is not None
        assert receipt_events[0].source_hash == receipt_events[0].artifact.content_hash
        assert [(event.event_id, event.source_hash) for event in first] == [
            (event.event_id, event.source_hash) for event in second
        ]
    finally:
        ACTION_ADAPTERS.unregister(action_id)
        client.app.dependency_overrides.pop(require_principal, None)
