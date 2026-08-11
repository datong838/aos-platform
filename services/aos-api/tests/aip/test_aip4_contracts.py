from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_contracts import ArtifactRef, TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    DatasetRevisionRef,
    EvalCaseDefinition,
    EvalCaseKind,
    EvalSuiteRevision,
    EvidenceQuality,
    JudgeRevisionRef,
    LineageEvent,
    LineageEventType,
    LineageRootType,
    MetricDefinitionRevision,
    ReleaseGateDecision,
    ReleaseGateStatus,
    UsageKind,
    UsageReceipt,
)

HASH = "a" * 64
NOW = datetime(2026, 8, 11, tzinfo=UTC)


def asset(asset_type: AssetType = AssetType.LOGIC_GRAPH) -> AssetRevisionRef:
    return AssetRevisionRef(
        asset_type=asset_type,
        asset_id="logic-1",
        revision="7",
        content_hash=HASH,
    )


def artifact(name: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=name,
        artifact_type="json",
        revision="1",
        content_hash=HASH,
    )


def test_suite_revision_freezes_dataset_judge_and_unique_cases() -> None:
    dataset = DatasetRevisionRef(
        dataset_id="dataset-1",
        revision=1,
        content_hash=HASH,
        source_hash="b" * 64,
        redaction_policy=asset(AssetType.POLICY),
    )
    suite = EvalSuiteRevision(
        suite_id="suite-1",
        revision=1,
        content_hash=HASH,
        target=asset(),
        dataset=dataset,
        judge=JudgeRevisionRef(
            judge_id="judge-1", revision=1, content_hash=HASH
        ),
        cases=[
            EvalCaseDefinition(
                case_id="positive-1",
                kind=EvalCaseKind.POSITIVE,
                input_artifact=artifact("input-1"),
                timeout_ms=30_000,
            )
        ],
        gate_threshold=0.9,
    )
    dumped = suite.model_dump(mode="json", by_alias=True)
    assert dumped["target"]["assetType"] == "logic_graph"
    assert dumped["dataset"]["redactionPolicy"]["assetType"] == "policy"

    with pytest.raises(ValidationError, match="unique"):
        EvalSuiteRevision(
            **{
                **suite.model_dump(),
                "cases": [suite.cases[0], suite.cases[0]],
            }
        )


def test_lineage_rejects_impossible_observation_order() -> None:
    with pytest.raises(ValidationError, match="observed_at"):
        LineageEvent(
            tenant=TenantContext(org_id="org-org", project_id="dev-project"),
            event_id="event-1",
            lineage_id="lineage-1",
            root_type=LineageRootType.TASK_RUN,
            root_id="run-1",
            sequence=1,
            event_type=LineageEventType.INPUT,
            payload_hash=HASH,
            quality=EvidenceQuality.MEASURED,
            occurred_at=NOW,
            observed_at=NOW - timedelta(seconds=1),
        )


def test_usage_cost_requires_currency_and_estimated_stays_explicit() -> None:
    common = dict(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        receipt_id="usage-1",
        provider="provider-1",
        provider_receipt_id="provider-receipt-1",
        lineage_id="lineage-1",
        usage_kind=UsageKind.COST,
        quantity=1.25,
        unit="major_currency",
        quality=EvidenceQuality.ESTIMATED,
        source_hash=HASH,
        observed_at=NOW,
    )
    with pytest.raises(ValidationError, match="currency"):
        UsageReceipt(**common)
    receipt = UsageReceipt(**common, currency="CNY")
    assert receipt.quality is EvidenceQuality.ESTIMATED


def test_invalidated_gate_requires_causal_reference() -> None:
    common = dict(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        decision_id="gate-1",
        target=asset(),
        suite_ref=asset(AssetType.EVAL_SUITE),
        eval_run_id="eval-run-1",
        eval_report=artifact("report-1"),
        status=ReleaseGateStatus.INVALIDATED,
        decision_hash=HASH,
        decided_by="dev-user",
        decided_at=NOW,
    )
    with pytest.raises(ValidationError, match="invalidated_by"):
        ReleaseGateDecision(**common)
    gate = ReleaseGateDecision(**common, invalidated_by="asset-revision-change")
    assert gate.status is ReleaseGateStatus.INVALIDATED


def test_release_gate_requires_exact_report_reference() -> None:
    with pytest.raises(ValidationError, match="exact eval report"):
        ReleaseGateDecision(
            tenant=TenantContext(org_id="org-org", project_id="dev-project"),
            decision_id="gate-1",
            target=asset(),
            suite_ref=asset(AssetType.EVAL_SUITE),
            eval_run_id="eval-run-1",
            eval_report=ArtifactRef(
                artifact_id="report-1", artifact_type="eval_report"
            ),
            status=ReleaseGateStatus.PASSED,
            decision_hash=HASH,
            decided_by="alice",
            decided_at=NOW,
        )


def test_metric_quality_set_is_non_empty_and_unique() -> None:
    definition = MetricDefinitionRevision(
        metric_id="token-cost",
        revision=1,
        content_hash=HASH,
        name="Token 成本",
        unit="CNY",
        source="provider_usage_receipt",
        window="run",
        aggregation="sum",
        accepted_quality=[EvidenceQuality.MEASURED],
    )
    assert definition.accepted_quality == [EvidenceQuality.MEASURED]
    with pytest.raises(ValidationError, match="duplicates"):
        MetricDefinitionRevision(
            **{
                **definition.model_dump(),
                "accepted_quality": [
                    EvidenceQuality.MEASURED,
                    EvidenceQuality.MEASURED,
                ],
            }
        )
