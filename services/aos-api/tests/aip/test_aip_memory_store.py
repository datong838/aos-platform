from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_memory_contracts import (
    GovernanceApprovalRef,
    KnowledgeScope,
    KnowledgeSourceRef,
    MemoryCandidateStatus,
    SubmitMemoryCandidateRequest,
)
from aos_api.aip_memory_store import (
    AipMemoryConflict,
    AipMemoryNotFound,
    AipMemoryStore,
    AipMemoryTransitionBlocked,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

PRIMARY = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 12, 11, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def resource(kind: str, identifier: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision="1",
        authority="postgresql",
    )


def source(content_hash: str = HASH_A) -> KnowledgeSourceRef:
    return KnowledgeSourceRef(
        source_kind="authorized_document",
        source_uri="urn:aip5:test-policy",
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=30),
        license_id="internal-authorized",
        usage_policy="summary-and-citation",
        content_hash=content_hash,
        provider="pytest",
        provider_version="1",
        applicability=["vertical:ecommerce"],
    )


def governance() -> GovernanceApprovalRef:
    return GovernanceApprovalRef(
        eval_report=ArtifactRef(
            artifact_id="eval-report-1",
            artifact_type="eval_report",
            revision="1",
            content_hash=HASH_C,
        ),
        draft=resource("aip.draft", "draft-1"),
        approval_event=resource("aip.approval_event", "approval-1"),
    )


@pytest.fixture()
def chain() -> dict[str, object]:
    suffix = uuid.uuid4().hex[:12]
    task_id = f"memory-task-{suffix}"
    plan_id = f"memory-plan-{suffix}"
    run_id = f"memory-run-{suffix}"
    candidate_id = f"memory-candidate-{suffix}"
    source_id = f"memory-source-{suffix}"
    item_id = f"memory-item-{suffix}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES ('org-org','栖月汇商贸有限公司') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name)
               VALUES ('org-org','dev-project','默认工作区')
               ON CONFLICT (org_id,project_id) DO NOTHING"""
        )
        conn.execute(
            """INSERT INTO aip_task (
               org_id,project_id,task_id,task_type,title,status,idempotency_key,
               request_hash,current_plan_revision_id,created_by)
               VALUES (%s,%s,%s,'memory','memory','executing',%s,%s,%s,'pytest')""",
            (*PRIMARY.key, task_id, task_id, HASH_A, plan_id),
        )
        conn.execute(
            """INSERT INTO aip_plan_revision (
               org_id,project_id,plan_revision_id,task_id,revision,content_hash,
               steps,approval_status,idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,'approved',%s,%s,'pytest')""",
            (*PRIMARY.key, plan_id, task_id, HASH_A, json.dumps([]), plan_id, HASH_A),
        )
        conn.execute(
            """INSERT INTO aip_task_run (
               org_id,project_id,run_id,task_id,plan_revision_id,status,
               idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,%s,'running',%s,%s,'pytest')""",
            (*PRIMARY.key, run_id, task_id, plan_id, run_id, HASH_A),
        )
        conn.commit()
    request = SubmitMemoryCandidateRequest(
        candidate_layer="semantic",
        task_id=task_id,
        run_id=run_id,
        subject=resource("ecom.product", "product-1"),
        payload=ArtifactRef(
            artifact_id=f"memory-payload-{suffix}",
            artifact_type="memory_candidate",
            revision="1",
            content_hash=HASH_B,
        ),
        source=source(),
        confidence=0.85,
        marking=["internal"],
    )
    return {
        "store": AipMemoryStore(),
        "request": request,
        "source_id": source_id,
        "candidate_id": candidate_id,
        "item_id": item_id,
    }


def create_candidate(chain: dict[str, object]):
    store = chain["store"]
    assert isinstance(store, AipMemoryStore)
    request = chain["request"]
    assert isinstance(request, SubmitMemoryCandidateRequest)
    source_id = str(chain["source_id"])
    store.create_source_revision(PRIMARY, source_id, 1, request.source, actor="pytest")
    return store.submit_candidate(
        PRIMARY,
        str(chain["candidate_id"]),
        request,
        source_id=source_id,
        source_revision=1,
        knowledge_scope=KnowledgeScope.WORKSPACE,
        actor="pytest",
        occurred_at=NOW,
    )


def test_source_and_candidate_are_idempotent_scoped_and_restart_safe(chain) -> None:
    store = chain["store"]
    request = chain["request"]
    source_id = chain["source_id"]
    candidate = create_candidate(chain)
    assert candidate.status is MemoryCandidateStatus.PENDING
    assert candidate.version == 1
    assert store.create_source_revision(
        PRIMARY, source_id, 1, request.source, actor="pytest"
    ) == request.source
    replay = store.submit_candidate(
        PRIMARY,
        chain["candidate_id"],
        request,
        source_id=source_id,
        source_revision=1,
        knowledge_scope=KnowledgeScope.WORKSPACE,
        actor="pytest",
        occurred_at=NOW,
    )
    assert replay == candidate
    restarted = AipMemoryStore()
    assert restarted.get_candidate(PRIMARY, chain["candidate_id"]) == candidate
    with pytest.raises(AipMemoryNotFound):
        restarted.get_candidate(CANARY, chain["candidate_id"])
    with pytest.raises(AipMemoryConflict):
        store.create_source_revision(
            PRIMARY, source_id, 1, source(HASH_C), actor="pytest"
        )


def test_candidate_transition_cas_governance_and_event_timeline(chain) -> None:
    store = chain["store"]
    candidate = create_candidate(chain)
    quarantined = store.transition_candidate(
        PRIMARY,
        candidate.candidate_id,
        to_status=MemoryCandidateStatus.QUARANTINED,
        expected_version=1,
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=1),
        reason_codes=["source_conflict"],
    )
    assert quarantined.version == 2
    with pytest.raises(AipMemoryConflict):
        store.transition_candidate(
            PRIMARY,
            candidate.candidate_id,
            to_status=MemoryCandidateStatus.REJECTED,
            expected_version=1,
            actor="reviewer",
            occurred_at=NOW + timedelta(minutes=2),
        )
    pending = store.transition_candidate(
        PRIMARY,
        candidate.candidate_id,
        to_status=MemoryCandidateStatus.PENDING,
        expected_version=2,
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=3),
    )
    assert pending.version == 3
    with pytest.raises(AipMemoryTransitionBlocked, match="governance"):
        store.transition_candidate(
            PRIMARY,
            candidate.candidate_id,
            to_status=MemoryCandidateStatus.APPROVED,
            expected_version=3,
            actor="approver",
            occurred_at=NOW + timedelta(minutes=4),
        )
    approved = store.transition_candidate(
        PRIMARY,
        candidate.candidate_id,
        to_status=MemoryCandidateStatus.APPROVED,
        expected_version=3,
        actor="approver",
        occurred_at=NOW + timedelta(minutes=5),
        governance=governance(),
    )
    assert approved.version == 4
    assert store.submit_candidate(
        PRIMARY,
        chain["candidate_id"],
        chain["request"],
        source_id=chain["source_id"],
        source_revision=1,
        knowledge_scope=KnowledgeScope.WORKSPACE,
        actor="pytest",
        occurred_at=NOW,
    ) == approved
    with pytest.raises(AipMemoryTransitionBlocked, match="atomically"):
        store.transition_candidate(
            PRIMARY,
            candidate.candidate_id,
            to_status=MemoryCandidateStatus.PROMOTED,
            expected_version=4,
            actor="promoter",
            occurred_at=NOW + timedelta(minutes=6),
            governance=governance(),
        )
    events = store.list_candidate_events(PRIMARY, candidate.candidate_id)
    assert [event.event_type for event in events] == [
        "submitted",
        "quarantined",
        "submitted",
        "approved",
    ]
    assert [event.sequence for event in events] == [1, 2, 3, 4]


def test_promotion_is_atomic_and_item_survives_store_recreation(chain) -> None:
    store = chain["store"]
    candidate = create_candidate(chain)
    approved = store.transition_candidate(
        PRIMARY,
        candidate.candidate_id,
        to_status=MemoryCandidateStatus.APPROVED,
        expected_version=1,
        actor="approver",
        occurred_at=NOW + timedelta(minutes=1),
        governance=governance(),
    )
    promoted, item, revision = store.promote_candidate(
        PRIMARY,
        approved.candidate_id,
        memory_item_id=chain["item_id"],
        expected_version=2,
        actor="promoter",
        occurred_at=NOW + timedelta(minutes=2),
    )
    assert promoted.status is MemoryCandidateStatus.PROMOTED
    assert item.current_revision == 1
    assert revision.content_hash == HASH_B
    assert revision.candidate_id == candidate.candidate_id
    restarted = AipMemoryStore()
    assert restarted.get_memory_item(PRIMARY, chain["item_id"]) == (item, revision)
    with pytest.raises(AipMemoryNotFound):
        restarted.get_memory_item(CANARY, chain["item_id"])
    replay = store.promote_candidate(
        PRIMARY,
        promoted.candidate_id,
        memory_item_id=chain["item_id"],
        expected_version=2,
        actor="promoter",
        occurred_at=NOW + timedelta(minutes=3),
    )
    assert replay == (promoted, item, revision)
    with pytest.raises(AipMemoryConflict, match="version"):
        store.promote_candidate(
            PRIMARY,
            promoted.candidate_id,
            memory_item_id=chain["item_id"],
            expected_version=99,
            actor="promoter",
            occurred_at=NOW + timedelta(minutes=3),
        )


def test_memory_revocation_is_cas_idempotent_audited_and_tenant_scoped(chain) -> None:
    store = chain["store"]
    candidate = create_candidate(chain)
    approved = store.transition_candidate(
        PRIMARY,
        candidate.candidate_id,
        to_status=MemoryCandidateStatus.APPROVED,
        expected_version=1,
        actor="approver",
        occurred_at=NOW + timedelta(minutes=1),
        governance=governance(),
    )
    _promoted, item, revision = store.promote_candidate(
        PRIMARY,
        approved.candidate_id,
        memory_item_id=chain["item_id"],
        expected_version=2,
        actor="promoter",
        occurred_at=NOW + timedelta(minutes=2),
    )

    revoked, retained_revision = store.revoke_memory_item(
        PRIMARY,
        item.memory_item_id,
        expected_version=1,
        reason_code="source_withdrawn",
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=3),
    )
    assert revoked.status.value == "revoked"
    assert revoked.version == 2
    assert retained_revision == revision

    replay = store.revoke_memory_item(
        PRIMARY,
        item.memory_item_id,
        expected_version=1,
        reason_code="source_withdrawn",
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=4),
    )
    assert replay == (revoked, revision)
    with pytest.raises(AipMemoryConflict, match="another command"):
        store.revoke_memory_item(
            PRIMARY,
            item.memory_item_id,
            expected_version=1,
            reason_code="different_reason",
            actor="reviewer",
            occurred_at=NOW + timedelta(minutes=5),
        )
    with pytest.raises(AipMemoryNotFound):
        store.revoke_memory_item(
            CANARY,
            item.memory_item_id,
            expected_version=1,
            reason_code="source_withdrawn",
            actor="reviewer",
            occurred_at=NOW + timedelta(minutes=5),
        )

    with connect(PRIMARY) as conn:
        evidence = conn.execute(
            """SELECT evidence_type,subject_ref,payload FROM aip_evidence
               WHERE org_id=%s AND project_id=%s AND source_ref=%s""",
            (*PRIMARY.key, item.memory_item_id),
        ).fetchone()
    assert evidence["evidence_type"] == "memory_revoke"
    assert evidence["subject_ref"]["resourceId"] == item.memory_item_id
    assert evidence["payload"]["reasonCode"] == "source_withdrawn"
