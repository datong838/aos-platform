from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import TenantContext
from aos_api.aip_ecommerce_growth_daily import (
    DailyLogicStage,
    DailyOperatingInput,
    DailyOperatingState,
    DailySourceObservation,
    GrowthEffectBinding,
    compile_daily_operating_loop,
    propose_task_graph_materialization,
)
from aos_api.aip_production_contracts import ExactRevisionRef


HASH = "b" * 64
CUTOFF = datetime(2026, 8, 22, 0, 0, tzinfo=timezone.utc)


def ref(kind: str, identity: str, revision: int = 1) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind,
        resource_id=identity,
        revision=revision,
        content_hash=HASH,
    )


def sources(**overrides: object) -> list[DailySourceObservation]:
    result = []
    for index in range(1, 13):
        values: dict[str, object] = {
            "source_id": f"P{index:02d}",
            "latest_run_ref": ref("PipelineRunRevision", f"p{index:02d}-run"),
            "cutoff_at": CUTOFF,
            "fresh_until": CUTOFF + timedelta(hours=2),
            "status": "succeeded",
            "reconciliation_passed": True,
            "source_count": index,
            "projection_count": index,
        }
        if index == int(overrides.get("source_index", -1)):
            values.update({key: value for key, value in overrides.items() if key != "source_index"})
        result.append(DailySourceObservation(**values))
    return result


def stages() -> list[DailyLogicStage]:
    return [
        DailyLogicStage(
            order=index,
            logic_id=f"D{index:02d}",
            logic_ref=ref("LogicGraphRevision", f"ecommerce.logic.D{index:02d}"),
        )
        for index in range(1, 7)
    ]


def request(**overrides: object) -> DailyOperatingInput:
    values: dict[str, object] = {
        "source_evidence_pack_ref": ref("SourceReadinessEvidencePackRevision", "p01-p12-cutoff"),
        "source_observations": sources(),
        "research_evidence_refs": [ref("IntelligenceEvidenceRevision", "research-1")],
        "wiki_snapshot_ref": ref("WikiSnapshotRevision", "wiki-1"),
        "okf_mapping_ref": ref("OkfMappingRevision", "okf-1"),
        "logic_stages": stages(),
        "objective": "提升有证据支持的经营效率",
        "baseline": "近七日已支付订单与商品经营基线",
        "target": "在护栏内形成可审批的增长方案",
        "constraints": ["不得外发", "不得改价"],
        "guardrails": ["预算上限", "库存与履约保护"],
        "budget_limit": "CNY 0 for draft-only",
        "stop_conditions": ["数据过期", "证据冲突", "人工撤回"],
        "expected_effect": "待审批后进入观察窗口",
        "observed_at": CUTOFF + timedelta(minutes=30),
    }
    values.update(overrides)
    return DailyOperatingInput(**values)


def test_ready_same_cutoff_input_compiles_draft_only_growth_plan() -> None:
    result = compile_daily_operating_loop(
        TenantContext(org_id="org-org", project_id="dev-project"), request()
    )
    assert result.state is DailyOperatingState.READY_FOR_PLAN_REVIEW
    assert result.plan_spec is not None
    assert result.plan_spec.status == "draft"
    assert result.plan_spec.production_written is False
    assert result.task_graph_proposal is None
    assert result.blockers == []


def test_compile_never_accepts_request_tenant_fields() -> None:
    with pytest.raises(ValidationError):
        DailyOperatingInput(**request().model_dump(), org_id="dev-org", project_id="dev-project")


def test_negative_canary_scope_never_inherits_positive_tenant() -> None:
    result = compile_daily_operating_loop(
        TenantContext(org_id="dev-org", project_id="dev-project"), request()
    )
    assert result.tenant.org_id == "dev-org"
    assert result.production_written is False


def test_exactly_twelve_unique_sources_are_required() -> None:
    with pytest.raises(ValidationError):
        request(source_observations=sources()[:-1])
    duplicate = sources()
    duplicate[-1] = duplicate[0]
    with pytest.raises(ValidationError, match="P01 through P12"):
        request(source_observations=duplicate)


def test_cross_cutoff_sources_are_inconclusive_and_produce_no_plan() -> None:
    result = compile_daily_operating_loop(
        TenantContext(org_id="org-org", project_id="dev-project"),
        request(source_observations=sources(source_index=4, cutoff_at=CUTOFF - timedelta(hours=1))),
    )
    assert result.state is DailyOperatingState.INCONCLUSIVE
    assert result.plan_spec is None
    assert "DAILY_SOURCE_CUTOFF_MISMATCH" in {item.code for item in result.blockers}


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        ({"status": "failed"}, "DAILY_SOURCE_LATEST_RUN_NOT_SUCCEEDED"),
        ({"reconciliation_passed": False}, "DAILY_SOURCE_RECONCILIATION_FAILED"),
        ({"projection_count": 999}, "DAILY_SOURCE_COUNT_MISMATCH"),
        ({"fresh_until": CUTOFF + timedelta(minutes=1)}, "DAILY_SOURCE_STALE"),
    ],
)
def test_latest_source_failure_never_hidden_by_historical_green(
    changes: dict[str, object], code: str
) -> None:
    result = compile_daily_operating_loop(
        TenantContext(org_id="org-org", project_id="dev-project"),
        request(source_observations=sources(source_index=2, **changes)),
    )
    assert result.plan_spec is None
    assert code in {item.code for item in result.blockers}


def test_missing_research_or_wiki_is_inconclusive_not_fake_zero() -> None:
    no_research = compile_daily_operating_loop(
        TenantContext(org_id="org-org", project_id="dev-project"),
        request(research_evidence_refs=[]),
    )
    assert no_research.state is DailyOperatingState.INCONCLUSIVE
    assert no_research.plan_spec is None
    assert "DAILY_RESEARCH_EVIDENCE_MISSING" in {item.code for item in no_research.blockers}


def test_logic_chain_requires_canonical_d01_through_d06_order() -> None:
    invalid = stages()
    invalid[0], invalid[1] = invalid[1], invalid[0]
    with pytest.raises(ValidationError, match="D01 through D06"):
        request(logic_stages=invalid)


def test_d04_materialization_requires_exact_approved_current_plan() -> None:
    proposal = propose_task_graph_materialization(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        plan_ref=ref("GrowthPlanRevision", "growth-plan-1", 3),
        approval_ref=ref("GrowthApprovalEventRevision", "approval-1"),
        approved_plan_ref=ref("GrowthPlanRevision", "growth-plan-1", 3),
        current_plan_ref=ref("GrowthPlanRevision", "growth-plan-1", 3),
    )
    assert proposal.status == "draft"
    assert proposal.execution_authorized is False
    assert proposal.production_written is False


@pytest.mark.parametrize(
    ("approved_revision", "current_revision"),
    [(2, 3), (3, 2)],
)
def test_d04_rejects_stale_or_unapproved_plan(
    approved_revision: int,
    current_revision: int,
) -> None:
    with pytest.raises(ValueError, match="current, approved exact plan revision"):
        propose_task_graph_materialization(
            tenant=TenantContext(org_id="org-org", project_id="dev-project"),
            plan_ref=ref("GrowthPlanRevision", "growth-plan-1", 3),
            approval_ref=ref("GrowthApprovalEventRevision", "approval-1"),
            approved_plan_ref=ref(
                "GrowthPlanRevision", "growth-plan-1", approved_revision
            ),
            current_plan_ref=ref(
                "GrowthPlanRevision", "growth-plan-1", current_revision
            ),
        )


def test_effect_binding_reuses_canonical_review_and_keeps_axes_separate() -> None:
    binding = GrowthEffectBinding(
        effect_review_ref=ref("EffectReviewRevision", "review-1"),
        accepted=True,
        effect_completed=False,
        maturity_status="immature",
        outcome="inconclusive",
    )
    assert binding.accepted is True
    assert binding.effect_completed is False
    with pytest.raises(ValidationError, match="mature"):
        GrowthEffectBinding(
            effect_review_ref=ref("EffectReviewRevision", "review-2"),
            accepted=True,
            effect_completed=True,
            maturity_status="immature",
            outcome="effective",
        )


def test_wrong_exact_authority_types_fail_closed() -> None:
    with pytest.raises(ValidationError, match="SourceReadinessEvidencePackRevision"):
        request(source_evidence_pack_ref=ref("EvidencePack", "wrong"))
