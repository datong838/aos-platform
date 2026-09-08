from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from ecommerce_growth.audit_projection import (
    audit_feedback_projection,
    business_feedback_projection,
)
from ecommerce_growth.content_artifact_review import (
    ContentReviewReceipt,
    ReadableContentArtifact,
)
from ecommerce_growth.result_feedback import ResultFeedbackRequest, build_result_feedback
from ecommerce_growth.sdk_ports import ExactRef


ROOT = Path(__file__).parents[4]


def ref(kind: str, identity: str, revision: int = 1) -> ExactRef:
    return ExactRef(
        resource_type=kind,
        resource_id=identity,
        revision=revision,
        content_hash="sha256:" + (identity.encode().hex() + "0" * 64)[:64],
        receipt_id=f"receipt-{identity}",
    )


def artifact() -> ReadableContentArtifact:
    return ReadableContentArtifact(
        artifact_ref=ref("ArtifactRevision", "artifact-1"),
        task_ref=ref("Task", "task-1"),
        brief_ref=ref("TaskBriefRevision", "brief-1"),
        growth_plan_ref=ref("GrowthPlanRevision", "plan-1"),
        source_artifact_refs=tuple(
            ref("ArtifactRevision", f"source-{index}") for index in range(1, 5)
        ),
        product_names=("玫瑰精粹面霜",),
        channels=("栖月汇微商城",),
        fact_source_refs=(ref("EvidenceBundleRevision", "evidence-1"),),
        body="围绕会员复购设计七夕内容，明确商品利益点与服务边界。",
        constraint_checks=("库存与价格信息已核对",),
    )


def review(decision: str = "ACCEPT") -> ContentReviewReceipt:
    item = artifact()
    return ContentReviewReceipt(
        receipt_ref=ref("ContentReviewReceipt", "review-1"),
        request_hash="sha256:" + "a" * 64,
        decision=decision,
        artifact_ref=item.artifact_ref,
        task_ref=item.task_ref,
        brief_ref=item.brief_ref,
        review_issue_ref=ref("ReviewIssueRevision", "issue-1"),
        reviewer_authority_ref=ref("ReviewerAuthorityRevision", "reviewer-1"),
        return_stage=None if decision == "ACCEPT" else "content_generation",
        replayed=False,
    )


def request(decision: str = "ACCEPT") -> ResultFeedbackRequest:
    return ResultFeedbackRequest(
        review_receipt=review(decision),
        artifact=artifact(),
        business_task_title="七夕会员复购内容策划",
        artifact_summary="内容已覆盖核心商品、会员权益、发布渠道与服务承诺。",
        idempotency_key="feedback-1",
    )


def test_accept_builds_exact_three_segments_without_effect_claim_or_side_effects() -> None:
    plan = build_result_feedback(request())
    assert [segment.kind for segment in plan.segments] == [
        "daily_review",
        "improvement_observation",
        "memory_candidate",
    ]
    assert [segment.sequence for segment in plan.segments] == [1, 2, 3]
    assert "暂无足够证据" in plan.segments[1].business_summary
    assert "尚未进入知识库" in plan.segments[2].business_summary
    assert set(plan.payload()["sideEffects"].values()) == {0}
    assert build_result_feedback(request()) == plan


def test_command_identity_only_uses_review_receipt_and_decision() -> None:
    original = build_result_feedback(request())
    other_key = build_result_feedback(replace(request(), idempotency_key="another-client-key"))
    other_copy = build_result_feedback(
        replace(request(), business_task_title="七夕老会员回购内容策划")
    )
    assert other_key.command_id == original.command_id
    assert other_key.command_hash == original.command_hash
    assert other_copy.command_id == original.command_id
    assert other_copy.command_hash != original.command_hash


def test_return_builds_only_new_content_stage_target_and_keeps_artifact_exact() -> None:
    item = request("RETURN")
    plan = build_result_feedback(item)
    assert len(plan.segments) == 1
    assert plan.segments[0].kind == "content_return_target"
    assert plan.segments[0].target_phase == "content_generation"
    assert plan.artifact_ref == item.artifact.artifact_ref
    assert plan.payload()["sideEffects"]["taskCreatedCount"] == 0


def test_feedback_rejects_lineage_stage_and_technical_business_copy_drift() -> None:
    item = request()
    with pytest.raises(ValueError, match="exact lineage drifted"):
        replace(item, artifact=replace(item.artifact, task_ref=ref("Task", "other")))
    with pytest.raises(ValueError, match="RETURN feedback must target"):
        replace(request("RETURN"), review_receipt=replace(review("RETURN"), return_stage="review"))
    with pytest.raises(ValueError, match="technical text"):
        replace(item, business_task_title="AR2-7C 开发任务")
    with pytest.raises(ValueError, match="technical text"):
        replace(item, artifact_summary="修改 services/aos-api/demo.py 完成任务。")
    for polluted in (
        "请修改代码后继续业务处理",
        r"请修改 C:\repo\demo.py 后继续业务处理",
        "请修改 demo.py 后继续业务处理",
    ):
        with pytest.raises(ValueError, match="technical text"):
            replace(item, artifact_summary=polluted)


def test_business_projection_has_no_exact_ids_and_audit_projection_contains_them() -> None:
    plan = build_result_feedback(request())
    business = business_feedback_projection(plan)
    audit = audit_feedback_projection(plan)
    business_text = str(business)
    for forbidden in (plan.command_id, plan.command_hash, "artifact-1", "task-1", "receipt-review-1"):
        assert forbidden not in business_text
    assert "auditDetails" not in business
    assert audit["auditDetails"]["artifactRef"]["resourceId"] == "artifact-1"
    assert audit["auditDetails"]["targets"][0]["targetId"].startswith("daily_review-")


def test_n8_package_files_do_not_import_platform_network_or_provider_code() -> None:
    package = ROOT / "bundles/solutions/ecommerce-growth/backend/ecommerce_growth"
    for name in ("result_feedback.py", "audit_projection.py"):
        source = (package / name).read_text(encoding="utf-8")
        for forbidden in ("aos_api", "psycopg", "requests", "httpx", "subprocess", "socket"):
            assert forbidden not in source
