from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_memory_contracts import KnowledgeQuery, KnowledgeScope, KnowledgeSourceRef
from aos_api.aip_memory_retrieval import (
    AipMemoryRetrieval,
    AipMemoryRetrievalIndex,
    O1WikiKnowledgeAdapter,
    ResolvedKnowledgePayload,
)
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

PRIMARY = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 12, 15, tzinfo=UTC)
HASH_A = "a" * 64


def ref(kind: str, identifier: str, revision: str = "1") -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identifier,
        revision=revision,
        authority="postgresql",
    )


def payload(content: str, identifier: str) -> tuple[ArtifactRef, ResolvedKnowledgePayload]:
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    artifact = ArtifactRef(
        artifact_id=identifier,
        artifact_type="memory_payload",
        revision="1",
        content_hash=content_hash,
    )
    return artifact, ResolvedKnowledgePayload(
        artifact=artifact,
        content=content,
        token_count=max(1, len(content) // 4),
    )


def seed_memory(
    *,
    item_id: str,
    knowledge_scope: str,
    subject: ResourceRef,
    artifact: ArtifactRef,
    markings: list[str],
    applicability: list[str],
    source_expires_at: datetime,
    effective_at: datetime = NOW - timedelta(hours=1),
    status: str = "active",
) -> None:
    source_id = f"source-{item_id}"
    candidate_id = f"candidate-{item_id}"
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
        task_id = f"task-{item_id}"
        plan_id = f"plan-{item_id}"
        run_id = f"run-{item_id}"
        conn.execute(
            """INSERT INTO aip_task (
               org_id,project_id,task_id,task_type,title,status,idempotency_key,
               request_hash,current_plan_revision_id,created_by)
               VALUES (%s,%s,%s,'memory','memory','completed',%s,%s,%s,'pytest')""",
            (*PRIMARY.key, task_id, task_id, HASH_A, plan_id),
        )
        conn.execute(
            """INSERT INTO aip_plan_revision (
               org_id,project_id,plan_revision_id,task_id,revision,content_hash,
               steps,approval_status,idempotency_key,request_hash,created_by)
               VALUES (%s,%s,%s,%s,1,%s,'[]','approved',%s,%s,'pytest')""",
            (*PRIMARY.key, plan_id, task_id, HASH_A, plan_id, HASH_A),
        )
        conn.execute(
            """INSERT INTO aip_task_run (
               org_id,project_id,run_id,task_id,plan_revision_id,status,
               idempotency_key,request_hash,created_by,finished_at)
               VALUES (%s,%s,%s,%s,%s,'succeeded',%s,%s,'pytest',%s)""",
            (*PRIMARY.key, run_id, task_id, plan_id, run_id, HASH_A, effective_at),
        )
        conn.execute(
            """INSERT INTO aip_memory_source_revision (
               org_id,project_id,source_id,revision,source_kind,source_uri,
               observed_at,freshness_expires_at,license_id,usage_policy,
               content_hash,provider,provider_version,applicability,created_by)
               VALUES (%s,%s,%s,1,'authorized_document',%s,%s,%s,'internal',
               'summary-and-citation',%s,'pytest','1',%s::jsonb,'pytest')""",
            (*PRIMARY.key, source_id, f"urn:{source_id}", effective_at,
             source_expires_at, HASH_A, json.dumps(applicability)),
        )
        conn.execute(
            """INSERT INTO aip_memory_candidate (
               org_id,project_id,candidate_id,memory_layer,scope,status,task_id,
               run_id,subject_ref,payload_ref,source_id,source_revision,confidence,
               markings,eval_report_ref,draft_ref,approval_event_ref,created_by,
               created_at,updated_at)
               VALUES (%s,%s,%s,'semantic',%s,'promoted',%s,%s,%s::jsonb,
               %s::jsonb,%s,1,0.9,%s::jsonb,'{}','{}','{}','pytest',%s,%s)""",
            (*PRIMARY.key, candidate_id, knowledge_scope, task_id, run_id,
             subject.model_dump_json(by_alias=True), artifact.model_dump_json(by_alias=True),
             source_id, json.dumps(markings), effective_at, effective_at),
        )
        conn.execute("SET CONSTRAINTS aip_memory_item_current_revision_fk DEFERRED")
        conn.execute(
            """INSERT INTO aip_memory_item (
               org_id,project_id,memory_item_id,memory_layer,scope,status,
               subject_ref,current_revision,created_at,updated_at)
               VALUES (%s,%s,%s,'semantic',%s,%s,%s::jsonb,1,%s,%s)""",
            (*PRIMARY.key, item_id, knowledge_scope, status,
             subject.model_dump_json(by_alias=True), effective_at, effective_at),
        )
        conn.execute(
            """INSERT INTO aip_memory_item_revision (
               org_id,project_id,memory_item_id,revision,candidate_id,source_id,
               source_revision,payload_ref,content_hash,confidence,applicability,
               markings,effective_at,created_by,created_at)
               VALUES (%s,%s,%s,1,%s,%s,1,%s::jsonb,%s,0.9,%s::jsonb,
               %s::jsonb,%s,'pytest',%s)""",
            (*PRIMARY.key, item_id, candidate_id, source_id,
             artifact.model_dump_json(by_alias=True), artifact.content_hash,
             json.dumps(applicability), json.dumps(markings), effective_at, effective_at),
        )
        conn.commit()


@pytest.fixture()
def knowledge() -> dict[str, object]:
    suffix = uuid.uuid4().hex[:10]
    subject = ref("ecom.product", f"product-{suffix}")
    workspace_artifact, workspace_payload = payload("工作区专属美妆话术", f"ws-{suffix}")
    organization_artifact, organization_payload = payload("组织级美妆话术", f"org-{suffix}")
    secret_artifact, secret_payload = payload("客户敏感经营事实", f"secret-{suffix}")
    stale_artifact, stale_payload = payload("已经过期的旧规则", f"stale-{suffix}")
    related_artifact, related_payload = payload("关联商品规则", f"related-{suffix}")
    related_subject = ref("ecom.product", f"related-{suffix}")
    seed_memory(
        item_id=f"ws-{suffix}", knowledge_scope="workspace", subject=subject,
        artifact=workspace_artifact, markings=["internal"],
        applicability=["skill:content"], source_expires_at=NOW + timedelta(days=30),
    )
    seed_memory(
        item_id=f"org-{suffix}", knowledge_scope="organization", subject=subject,
        artifact=organization_artifact, markings=["internal"],
        applicability=["skill:content"], source_expires_at=NOW + timedelta(days=30),
    )
    seed_memory(
        item_id=f"secret-{suffix}", knowledge_scope="workspace", subject=ref("ecom.product", f"secret-{suffix}"),
        artifact=secret_artifact, markings=["restricted"],
        applicability=["skill:content"], source_expires_at=NOW + timedelta(days=30),
    )
    seed_memory(
        item_id=f"stale-{suffix}", knowledge_scope="workspace", subject=ref("ecom.product", f"stale-{suffix}"),
        artifact=stale_artifact, markings=["internal"],
        applicability=["skill:content"], source_expires_at=NOW - timedelta(minutes=1),
    )
    seed_memory(
        item_id=f"related-{suffix}", knowledge_scope="workspace", subject=related_subject,
        artifact=related_artifact, markings=["internal"],
        applicability=["skill:content"], source_expires_at=NOW + timedelta(days=30),
    )
    resolved = {
        item.artifact.artifact_id: item
        for item in [workspace_payload, organization_payload, secret_payload, stale_payload, related_payload]
    }
    return {"subject": subject, "related_subject": related_subject, "resolved": resolved, "suffix": suffix}


def query(subject: ResourceRef, *, max_tokens: int = 256) -> KnowledgeQuery:
    return KnowledgeQuery(
        subject=subject,
        task_id="task-query",
        skill_ref=ref("aip.skill", "content"),
        time_cutoff=NOW,
        markings=["internal"],
        max_tokens=max_tokens,
    )


def retrieval(knowledge, index=None, resolver=None) -> AipMemoryRetrieval:
    resolved = knowledge["resolved"]
    return AipMemoryRetrieval(
        payload_resolver=resolver or (lambda _scope, artifact: resolved[artifact.artifact_id]),
        index=index,
    )


def test_workspace_overrides_organization_and_returns_exact_citation(knowledge) -> None:
    result = retrieval(knowledge).query(
        PRIMARY, query(knowledge["subject"]),
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert result.status == "complete"
    assert [citation.scope for citation in result.citations] == [KnowledgeScope.WORKSPACE]
    assert result.chunks[0].content == "工作区专属美妆话术"
    assert result.citations[0].source.content_hash == HASH_A


def test_requested_markings_never_authorize_and_stale_is_blocked(knowledge) -> None:
    secret = query(ref("ecom.product", f"secret-{knowledge['suffix']}"))
    secret = secret.model_copy(update={"markings": ["restricted"]})
    result = retrieval(knowledge).query(
        PRIMARY, secret, authorized_markings=["internal"],
        required_applicability=["skill:content"],
    )
    assert result.status == "blocked"
    assert result.blocked_reasons == ["requested_marking_forbidden"]

    stale = retrieval(knowledge).query(
        PRIMARY, query(ref("ecom.product", f"stale-{knowledge['suffix']}")),
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert stale.status == "blocked"
    assert "source_stale" in stale.blocked_reasons


def test_cross_tenant_and_wrong_applicability_return_no_knowledge(knowledge) -> None:
    cross = retrieval(knowledge).query(
        CANARY, query(knowledge["subject"]),
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert cross.status == "blocked"
    assert "knowledge_not_found" in cross.blocked_reasons
    wrong = retrieval(knowledge).query(
        PRIMARY, query(knowledge["subject"]),
        authorized_markings=["internal"], required_applicability=["skill:service"],
    )
    assert wrong.status == "blocked"
    assert "applicability_mismatch" in wrong.blocked_reasons


def test_token_budget_and_payload_drift_are_honest_degradation(knowledge) -> None:
    related_payload = knowledge["resolved"][f"related-{knowledge['suffix']}"]
    knowledge["resolved"][f"related-{knowledge['suffix']}"] = related_payload.model_copy(
        update={"token_count": 64}
    )
    progressive = query(knowledge["subject"], max_tokens=64).model_copy(
        update={"object_refs": [knowledge["related_subject"]]}
    )
    too_small = retrieval(knowledge).query(
        PRIMARY, progressive,
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert too_small.status == "degraded"
    assert len(too_small.chunks) == 1
    assert too_small.chunks[0].content == "工作区专属美妆话术"
    assert "token_budget_exceeded" in too_small.blocked_reasons
    resolved = knowledge["resolved"]
    drifted = retrieval(
        knowledge,
        resolver=lambda _scope, artifact: resolved[artifact.artifact_id].model_copy(
            update={
                "artifact": resolved[artifact.artifact_id].artifact.model_copy(
                    update={"content_hash": "f" * 64}
                )
            }
        ),
    ).query(
        PRIMARY, query(knowledge["subject"]),
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert drifted.status == "blocked"
    assert "payload_authority_drift" in drifted.blocked_reasons


def test_reference_index_can_be_cleared_and_rebuilt_without_changing_authority(knowledge) -> None:
    index = AipMemoryRetrievalIndex()
    engine = retrieval(knowledge, index=index)
    before = engine.query(
        PRIMARY, query(knowledge["subject"]),
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    index.clear(PRIMARY)
    degraded = engine.query(
        PRIMARY, query(knowledge["subject"]),
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert degraded.citations == before.citations
    assert "index_unavailable_authority_scan" in degraded.blocked_reasons
    index.rebuild(PRIMARY)
    rebuilt = engine.query(
        PRIMARY, query(knowledge["subject"]),
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert rebuilt.citations == before.citations


def test_same_scope_conflicting_knowledge_fails_closed(knowledge) -> None:
    suffix = knowledge["suffix"]
    subject = ref("ecom.product", f"conflict-{suffix}")
    first_artifact, first_payload = payload("冲突规则甲", f"conflict-a-{suffix}")
    second_artifact, second_payload = payload("冲突规则乙", f"conflict-b-{suffix}")
    for item_id, artifact in (
        (f"conflict-a-{suffix}", first_artifact),
        (f"conflict-b-{suffix}", second_artifact),
    ):
        seed_memory(
            item_id=item_id, knowledge_scope="workspace", subject=subject,
            artifact=artifact, markings=["internal"],
            applicability=["skill:content"],
            source_expires_at=NOW + timedelta(days=30),
        )
    knowledge["resolved"].update({
        first_artifact.artifact_id: first_payload,
        second_artifact.artifact_id: second_payload,
    })
    result = retrieval(knowledge).query(
        PRIMARY, query(subject), authorized_markings=["internal"],
        required_applicability=["skill:content"],
    )
    assert result.status == "blocked"
    assert result.blocked_reasons == ["memory_conflict"]


def test_o1_wiki_adapter_rejects_legacy_and_verifies_governance_envelope() -> None:
    suffix = uuid.uuid4().hex[:10]
    with connect() as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES ('org-org','栖月汇商贸有限公司') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            "INSERT INTO twa_workspace(org_id,project_id,name) VALUES ('org-org','dev-project','默认工作区') ON CONFLICT DO NOTHING"
        )
        conn.execute(
            """INSERT INTO wiki_page(object_type,object_id,body,org_id,project_id)
               VALUES ('Product',%s,'{"summary":"legacy"}',%s,%s)""",
            (f"legacy-{suffix}", *PRIMARY.key),
        )
        conn.commit()
    adapter = O1WikiKnowledgeAdapter()
    result = adapter.read(
        PRIMARY, "Product", f"legacy-{suffix}", time_cutoff=NOW,
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert result.status == "blocked"
    assert result.blocked_reasons == ["wiki_governance_envelope_missing"]

    content = "经治理的商品知识"
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    artifact = ArtifactRef(
        artifact_id=f"wiki-{suffix}", artifact_type="wiki_payload",
        revision="3", content_hash=content_hash,
    )
    source = KnowledgeSourceRef(
        source_kind="authorized_document", source_uri=f"urn:wiki:{suffix}",
        observed_at=NOW - timedelta(days=1),
        freshness_expires_at=NOW + timedelta(days=30),
        license_id="internal", usage_policy="summary-and-citation",
        content_hash=HASH_A, provider="pytest", provider_version="1",
        applicability=["skill:content"],
    )
    body = {
        "content": content,
        "governance": {
            "revision": 3, "contentHash": content_hash,
            "source": source.model_dump(mode="json", by_alias=True),
            "confidence": 0.9, "applicability": ["skill:content"],
            "markings": ["internal"],
            "payload": artifact.model_dump(mode="json", by_alias=True),
        },
    }
    with connect() as conn:
        conn.execute(
            """INSERT INTO wiki_page(object_type,object_id,body,org_id,project_id)
               VALUES ('Product',%s,%s::jsonb,%s,%s)""",
            (f"governed-{suffix}", json.dumps(body), *PRIMARY.key),
        )
        conn.commit()
    governed = adapter.read(
        PRIMARY, "Product", f"governed-{suffix}", time_cutoff=NOW,
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert governed.status == "complete"
    assert governed.citation.revision == 3
    assert governed.content == content

    drifted = json.loads(json.dumps(body))
    drifted["governance"]["payload"]["contentHash"] = "f" * 64
    with connect() as conn:
        conn.execute(
            """INSERT INTO wiki_page(object_type,object_id,body,org_id,project_id)
               VALUES ('Product',%s,%s::jsonb,%s,%s)""",
            (f"drifted-{suffix}", json.dumps(drifted), *PRIMARY.key),
        )
        conn.commit()
    drifted_result = adapter.read(
        PRIMARY, "Product", f"drifted-{suffix}", time_cutoff=NOW,
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert drifted_result.blocked_reasons == ["wiki_governance_envelope_invalid"]
    forbidden = adapter.read(
        PRIMARY, "Product", f"governed-{suffix}", time_cutoff=NOW,
        authorized_markings=[], required_applicability=["skill:content"],
    )
    assert forbidden.blocked_reasons == ["marking_forbidden"]
    cross = adapter.read(
        CANARY, "Product", f"governed-{suffix}", time_cutoff=NOW,
        authorized_markings=["internal"], required_applicability=["skill:content"],
    )
    assert cross.blocked_reasons == ["wiki_not_found"]


def test_revoked_and_future_effective_memory_are_excluded(knowledge) -> None:
    suffix = knowledge["suffix"]
    revoked_artifact, revoked_payload = payload("已撤回的规则", f"revoked-{suffix}")
    future_artifact, future_payload = payload("未来才生效的规则", f"future-{suffix}")
    revoked_subject = ref("ecom.product", f"revoked-{suffix}")
    future_subject = ref("ecom.product", f"future-{suffix}")
    seed_memory(
        item_id=f"revoked-{suffix}", knowledge_scope="workspace",
        subject=revoked_subject, artifact=revoked_artifact, markings=["internal"],
        applicability=["skill:content"], source_expires_at=NOW + timedelta(days=30),
        status="revoked",
    )
    seed_memory(
        item_id=f"future-{suffix}", knowledge_scope="workspace",
        subject=future_subject, artifact=future_artifact, markings=["internal"],
        applicability=["skill:content"], source_expires_at=NOW + timedelta(days=30),
        effective_at=NOW + timedelta(minutes=1),
    )
    knowledge["resolved"].update({
        revoked_payload.artifact.artifact_id: revoked_payload,
        future_payload.artifact.artifact_id: future_payload,
    })
    revoked = retrieval(knowledge).query(
        PRIMARY, query(revoked_subject), authorized_markings=["internal"],
        required_applicability=["skill:content"],
    )
    assert revoked.blocked_reasons == ["memory_revoked"]
    future = retrieval(knowledge).query(
        PRIMARY, query(future_subject), authorized_markings=["internal"],
        required_applicability=["skill:content"],
    )
    assert future.blocked_reasons == ["time_cutoff_excluded"]
