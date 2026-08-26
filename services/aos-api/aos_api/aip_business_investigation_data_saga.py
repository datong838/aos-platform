"""BI-W6-02 exact-ref command bridge from AIP runtime to DataRequirement."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Literal, Protocol

from pydantic import Field, model_validator

from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceipt,
)
from aos_api.aip_business_investigation_data_requester import (
    MissingFactDataRequest,
    MissingFactDataSpec,
)
from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinding,
)
from aos_api.aip_contracts import AipContractModel, TaskRunStatus, TenantContext
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_store import DataRequirementApplyResult
from aos_api.tenant_scope import TenantScope


SCHEMA_VERSION = "aos.aip.business-investigation-data-requirement-command-result/v1"
SHA256 = r"^sha256:[0-9a-f]{64}$"


def _canonical_hash(value: object, *, prefixed: bool = True) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"sha256:{digest}" if prefixed else digest


def _stable_id(prefix: str, value: object) -> str:
    return f"{prefix}-{_canonical_hash(value, prefixed=False)}"


class BusinessInvestigationDataRequirementCommandResult(AipContractModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    tenant: TenantContext
    command_id: str = Field(min_length=1, max_length=200)
    request_hash: str = Field(pattern=SHA256)
    compilation_receipt_ref: InvestigationExactRef
    checkpoint_ref: InvestigationExactRef
    data_requirement_ref: InvestigationExactRef
    replayed: bool
    source_read_performed: Literal[False] = False
    external_effect_authorized: Literal[False] = False

    @model_validator(mode="after")
    def _exact_ref_types(self) -> BusinessInvestigationDataRequirementCommandResult:
        expected_types = (
            (self.compilation_receipt_ref, "BusinessInvestigationCompilationReceipt"),
            (self.checkpoint_ref, "CheckpointRevision"),
            (self.data_requirement_ref, "DataRequirementRevision"),
        )
        for exact_ref, expected_type in expected_types:
            if exact_ref.resource_type != expected_type:
                raise ValueError(f"exact ref must reference {expected_type}")
        return self


class BusinessInvestigationDataSagaConflict(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BusinessInvestigationDataCommandIdentity:
    command_id: str
    requirement_id: str


class MissingFactRequester(Protocol):
    def request_missing_facts(
        self,
        scope: TenantScope,
        runtime: BusinessInvestigationRuntimeBinding,
        request: MissingFactDataRequest,
        actor: str,
        *,
        created_at: datetime,
    ) -> DataRequirementApplyResult: ...


class BusinessInvestigationDataRequirementSaga:
    """Submit one canonical requested revision; never read or deliver source data."""

    def __init__(self, requester: MissingFactRequester) -> None:
        self._requester = requester

    def execute(
        self,
        scope: TenantScope,
        actor: str,
        compilation_receipt: BusinessInvestigationCompilationReceipt,
        runtime: BusinessInvestigationRuntimeBinding,
        spec: MissingFactDataSpec,
        *,
        created_at: datetime,
        data_idempotency_key: str | None = None,
    ) -> BusinessInvestigationDataRequirementCommandResult:
        actor = actor.strip()
        if not actor:
            raise BusinessInvestigationDataSagaConflict("actor is required")
        if created_at.utcoffset() is None:
            raise BusinessInvestigationDataSagaConflict(
                "createdAt must be timezone-aware"
            )
        if data_idempotency_key is not None and (
            not data_idempotency_key.strip() or len(data_idempotency_key) > 200
        ):
            raise BusinessInvestigationDataSagaConflict(
                "data idempotency key must be non-empty and bounded"
            )
        checkpoint_ref = self._validate_lineage(scope, compilation_receipt, runtime)
        compilation_receipt_ref = compilation_receipt.exact_ref
        command_identity = self._command_identity(scope, compilation_receipt, runtime, spec)
        command_id = _stable_id("bi-data-requirement", command_identity)
        requirement_id = _stable_id("data-requirement", command_identity)
        request_hash = _canonical_hash(
            {
                "commandId": command_id,
                "requirementId": requirement_id,
                **command_identity,
                "actor": actor,
                "createdAt": created_at,
                "missingFactSpec": spec.model_dump(mode="json", by_alias=True),
            }
        )
        request = MissingFactDataRequest.model_validate(
            {
                **spec.model_dump(mode="json", by_alias=True),
                "requirementId": requirement_id,
                "idempotencyKey": data_idempotency_key or command_id,
            }
        )
        result = self._requester.request_missing_facts(
            scope, runtime, request, actor, created_at=created_at
        )
        exact_ref = result.exact_ref
        if (
            exact_ref.resource_type != "DataRequirementRevision"
            or exact_ref.resource_id != requirement_id
            or exact_ref.revision != 1
            or result.version != 1
            or result.etag != exact_ref.content_hash
        ):
            raise BusinessInvestigationDataSagaConflict(
                "canonical DataRequirement result drifted"
            )
        return BusinessInvestigationDataRequirementCommandResult(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            command_id=command_id,
            request_hash=request_hash,
            compilation_receipt_ref=compilation_receipt_ref,
            checkpoint_ref=checkpoint_ref,
            data_requirement_ref=exact_ref,
            replayed=result.replayed,
        )

    def identify(
        self,
        scope: TenantScope,
        compilation_receipt: BusinessInvestigationCompilationReceipt,
        runtime: BusinessInvestigationRuntimeBinding,
        spec: MissingFactDataSpec,
    ) -> BusinessInvestigationDataCommandIdentity:
        self._validate_lineage(scope, compilation_receipt, runtime)
        material = self._command_identity(scope, compilation_receipt, runtime, spec)
        return BusinessInvestigationDataCommandIdentity(
            command_id=_stable_id("bi-data-requirement", material),
            requirement_id=_stable_id("data-requirement", material),
        )

    @staticmethod
    def _command_identity(
        scope: TenantScope,
        compilation_receipt: BusinessInvestigationCompilationReceipt,
        runtime: BusinessInvestigationRuntimeBinding,
        spec: MissingFactDataSpec,
    ) -> dict:
        checkpoint_ref = runtime.checkpoint_ref
        if checkpoint_ref is None:
            raise BusinessInvestigationDataSagaConflict("exact Checkpoint is required")
        return {
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "compilationReceiptRef": compilation_receipt.exact_ref.model_dump(
                mode="json", by_alias=True
            ),
            "checkpointRef": InvestigationExactRef(
                resource_type="CheckpointRevision",
                resource_id=checkpoint_ref.resource_id,
                revision=checkpoint_ref.sequence,
                content_hash=f"sha256:{checkpoint_ref.state_hash}",
            ).model_dump(mode="json", by_alias=True),
            "missingFactSpec": spec.model_dump(mode="json", by_alias=True),
        }

    @staticmethod
    def _validate_lineage(
        scope: TenantScope,
        receipt: BusinessInvestigationCompilationReceipt,
        runtime: BusinessInvestigationRuntimeBinding,
    ) -> InvestigationExactRef:
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if receipt.tenant != tenant or runtime.tenant != tenant:
            raise BusinessInvestigationDataSagaConflict("tenant lineage drifted")
        if runtime.checkpoint_ref is None:
            raise BusinessInvestigationDataSagaConflict("exact Checkpoint is required")
        run_ref = receipt.run_ref
        runtime_run_ref = runtime.business_investigation_run_ref
        if (
            run_ref.resource_type != runtime_run_ref.resource_type
            or run_ref.resource_id != runtime_run_ref.resource_id
            or run_ref.revision != runtime_run_ref.revision
            or run_ref.content_hash != f"sha256:{runtime_run_ref.content_hash}"
        ):
            raise BusinessInvestigationDataSagaConflict("Run exact lineage drifted")
        if receipt.plan_ref != runtime.plan_ref:
            raise BusinessInvestigationDataSagaConflict("Plan exact lineage drifted")
        if receipt.task_id != runtime.task_ref.resource_id:
            raise BusinessInvestigationDataSagaConflict("Task lineage drifted")
        if receipt.compilation_hash != runtime.compilation_hash:
            raise BusinessInvestigationDataSagaConflict("compilation hash drifted")
        if runtime.task_run_status is not TaskRunStatus.PAUSED:
            raise BusinessInvestigationDataSagaConflict(
                "TaskRun must be PAUSED before requesting data"
            )
        return InvestigationExactRef(
            resource_type="CheckpointRevision",
            resource_id=runtime.checkpoint_ref.resource_id,
            revision=runtime.checkpoint_ref.sequence,
            content_hash=f"sha256:{runtime.checkpoint_ref.state_hash}",
        )
