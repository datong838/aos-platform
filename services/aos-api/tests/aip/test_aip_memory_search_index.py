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
from aos_api.aip_memory_search_index import (
    AipMemorySearchIndex,
    AipMemorySearchIndexConflict,
    SearchCapability,
    SearchReferenceDraft,
)
from aos_api.aip_memory_store import AipMemoryStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope


PRIMARY = TenantScope("e6c-test-org", "e6c-test-project")
CANARY = TenantScope("e6c-canary-org", "e6c-test-project")
NOW = datetime(2026, 8, 13, 6, tzinfo=UTC)
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


@pytest.fixture()
def promoted_memory() -> dict[str, object]:
    suffix = uuid.uuid4().hex[:12]
    task_id, plan_id, run_id = (
        f"search-task-{suffix}",
        f"search-plan-{suffix}",
        f"search-run-{suffix}",
    )
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES ('e6c-test-org','E6C 隔离测试组织') "
            "ON CONFLICT (id) DO NOTHING"
        )
        conn.execute(
            """INSERT INTO twa_workspace(org_id,project_id,name)
               VALUES ('e6c-test-org','e6c-test-project','E6C 隔离测试工作区')
               ON CONFLICT (org_id,project_id) DO NOTHING"""
        )
        conn.execute(
            """INSERT INTO aip_task (
               org_id,project_id,task_id,task_type,title,status,idempotency_key,
               request_hash,current_plan_revision_id,created_by)
               VALUES (%s,%s,%s,'memory','search','executing',%s,%s,%s,'pytest')""",
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
    source_id = f"search-source-{suffix}"
    candidate_id = f"search-candidate-{suffix}"
    item_id = f"search-item-{suffix}"
    source = KnowledgeSourceRef(
        source_kind="authorized_document",
        source_uri="https://example.invalid/authorized-beauty-policy",
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=30),
        license_id="internal-authorized",
        usage_policy="summary-and-citation",
        content_hash=HASH_A,
        provider="pytest",
        provider_version="1",
        applicability=["vertical:ecommerce", "category:beauty"],
    )
    request = SubmitMemoryCandidateRequest(
        candidate_layer="semantic",
        task_id=task_id,
        run_id=run_id,
        subject=resource("ecom.product", "beauty-product-1"),
        payload=ArtifactRef(
            artifact_id=f"search-payload-{suffix}",
            artifact_type="memory_candidate",
            revision="1",
            content_hash=HASH_B,
        ),
        source=source,
        confidence=0.9,
        marking=["internal"],
    )
    store = AipMemoryStore()
    store.create_source_revision(PRIMARY, source_id, 1, source, actor="pytest")
    candidate = store.submit_candidate(
        PRIMARY,
        candidate_id,
        request,
        source_id=source_id,
        source_revision=1,
        knowledge_scope=KnowledgeScope.WORKSPACE,
        actor="pytest",
        occurred_at=NOW,
    )
    approved = store.transition_candidate(
        PRIMARY,
        candidate_id,
        to_status=MemoryCandidateStatus.APPROVED,
        expected_version=candidate.version,
        actor="reviewer",
        occurred_at=NOW + timedelta(minutes=1),
        governance=GovernanceApprovalRef(
            eval_report=ArtifactRef(
                artifact_id="eval-search-1",
                artifact_type="eval_report",
                revision="1",
                content_hash=HASH_C,
            ),
            draft=resource("aip.draft", "search-draft-1"),
            approval_event=resource("aip.approval_event", "search-approval-1"),
        ),
    )
    _, item, revision = store.promote_candidate(
        PRIMARY,
        approved.candidate_id,
        memory_item_id=item_id,
        expected_version=approved.version,
        actor="promoter",
        occurred_at=NOW + timedelta(minutes=2),
    )
    return {"item": item, "revision": revision, "source": source}


def draft(promoted_memory: dict[str, object], **changes) -> SearchReferenceDraft:
    item = promoted_memory["item"]
    revision = promoted_memory["revision"]
    source = promoted_memory["source"]
    values = {
        "memory_item_id": item.memory_item_id,
        "revision": revision.revision,
        "content_hash": revision.content_hash,
        "subject": item.subject,
        "source_id": revision.source_id,
        "source_revision": revision.source_revision,
        "terms": ["美妆", "成分安全", "敏感肌"],
        "markings": revision.markings,
        "applicability": revision.applicability,
        "freshness_expires_at": source.freshness_expires_at,
    }
    values.update(changes)
    return SearchReferenceDraft(**values)


def test_reference_projection_is_restart_safe_scoped_and_rebuildable(promoted_memory) -> None:
    index = AipMemorySearchIndex()
    item = promoted_memory["item"]
    assert index.replace_references(PRIMARY, [draft(promoted_memory)], indexed_at=NOW) == 1
    with connect(PRIMARY) as conn:
        row = conn.execute(
            "SELECT * FROM aip_memory_search_reference WHERE memory_item_id=%s",
            (item.memory_item_id,),
        ).fetchone()
        assert row["search_terms"] == ["美妆", "成分安全", "敏感肌"]
        assert "payload_ref" not in row
    with connect(CANARY) as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM aip_memory_search_reference WHERE memory_item_id=%s",
            (item.memory_item_id,),
        ).fetchone()["n"] == 0
    assert AipMemorySearchIndex().clear_references(PRIMARY) >= 1
    with connect(PRIMARY) as conn:
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM aip_memory_item WHERE memory_item_id=%s",
            (item.memory_item_id,),
        ).fetchone()["n"] == 1


def test_reference_rejects_authority_drift_and_pii(promoted_memory) -> None:
    with pytest.raises(ValueError, match="PII"):
        draft(promoted_memory, terms=["联系 13800138000"])
    with pytest.raises(AipMemorySearchIndexConflict):
        AipMemorySearchIndex().replace_references(
            PRIMARY,
            [draft(promoted_memory, content_hash=HASH_C)],
            indexed_at=NOW,
        )


def test_capabilities_are_tenant_scoped_and_cas_guarded() -> None:
    index = AipMemorySearchIndex()
    vector = index.set_capability(
        PRIMARY,
        SearchCapability(
            lane="vector",
            status="degraded",
            reason_code="degraded_vector_unavailable",
            version=1,
            observed_at=NOW,
        ),
        expected_version=0,
    )
    assert vector.version == 1
    created = index.set_capability(
        PRIMARY,
        SearchCapability(
            lane="fulltext",
            status="unbuilt",
            reason_code="fulltext_index_unbuilt",
            version=1,
            observed_at=NOW,
        ),
        expected_version=0,
    )
    assert index.list_capabilities(CANARY) == []
    ready = index.set_capability(
        PRIMARY,
        SearchCapability(
            lane="fulltext",
            status="ready",
            provider="postgresql_fulltext",
            provider_revision="simple-v1",
            version=1,
            observed_at=NOW + timedelta(minutes=1),
        ),
        expected_version=1,
    )
    assert ready.version == 2
    with pytest.raises(AipMemorySearchIndexConflict, match="CAS"):
        index.set_capability(PRIMARY, created, expected_version=1)
    with pytest.raises(AipMemorySearchIndexConflict, match="pgvector"):
        index.set_capability(
            PRIMARY,
            SearchCapability(
                lane="vector",
                status="ready",
                provider="pgvector",
                provider_revision="0.8",
                version=1,
                observed_at=NOW,
            ),
            expected_version=1,
        )
