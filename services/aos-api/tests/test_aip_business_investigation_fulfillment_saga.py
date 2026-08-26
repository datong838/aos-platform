"""BI-W6-03 exact Fulfillment-to-AIP resume saga tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aos_api.aip_business_investigation_data_saga import (
    BusinessInvestigationDataRequirementCommandResult,
)
from aos_api.aip_business_investigation_evidence import (
    BusinessInvestigationEvidenceBuilder,
)
from aos_api.aip_business_investigation_fulfillment_saga import (
    BusinessInvestigationFulfillmentResumeBlocked,
    BusinessInvestigationFulfillmentResumeSaga,
)
from aos_api.aip_business_investigation_runtime import CanonicalCheckpointRef
from aos_api.aip_contracts import TaskRunStatus, TenantContext
from aos_api.aip_production_contracts import Coverage, Freshness
from aos_api.aip_task_models import RunControlResult, TaskRunSnapshot, TaskSnapshot
from aos_api.business_investigation_hydration import SemanticHydrationReceipt
from aos_api.business_investigation_shared_contracts import (
    FulfillmentStatus,
    InvestigationExactRef,
)
from aos_api.data_fulfillment_store import canonical_fulfillment_content_hash
from aos_api.data_requirement_contracts import DataFulfillmentReceiptRecord
from aos_api.public_contracts import TaskStatus
from aos_api.source_readiness_contracts import ExactResourceRef, SourceReadinessStatus
from aos_api.tenant_scope import TenantScope
from test_aip_business_investigation_evidence import (
    FixedBuilder,
    bundle,
    request as evidence_request,
    runtime,
)
from test_business_investigation_semantic_hydration import receipt_payload
from test_source_readiness_investigation_projection import (
    envelope,
    projection,
)


SCOPE = TenantScope("org-org", "dev-project")
CUTOFF = datetime(2026, 8, 26, 5, 30, tzinfo=UTC)
NOW = CUTOFF + timedelta(minutes=30)


def exact(kind: str, identity: str, fill: str, *, receipt_id: str | None = None):
    value = {
        "resourceType": kind,
        "resourceId": identity,
        "revision": 1,
        "contentHash": f"sha256:{fill * 64}",
    }
    if receipt_id is not None:
        value["receiptId"] = receipt_id
    return value


def data_command(**changes) -> BusinessInvestigationDataRequirementCommandResult:
    value = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "commandId": "bi-data-requirement-1",
        "requestHash": "sha256:" + "a" * 64,
        "compilationReceiptRef": exact(
            "BusinessInvestigationCompilationReceipt", "compile-receipt-1", "b"
        ),
        "checkpointRef": exact("CheckpointRevision", "checkpoint-1", "5"),
        "dataRequirementRef": exact(
            "DataRequirementRevision", "data-requirement-1", "c"
        ),
        "replayed": False,
    }
    value.update(changes)
    return BusinessInvestigationDataRequirementCommandResult.model_validate(value)


def evidence_response(*, complete: bool = True):
    authority = FixedBuilder()
    req = evidence_request(cutoffAt=CUTOFF)
    authority.result = bundle(
        req,
        coverage=Coverage.COMPLETE if complete else Coverage.PARTIAL,
        missing=[] if complete else [{"factId": "Customer.repeat_rate"}],
        conflicts=[],
        uncertainties=[],
    ).model_copy(
        update={"freshness": Freshness.FRESH if complete else Freshness.STALE}
    )
    return BusinessInvestigationEvidenceBuilder(authority).build(
        SCOPE, runtime(), req, "aip:investigation", created_at=NOW
    )


def hydration(**changes) -> SemanticHydrationReceipt:
    value = receipt_payload(
        tenant={"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        hydrationId="hydration-1",
        contentHash="sha256:" + "7" * 64,
        outputRefs=[exact("DataProductRevision", "data-product-1", "8")],
        unknownFields=[],
        unmetSemanticFacts=[],
        counts={
            "attempted": 1,
            "created": 1,
            "updated": 0,
            "quarantined": 0,
            "unknown": 0,
        },
        hydratedAt=CUTOFF + timedelta(minutes=5),
    )
    value.update(changes)
    return SemanticHydrationReceipt.model_validate(value)


def readiness(**projection_changes):
    requirement = {
        "resourceType": "DataRequirementRevision",
        "resourceId": "data-requirement-1",
        "revision": "1",
        "contentHash": "c" * 64,
        "authority": "data-requirement",
    }
    investigation = projection(
        requirementRef=requirement,
        requiredCutoff=CUTOFF,
        freshnessExpiresAt=NOW + timedelta(minutes=30),
        **projection_changes,
    )
    return envelope(investigation=investigation).model_copy(
        update={
            "receipt_ref": ExactResourceRef(
                resource_type="SourceReadinessEnvelope",
                resource_id="readiness-1",
                revision="1",
                content_hash="e" * 64,
                authority="data-adapter",
            )
        }
    )


def fulfillment(**changes) -> DataFulfillmentReceiptRecord:
    evidence = evidence_response()
    value = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "fulfillmentId": "fulfillment-1",
        "receiptId": "fulfillment-receipt-1",
        "requirementRef": exact(
            "DataRequirementRevision", "data-requirement-1", "c"
        ),
        "status": "fulfilled",
        "artifactRefs": [
            exact("DataProductRevision", "data-product-1", "8"),
            exact(
                "EvidenceBundleRevision",
                evidence.receipt.evidence_bundle_ref.resource_id,
                "d",
            ),
        ],
        "sourceReadinessRef": exact(
            "SourceReadinessEnvelope",
            "readiness-1",
            "e",
            receipt_id="readiness-1",
        ),
        "cutoffAt": CUTOFF,
        "fulfilledAt": CUTOFF + timedelta(minutes=10),
        "contentHash": "sha256:" + "0" * 64,
        "createdBy": "data-owner",
        "blockers": [],
    }
    value.update(changes)
    item = DataFulfillmentReceiptRecord.model_validate(value)
    return item.model_copy(update={"content_hash": canonical_fulfillment_content_hash(item)})


def rehash_fulfillment(item: DataFulfillmentReceiptRecord):
    return item.model_copy(update={"content_hash": canonical_fulfillment_content_hash(item)})


class FixedResumer:
    def __init__(self) -> None:
        self.calls = []
        self.drift = False

    def resume_run(
        self,
        scope,
        run_id,
        *,
        expected_run_version,
        expected_task_version,
        actor,
        idempotency_key,
        reason="",
    ):
        self.calls.append(
            (
                scope,
                run_id,
                expected_run_version,
                expected_task_version,
                actor,
                idempotency_key,
                reason,
            )
        )
        task_id = "task-drift" if self.drift else "task-1"
        return RunControlResult(
            task=TaskSnapshot(
                id=task_id,
                type="business-investigation",
                title="investigation",
                description="",
                status=TaskStatus.EXECUTING,
                priority=50,
                goal={},
                created_by={"actorType": "service", "actorId": "aip"},
                created_at=CUTOFF,
                current_plan_revision_id="plan-1",
                version=3,
                updated_at=NOW,
            ),
            run=TaskRunSnapshot(
                id="task-run-1",
                task_id="task-1",
                plan_revision_id="plan-1",
                status=TaskRunStatus.RUNNING,
                last_checkpoint_id="checkpoint-1",
                version=4,
                created_by={"actorType": "service", "actorId": "aip"},
                created_at=CUTOFF,
                updated_at=NOW,
            ),
        )


def test_exact_fulfillment_resume_command_is_stable_and_delegates_canonical_versions() -> None:
    resumer = FixedResumer()
    saga = BusinessInvestigationFulfillmentResumeSaga(resumer)
    args = (
        SCOPE,
        "aip:investigation",
        data_command(),
        fulfillment(),
        hydration(),
        readiness(),
        evidence_response(),
        runtime(),
    )
    first = saga.execute(*args, created_at=NOW)
    second = saga.execute(*args, created_at=NOW)

    assert first.command_id == second.command_id
    assert first.request_hash == second.request_hash
    assert first.task_ref.version == 3 and first.task_run_ref.version == 4
    assert first.task_run_status is TaskRunStatus.RUNNING
    assert first.task_run_transition_count == 1
    assert first.source_read_count == first.provider_invocation_count == 0
    assert first.external_business_mutation_count == 0
    assert first.external_effect_authorized is False
    assert len(resumer.calls) == 2
    call = resumer.calls[0]
    assert call[1:5] == ("task-run-1", 3, 2, "aip:investigation")
    assert call[5] == first.command_id


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (
            lambda values: values.__setitem__(
                "fulfillment",
                values["fulfillment"].model_copy(
                    update={"status": FulfillmentStatus.PARTIAL}
                ),
            ),
            "FULFILLMENT_NOT_COMPLETE",
        ),
        (
            lambda values: values.__setitem__(
                "fulfillment",
                values["fulfillment"].model_copy(
                    update={
                        "requirement_ref": InvestigationExactRef.model_validate(
                            exact("DataRequirementRevision", "other", "c")
                        )
                    }
                ),
            ),
            "REQUIREMENT_LINEAGE_DRIFTED",
        ),
        (
            lambda values: values.__setitem__(
                "hydration",
                values["hydration"].model_copy(
                    update={
                        "output_refs": [
                            InvestigationExactRef.model_validate(
                                exact("DataProductRevision", "other", "8")
                            )
                        ]
                    }
                ),
            ),
            "HYDRATION_OUTPUT_NOT_FULFILLED",
        ),
        (
            lambda values: values.__setitem__(
                "readiness",
                values["readiness"].model_copy(
                    update={"status": SourceReadinessStatus.STALE}
                ),
            ),
            "READINESS_NOT_READY",
        ),
        (
            lambda values: values.__setitem__(
                "readiness",
                values["readiness"].model_copy(
                    update={
                        "investigation": values["readiness"].investigation.model_copy(
                            update={"freshness_expires_at": NOW}
                        )
                    }
                ),
            ),
            "READINESS_STALE",
        ),
        (
            lambda values: values.__setitem__("evidence", evidence_response(complete=False)),
            "EVIDENCE_NOT_READY",
        ),
        (
            lambda values: values.__setitem__(
                "runtime",
                values["runtime"].model_copy(
                    update={"task_run_status": TaskRunStatus.RUNNING}
                ),
            ),
            "TASK_RUN_NOT_PAUSED",
        ),
        (
            lambda values: values.__setitem__(
                "hydration",
                values["hydration"].model_copy(
                    update={
                        "tenant": TenantContext(
                            org_id="dev-org", project_id="dev-project"
                        )
                    }
                ),
            ),
            "TENANT_LINEAGE_DRIFTED",
        ),
        (
            lambda values: values.__setitem__(
                "readiness",
                values["readiness"].model_copy(
                    update={
                        "receipt_ref": ExactResourceRef(
                            resource_type="SourceReadinessEnvelope",
                            resource_id="readiness-other",
                            revision="1",
                            content_hash="e" * 64,
                            authority="data-adapter",
                        )
                    }
                ),
            ),
            "READINESS_RECEIPT_DRIFTED",
        ),
        (
            lambda values: values.__setitem__(
                "readiness",
                values["readiness"].model_copy(
                    update={
                        "investigation": values["readiness"].investigation.model_copy(
                            update={
                                "requirement_ref": ExactResourceRef(
                                    resource_type="DataRequirementRevision",
                                    resource_id="data-requirement-other",
                                    revision="1",
                                    content_hash="c" * 64,
                                    authority="data-requirement",
                                )
                            }
                        )
                    }
                ),
            ),
            "READINESS_REQUIREMENT_DRIFTED",
        ),
        (
            lambda values: values.__setitem__(
                "readiness",
                values["readiness"].model_copy(
                    update={
                        "investigation": values["readiness"].investigation.model_copy(
                            update={"required_cutoff": CUTOFF - timedelta(minutes=1)}
                        )
                    }
                ),
            ),
            "READINESS_CUTOFF_DRIFTED",
        ),
        (
            lambda values: values.__setitem__(
                "evidence",
                values["evidence"].model_copy(
                    update={
                        "receipt": values["evidence"].receipt.model_copy(
                            update={
                                "checkpoint_ref": CanonicalCheckpointRef(
                                    resource_id="checkpoint-other",
                                    sequence=1,
                                    state_hash="5" * 64,
                                )
                            }
                        )
                    }
                ),
            ),
            "EVIDENCE_CHECKPOINT_DRIFTED",
        ),
        (
            lambda values: values.__setitem__(
                "evidence",
                values["evidence"].model_copy(
                    update={
                        "receipt": values["evidence"].receipt.model_copy(
                            update={"runtime_binding_hash": "9" * 64}
                        )
                    }
                ),
            ),
            "EVIDENCE_RUNTIME_BINDING_DRIFTED",
        ),
        (
            lambda values: values.__setitem__(
                "fulfillment",
                rehash_fulfillment(
                    values["fulfillment"].model_copy(
                        update={
                            "artifact_refs": [values["fulfillment"].artifact_refs[0]]
                        }
                    )
                ),
            ),
            "EVIDENCE_NOT_FULFILLED",
        ),
    ],
)
def test_stale_partial_or_drifted_inputs_block_before_resumer(mutate, code) -> None:
    values = {
        "data": data_command(),
        "fulfillment": fulfillment(),
        "hydration": hydration(),
        "readiness": readiness(),
        "evidence": evidence_response(),
        "runtime": runtime(),
    }
    mutate(values)
    resumer = FixedResumer()
    with pytest.raises(BusinessInvestigationFulfillmentResumeBlocked, match=code):
        BusinessInvestigationFulfillmentResumeSaga(resumer).execute(
            SCOPE,
            "aip:investigation",
            values["data"],
            values["fulfillment"],
            values["hydration"],
            values["readiness"],
            values["evidence"],
            values["runtime"],
            created_at=NOW,
        )
    assert resumer.calls == []


def test_resume_result_drift_fails_closed_after_single_canonical_call() -> None:
    resumer = FixedResumer()
    resumer.drift = True
    with pytest.raises(
        BusinessInvestigationFulfillmentResumeBlocked, match="RESUME_RESULT_DRIFTED"
    ):
        BusinessInvestigationFulfillmentResumeSaga(resumer).execute(
            SCOPE,
            "aip:investigation",
            data_command(),
            fulfillment(),
            hydration(),
            readiness(),
            evidence_response(),
            runtime(),
            created_at=NOW,
        )
    assert len(resumer.calls) == 1
