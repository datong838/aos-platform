"""BI-W6-04 receipt-first Artifact publication and canonical Step acceptance."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import Field, model_validator

from aos_api.aip_business_investigation_eval import BusinessInvestigationStageQualityGate
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_eval_contracts import EvalStageAttemptRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_artifact import (
    BusinessInvestigationArtifactBinding,
    BusinessInvestigationArtifactRevision,
)
from aos_api.ecommerce_business_investigation_artifact_publication import (
    ArtifactPublicationWrite,
    BusinessInvestigationArtifactPublisher,
)
from aos_api.tenant_scope import TenantScope


SCHEMA_VERSION = "aos.aip.business-investigation-artifact-acceptance/v1"


class CanonicalStepCompleter(Protocol):
    def complete_step(
        self, scope: TenantScope, step_run_id: str, worker_id: str, fence: int, actor: str
    ) -> str: ...


class BusinessInvestigationArtifactAcceptance(AipContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    tenant: TenantContext
    artifact_ref: InvestigationExactRef
    publication_receipt_ref: InvestigationExactRef
    stage_attempt_ref: InvestigationExactRef
    checkpoint_id: str = Field(min_length=1, max_length=200)
    publication_transition_count: Literal[1] = 1
    step_transition_count: Literal[1] = 1
    provider_invocation_count: Literal[0] = 0
    source_read_count: Literal[0] = 0
    external_business_mutation_count: Literal[0] = 0
    external_effect_authorized: Literal[False] = False

    @model_validator(mode="after")
    def _types(self) -> BusinessInvestigationArtifactAcceptance:
        if self.publication_receipt_ref.resource_type != "ArtifactPublicationReceipt":
            raise ValueError("publicationReceiptRef must reference ArtifactPublicationReceipt")
        if self.stage_attempt_ref.resource_type != "StepRunAttempt":
            raise ValueError("stageAttemptRef must reference StepRunAttempt")
        return self


class BusinessInvestigationArtifactAcceptanceBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class BusinessInvestigationArtifactPublicationSaga:
    def __init__(
        self,
        publisher: BusinessInvestigationArtifactPublisher,
        completer: CanonicalStepCompleter,
    ) -> None:
        self._publisher = publisher
        self._completer = completer

    def execute(
        self,
        scope: TenantScope,
        *,
        actor: str,
        worker_id: str,
        fence: int,
        expected_head_revision: int,
        artifact: BusinessInvestigationArtifactRevision,
        binding: BusinessInvestigationArtifactBinding,
        quality_gate: BusinessInvestigationStageQualityGate,
        stage_attempt: EvalStageAttemptRef,
        published_at: datetime,
    ) -> BusinessInvestigationArtifactAcceptance:
        actor = actor.strip()
        worker_id = worker_id.strip()
        if not actor or not worker_id:
            raise BusinessInvestigationArtifactAcceptanceBlocked("ACTOR_AND_WORKER_REQUIRED")
        if fence < 1:
            raise BusinessInvestigationArtifactAcceptanceBlocked("STEP_FENCE_INVALID")

        publication = self._publisher.publish(
            scope,
            actor=actor,
            expected_head_revision=expected_head_revision,
            artifact=artifact,
            binding=binding,
            quality_gate=quality_gate,
            stage_attempt=stage_attempt,
            published_at=published_at,
        )
        self._validate_receipt(scope, artifact, binding, quality_gate, stage_attempt, publication)
        checkpoint_id = self._completer.complete_step(
            scope,
            stage_attempt.step_run_id,
            worker_id,
            fence,
            actor,
        )
        if not checkpoint_id or len(checkpoint_id) > 200:
            raise BusinessInvestigationArtifactAcceptanceBlocked("STEP_CHECKPOINT_INVALID")
        receipt = publication.authority
        return BusinessInvestigationArtifactAcceptance(
            tenant=receipt.tenant,
            artifact_ref=receipt.artifact_ref,
            publication_receipt_ref=InvestigationExactRef(
                resource_type="ArtifactPublicationReceipt",
                resource_id=receipt.receipt_id,
                revision=1,
                content_hash=receipt.calculated_content_hash(),
                receipt_id=receipt.receipt_id,
            ),
            stage_attempt_ref=receipt.stage_attempt_ref,
            checkpoint_id=checkpoint_id,
        )

    @staticmethod
    def _validate_receipt(
        scope: TenantScope,
        artifact: BusinessInvestigationArtifactRevision,
        binding: BusinessInvestigationArtifactBinding,
        quality_gate: BusinessInvestigationStageQualityGate,
        stage_attempt: EvalStageAttemptRef,
        publication: ArtifactPublicationWrite,
    ) -> None:
        receipt = publication.authority
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if receipt.tenant != tenant:
            raise BusinessInvestigationArtifactAcceptanceBlocked("RECEIPT_TENANT_DRIFTED")
        if (
            receipt.artifact_ref.resource_id != artifact.artifact_id
            or receipt.artifact_ref.revision != artifact.revision
            or receipt.artifact_ref.content_hash != artifact.content_hash
        ):
            raise BusinessInvestigationArtifactAcceptanceBlocked("RECEIPT_ARTIFACT_DRIFTED")
        if (
            receipt.binding_ref.resource_id != binding.binding_id
            or receipt.binding_ref.content_hash != binding.binding_hash
            or receipt.data_cutoff != binding.data_cutoff
        ):
            raise BusinessInvestigationArtifactAcceptanceBlocked("RECEIPT_BINDING_DRIFTED")
        if (
            receipt.eval_report_ref.resource_id != quality_gate.eval_report_ref.resource_id
            or receipt.eval_report_ref.revision != quality_gate.eval_report_ref.revision
            or receipt.eval_report_ref.content_hash
            != f"sha256:{quality_gate.eval_report_ref.content_hash}"
        ):
            raise BusinessInvestigationArtifactAcceptanceBlocked("RECEIPT_EVAL_DRIFTED")
        if (
            receipt.stage_attempt_ref.resource_id != stage_attempt.step_run_id
            or receipt.stage_attempt_ref.revision != stage_attempt.attempt
            or receipt.stage_attempt_ref.content_hash != f"sha256:{stage_attempt.input_hash}"
        ):
            raise BusinessInvestigationArtifactAcceptanceBlocked("RECEIPT_STAGE_ATTEMPT_DRIFTED")


__all__ = [
    "BusinessInvestigationArtifactAcceptance",
    "BusinessInvestigationArtifactAcceptanceBlocked",
    "BusinessInvestigationArtifactPublicationSaga",
]
