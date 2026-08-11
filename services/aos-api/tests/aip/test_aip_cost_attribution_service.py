from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_cost_attribution_service import AipCostAttributionService
from aos_api.aip_eval_authority_store import AipEvalAuthorityConflict
from aos_api.aip_eval_contracts import (
    AttributionSubjectType,
    CapabilityReceiptIngestRequest,
    CapabilityReceiptStatus,
    EvidenceQuality,
    UsageAdjustmentRequest,
    UsageAttributionRequest,
    UsageKind,
    UsageReceiptIngestRequest,
)
from aos_api.aip_telemetry_usage_service import AipTelemetryUsageService
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("dev-org", "dev-project")
OTHER = TenantScope("org-org", "dev-project")
HASH = "a" * 64
H2 = "b" * 64
NOW = datetime(2026, 8, 12, tzinfo=UTC)


@pytest.fixture()
def authority_chain() -> dict[str, str]:
    suffix = uuid.uuid4().hex[:12]
    task_id = f"task-{suffix}"
    plan_id = f"plan-{suffix}"
    run_id = f"run-{suffix}"
    lineage_id = f"lineage-{suffix}"
    capability = ResourceRef(
        resource_type="capability",
        resource_id="browser.navigate",
        revision="3",
        authority="aos.plan",
    )
    step = {
        "stepKey": "navigate",
        "title": "navigate",
        "capabilityRef": capability.model_dump(mode="json", by_alias=True),
        "inputRefs": [],
    }
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_task (
                 org_id,project_id,task_id,task_type,title,status,idempotency_key,
                 request_hash,current_plan_revision_id,created_by
               ) VALUES (%s,%s,%s,'test','test','executing',%s,%s,%s,'tester')""",
            (*SCOPE.key, task_id, f"idem-{suffix}", HASH, plan_id),
        )
        conn.execute(
            """INSERT INTO aip_plan_revision (
                 org_id,project_id,plan_revision_id,task_id,revision,content_hash,
                 steps,approval_status,idempotency_key,request_hash,created_by
               ) VALUES (%s,%s,%s,%s,1,%s,%s::jsonb,'approved',%s,%s,'tester')""",
            (
                *SCOPE.key,
                plan_id,
                task_id,
                HASH,
                __import__("json").dumps([step]),
                f"plan-idem-{suffix}",
                HASH,
            ),
        )
        conn.execute(
            """INSERT INTO aip_task_run (
                 org_id,project_id,run_id,task_id,plan_revision_id,status,
                 idempotency_key,request_hash,created_by
               ) VALUES (%s,%s,%s,%s,%s,'running',%s,%s,'tester')""",
            (*SCOPE.key, run_id, task_id, plan_id, f"run-idem-{suffix}", HASH),
        )
        conn.execute(
            """INSERT INTO aip_lineage_event (
                 org_id,project_id,event_id,lineage_id,root_type,root_id,sequence,
                 event_type,payload_hash,quality,occurred_at,observed_at,
                 source_kind,source_id,source_hash
               ) VALUES (%s,%s,%s,%s,'task_run',%s,1,'input',%s,'measured',
                 %s,%s,'task_run',%s,%s)""",
            (
                *SCOPE.key,
                f"event-{suffix}",
                lineage_id,
                run_id,
                HASH,
                NOW,
                NOW,
                f"{run_id}:v1",
                HASH,
            ),
        )
        conn.commit()
    return {
        "task_id": task_id,
        "plan_id": plan_id,
        "run_id": run_id,
        "lineage_id": lineage_id,
        "capability_id": capability.resource_id,
        "capability_revision": capability.revision or "",
    }


def _cost_receipt(lineage_id: str, *, quality: EvidenceQuality, quantity: float | None):
    return AipTelemetryUsageService().ingest_usage(
        SCOPE,
        UsageReceiptIngestRequest(
            provider="billing",
            provider_receipt_id=f"bill-{uuid.uuid4().hex}",
            lineage_id=lineage_id,
            usage_kind=UsageKind.COST,
            quantity=quantity,
            unit="major_currency",
            currency="CNY",
            quality=quality,
            source_hash=HASH,
            observed_at=NOW,
        ),
    )


def test_capability_receipt_requires_exact_approved_plan_binding(
    authority_chain,
) -> None:
    service = AipCostAttributionService()
    request = CapabilityReceiptIngestRequest(
        provider="browser-runtime",
        provider_receipt_id=f"cap-{uuid.uuid4().hex}",
        lineage_id=authority_chain["lineage_id"],
        task_run_id=authority_chain["run_id"],
        step_key="navigate",
        capability=ResourceRef(
            resource_type="capability",
            resource_id=authority_chain["capability_id"],
            revision=authority_chain["capability_revision"],
            authority="aos.plan",
        ),
        status=CapabilityReceiptStatus.SUCCEEDED,
        quality=EvidenceQuality.MEASURED,
        input_hash=HASH,
        output_hash=H2,
        source_hash=HASH,
        observed_at=NOW,
    )
    first = service.ingest_capability_receipt(SCOPE, request)
    assert service.ingest_capability_receipt(SCOPE, request) == first
    assert service.list_capability_receipts(SCOPE, authority_chain["lineage_id"]) == [
        first
    ]
    assert service.list_capability_receipts(OTHER, authority_chain["lineage_id"]) == []
    with pytest.raises(AipEvalAuthorityConflict, match="binding"):
        service.ingest_capability_receipt(
            SCOPE,
            request.model_copy(
                update={
                    "provider_receipt_id": f"cap-{uuid.uuid4().hex}",
                    "capability": request.capability.model_copy(
                        update={"revision": "4"}
                    ),
                }
            ),
        )
    with pytest.raises(AipEvalAuthorityConflict, match="different content"):
        service.ingest_capability_receipt(
            SCOPE,
            request.model_copy(update={"source_hash": H2}),
        )


def test_cost_summary_separates_quality_and_applies_adjustments(
    authority_chain,
) -> None:
    service = AipCostAttributionService()
    telemetry = AipTelemetryUsageService()
    measured = _cost_receipt(
        authority_chain["lineage_id"], quality=EvidenceQuality.MEASURED, quantity=10
    )
    estimated = _cost_receipt(
        authority_chain["lineage_id"], quality=EvidenceQuality.ESTIMATED, quantity=4
    )
    subject = ResourceRef(
        resource_type="task",
        resource_id=authority_chain["task_id"],
        revision=authority_chain["plan_id"],
        authority="aos.task",
    )
    for receipt in (measured, estimated):
        attribution = service.attribute_usage(
            SCOPE,
            UsageAttributionRequest(
                receipt_id=receipt.receipt_id,
                subject_type=AttributionSubjectType.TASK,
                subject=subject,
                quality=receipt.quality,
                weight=1,
                source_hash=HASH,
            ),
        )
        assert (
            service.attribute_usage(
                SCOPE,
                UsageAttributionRequest(
                    receipt_id=receipt.receipt_id,
                    subject_type=AttributionSubjectType.TASK,
                    subject=subject,
                    quality=receipt.quality,
                    weight=1,
                    source_hash=HASH,
                ),
            )
            == attribution
        )
    telemetry.append_adjustment(
        SCOPE,
        UsageAdjustmentRequest(
            adjustment_id=f"adj-{uuid.uuid4().hex}",
            receipt_id=measured.receipt_id,
            delta=-2,
            reason_hash=H2,
        ),
        actor="tester",
        created_at=NOW,
    )
    summaries = service.summarize_cost(
        SCOPE,
        subject_type=AttributionSubjectType.TASK,
        subject_id=authority_chain["task_id"],
        subject_revision=authority_chain["plan_id"],
    )
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.measured_amount == 8
    assert summary.estimated_amount == 4
    assert summary.unknown_receipt_count == 0
    assert summary.hard_budget_eligible is False
    assert summary.hard_budget_amount is None


def test_measured_cost_is_hard_budget_eligible_only_without_gaps(
    authority_chain,
) -> None:
    service = AipCostAttributionService()
    receipt = _cost_receipt(
        authority_chain["lineage_id"],
        quality=EvidenceQuality.MEASURED,
        quantity=6,
    )
    service.attribute_usage(
        SCOPE,
        UsageAttributionRequest(
            receipt_id=receipt.receipt_id,
            subject_type=AttributionSubjectType.TASK,
            subject=ResourceRef(
                resource_type="task",
                resource_id=authority_chain["task_id"],
                revision=authority_chain["plan_id"],
                authority="aos.task",
            ),
            quality=EvidenceQuality.MEASURED,
            weight=1,
            source_hash=HASH,
        ),
    )
    summary = service.summarize_cost(
        SCOPE,
        subject_type=AttributionSubjectType.TASK,
        subject_id=authority_chain["task_id"],
        subject_revision=authority_chain["plan_id"],
    )[0]
    assert summary.hard_budget_eligible is True
    assert summary.hard_budget_amount == 6


def test_attribution_weights_cannot_double_count_same_dimension(
    authority_chain,
) -> None:
    service = AipCostAttributionService()
    receipt = _cost_receipt(
        authority_chain["lineage_id"],
        quality=EvidenceQuality.ESTIMATED,
        quantity=3,
    )
    for model_id, weight in (("model-a", 0.7), ("model-b", 0.4)):
        request = UsageAttributionRequest(
            receipt_id=receipt.receipt_id,
            subject_type=AttributionSubjectType.MODEL,
            subject=ResourceRef(
                resource_type="model",
                resource_id=model_id,
                revision="1",
                authority="legacy.model",
            ),
            quality=EvidenceQuality.ESTIMATED,
            weight=weight,
            source_hash=HASH,
        )
        if model_id == "model-a":
            service.attribute_usage(SCOPE, request)
        else:
            with pytest.raises(AipEvalAuthorityConflict, match="weight"):
                service.attribute_usage(SCOPE, request)


def test_unowned_model_cannot_claim_measured_attribution(authority_chain) -> None:
    receipt = _cost_receipt(
        authority_chain["lineage_id"], quality=EvidenceQuality.MEASURED, quantity=3
    )
    with pytest.raises(AipEvalAuthorityConflict, match="authority registry"):
        AipCostAttributionService().attribute_usage(
            SCOPE,
            UsageAttributionRequest(
                receipt_id=receipt.receipt_id,
                subject_type=AttributionSubjectType.MODEL,
                subject=ResourceRef(
                    resource_type="model",
                    resource_id="model-1",
                    revision="1",
                    authority="legacy.model",
                ),
                quality=EvidenceQuality.MEASURED,
                weight=1,
                source_hash=HASH,
            ),
        )


def test_adjustment_cannot_make_effective_usage_negative(authority_chain) -> None:
    receipt = _cost_receipt(
        authority_chain["lineage_id"], quality=EvidenceQuality.MEASURED, quantity=1
    )
    with pytest.raises(AipEvalAuthorityConflict, match="negative"):
        AipTelemetryUsageService().append_adjustment(
            SCOPE,
            UsageAdjustmentRequest(
                adjustment_id=f"adj-{uuid.uuid4().hex}",
                receipt_id=receipt.receipt_id,
                delta=-2,
                reason_hash=H2,
            ),
            actor="tester",
            created_at=NOW,
        )
