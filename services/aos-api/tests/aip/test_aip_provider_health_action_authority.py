"""BI-W10 Provider Health Action authority bridge acceptance."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import uuid

import pytest

from aos_api.aip_action_adapters import ACTION_ADAPTERS, ActionAdapterRegistry
from aos_api.aip_action_execution import (
    AipActionDependencyUnavailable,
    AipActionExecutionService,
)
from aos_api.aip_action_store import AipActionStore
from aos_api.aip_provider_health_action import (
    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
    ProviderHealthProbeActionAdapter,
)
from aos_api.aip_provider_health_action_authority import (
    PROVIDER_HEALTH_ACTION_PURPOSE,
    provider_health_action_type_snapshot,
    provider_health_adapter_revision,
    register_provider_health_action_adapter,
)
from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")


def _principal(subject: str, role: str) -> Principal:
    return Principal(
        subject=subject,
        org_id=SCOPE.org_id,
        project_id=SCOPE.project_id,
        roles=[role],
        markings=["public", "restricted"],
    )


def _headers(key: str, *, scope: TenantScope = SCOPE) -> dict[str, str]:
    return {
        "Authorization": "Bearer dev",
        "X-Org-Id": scope.org_id,
        "X-Project-Id": scope.project_id,
        "Idempotency-Key": key,
    }


def _seed_action_type() -> dict:
    snapshot = provider_health_action_type_snapshot()
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO meta_action_type
               (id,name,object_type,parameters,required_markings,submission_criteria)
               VALUES (%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)
               ON CONFLICT (id) DO UPDATE SET
                 name=EXCLUDED.name,
                 object_type=EXCLUDED.object_type,
                 parameters=EXCLUDED.parameters,
                 required_markings=EXCLUDED.required_markings,
                 submission_criteria=EXCLUDED.submission_criteria""",
            (
                snapshot["id"],
                snapshot["name"],
                snapshot["objectType"],
                json.dumps(snapshot["parameters"]),
                json.dumps(snapshot["requiredMarkings"]),
                json.dumps(snapshot["submissionCriteria"]),
            ),
        )
        conn.commit()
    return snapshot


class FakeRefresh:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> dict:
        self.calls += 1
        return {
            "status": "PROVIDER_HEALTH_REFRESH_GREEN",
            "observationId": "provider-health-observation-test",
            "expiresAt": "2099-01-01T00:00:00Z",
            "providerCalls": 3,
            "secretPayloadReadsReported": 0,
            "promptOrAnswerBodiesReported": 0,
        }


def test_code_backed_action_and_adapter_revisions_are_deterministic() -> None:
    action = provider_health_action_type_snapshot()
    assert action == provider_health_action_type_snapshot()
    assert len(action["revisionHash"]) == 64
    assert action["id"] == PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
    revision = provider_health_adapter_revision()
    assert revision == provider_health_adapter_revision()
    assert revision.content_hash == revision.expected_content_hash()
    assert revision.action_type_family == action["id"]
    assert ACTION_ADAPTERS.get(action["id"]) is None


def test_explicit_registration_is_exact_and_does_not_call_runtime_refresh() -> None:
    registry = ActionAdapterRegistry()
    refresh = FakeRefresh()
    adapter, revision, report = register_provider_health_action_adapter(
        registry, refresh
    )
    assert report.green is True
    assert refresh.calls == 0
    assert registry.get(PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID) is adapter
    assert registry.get_conformant(revision.exact_ref()) == (revision, adapter)


def test_unconformant_exact_alias_fails_closed() -> None:
    registry = ActionAdapterRegistry()
    adapter = ProviderHealthProbeActionAdapter(FakeRefresh())
    adapter.adapter_revision_ref = provider_health_adapter_revision().exact_ref()
    registry.register(PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID, adapter)
    service = AipActionExecutionService(AipActionStore(), registry)
    with pytest.raises(
        AipActionDependencyUnavailable,
        match="exact revision is not conformant",
    ):
        service._resolve_adapter(
            {"action_type_id": PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID}, {}
        )


def test_full_authority_chain_is_exact_single_attempt_and_tenant_safe(client) -> None:
    action = _seed_action_type()
    suffix = uuid.uuid4().hex
    client.app.dependency_overrides[require_principal] = lambda: _principal(
        "provider-health-maker", "admin"
    )
    proposal_response = client.post(
        "/v1/aip/action-proposals",
        headers=_headers(f"provider-health-proposal-{suffix}"),
        json={
            "actionTypeId": PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
            "purpose": PROVIDER_HEALTH_ACTION_PURPOSE,
            "riskHint": "R0",
            "payload": {
                "providerId": "agnes-text-qyh-dev",
                "providerRevision": 7,
                "probeCount": 3,
                "outputPolicy": "metadata-only",
            },
        },
    )
    assert proposal_response.status_code == 201, proposal_response.text
    proposal = proposal_response.json()["proposal"]
    assert proposal["actionType"]["revisionHash"] == action["revisionHash"]
    assert proposal["riskLevel"] == "R2"
    assert proposal["policySnapshot"]["makerChecker"] is True

    client.app.dependency_overrides[require_principal] = lambda: _principal(
        "provider-health-maker", "approver"
    )
    same_actor = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/decision",
        headers=_headers(f"provider-health-same-actor-{suffix}"),
        json={
            "expectedProposalVersion": proposal["version"],
            "expectedProposalHash": proposal["proposalHash"],
            "decision": "approved",
        },
    )
    assert same_actor.status_code == 422

    client.app.dependency_overrides[require_principal] = lambda: _principal(
        "provider-health-checker", "approver"
    )
    approved_response = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/decision",
        headers=_headers(f"provider-health-approval-{suffix}"),
        json={
            "expectedProposalVersion": proposal["version"],
            "expectedProposalHash": proposal["proposalHash"],
            "decision": "approved",
            "approvalExpiresAt": (
                datetime.now(timezone.utc) + timedelta(minutes=10)
            ).isoformat(),
        },
    )
    assert approved_response.status_code == 200, approved_response.text
    approved = approved_response.json()["proposal"]

    client.app.dependency_overrides[require_principal] = lambda: _principal(
        "provider-health-executor", "aip_executor"
    )
    wrong_hash = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/lease",
        headers=_headers(f"provider-health-wrong-hash-{suffix}"),
        json={
            "expectedProposalVersion": approved["version"],
            "expectedProposalHash": "f" * 64,
        },
    )
    assert wrong_hash.status_code == 409

    leased_response = client.post(
        f"/v1/aip/action-proposals/{proposal['id']}/lease",
        headers=_headers(f"provider-health-lease-{suffix}"),
        json={
            "expectedProposalVersion": approved["version"],
            "expectedProposalHash": approved["proposalHash"],
        },
    )
    assert leased_response.status_code == 200, leased_response.text
    lease = leased_response.json()["lease"]

    refresh = FakeRefresh()
    _adapter, revision, report = register_provider_health_action_adapter(
        ACTION_ADAPTERS, refresh
    )
    try:
        executed = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers=_headers(f"provider-health-execute-{suffix}"),
            json={"expectedProposalHash": approved["proposalHash"]},
        )
        assert executed.status_code == 200, executed.text
        body = executed.json()
        assert body["attempt"]["status"] == "applied"
        assert body["attempt"]["adapterRevisionRef"] == revision.exact_ref().model_dump(
            mode="json", by_alias=True
        )
        assert len(body["receipts"]) == 1
        receipt = body["receipts"][0]
        assert receipt["adapterRevisionRef"] == body["attempt"]["adapterRevisionRef"]
        expected_payload = {
            "observationId": "provider-health-observation-test",
            "expiresAt": "2099-01-01T00:00:00Z",
            "providerCalls": 3,
            "secretPayloadReadsReported": 0,
            "promptOrAnswerBodiesReported": 0,
        }
        assert {
            key: receipt["payload"][key] for key in expected_payload
        } == expected_payload
        assert receipt["payload"]["redactionApplied"] is False
        assert receipt["usageReceiptRefs"]
        assert refresh.calls == 1
        replay = client.post(
            f"/v1/aip/action-leases/{lease['id']}/execute",
            headers=_headers(f"provider-health-replay-{suffix}"),
            json={"expectedProposalHash": approved["proposalHash"]},
        )
        assert replay.status_code == 200
        assert len(replay.json()["receipts"]) == 1
        assert refresh.calls == 1

        with connect(SCOPE) as conn:
            counts = conn.execute(
                """SELECT
                     (SELECT COUNT(*) FROM aip_action_execution_attempt
                       WHERE org_id=%s AND project_id=%s AND proposal_id=%s) AS attempts,
                     (SELECT COUNT(*) FROM aip_action_receipt
                       WHERE org_id=%s AND project_id=%s AND proposal_id=%s) AS receipts""",
                (*SCOPE.key, proposal["id"], *SCOPE.key, proposal["id"]),
            ).fetchone()
        assert dict(counts) == {"attempts": 1, "receipts": 1}
        with connect(CANARY) as conn:
            assert conn.execute(
                "SELECT 1 FROM aip_action_receipt WHERE proposal_id=%s",
                (proposal["id"],),
            ).fetchone() is None
        assert report.green is True
    finally:
        ACTION_ADAPTERS.unregister(PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID)
        ACTION_ADAPTERS.unregister_conformant(revision.exact_ref())
        client.app.dependency_overrides.pop(require_principal, None)
