from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import uuid

import pytest

from aos_api.aip_memory_cold_start import (
    InternalDocumentSeedAdapter,
    R15_ADAPTER_ID,
    R15_TARGET_SCOPE,
    R15_SUBJECT,
    apply_internal_knowledge_seed,
    build_internal_knowledge_receipt,
    internal_document_seed_adapter_definition,
    plan_internal_knowledge_seed,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_memory_contracts import KnowledgeQuery
from aos_api.aip_memory_pipeline_contracts import KnowledgePipelineKind
from aos_api.aip_memory_pipeline_service import AipMemoryPipelinePolicyBlocked
from aos_api.aip_memory_production_factory import build_memory_retrieval_service
from aos_api.aip_memory_store import AipMemoryNotFound, AipMemoryStore
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

NOW = datetime(2026, 8, 22, 0, tzinfo=UTC)


def test_real_internal_document_plan_is_ready_and_deterministic() -> None:
    source = Path(__file__).resolve().parents[4] / (
        "bundles/solutions/ecommerce-growth/content/knowledge/internal/"
        "qyh-customer-service-escalation-v1.md"
    )
    first = plan_internal_knowledge_seed(
        R15_TARGET_SCOPE,
        source,
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=90),
        now=NOW,
    )
    second = plan_internal_knowledge_seed(
        R15_TARGET_SCOPE,
        source,
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=90),
        now=NOW,
        expected_hash=first.content_hash,
    )
    assert first.status == "ready"
    assert first.blockers == []
    assert first.ids == second.ids
    assert first.content_hash == second.content_hash
    assert first.license_id == "aos-internal-owned-v1"
    assert first.usage_policy == "workspace_retrieval"


def test_internal_document_receipt_and_adapter_are_exact_and_deterministic() -> None:
    source = Path(__file__).resolve().parents[4] / (
        "bundles/solutions/ecommerce-growth/content/knowledge/internal/"
        "qyh-customer-service-escalation-v1.md"
    )
    plan = plan_internal_knowledge_seed(
        R15_TARGET_SCOPE,
        source,
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=90),
        now=NOW,
    )
    receipt = build_internal_knowledge_receipt(plan)
    definition = internal_document_seed_adapter_definition()
    assert definition.adapter_id == R15_ADAPTER_ID
    assert definition.pipeline_kinds == [KnowledgePipelineKind.SEED_IMPORT]
    draft = InternalDocumentSeedAdapter(plan).adapt(
        receipt, pipeline_kind=KnowledgePipelineKind.SEED_IMPORT
    )[0]
    assert draft.candidate_id == plan.ids.candidate_id
    assert draft.source_id == plan.ids.source_id
    assert draft.knowledge_scope.value == "workspace"
    assert draft.candidate_layer.value == "semantic"

    drifted = receipt.model_copy(update={"task_id": "different-task"})
    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="receipt_drift"):
        InternalDocumentSeedAdapter(plan).adapt(
            drifted, pipeline_kind=KnowledgePipelineKind.SEED_IMPORT
        )
    with pytest.raises(AipMemoryPipelinePolicyBlocked, match="kind_not_allowed"):
        InternalDocumentSeedAdapter(plan).adapt(
            receipt, pipeline_kind=KnowledgePipelineKind.OPERATIONAL_LEARNING
        )


def test_plan_fails_closed_for_tenant_hash_freshness_and_sensitive_text(tmp_path) -> None:
    source = tmp_path / "knowledge.md"
    source.write_text("contact 13800138000 token=unsafe-value", encoding="utf-8")
    plan = plan_internal_knowledge_seed(
        TenantScope("dev-org", "dev-project"),
        source,
        observed_at=NOW + timedelta(hours=1),
        freshness_expires_at=NOW,
        now=NOW,
        expected_hash="0" * 64,
    )
    assert plan.status == "blocked"
    assert set(plan.blockers) >= {
        "tenant_not_authorized",
        "source_hash_drift",
        "observed_at_from_future",
        "freshness_window_invalid",
        "source_stale",
        "pii_mobile",
        "secret_assignment",
    }


def test_plan_fails_closed_for_missing_or_empty_source(tmp_path) -> None:
    missing = plan_internal_knowledge_seed(
        R15_TARGET_SCOPE,
        tmp_path / "missing.md",
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=1),
        now=NOW,
    )
    empty_path = tmp_path / "empty.md"
    empty_path.write_bytes(b"")
    empty = plan_internal_knowledge_seed(
        R15_TARGET_SCOPE,
        empty_path,
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=1),
        now=NOW,
    )
    assert missing.blockers == ["source_unreadable", "source_empty"]
    assert empty.blockers == ["source_empty"]


def test_apply_replay_query_revoke_and_canary_fail_closed(tmp_path) -> None:
    source = tmp_path / "internal-knowledge.md"
    marker = uuid.uuid4().hex
    content = f"# 客服升级规则\n\n高风险承诺必须人工复核。\n\n版本标识：{marker}\n"
    source.write_text(content, encoding="utf-8")
    plan = plan_internal_knowledge_seed(
        R15_TARGET_SCOPE,
        source,
        observed_at=NOW,
        freshness_expires_at=NOW + timedelta(days=30),
        now=NOW,
    )
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
        conn.commit()

    first = apply_internal_knowledge_seed(
        R15_TARGET_SCOPE,
        plan,
        content=content,
        actor="pytest-maker",
        reviewer="pytest-reviewer",
        occurred_at=NOW + timedelta(minutes=1),
    )
    replay = apply_internal_knowledge_seed(
        R15_TARGET_SCOPE,
        plan,
        content=content,
        actor="pytest-maker",
        reviewer="pytest-reviewer",
        occurred_at=NOW + timedelta(minutes=2),
    )
    assert first.status == "applied"
    assert replay.status == "replayed"
    assert first.memory_item.memory_item_id == plan.ids.memory_item_id
    assert replay.search_reference_created is False
    with connect() as conn:
        run = conn.execute(
            """SELECT status,request_hash FROM aip_task_run
               WHERE org_id=%s AND project_id=%s AND run_id=%s""",
            (*R15_TARGET_SCOPE.key, plan.ids.run_id),
        ).fetchone()
    assert run == {"status": "succeeded", "request_hash": plan.content_hash}

    query = KnowledgeQuery(
        subject=R15_SUBJECT,
        task_id=plan.ids.task_id,
        skill_ref=ResourceRef(
            resource_type="aip.skill_revision",
            resource_id="ecommerce.customer_service.response",
            revision="1",
            authority="postgresql",
        ),
        time_cutoff=NOW + timedelta(minutes=3),
        markings=["internal"],
        max_tokens=2048,
    )
    primary = build_memory_retrieval_service().query(
        R15_TARGET_SCOPE,
        query,
        authorized_markings=["internal"],
        required_applicability=["vertical:ecommerce"],
    )
    canary = build_memory_retrieval_service().query(
        TenantScope("dev-org", "dev-project"),
        query,
        authorized_markings=["internal"],
        required_applicability=["vertical:ecommerce"],
    )
    assert primary.status in {"complete", "degraded"}
    assert primary.citations[0].content_hash == plan.content_hash
    assert content.strip() in primary.chunks[0].content
    assert canary.status == "blocked"

    store = AipMemoryStore()
    revoked, revision = store.revoke_memory_item(
        R15_TARGET_SCOPE,
        plan.ids.memory_item_id,
        expected_version=first.memory_item.version,
        reason_code="r15_test_revoke",
        actor="pytest-reviewer",
        occurred_at=NOW + timedelta(minutes=4),
    )
    assert revoked.status.value == "revoked"
    assert revision.content_hash == plan.content_hash
    after_revoke = build_memory_retrieval_service().query(
        R15_TARGET_SCOPE,
        query,
        authorized_markings=["internal"],
        required_applicability=["vertical:ecommerce"],
    )
    assert after_revoke.status == "blocked"
    with pytest.raises(AipMemoryNotFound):
        store.get_memory_item(
            TenantScope("dev-org", "dev-project"), plan.ids.memory_item_id
        )
