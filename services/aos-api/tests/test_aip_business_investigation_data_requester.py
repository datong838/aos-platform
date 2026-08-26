"""BI-W5-04 missing-fact DataRequirement requester tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_business_investigation_data_requester import (
    BusinessInvestigationDataRequester,
    BusinessInvestigationDataRequestBlocked,
    MissingFactDataRequest,
)
from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinding,
    CanonicalCheckpointRef,
    CanonicalRuntimeRef,
)
from aos_api.aip_contracts import TaskRunStatus, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_store import (
    DataRequirementApplyResult,
    canonical_revision_content_hash,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def exact(kind: str, identity: str, fill: str) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind,
        resource_id=identity,
        revision=1,
        content_hash=fill * 64,
    )


def investigation_ref(kind: str, identity: str) -> InvestigationExactRef:
    return InvestigationExactRef(
        resource_type=kind,
        resource_id=identity,
        revision=1,
        content_hash=f"sha256:{'a' * 64}",
    )


def runtime(*, checkpoint=True) -> BusinessInvestigationRuntimeBinding:
    return BusinessInvestigationRuntimeBinding(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        case_ref=exact("BusinessInvestigationCaseRevision", "case-1", "1"),
        business_investigation_run_ref=exact(
            "BusinessInvestigationRun", "investigation-run-1", "2"
        ),
        compilation_hash="3" * 64,
        task_ref=CanonicalRuntimeRef(
            resource_type="Task", resource_id="task-1", version=2
        ),
        plan_ref=exact("PlanRevision", "plan-1", "4"),
        task_run_ref=CanonicalRuntimeRef(
            resource_type="TaskRun", resource_id="task-run-1", version=3
        ),
        checkpoint_ref=(
            CanonicalCheckpointRef(
                resource_id="checkpoint-1", sequence=1, state_hash="5" * 64
            )
            if checkpoint
            else None
        ),
        task_run_status=TaskRunStatus.PAUSED,
        plan_step_count=3,
        binding_hash="6" * 64,
        start_authorized=False,
    )


def request(**changes) -> MissingFactDataRequest:
    value = {
        "requirementId": "requirement-1",
        "idempotencyKey": "requirement-request-1",
        "purposeCode": "business_portrait_gap",
        "channelRef": investigation_ref("ChannelRevision", "channel-1"),
        "entityRef": investigation_ref("BusinessEntityRevision", "shop-1"),
        "requiredFacts": ["Order.daily_amount", "Product.active_count"],
        "timeWindow": {
            "startAt": NOW - timedelta(days=30),
            "endAt": NOW - timedelta(minutes=5),
        },
        "grain": "day",
        "cutoffAt": NOW,
        "freshnessMaxAgeSeconds": 3600,
        "qualityThreshold": 0.95,
        "markings": ["INTERNAL"],
        "minPopulation": 20,
        "acceptableDegradation": ["narrow_time_window"],
        "requestedOutputs": ["DataProductRevision", "EvidenceBundleRevision"],
        "budgetMinor": 1000,
        "expiresAt": NOW + timedelta(days=1),
    }
    value.update(changes)
    return MissingFactDataRequest.model_validate(value)


class FixedRequester:
    def __init__(self) -> None:
        self.calls = []

    def request(self, scope, actor, idempotency_key, item, *, expected_version):
        self.calls.append((scope, actor, idempotency_key, item, expected_version))
        return DataRequirementApplyResult(
            exact_ref=InvestigationExactRef(
                resource_type="DataRequirementRevision",
                resource_id=item.requirement_id,
                revision=1,
                content_hash=item.content_hash,
            ),
            version=1,
            etag=item.content_hash,
            replayed=False,
        )


def test_missing_facts_delegate_to_canonical_request_only() -> None:
    store = FixedRequester()
    result = BusinessInvestigationDataRequester(store).request_missing_facts(
        SCOPE, runtime(), request(), "aip:investigation", created_at=NOW
    )

    assert result.exact_ref.resource_type == "DataRequirementRevision"
    assert len(store.calls) == 1
    scope, actor, key, item, expected_version = store.calls[0]
    assert (scope, actor, key, expected_version) == (
        SCOPE,
        "aip:investigation",
        "requirement-request-1",
        0,
    )
    assert item.status.value == "requested"
    assert item.revision == 1 and item.prior_ref is None
    assert item.case_ref.resource_id == runtime().case_ref.resource_id
    assert item.run_ref.resource_id == runtime().business_investigation_run_ref.resource_id
    assert item.checkpoint_ref.resource_id == "checkpoint-1"
    assert item.pii_allowed is False
    assert item.content_hash == canonical_revision_content_hash(item)


def test_checkpoint_cross_tenant_or_time_drift_blocks_before_store() -> None:
    store = FixedRequester()
    requester = BusinessInvestigationDataRequester(store)
    with pytest.raises(
        BusinessInvestigationDataRequestBlocked, match="CHECKPOINT_REQUIRED"
    ):
        requester.request_missing_facts(
            SCOPE, runtime(checkpoint=False), request(), "owner", created_at=NOW
        )
    with pytest.raises(
        BusinessInvestigationDataRequestBlocked, match="RUNTIME_TENANT_MISMATCH"
    ):
        requester.request_missing_facts(
            OTHER_SCOPE, runtime(), request(), "owner", created_at=NOW
        )
    with pytest.raises(
        BusinessInvestigationDataRequestBlocked, match="CUTOFF_AFTER_CREATED_AT"
    ):
        requester.request_missing_facts(
            SCOPE,
            runtime(),
            request(cutoffAt=NOW + timedelta(minutes=1)),
            "owner",
            created_at=NOW,
        )
    with pytest.raises(
        BusinessInvestigationDataRequestBlocked, match="REQUIREMENT_ALREADY_EXPIRED"
    ):
        requester.request_missing_facts(
            SCOPE,
            runtime(),
            request(expiresAt=NOW),
            "owner",
            created_at=NOW,
        )
    assert store.calls == []


def test_request_contract_rejects_duplicate_or_payload_shaped_facts() -> None:
    with pytest.raises(ValidationError, match="requiredFacts must be unique"):
        request(requiredFacts=["Order.amount", "Order.amount"])
    with pytest.raises(ValidationError, match="bounded fact identifiers"):
        request(requiredFacts=["SELECT * FROM orders"])
    with pytest.raises(ValidationError, match="ChannelRevision"):
        request(channelRef=investigation_ref("DataSourceRevision", "source-1"))
    with pytest.raises(ValidationError, match="timeWindow"):
        request(
            timeWindow={
                "startAt": NOW - timedelta(days=1),
                "endAt": NOW + timedelta(minutes=1),
            }
        )


def test_non_canonical_output_is_rejected_before_store_call() -> None:
    store = FixedRequester()
    with pytest.raises(ValidationError, match="non-canonical output type"):
        BusinessInvestigationDataRequester(store).request_missing_facts(
            SCOPE,
            runtime(),
            request(requestedOutputs=["RawSourceRows"]),
            "owner",
            created_at=NOW,
        )
    assert store.calls == []
