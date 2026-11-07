"""BI-W6-04 controlled publication into the canonical investigation Artifact authority."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Protocol

import psycopg
from psycopg.types.json import Jsonb

from aos_api.aip_business_investigation_eval import BusinessInvestigationStageQualityGate
from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import EvalStageAttemptRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.ecommerce_business_investigation_artifact import (
    ArtifactPublicationReceipt,
    BusinessInvestigationArtifactBinding,
    BusinessInvestigationArtifactRevision,
    BusinessInvestigationArtifactType,
)
from aos_api.tenant_scope import TenantScope


def _canonical_hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


def _stable_id(prefix: str, value: object) -> str:
    return f"{prefix}-{_canonical_hash(value).removeprefix('sha256:')}"


_STAGE_ARTIFACTS = {
    "portrait": {BusinessInvestigationArtifactType.DOSSIER},
    "diagnosis": {
        BusinessInvestigationArtifactType.PROBLEM_MAP,
        BusinessInvestigationArtifactType.OPPORTUNITY_MAP,
    },
    "solution_design": {BusinessInvestigationArtifactType.SOLUTION_PORTFOLIO},
}


class ArtifactPublicationBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ArtifactPublicationWrite:
    authority: ArtifactPublicationReceipt
    replayed: bool


class ArtifactPublicationAuthority(Protocol):
    def publish(
        self,
        scope: TenantScope,
        *,
        expected_head_revision: int,
        artifact: BusinessInvestigationArtifactRevision,
        binding: BusinessInvestigationArtifactBinding,
        receipt: ArtifactPublicationReceipt,
    ) -> ArtifactPublicationWrite: ...


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class ArtifactPublicationStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def publish(
        self,
        scope: TenantScope,
        *,
        expected_head_revision: int,
        artifact: BusinessInvestigationArtifactRevision,
        binding: BusinessInvestigationArtifactBinding,
        receipt: ArtifactPublicationReceipt,
    ) -> ArtifactPublicationWrite:
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT receipt_data,replayed
                    FROM ecommerce_investigation_publish_artifact_biw6_002(%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb)""",
                    (
                        scope.org_id,
                        scope.project_id,
                        expected_head_revision,
                        Jsonb(artifact.model_dump(mode="json", by_alias=True)),
                        Jsonb(binding.model_dump(mode="json", by_alias=True)),
                        Jsonb(receipt.model_dump(mode="json", by_alias=True)),
                    ),
                ).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            raise ArtifactPublicationBlocked("ARTIFACT_PUBLICATION_AUTHORITY_REJECTED") from exc
        if row is None:
            raise ArtifactPublicationBlocked("ARTIFACT_PUBLICATION_RECEIPT_MISSING")
        return ArtifactPublicationWrite(
            authority=ArtifactPublicationReceipt.model_validate(row["receipt_data"]),
            replayed=bool(row["replayed"]),
        )


class BusinessInvestigationArtifactPublisher:
    def __init__(self, authority: ArtifactPublicationAuthority) -> None:
        self._authority = authority

    def publish(
        self,
        scope: TenantScope,
        *,
        actor: str,
        expected_head_revision: int,
        artifact: BusinessInvestigationArtifactRevision,
        binding: BusinessInvestigationArtifactBinding,
        quality_gate: BusinessInvestigationStageQualityGate,
        stage_attempt: EvalStageAttemptRef,
        published_at: datetime,
    ) -> ArtifactPublicationWrite:
        actor = actor.strip()
        if not actor:
            raise ArtifactPublicationBlocked("ACTOR_REQUIRED")
        if expected_head_revision < 0:
            raise ArtifactPublicationBlocked("EXPECTED_HEAD_REVISION_INVALID")
        if published_at.utcoffset() is None:
            raise ArtifactPublicationBlocked("PUBLISHED_AT_TIMEZONE_REQUIRED")
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if artifact.tenant != tenant or binding.tenant != tenant:
            raise ArtifactPublicationBlocked("PUBLICATION_TENANT_DRIFTED")
        if artifact.calculated_content_hash() != artifact.content_hash:
            raise ArtifactPublicationBlocked("ARTIFACT_CONTENT_HASH_DRIFTED")
        if binding.calculated_binding_hash() != binding.binding_hash:
            raise ArtifactPublicationBlocked("BINDING_CONTENT_HASH_DRIFTED")
        if binding.artifact_ref != self._artifact_ref(artifact):
            raise ArtifactPublicationBlocked("BINDING_ARTIFACT_DRIFTED")
        if binding.case_ref != artifact.case_ref or binding.run_ref != artifact.run_ref:
            raise ArtifactPublicationBlocked("BINDING_RUNTIME_DRIFTED")
        if binding.data_cutoff > published_at:
            raise ArtifactPublicationBlocked("PUBLICATION_CUTOFF_IN_FUTURE")
        if not quality_gate.gate_passed:
            raise ArtifactPublicationBlocked("EVAL_GATE_NOT_PASSED")
        if artifact.artifact_type not in _STAGE_ARTIFACTS[quality_gate.stage]:
            raise ArtifactPublicationBlocked("STAGE_ARTIFACT_TYPE_DRIFTED")
        subject = quality_gate.subject_artifact_ref
        if (
            subject.resource_id != artifact.artifact_id
            or f"sha256:{subject.content_hash}" != artifact.content_hash
        ):
            raise ArtifactPublicationBlocked("EVAL_ARTIFACT_DRIFTED")
        if stage_attempt.step_key != quality_gate.stage:
            raise ArtifactPublicationBlocked("STAGE_ATTEMPT_KEY_DRIFTED")
        if stage_attempt.run_id != artifact.run_ref.resource_id:
            raise ArtifactPublicationBlocked("STAGE_ATTEMPT_RUN_DRIFTED")
        if artifact.revision != expected_head_revision + 1:
            raise ArtifactPublicationBlocked("ARTIFACT_EXPECTED_VERSION_DRIFTED")

        eval_ref = InvestigationExactRef(
            resource_type="EvalReportRevision",
            resource_id=quality_gate.eval_report_ref.resource_id,
            revision=quality_gate.eval_report_ref.revision,
            content_hash=f"sha256:{quality_gate.eval_report_ref.content_hash}",
        )
        attempt_ref = InvestigationExactRef(
            resource_type="StepRunAttempt",
            resource_id=stage_attempt.step_run_id,
            revision=stage_attempt.attempt,
            content_hash=f"sha256:{stage_attempt.input_hash}",
        )
        identity = {
            "tenant": tenant.model_dump(mode="json", by_alias=True),
            "artifactRef": binding.artifact_ref.model_dump(mode="json", by_alias=True),
            "bindingHash": binding.binding_hash,
            "evalReportRef": eval_ref.model_dump(mode="json", by_alias=True),
            "stageAttemptRef": attempt_ref.model_dump(mode="json", by_alias=True),
        }
        command_id = _stable_id("bi-artifact-publish", identity)
        request_hash = _canonical_hash(
            {
                **identity,
                "commandId": command_id,
                "expectedHeadRevision": expected_head_revision,
                "artifact": artifact.model_dump(mode="json", by_alias=True),
                "binding": binding.model_dump(mode="json", by_alias=True),
                "actor": actor,
                "publishedAt": published_at,
            }
        )
        receipt_id = _stable_id("bi-artifact-publication-receipt", {"commandId": command_id})
        receipt = ArtifactPublicationReceipt(
            tenant=tenant,
            receipt_id=receipt_id,
            command_id=command_id,
            request_hash=request_hash,
            artifact_ref=binding.artifact_ref,
            binding_ref=InvestigationExactRef(
                resource_type="BusinessInvestigationArtifactBinding",
                resource_id=binding.binding_id,
                revision=1,
                content_hash=binding.binding_hash,
            ),
            eval_report_ref=eval_ref,
            stage_attempt_ref=attempt_ref,
            case_ref=artifact.case_ref,
            run_ref=artifact.run_ref,
            data_cutoff=binding.data_cutoff,
            published_by=actor,
            published_at=published_at,
        )
        result = self._authority.publish(
            scope,
            expected_head_revision=expected_head_revision,
            artifact=artifact,
            binding=binding,
            receipt=receipt,
        )
        if result.authority != receipt:
            raise ArtifactPublicationBlocked("PUBLICATION_RECEIPT_DRIFTED")
        return result

    @staticmethod
    def _artifact_ref(artifact: BusinessInvestigationArtifactRevision) -> InvestigationExactRef:
        return InvestigationExactRef(
            resource_type=artifact.artifact_type.value,
            resource_id=artifact.artifact_id,
            revision=artifact.revision,
            content_hash=artifact.content_hash,
        )


__all__ = [
    "ArtifactPublicationAuthority",
    "ArtifactPublicationBlocked",
    "ArtifactPublicationStore",
    "ArtifactPublicationWrite",
    "BusinessInvestigationArtifactPublisher",
]
