"""BG-03 draft can be handed to the existing content Task without new authority."""

from dataclasses import replace
from datetime import timedelta

import pytest

from ecommerce_growth.ecommerce_content_campaign_workflow_contracts import (
    ContentTaskSpec,
    content_task_from_sales_weapon_brief,
)
from ecommerce_growth.sdk_ports import ExactRef
from ecommerce_growth.ecommerce_business_investigation_review_command import (
    ARTIFACT_FAMILIES,
    ArtifactBinding,
    ReviewHandoffRequest,
)
from test_sales_weapon_brief import NOW, draft, ref
from test_ecommerce_analyst_authority_contracts import sales_weapon_method
from aos_api.ecommerce_analyst_authority_contracts import SalesWeaponMethod
from aos_api.ecommerce_growth_runtime_adapters import ReviewAdvanceHostService


ARTIFACTS = tuple(ExactRef("ArtifactRevision", f"artifact-{index}", 1, "sha256:" + "b" * 64)
                  for index in range(4))


def build(brief=None):
    return content_task_from_sales_weapon_brief(
        brief or draft(), artifact_refs=ARTIFACTS,
        channels=("内部方案",), time_window="本轮内部评审前",
    )


def test_business_context_maps_into_existing_task_without_technical_source_key():
    task = build()
    assert isinstance(task, ContentTaskSpec)
    assert task.growth_plan_ref == draft().plan_ref
    assert task.artifact_refs == ARTIFACTS
    assert "栖月汇候选商品" in task.title
    assert "线下体验后的知识解释场景" in task.objective
    assert task.audience == draft().audience_hypothesis.text
    assert "niushop:goods:65" not in repr(task)
    assert any("不适合" in value for value in task.constraints)
    assert any("未知" in value for value in task.constraints)
    assert any("禁说" in value for value in task.constraints)
    assert any("交接" in value for value in task.constraints)


def test_no_silent_truncation_of_business_method():
    with pytest.raises(ValueError):
        build(replace(draft(), product_label="商" * 121))
    with pytest.raises(ValueError):
        build(replace(draft(), handoff_condition="人工核验" * 60))


def test_exact_artifact_boundary_is_reused():
    with pytest.raises(ValueError):
        content_task_from_sales_weapon_brief(draft(), artifact_refs=ARTIFACTS[:3],
                                             channels=("内部方案",), time_window="本轮内部评审前")
    with pytest.raises(ValueError):
        content_task_from_sales_weapon_brief(draft(), artifact_refs=(ARTIFACTS[0],) * 4,
                                             channels=("内部方案",), time_window="本轮内部评审前")


def test_existing_content_task_contract_remains_unchanged():
    task = ContentTaskSpec(
        title="编写商品说明", objective="形成可评审的内容草稿", channels=("内部方案",),
        audience="目标客群", time_window="本轮内部评审前", constraints=("只用已核实事实",),
        growth_plan_ref=draft().plan_ref, artifact_refs=ARTIFACTS,
    )
    assert task.title == "编写商品说明"


def review(task):
    return ReviewHandoffRequest(
        occurrence_ref=ref("AutomationOccurrence", "occurrence-1"),
        case_ref=ref("BusinessInvestigationCaseRevision", "case-1"),
        run_ref=ref("BusinessInvestigationRun", "run-1"),
        analysis_receipt_ref=ref("AnalysisRuntimeReceipt", "analysis-1"),
        current_plan_ref=ref("PlanRevision", "plan-1"),
        growth_plan_ref=task.growth_plan_ref,
        review_issue_ref=ref("ReviewIssueRevision", "issue-1"),
        eval_report_ref=ref("EvalReportRevision", "eval-1"),
        artifact_bindings=tuple(ArtifactBinding(family, artifact)
                                for family, artifact in zip(ARTIFACT_FAMILIES, ARTIFACTS)),
        decision="ACCEPT", idempotency_key="review-1", cutoff_at=NOW,
        target_module_id="ecommerce.content-campaign", source_slot_id="analyst.solution",
        target_slot_id="content.plan", markings=("internal",),
        expires_at=NOW + timedelta(days=1), content_task=task,
    )


def test_existing_exact_review_accepts_business_task_and_rejects_technical_pollution():
    assert review(build()).command_payload()["taskSpec"]["audience"] == draft().audience_hypothesis.text
    with pytest.raises(ValueError, match="business text"):
        review(build(replace(draft(), product_label="API商品")))


def test_host_review_task_values_match_package_sales_weapon_mapping():
    task = build()
    method = SalesWeaponMethod.model_validate(sales_weapon_method())
    assert ReviewAdvanceHostService._sales_weapon_task_values(method) == {
        "title": task.title,
        "objective": task.objective,
        "audience": task.audience,
        "channels": list(task.channels),
        "timeWindow": task.time_window,
        "constraints": list(task.constraints),
    }
