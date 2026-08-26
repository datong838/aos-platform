"""BI-W6-03 exact Fulfillment-to-AIP resume command bridge."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Literal, Protocol

from pydantic import Field, model_validator

from aos_api.aip_business_investigation_data_saga import (
    BusinessInvestigationDataRequirementCommandResult,
)
from aos_api.aip_business_investigation_evidence import (
    BusinessInvestigationEvidenceBuildResponse,
)
from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinding,
    CanonicalRuntimeRef,
)
from aos_api.aip_contracts import AipContractModel, TaskRunStatus, TenantContext
from aos_api.aip_production_contracts import Coverage, ExactRevisionRef, Freshness
from aos_api.aip_task_models import RunControlResult
from aos_api.business_investigation_hydration import (
    HydrationReceiptStatus,
    SemanticHydrationReceipt,
)
from aos_api.business_investigation_shared_contracts import (
    FulfillmentStatus,
    InvestigationExactRef,
)
from aos_api.data_fulfillment_store import canonical_fulfillment_content_hash
from aos_api.data_requirement_contracts import DataFulfillmentReceiptRecord
from aos_api.public_contracts import TaskStatus
from aos_api.source_readiness_contracts import (
    ExactResourceRef,
    SourceReadinessEnvelope,
    SourceReadinessStatus,
)
from aos_api.tenant_scope import TenantScope


SCHEMA_VERSION = "aos.aip.business-investigation-fulfillment-resume-result/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"
RESUME_REASON = "BI-W6-03 exact fulfillment/readiness/evidence resume"


def _canonical_hash(value: object, *, prefixed: bool = True) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"sha256:{digest}" if prefixed else digest


def _stable_id(prefix: str, value: object) -> str:
    return f"{prefix}-{_canonical_hash(value, prefixed=False)}"


def _investigation_ref_from_source(ref: ExactResourceRef) -> InvestigationExactRef:
    try:
        revision = int(ref.revision)
    except ValueError as exc:
        raise BusinessInvestigationFulfillmentResumeBlocked(
            "READINESS_RECEIPT_REVISION_INVALID"
        ) from exc
    if revision < 1:
        raise BusinessInvestigationFulfillmentResumeBlocked(
            "READINESS_RECEIPT_REVISION_INVALID"
        )
    return InvestigationExactRef(
        resource_type=ref.resource_type,
        resource_id=ref.resource_id,
        revision=revision,
        content_hash=f"sha256:{ref.content_hash}",
        receipt_id=ref.resource_id,
    )


def _same_source_requirement(
    source_ref: ExactResourceRef,
    requirement_ref: InvestigationExactRef,
) -> bool:
    return (
        source_ref.resource_type == requirement_ref.resource_type
        and source_ref.resource_id == requirement_ref.resource_id
        and source_ref.revision == str(requirement_ref.revision)
        and f"sha256:{source_ref.content_hash}" == requirement_ref.content_hash
    )


class BusinessInvestigationFulfillmentResumeResult(AipContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    tenant: TenantContext
    command_id: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    data_requirement_ref: InvestigationExactRef
    fulfillment_receipt_ref: InvestigationExactRef
    hydration_receipt_ref: InvestigationExactRef
    source_readiness_ref: InvestigationExactRef
    evidence_bundle_ref: ExactRevisionRef
    checkpoint_ref: InvestigationExactRef
    task_ref: CanonicalRuntimeRef
    task_run_ref: CanonicalRuntimeRef
    task_run_status: Literal[TaskRunStatus.RUNNING] = TaskRunStatus.RUNNING
    task_run_transition_count: Literal[1] = 1
    source_read_count: Literal[0] = 0
    provider_invocation_count: Literal[0] = 0
    external_business_mutation_count: Literal[0] = 0
    external_effect_authorized: Literal[False] = False

    @model_validator(mode="after")
    def _exact_types(self) -> BusinessInvestigationFulfillmentResumeResult:
        expected = (
            (self.data_requirement_ref, "DataRequirementRevision"),
            (self.fulfillment_receipt_ref, "DataFulfillmentReceipt"),
            (self.hydration_receipt_ref, "SemanticHydrationReceipt"),
            (self.source_readiness_ref, "SourceReadinessEnvelope"),
            (self.checkpoint_ref, "CheckpointRevision"),
        )
        for exact_ref, resource_type in expected:
            if exact_ref.resource_type != resource_type:
                raise ValueError(f"exact ref must reference {resource_type}")
        if self.evidence_bundle_ref.resource_type != "EvidenceBundleRevision":
            raise ValueError("evidenceBundleRef must reference EvidenceBundleRevision")
        return self


class BusinessInvestigationFulfillmentResumeBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class CanonicalTaskRunResumer(Protocol):
    def resume_run(
        self,
        scope: TenantScope,
        run_id: str,
        *,
        expected_run_version: int,
        expected_task_version: int,
        actor: str,
        idempotency_key: str,
        reason: str = "",
    ) -> RunControlResult: ...


class BusinessInvestigationFulfillmentResumeSaga:
    """Resume only after exact, current Data and Evidence receipts agree."""

    def __init__(self, resumer: CanonicalTaskRunResumer) -> None:
        self._resumer = resumer

    def execute(
        self,
        scope: TenantScope,
        actor: str,
        data_command: BusinessInvestigationDataRequirementCommandResult,
        fulfillment: DataFulfillmentReceiptRecord,
        hydration: SemanticHydrationReceipt,
        readiness: SourceReadinessEnvelope,
        evidence: BusinessInvestigationEvidenceBuildResponse,
        runtime: BusinessInvestigationRuntimeBinding,
        *,
        created_at: datetime,
    ) -> BusinessInvestigationFulfillmentResumeResult:
        actor = actor.strip()
        if not actor:
            raise BusinessInvestigationFulfillmentResumeBlocked("ACTOR_REQUIRED")
        if created_at.utcoffset() is None:
            raise BusinessInvestigationFulfillmentResumeBlocked(
                "CREATED_AT_TIMEZONE_REQUIRED"
            )
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        self._validate_tenant(
            tenant,
            data_command,
            fulfillment,
            hydration,
            readiness,
            evidence,
            runtime,
        )
        checkpoint_ref = self._validate_runtime(data_command, runtime)
        fulfillment_ref = self._validate_fulfillment(data_command, fulfillment, created_at)
        hydration_ref = self._validate_hydration(fulfillment, hydration, created_at)
        readiness_ref = self._validate_readiness(
            data_command, fulfillment, readiness, created_at
        )
        evidence_ref = self._validate_evidence(
            fulfillment, evidence, checkpoint_ref, runtime
        )

        command_identity = {
            "tenant": tenant.model_dump(mode="json", by_alias=True),
            "dataCommandId": data_command.command_id,
            "dataRequirementRef": data_command.data_requirement_ref.model_dump(
                mode="json", by_alias=True
            ),
            "fulfillmentReceiptRef": fulfillment_ref.model_dump(
                mode="json", by_alias=True
            ),
            "hydrationReceiptRef": hydration_ref.model_dump(
                mode="json", by_alias=True
            ),
            "sourceReadinessRef": readiness_ref.model_dump(
                mode="json", by_alias=True
            ),
            "evidenceBundleRef": evidence_ref.model_dump(
                mode="json", by_alias=True
            ),
            "checkpointRef": checkpoint_ref.model_dump(mode="json", by_alias=True),
        }
        command_id = _stable_id("bi-fulfillment-resume", command_identity)
        request_hash = _canonical_hash(
            {
                **command_identity,
                "commandId": command_id,
                "actor": actor,
                "taskRef": runtime.task_ref.model_dump(mode="json", by_alias=True),
                "taskRunRef": runtime.task_run_ref.model_dump(
                    mode="json", by_alias=True
                ),
                "reason": RESUME_REASON,
            }
        )
        result = self._resumer.resume_run(
            scope,
            runtime.task_run_ref.resource_id,
            expected_run_version=runtime.task_run_ref.version,
            expected_task_version=runtime.task_ref.version,
            actor=actor,
            idempotency_key=command_id,
            reason=RESUME_REASON,
        )
        self._validate_resume_result(result, runtime)
        return BusinessInvestigationFulfillmentResumeResult(
            tenant=tenant,
            command_id=command_id,
            request_hash=request_hash,
            data_requirement_ref=data_command.data_requirement_ref,
            fulfillment_receipt_ref=fulfillment_ref,
            hydration_receipt_ref=hydration_ref,
            source_readiness_ref=readiness_ref,
            evidence_bundle_ref=evidence_ref,
            checkpoint_ref=checkpoint_ref,
            task_ref=CanonicalRuntimeRef(
                resource_type="Task",
                resource_id=result.task.id,
                version=result.task.version,
            ),
            task_run_ref=CanonicalRuntimeRef(
                resource_type="TaskRun",
                resource_id=result.run.id,
                version=result.run.version,
            ),
        )

    @staticmethod
    def _validate_tenant(
        tenant, data_command, fulfillment, hydration, readiness, evidence, runtime
    ) -> None:
        if any(
            value.tenant != tenant
            for value in (data_command, fulfillment, hydration, readiness, evidence, runtime)
        ):
            raise BusinessInvestigationFulfillmentResumeBlocked("TENANT_LINEAGE_DRIFTED")

    @staticmethod
    def _validate_runtime(data_command, runtime) -> InvestigationExactRef:
        if runtime.task_run_status is not TaskRunStatus.PAUSED:
            raise BusinessInvestigationFulfillmentResumeBlocked("TASK_RUN_NOT_PAUSED")
        if runtime.checkpoint_ref is None:
            raise BusinessInvestigationFulfillmentResumeBlocked("CHECKPOINT_REQUIRED")
        checkpoint_ref = InvestigationExactRef(
            resource_type="CheckpointRevision",
            resource_id=runtime.checkpoint_ref.resource_id,
            revision=runtime.checkpoint_ref.sequence,
            content_hash=f"sha256:{runtime.checkpoint_ref.state_hash}",
        )
        if checkpoint_ref != data_command.checkpoint_ref:
            raise BusinessInvestigationFulfillmentResumeBlocked("CHECKPOINT_LINEAGE_DRIFTED")
        return checkpoint_ref

    @staticmethod
    def _validate_fulfillment(data_command, fulfillment, created_at) -> InvestigationExactRef:
        if fulfillment.status is not FulfillmentStatus.FULFILLED:
            raise BusinessInvestigationFulfillmentResumeBlocked("FULFILLMENT_NOT_COMPLETE")
        if fulfillment.requirement_ref != data_command.data_requirement_ref:
            raise BusinessInvestigationFulfillmentResumeBlocked("REQUIREMENT_LINEAGE_DRIFTED")
        if fulfillment.content_hash != canonical_fulfillment_content_hash(fulfillment):
            raise BusinessInvestigationFulfillmentResumeBlocked("FULFILLMENT_HASH_DRIFTED")
        if fulfillment.fulfilled_at > created_at:
            raise BusinessInvestigationFulfillmentResumeBlocked("FULFILLMENT_FROM_FUTURE")
        return InvestigationExactRef(
            resource_type="DataFulfillmentReceipt",
            resource_id=fulfillment.receipt_id,
            revision=1,
            content_hash=fulfillment.content_hash,
            receipt_id=fulfillment.receipt_id,
        )

    @staticmethod
    def _validate_hydration(fulfillment, hydration, created_at) -> InvestigationExactRef:
        if hydration.status is not HydrationReceiptStatus.SUCCEEDED or hydration.blockers:
            raise BusinessInvestigationFulfillmentResumeBlocked("HYDRATION_NOT_SUCCEEDED")
        if hydration.hydrated_at < fulfillment.cutoff_at or hydration.hydrated_at > created_at:
            raise BusinessInvestigationFulfillmentResumeBlocked("HYDRATION_CUTOFF_DRIFTED")
        fulfilled_artifacts = {
            (ref.resource_type, ref.resource_id, ref.revision, ref.content_hash)
            for ref in fulfillment.artifact_refs
        }
        if not any(
            (ref.resource_type, ref.resource_id, ref.revision, ref.content_hash)
            in fulfilled_artifacts
            for ref in hydration.output_refs
        ):
            raise BusinessInvestigationFulfillmentResumeBlocked("HYDRATION_OUTPUT_NOT_FULFILLED")
        return InvestigationExactRef(
            resource_type="SemanticHydrationReceipt",
            resource_id=hydration.hydration_id,
            revision=1,
            content_hash=hydration.content_hash,
        )

    @staticmethod
    def _validate_readiness(
        data_command, fulfillment, readiness, created_at
    ) -> InvestigationExactRef:
        if readiness.receipt_ref is None:
            raise BusinessInvestigationFulfillmentResumeBlocked("READINESS_RECEIPT_REQUIRED")
        readiness_ref = _investigation_ref_from_source(readiness.receipt_ref)
        if readiness_ref != fulfillment.source_readiness_ref:
            raise BusinessInvestigationFulfillmentResumeBlocked("READINESS_RECEIPT_DRIFTED")
        projection = readiness.investigation
        if readiness.status is not SourceReadinessStatus.READY or projection is None:
            raise BusinessInvestigationFulfillmentResumeBlocked("READINESS_NOT_READY")
        if projection.status is not SourceReadinessStatus.READY:
            raise BusinessInvestigationFulfillmentResumeBlocked(
                "INVESTIGATION_READINESS_NOT_READY"
            )
        if not _same_source_requirement(
            projection.requirement_ref, data_command.data_requirement_ref
        ):
            raise BusinessInvestigationFulfillmentResumeBlocked("READINESS_REQUIREMENT_DRIFTED")
        if projection.required_cutoff != fulfillment.cutoff_at:
            raise BusinessInvestigationFulfillmentResumeBlocked("READINESS_CUTOFF_DRIFTED")
        if readiness.checked_at > created_at:
            raise BusinessInvestigationFulfillmentResumeBlocked("READINESS_FROM_FUTURE")
        if (
            projection.freshness_expires_at is None
            or projection.freshness_expires_at <= created_at
        ):
            raise BusinessInvestigationFulfillmentResumeBlocked("READINESS_STALE")
        return readiness_ref

    @staticmethod
    def _validate_evidence(
        fulfillment, evidence, checkpoint_ref, runtime
    ) -> ExactRevisionRef:
        receipt_checkpoint = evidence.receipt.checkpoint_ref
        if (
            receipt_checkpoint.resource_id != checkpoint_ref.resource_id
            or receipt_checkpoint.sequence != checkpoint_ref.revision
            or f"sha256:{receipt_checkpoint.state_hash}" != checkpoint_ref.content_hash
        ):
            raise BusinessInvestigationFulfillmentResumeBlocked("EVIDENCE_CHECKPOINT_DRIFTED")
        if evidence.receipt.runtime_binding_hash != runtime.binding_hash:
            raise BusinessInvestigationFulfillmentResumeBlocked(
                "EVIDENCE_RUNTIME_BINDING_DRIFTED"
            )
        if evidence.bundle.cutoff_at != fulfillment.cutoff_at:
            raise BusinessInvestigationFulfillmentResumeBlocked("EVIDENCE_CUTOFF_DRIFTED")
        if (
            evidence.assessment.coverage is not Coverage.COMPLETE
            or evidence.assessment.freshness is not Freshness.FRESH
            or evidence.assessment.missing_fact_ids
        ):
            raise BusinessInvestigationFulfillmentResumeBlocked("EVIDENCE_NOT_READY")
        evidence_ref = evidence.receipt.evidence_bundle_ref
        if (
            evidence_ref.resource_id != evidence.bundle.bundle_id
            or evidence_ref.revision != evidence.bundle.revision
            or evidence_ref.content_hash != evidence.bundle.content_hash
        ):
            raise BusinessInvestigationFulfillmentResumeBlocked(
                "EVIDENCE_BUNDLE_REF_DRIFTED"
            )
        fulfillment_evidence_ref = InvestigationExactRef(
            resource_type=evidence_ref.resource_type,
            resource_id=evidence_ref.resource_id,
            revision=evidence_ref.revision,
            content_hash=f"sha256:{evidence_ref.content_hash}",
        )
        if fulfillment_evidence_ref not in fulfillment.artifact_refs:
            raise BusinessInvestigationFulfillmentResumeBlocked("EVIDENCE_NOT_FULFILLED")
        return evidence_ref

    @staticmethod
    def _validate_resume_result(
        result: RunControlResult, runtime: BusinessInvestigationRuntimeBinding
    ) -> None:
        if (
            result.task.id != runtime.task_ref.resource_id
            or result.task.version != runtime.task_ref.version + 1
            or result.task.status is not TaskStatus.EXECUTING
            or result.run.id != runtime.task_run_ref.resource_id
            or result.run.task_id != runtime.task_ref.resource_id
            or result.run.plan_revision_id != runtime.plan_ref.resource_id
            or result.run.version != runtime.task_run_ref.version + 1
            or result.run.status is not TaskRunStatus.RUNNING
        ):
            raise BusinessInvestigationFulfillmentResumeBlocked("RESUME_RESULT_DRIFTED")
