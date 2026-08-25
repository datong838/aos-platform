"""W5-06 canonical Action webhook inbox acceptance tests."""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from aos_api.aip_action_webhook_service import (
    AipActionWebhookService,
    get_action_webhook_service,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
SECRET = b"w5-06-test-secret"
HASH = "a" * 64


def _seed(scope: TenantScope = SCOPE, *, max_body_bytes: int = 65536) -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex
    endpoint_key = f"endpoint-key-{suffix}"
    endpoint_id = f"endpoint-{suffix}"
    provider_request_id = f"provider-request-{suffix}"
    account_ref = {
        "resourceType": "AccountBindingRevision",
        "resourceId": f"account-{suffix}",
        "revision": 1,
        "contentHash": HASH,
    }
    with connect(scope) as conn:
        conn.execute(
            """INSERT INTO aip_action_webhook_endpoint_revision
               (org_id,project_id,endpoint_id,revision,content_hash,lifecycle,
                adapter_revision_ref,account_binding_ref,signature_policy,secret_ref,
                event_schema,max_body_bytes)
               VALUES (%s,%s,%s,1,%s,'published',%s::jsonb,%s::jsonb,%s::jsonb,
                       'secret://test/w5-06',%s::jsonb,%s)""",
            (
                *scope.key, endpoint_id, HASH,
                json.dumps({"resourceType": "AdapterCapabilityRevision", "resourceId": "adapter", "revision": 1, "contentHash": HASH}),
                json.dumps(account_ref),
                json.dumps({
                    "algorithm": "hmac-sha256",
                    "timestampHeader": "x-aos-timestamp",
                    "nonceHeader": "x-aos-nonce",
                    "signatureHeader": "x-aos-signature",
                    "keyRevisionHeader": "x-aos-key-revision",
                    "allowedKeyRevisions": ["1", "2"],
                    "maxSkewSeconds": 300,
                    "signedHeaders": ["x-aos-key-revision", "x-aos-nonce", "x-aos-timestamp"],
                }),
                json.dumps({
                    "required": ["providerEventId", "providerRequestId", "eventType", "providerOutcome"],
                    "allowedOutcomes": ["accepted", "applied", "failed", "partial", "unknown"],
                    "allowedEventTypes": ["queued", "applied", "failed", "partial"],
                }),
                max_body_bytes,
            ),
        )
        conn.execute(
            """INSERT INTO aip_action_proposal
               (org_id,project_id,proposal_id,action_type_id,action_type_revision_hash,
                action_type_snapshot,purpose,risk_level,policy_snapshot,payload,
                proposal_hash,status,expires_at,idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,'w5_06_webhook_test',%s,'{}'::jsonb,'webhook inbox',
                       'R1','{}'::jsonb,'{}'::jsonb,%s,'executing',%s,%s,%s,'pytest')""",
            (
                *scope.key, f"proposal-{suffix}", HASH, HASH,
                datetime.now(timezone.utc) + timedelta(hours=1),
                f"proposal-key-{suffix}", HASH,
            ),
        )
        conn.execute(
            """INSERT INTO aip_action_execution_lease
               (org_id,project_id,lease_id,proposal_id,proposal_hash,attempt,status,
                owner_id,expires_at)
               VALUES (%s,%s,%s,%s,%s,1,'consumed','pytest',%s)""",
            (
                *scope.key, f"lease-{suffix}", f"proposal-{suffix}", HASH,
                datetime.now(timezone.utc) + timedelta(hours=1),
            ),
        )
        conn.execute(
            """INSERT INTO aip_action_execution_attempt
               (org_id,project_id,attempt_id,lease_id,proposal_id,status,
                action_binding_hash,account_binding_ref,idempotency_envelope,
                request_hash,provider_request_id)
               VALUES (%s,%s,%s,%s,%s,'accepted',%s,%s::jsonb,%s,%s,%s)""",
            (
                *scope.key, f"attempt-{suffix}", f"lease-{suffix}",
                f"proposal-{suffix}", "b" * 64, json.dumps(account_ref),
                HASH, HASH, provider_request_id,
            ),
        )
        conn.execute(
            """INSERT INTO aip_action_receipt
               (org_id,project_id,receipt_id,proposal_id,lease_id,status,
                provider_request_id,request_fingerprint,receipt_kind,attempt_id,
                action_binding_hash,account_binding_ref,provider_outcome,reconciliation_status)
               VALUES (%s,%s,%s,%s,%s,'accepted',%s,%s,'initial',%s,%s,%s::jsonb,
                       'accepted','pending')""",
            (
                *scope.key, f"receipt-{suffix}", f"proposal-{suffix}", f"lease-{suffix}",
                provider_request_id, HASH, f"attempt-{suffix}", "b" * 64,
                json.dumps(account_ref),
            ),
        )
        conn.commit()
    with connect(inherit_scope=False) as conn:
        conn.execute(
            """INSERT INTO aip_action_webhook_endpoint_directory
               (endpoint_key,org_id,project_id,endpoint_id,active_revision)
               VALUES (%s,%s,%s,%s,1)""",
            (endpoint_key, *scope.key, endpoint_id),
        )
        conn.commit()
    return endpoint_key, provider_request_id, "b" * 64


def _request(
    endpoint_key: str,
    provider_request_id: str,
    *,
    event_id: str | None = None,
    outcome: str = "accepted",
    sequence: Any = 1,
    binding_hash: str = "b" * 64,
    key_revision: str = "1",
    timestamp: int | None = None,
    provider_event_at: Any = None,
) -> tuple[bytes, dict[str, str]]:
    event_id = event_id or f"event-{uuid.uuid4().hex}"
    payload = {
        "providerEventId": event_id,
        "providerRequestId": provider_request_id,
        "eventType": "queued" if outcome == "accepted" else outcome,
        "providerOutcome": outcome,
        "providerSequence": sequence,
        "providerEventAt": (
            datetime.now(timezone.utc).isoformat()
            if provider_event_at is None else provider_event_at
        ),
        "actionBindingHash": binding_hash,
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = timestamp or int(datetime.now(timezone.utc).timestamp())
    nonce = f"nonce-{uuid.uuid4().hex}"
    body_hash = hashlib.sha256(body).hexdigest()
    canonical_headers = "\n".join((
        f"x-aos-key-revision:{key_revision}",
        f"x-aos-nonce:{nonce}",
        f"x-aos-timestamp:{timestamp}",
    ))
    signature = hmac.new(
        SECRET, f"{canonical_headers}\nbody-sha256:{body_hash}".encode(), hashlib.sha256
    ).hexdigest()
    return body, {
        "x-aos-timestamp": str(timestamp),
        "x-aos-nonce": nonce,
        "x-aos-signature": signature,
        "x-aos-key-revision": key_revision,
        "x-org-id": "forged-org",
        "x-project-id": "forged-project",
    }


def _service() -> AipActionWebhookService:
    return AipActionWebhookService(lambda _scope, _ref, _revision: SECRET)


def test_provider_route_resolves_tenant_only_from_endpoint_and_never_principal(client) -> None:
    endpoint_key, provider_request_id, binding_hash = _seed()
    service = _service()
    client.app.dependency_overrides[get_action_webhook_service] = lambda: service
    try:
        body, headers = _request(endpoint_key, provider_request_id, binding_hash=binding_hash)
        response = client.post(
            f"/v1/aip/action-webhooks/{endpoint_key}/events", content=body, headers=headers
        )
        assert response.status_code == 202, response.text
        result = response.json()
        assert result["verificationStatus"] == "verified"
        assert result["processingStatus"] == "accepted"
        assert result["observation"]["attemptId"].startswith("attempt-")
        assert result["reducer"]["status"] == "pending"
    finally:
        client.app.dependency_overrides.pop(get_action_webhook_service, None)


def test_unknown_bad_expired_and_oversize_requests_fail_before_event_parse(client) -> None:
    endpoint_key, provider_request_id, _binding_hash = _seed(max_body_bytes=1024)
    client.app.dependency_overrides[get_action_webhook_service] = _service
    try:
        body, headers = _request(endpoint_key, provider_request_id)
        unknown = client.post("/v1/aip/action-webhooks/unknown/events", content=body, headers=headers)
        assert unknown.status_code == 404
        bad = client.post(
            f"/v1/aip/action-webhooks/{endpoint_key}/events",
            content=body,
            headers={**headers, "x-aos-signature": "0" * 64},
        )
        assert bad.status_code == 401
        old_body, old_headers = _request(
            endpoint_key, provider_request_id,
            timestamp=int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()),
        )
        expired = client.post(
            f"/v1/aip/action-webhooks/{endpoint_key}/events",
            content=old_body,
            headers=old_headers,
        )
        assert expired.status_code == 401
        huge = client.post(
            f"/v1/aip/action-webhooks/{endpoint_key}/events",
            content=b"{" + b"x" * 2048,
            headers=headers,
        )
        assert huge.status_code == 413
    finally:
        client.app.dependency_overrides.pop(get_action_webhook_service, None)


def test_replay_is_idempotent_and_same_event_key_body_drift_is_quarantined() -> None:
    endpoint_key, provider_request_id, binding_hash = _seed()
    event_id = f"event-{uuid.uuid4().hex}"
    body, headers = _request(
        endpoint_key, provider_request_id, event_id=event_id, binding_hash=binding_hash
    )
    service = _service()
    first = service.receive(endpoint_key, headers, body)
    replay = service.receive(endpoint_key, headers, body)
    assert replay.id == first.id
    assert replay.replay_status == "duplicate"
    drift_body, drift_headers = _request(
        endpoint_key, provider_request_id, event_id=event_id, outcome="applied",
        binding_hash=binding_hash,
    )
    drift = service.receive(endpoint_key, drift_headers, drift_body)
    assert drift.replay_status == "drift"
    assert drift.processing_status == "quarantined"
    assert drift.case_id is not None


def test_gap_late_event_and_terminal_conflict_reduce_without_last_write_wins() -> None:
    endpoint_key, provider_request_id, binding_hash = _seed()
    service = _service()
    for sequence, outcome, expected in (
        (1, "accepted", "pending"),
        (3, "applied", "awaiting_gap"),
        (2, "accepted", "applied"),
        (4, "failed", "disputed"),
    ):
        body, headers = _request(
            endpoint_key, provider_request_id, outcome=outcome,
            sequence=sequence, binding_hash=binding_hash,
        )
        result = service.receive(endpoint_key, headers, body)
        assert result.reducer is not None
        assert result.reducer.status == expected
    assert result.reducer.provider_outcome is None
    assert result.case_id is not None


def test_other_tenant_endpoint_cannot_bind_real_tenant_attempt() -> None:
    _real_endpoint, provider_request_id, binding_hash = _seed(SCOPE)
    other_endpoint, _other_request, _other_binding = _seed(OTHER_SCOPE)
    body, headers = _request(
        other_endpoint, provider_request_id, binding_hash=binding_hash
    )
    result = _service().receive(other_endpoint, headers, body)
    assert result.processing_status == "quarantined"
    assert result.case_id is not None


def test_binding_drift_and_same_sequence_conflict_never_last_write_win() -> None:
    endpoint_key, provider_request_id, binding_hash = _seed()
    service = _service()
    drift_body, drift_headers = _request(
        endpoint_key, provider_request_id, binding_hash="c" * 64
    )
    drift = service.receive(endpoint_key, drift_headers, drift_body)
    assert drift.processing_status == "quarantined"
    assert drift.case_id is not None

    first_body, first_headers = _request(
        endpoint_key, provider_request_id, sequence=1, outcome="accepted",
        binding_hash=binding_hash,
    )
    service.receive(endpoint_key, first_headers, first_body)
    conflict_body, conflict_headers = _request(
        endpoint_key, provider_request_id, sequence=1, outcome="applied",
        binding_hash=binding_hash,
    )
    conflict = service.receive(endpoint_key, conflict_headers, conflict_body)
    assert conflict.reducer is not None
    assert conflict.reducer.status == "disputed"
    assert conflict.case_id is not None


def test_key_rotation_and_schema_types_fail_closed_after_verification() -> None:
    endpoint_key, provider_request_id, binding_hash = _seed()
    seen_revisions: list[str] = []

    def resolver(_scope: TenantScope, _ref: str, revision: str) -> bytes:
        seen_revisions.append(revision)
        return SECRET

    service = AipActionWebhookService(resolver)
    body, headers = _request(
        endpoint_key, provider_request_id, binding_hash=binding_hash, key_revision="2"
    )
    accepted = service.receive(endpoint_key, headers, body)
    assert accepted.processing_status == "accepted"
    assert seen_revisions == ["2"]

    for sequence, event_at in ((True, None), (2, "not-a-datetime")):
        invalid_body, invalid_headers = _request(
            endpoint_key, provider_request_id, binding_hash=binding_hash,
            sequence=sequence, provider_event_at=event_at,
        )
        invalid = service.receive(endpoint_key, invalid_headers, invalid_body)
        assert invalid.processing_status == "quarantined"
        assert invalid.case_id is not None


def test_concurrent_same_event_is_one_observation_without_orphan_replay_claim() -> None:
    endpoint_key, provider_request_id, binding_hash = _seed()
    event_id = f"event-{uuid.uuid4().hex}"
    body, headers = _request(
        endpoint_key, provider_request_id, event_id=event_id, binding_hash=binding_hash
    )
    service = _service()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: service.receive(endpoint_key, headers, body), range(2)))
    assert {item.replay_status for item in results} == {"new", "duplicate"}
    assert len({item.id for item in results}) == 1
    with connect(SCOPE) as conn:
        replay_count = conn.execute(
            """SELECT COUNT(*) AS count FROM aip_action_webhook_replay_key
               WHERE org_id=%s AND project_id=%s AND endpoint_id=(
                 SELECT endpoint_id FROM aip_action_webhook_endpoint_directory
                 WHERE endpoint_key=%s) AND event_key=%s""",
            (*SCOPE.key, endpoint_key, event_id),
        ).fetchone()["count"]
        observation_count = conn.execute(
            """SELECT COUNT(*) AS count FROM aip_action_webhook_observation
               WHERE org_id=%s AND project_id=%s AND provider_event_id=%s""",
            (*SCOPE.key, event_id),
        ).fetchone()["count"]
    assert replay_count == 1
    assert observation_count == 1
