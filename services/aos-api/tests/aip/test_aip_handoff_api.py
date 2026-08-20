"""HTTP surface tests for Canonical Handoff issue → get → consume (W-L3)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from aos_api.aip_agent_registry_contracts import (
    HandoffEnvelope,
    HandoffEnvelopeRequest,
    IssuedHandoff,
    RegistryReceipt,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound, AipAgentRegistryTransitionBlocked
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.routers import aip_handoffs

NOW = datetime(2026, 8, 20, 3, tzinfo=UTC)
HASH = "a" * 64


def headers(org_id: str = "org-org", **extra: str) -> dict[str, str]:
    return {"Authorization": "Bearer dev", "X-Org-Id": org_id, "X-Project-Id": "dev-project", **extra}


def asset(kind: str, value: str) -> VersionedAssetRef:
    return VersionedAssetRef(assetType=kind, assetId=value, revision=1, contentHash=HASH)


def envelope(org_id: str = "org-org") -> HandoffEnvelope:
    return HandoffEnvelope(
        tenant=TenantContext(orgId=org_id, projectId="dev-project"),
        handoffId="handoff-1",
        envelope=HandoffEnvelopeRequest(
            taskRef=ResourceRef(resourceType="Task", resourceId="task-1", revision="1", authority="postgresql"),
            runRef=ResourceRef(resourceType="TaskRun", resourceId="run-1", revision="1", authority="postgresql"),
            senderInstance=asset("AgentInstance", "sender-1"),
            receiverInstance=asset("AgentInstance", "receiver-1"),
            objectRefs=[],
            artifactRefs=[],
            evidenceRefs=[],
            context={"intent": "demo"},
            allowedContextFields=["intent"],
            markings=["internal"],
            expiresAt=NOW + timedelta(minutes=10),
        ),
        status="issued",
        version=1,
        createdAt=NOW,
    )


def receipt(org_id: str = "org-org") -> RegistryReceipt:
    return RegistryReceipt(
        tenant=TenantContext(orgId=org_id, projectId="dev-project"),
        receiptId="receipt-1",
        operation="handoff.issue",
        idempotencyKey="idem-1",
        requestHash="b" * 64,
        resourceRef=ResourceRef(resourceType="TaskRun", resourceId="run-1", authority="postgresql"),
        resultRef=ResourceRef(resourceType="HandoffEnvelope", resourceId="handoff-1", authority="postgresql"),
        status="applied",
        createdBy="user:dev",
        createdAt=NOW,
    )


class HandoffService:
    def __init__(self) -> None:
        self.scope = None
        self.issued_once = False
        self.consumed = False
        self.last_bearer: str | None = None

    def issue(self, scope, request, *, idempotency_key, actor, occurred_at):
        self.scope = scope
        if self.issued_once:
            return IssuedHandoff(handoff=envelope(scope.org_id), bearerToken=None, receipt=receipt(scope.org_id))
        self.issued_once = True
        self.last_bearer = "b" * 40
        return IssuedHandoff(
            handoff=envelope(scope.org_id),
            bearerToken=self.last_bearer,
            receipt=receipt(scope.org_id),
        )

    def get(self, scope, handoff_id):
        self.scope = scope
        if scope.org_id == "dev-org":
            raise AipAgentRegistryNotFound("handoff not found")
        return envelope(scope.org_id)

    def consume(self, scope, handoff_id, *, bearer_token, receiver_instance, actor, occurred_at):
        self.scope = scope
        if self.consumed:
            raise AipAgentRegistryTransitionBlocked("handoff is no longer consumable")
        if bearer_token != self.last_bearer and bearer_token != "b" * 40:
            raise AipAgentRegistryNotFound("handoff token is invalid")
        self.consumed = True
        item = envelope(scope.org_id)
        return item.model_copy(update={"status": "consumed", "version": 2, "consumedAt": occurred_at})


def test_openapi_registers_handoff_consume_surface(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/v1/aip/handoffs" in paths
    assert "/v1/aip/handoffs/{handoff_id}" in paths
    assert "/v1/aip/handoffs/{handoff_id}/consume" in paths
    assert "/v1/aip/handoffs/{handoff_id}/decisions" in paths
    assert "/v1/aip/handoffs/{handoff_id}/decisions/{decision_id}" in paths


def test_issue_replay_hides_bearer_and_consume_is_one_shot(client) -> None:
    service = HandoffService()
    client.app.dependency_overrides[aip_handoffs.get_handoff_service] = lambda: service
    body = {
        "handoffId": "handoff-1",
        "envelope": envelope().envelope.model_dump(mode="json", by_alias=True),
    }
    try:
        first = client.post("/v1/aip/handoffs", headers=headers(**{"Idempotency-Key": "idem-1"}), json=body)
        assert first.status_code == 201
        assert first.json()["bearerToken"] and first.json()["handoff"]["status"] == "issued"
        replay = client.post("/v1/aip/handoffs", headers=headers(**{"Idempotency-Key": "idem-1"}), json=body)
        assert replay.status_code == 201
        assert replay.json()["bearerToken"] is None
        got = client.get("/v1/aip/handoffs/handoff-1", headers=headers())
        assert got.status_code == 200 and got.json()["handoffId"] == "handoff-1"
        assert service.scope.key == ("org-org", "dev-project")
        canary = client.get("/v1/aip/handoffs/handoff-1", headers=headers("dev-org"))
        assert canary.status_code == 404
        consume_body = {
            "bearerToken": first.json()["bearerToken"],
            "receiverInstance": asset("AgentInstance", "receiver-1").model_dump(mode="json", by_alias=True),
        }
        ok = client.post("/v1/aip/handoffs/handoff-1/consume", headers=headers(), json=consume_body)
        assert ok.status_code == 200 and ok.json()["status"] == "consumed"
        again = client.post("/v1/aip/handoffs/handoff-1/consume", headers=headers(), json=consume_body)
        assert again.status_code == 422
    finally:
        client.app.dependency_overrides.pop(aip_handoffs.get_handoff_service, None)


def test_issue_requires_idempotency_header(client) -> None:
    response = client.post("/v1/aip/handoffs", headers=headers(), json={})
    assert response.status_code == 400
