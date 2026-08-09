from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from aos_api.db import connect
from aos_api.errors import ApiError
from aos_api.ontology_operational_authority import (
    append_record,
    archive_record,
    read_record,
    record_evidence_cleanup,
)
from aos_api.tenant_scope import TenantScope


DEV_SCOPE = TenantScope(org_id="dev-org", project_id="dev-project")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def _retention_payload() -> dict[str, object]:
    return {
        "dataCategory": "customer-message",
        "durationDays": 30,
        "cleanupMode": "delete_content_keep_hash",
        "policyOwner": "security-owner",
    }


def test_revision_cas_idempotency_archive_and_scope_isolation() -> None:
    record_id = _id("policy")
    key = _id("idem")
    first, first_etag = append_record(
        DEV_SCOPE,
        record_kind="retention_policy",
        record_id=record_id,
        payload=_retention_payload(),
        expected_revision=0,
        idempotency_key=key,
        actor="pytest",
    )
    replay, replay_etag = append_record(
        DEV_SCOPE,
        record_kind="retention_policy",
        record_id=record_id,
        payload=_retention_payload(),
        expected_revision=0,
        idempotency_key=key,
        actor="pytest",
    )
    assert replay == first
    assert replay_etag == first_etag

    with pytest.raises(ApiError) as changed_payload:
        append_record(
            DEV_SCOPE,
            record_kind="retention_policy",
            record_id=record_id,
            payload={**_retention_payload(), "durationDays": 31},
            expected_revision=0,
            idempotency_key=key,
            actor="pytest",
        )
    assert changed_payload.value.status_code == 409

    with pytest.raises(ApiError) as stale:
        append_record(
            DEV_SCOPE,
            record_kind="retention_policy",
            record_id=record_id,
            payload=_retention_payload(),
            expected_revision=0,
            idempotency_key=_id("stale"),
            actor="pytest",
        )
    assert stale.value.status_code == 412

    archive_key = _id("archive")
    archived = archive_record(
        DEV_SCOPE,
        record_kind="retention_policy",
        record_id=record_id,
        expected_revision=1,
        idempotency_key=archive_key,
        actor="pytest",
    )
    assert archive_record(
        DEV_SCOPE,
        record_kind="retention_policy",
        record_id=record_id,
        expected_revision=1,
        idempotency_key=archive_key,
        actor="pytest",
    ) == archived
    assert read_record(DEV_SCOPE, record_kind="retention_policy", record_id=record_id) is None
    assert read_record(
        TenantScope(org_id="org-org", project_id="dev-project"),
        record_kind="retention_policy",
        record_id=record_id,
    ) is None


def test_evidence_correction_cleanup_and_immutable_revision() -> None:
    policy_id = _id("policy")
    append_record(
        DEV_SCOPE,
        record_kind="retention_policy",
        record_id=policy_id,
        payload=_retention_payload(),
        expected_revision=0,
        idempotency_key=_id("policy"),
        actor="pytest",
    )
    evidence_id = _id("evidence")
    content_hash = "sha256:" + "a" * 64
    base_payload = {
        "subjectRef": {"kind": "object", "id": "Payment/niushop:1:27"},
        "conclusion": "payment metric verified",
        "contentHash": content_hash,
        "retentionPolicyRef": {"policyId": policy_id, "revision": 1},
        "sensitive": True,
    }
    append_record(
        DEV_SCOPE,
        record_kind="evidence",
        record_id=evidence_id,
        payload=base_payload,
        expected_revision=0,
        idempotency_key=_id("evidence"),
        actor="pytest",
    )
    append_record(
        DEV_SCOPE,
        record_kind="evidence",
        record_id=evidence_id,
        payload={**base_payload, "conclusion": "corrected", "supersedesRevision": 1},
        expected_revision=1,
        idempotency_key=_id("correct"),
        actor="pytest",
    )
    with pytest.raises(ApiError, match="not found"):
        append_record(
            DEV_SCOPE,
            record_kind="evidence",
            record_id=evidence_id,
            payload={**base_payload, "supersedesRevision": 999},
            expected_revision=2,
            idempotency_key=_id("bad-correction"),
            actor="pytest",
        )

    cleanup_key = _id("cleanup")
    cleanup = record_evidence_cleanup(
        DEV_SCOPE,
        evidence_id=evidence_id,
        evidence_revision=2,
        idempotency_key=cleanup_key,
        actor="pytest",
    )
    replay = record_evidence_cleanup(
        DEV_SCOPE,
        evidence_id=evidence_id,
        evidence_revision=2,
        idempotency_key=cleanup_key,
        actor="pytest",
    )
    assert cleanup == replay
    assert cleanup["contentHash"] == content_hash

    with connect(DEV_SCOPE) as conn, pytest.raises(
        psycopg.Error, match="permission denied|IMMUTABLE"
    ):
        conn.execute(
            "UPDATE ontology_evidence_revision SET created_by='tampered' "
            "WHERE org_id=%s AND workspace_id=%s AND record_id=%s AND revision=1",
            (*DEV_SCOPE.key, evidence_id),
        )


def test_action_instance_cannot_lower_authoritative_policy() -> None:
    action_type_id = _id("action-type")
    append_record(
        DEV_SCOPE,
        record_kind="action_type",
        record_id=action_type_id,
        payload={
            "name": "Refund",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "object"},
            "policy": {
                "riskLevel": "high",
                "requiresApproval": True,
                "capabilities": ["refund.execute"],
            },
            "timeoutSeconds": 60,
        },
        expected_revision=0,
        idempotency_key=_id("action-type"),
        actor="pytest",
    )
    base_instance = {
        "actionTypeRef": {"recordId": action_type_id, "revision": 1},
        "status": "proposed",
        "riskLevel": "high",
        "requiresApproval": True,
        "inputSnapshotHash": "sha256:" + "b" * 64,
    }
    append_record(
        DEV_SCOPE,
        record_kind="action_instance",
        record_id=_id("instance"),
        payload=base_instance,
        expected_revision=0,
        idempotency_key=_id("instance"),
        actor="pytest",
    )
    with pytest.raises(ApiError) as lowered:
        append_record(
            DEV_SCOPE,
            record_kind="action_instance",
            record_id=_id("instance"),
            payload={**base_instance, "riskLevel": "low", "requiresApproval": False},
            expected_revision=0,
            idempotency_key=_id("lowered"),
            actor="pytest",
        )
    assert lowered.value.code == "ACTION_POLICY_MISMATCH"


def test_uninstalled_public_knowledge_is_not_visible() -> None:
    record_id = _id("knowledge")
    append_record(
        DEV_SCOPE,
        record_kind="knowledge",
        record_id=record_id,
        payload={
            "title": "公共支付口径",
            "body": "only visible with active installation",
            "subject": {"subjectType": "object_type", "subjectId": "Payment"},
            "sources": [{
                "sourceType": "document",
                "sourceRef": "doc:payment",
                "revision": "sha256:" + "c" * 64,
            }],
            "visibility": "installed_template",
            "knowledgePackId": "domain.ecommerce.core",
        },
        expected_revision=0,
        idempotency_key=_id("knowledge"),
        actor="pytest",
    )
    assert read_record(DEV_SCOPE, record_kind="knowledge", record_id=record_id) is None
