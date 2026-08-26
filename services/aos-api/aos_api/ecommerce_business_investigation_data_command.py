"""BI-W8-03 Receipt-first missing-data command for the investigation workbench."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceiptStore,
)
from aos_api.aip_business_investigation_data_requester import (
    BusinessInvestigationDataRequester,
    MissingFactDataSpec,
)
from aos_api.aip_business_investigation_data_saga import (
    BusinessInvestigationDataRequirementSaga,
)
from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinder,
)
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_task_store import AipTaskStore
from aos_api.business_investigation_shared_contracts import (
    BlockerSeverity,
    DataRequirementStatus,
    InvestigationBlocker,
    InvestigationExactRef,
)
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.data_requirement_contracts import DataRequirementTimeWindow
from aos_api.data_requirement_store import (
    DataRequirementApplyResult,
    DataRequirementStore,
    canonical_revision_content_hash,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunStateRevision,
    BusinessInvestigationRunStore,
)
from aos_api.ecommerce_business_investigation_case import BusinessInvestigationCaseStore
from aos_api.tenant_scope import TenantScope


class RequestBusinessInvestigationMissingDataCommand(AipContractModel):
    """Only the bounded missing-fact intent is accepted from the Web client."""

    purpose_code: str = Field(pattern=r"^[a-z][a-z0-9_]{1,119}$")
    required_facts: list[str] = Field(min_length=1, max_length=100)
    time_window: DataRequirementTimeWindow
    grain: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    cutoff_at: datetime
    freshness_max_age_seconds: int = Field(ge=1, le=31_536_000)
    quality_threshold: float = Field(ge=0, le=1)
    markings: list[str] = Field(default_factory=list, max_length=50)
    min_population: int = Field(ge=1)
    acceptable_degradation: list[str] = Field(default_factory=list, max_length=50)
    requested_outputs: list[str] = Field(min_length=1, max_length=20)
    budget_minor: int = Field(ge=0)
    expires_at: datetime


class ConfirmBusinessInvestigationDataRequirementCommand(AipContractModel):
    decision: Literal["accept", "reject"]
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _trim_reason(cls, value: str | None) -> str | None:
        return None if value is None else value.strip()

    @model_validator(mode="after")
    def _decision_reason(self) -> Self:
        if self.decision == "reject" and self.reason is None:
            raise ValueError("rejection reason is required")
        if self.decision == "accept" and self.reason is not None:
            raise ValueError("accept does not persist a reason")
        return self


class BusinessInvestigationDataCommandResponse(AipContractModel):
    tenant: TenantContext
    requirement_ref: InvestigationExactRef
    requirement_status: DataRequirementStatus
    run_authority: BusinessInvestigationRunStateRevision
    data_replayed: bool
    run_replayed: bool
    source_read_performed: Literal[False] = False
    external_effect_authorized: Literal[False] = False


class BusinessInvestigationDataCommandConflict(RuntimeError):
    pass


class EcommerceBusinessInvestigationDataCommandService:
    """Own the cross-layer command; never read a platform or authorize an effect."""

    def __init__(
        self,
        *,
        case_store: BusinessInvestigationCaseStore | None = None,
        run_store: BusinessInvestigationRunStore | None = None,
        receipt_store: BusinessInvestigationCompilationReceiptStore | None = None,
        runtime_binder: BusinessInvestigationRuntimeBinder | None = None,
        data_store: DataRequirementStore | None = None,
        data_saga: BusinessInvestigationDataRequirementSaga | None = None,
    ) -> None:
        self._cases = case_store or BusinessInvestigationCaseStore()
        self._runs = run_store or BusinessInvestigationRunStore()
        self._receipts = receipt_store or BusinessInvestigationCompilationReceiptStore()
        self._runtime = runtime_binder or BusinessInvestigationRuntimeBinder(AipTaskStore())
        self._data = data_store or DataRequirementStore()
        self._saga = data_saga or BusinessInvestigationDataRequirementSaga(
            BusinessInvestigationDataRequester(self._data)
        )

    def request_missing_data(
        self,
        scope: TenantScope,
        run_id: str,
        command: RequestBusinessInvestigationMissingDataCommand,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationDataCommandResponse:
        self._validate_command_envelope(idempotency_key, actor, occurred_at)
        run = self._runs.get(scope, run_id)
        case = self._cases.get(scope, run.authority.case_ref.resource_id)
        if self._case_ref(case) != run.authority.case_ref:
            raise BusinessInvestigationDataCommandConflict("Run Case exact ref drifted")
        spec = MissingFactDataSpec.model_validate(
            {
                **command.model_dump(mode="json", by_alias=True),
                "channelRef": case.channel_ref.model_dump(mode="json", by_alias=True),
                "entityRef": case.business_entity_ref.model_dump(
                    mode="json", by_alias=True
                ),
            }
        )
        receipt = self._receipts.get_for_run(scope, self._run_ref(run.authority))
        runtime = self._runtime.bind_receipt(scope, receipt, run)
        identity = self._saga.identify(scope, receipt, runtime, spec)
        existing = self._data.find_command_receipt(scope, "request", idempotency_key)
        if existing is None:
            saga_result = self._saga.execute(
                scope,
                actor,
                receipt,
                runtime,
                spec,
                created_at=occurred_at,
                data_idempotency_key=idempotency_key,
            )
            requirement = self._data.get_current(
                scope, saga_result.data_requirement_ref.resource_id
            )
            data_result = DataRequirementApplyResult(
                exact_ref=saga_result.data_requirement_ref,
                version=saga_result.data_requirement_ref.revision,
                etag=saga_result.data_requirement_ref.content_hash,
                replayed=saga_result.replayed,
            )
        else:
            requirement = existing.authority
            data_result = existing.result
            self._validate_replayed_request(
                requirement, spec, receipt.run_ref, runtime.checkpoint_ref
            )
        run_result = self._runs.request_data(
            scope,
            run_id,
            data_result.exact_ref,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )
        return BusinessInvestigationDataCommandResponse(
            tenant=self._tenant(scope),
            requirement_ref=self._requirement_ref(requirement),
            requirement_status=requirement.status,
            run_authority=run_result.authority,
            data_replayed=data_result.replayed,
            run_replayed=run_result.replayed,
        )

    def confirm_requirement(
        self,
        scope: TenantScope,
        run_id: str,
        command: ConfirmBusinessInvestigationDataRequirementCommand,
        *,
        expected_version: int,
        idempotency_key: str,
        actor: str,
        occurred_at: datetime,
    ) -> BusinessInvestigationDataCommandResponse:
        self._validate_command_envelope(idempotency_key, actor, occurred_at)
        run = self._runs.get(scope, run_id)
        pending = run.state.pending_requirement_ref
        if pending is None:
            raise BusinessInvestigationDataCommandConflict(
                "current Run has no pending DataRequirement"
            )
        current = self._data.get_current(scope, pending.resource_id)
        operation = command.decision
        data_key = idempotency_key
        existing = self._data.find_command_receipt(scope, operation, data_key)
        opposite = "reject" if operation == "accept" else "accept"
        if self._data.find_command_receipt(scope, opposite, data_key) is not None:
            raise BusinessInvestigationDataCommandConflict(
                "DataRequirement confirmation idempotency conflict"
            )
        if existing is None:
            if self._requirement_ref(current) != pending:
                raise BusinessInvestigationDataCommandConflict(
                    "pending DataRequirement exact ref drifted"
                )
            successor = self._successor(
                current, command=command, actor=actor, occurred_at=occurred_at
            )
            apply = self._data.accept if operation == "accept" else self._data.reject
            data_result = apply(
                scope,
                actor,
                data_key,
                successor,
                expected_version=current.revision,
            )
            requirement = successor
        else:
            requirement = existing.authority
            data_result = existing.result
            expected_status = (
                DataRequirementStatus.ACCEPTED
                if operation == "accept"
                else DataRequirementStatus.REJECTED
            )
            if requirement.status is not expected_status:
                raise BusinessInvestigationDataCommandConflict(
                    "DataRequirement confirmation Receipt drifted"
                )
            if operation == "reject" and (
                len(requirement.blockers) != 1
                or requirement.blockers[0].code != "MANUAL_DATA_REQUIREMENT_REJECTED"
                or requirement.blockers[0].required_action != command.reason
            ):
                raise BusinessInvestigationDataCommandConflict(
                    "DataRequirement rejection reason idempotency conflict"
                )
        run_result = self._runs.request_data(
            scope,
            run_id,
            data_result.exact_ref,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            actor=actor,
            occurred_at=occurred_at,
        )
        return BusinessInvestigationDataCommandResponse(
            tenant=self._tenant(scope),
            requirement_ref=self._requirement_ref(requirement),
            requirement_status=requirement.status,
            run_authority=run_result.authority,
            data_replayed=data_result.replayed,
            run_replayed=run_result.replayed,
        )

    @staticmethod
    def _successor(
        current: DataRequirementRevisionRecord,
        *,
        command: ConfirmBusinessInvestigationDataRequirementCommand,
        actor: str,
        occurred_at: datetime,
    ) -> DataRequirementRevisionRecord:
        payload = current.model_dump(mode="json", by_alias=True)
        payload.update(
            revision=current.revision + 1,
            priorRef=EcommerceBusinessInvestigationDataCommandService._requirement_ref(
                current
            ).model_dump(mode="json", by_alias=True),
            contentHash="sha256:" + "0" * 64,
            status=(
                DataRequirementStatus.ACCEPTED.value
                if command.decision == "accept"
                else DataRequirementStatus.REJECTED.value
            ),
            createdBy=actor,
            createdAt=occurred_at.isoformat(),
            blockers=(
                []
                if command.decision == "accept"
                else [
                    InvestigationBlocker(
                        code="MANUAL_DATA_REQUIREMENT_REJECTED",
                        severity=BlockerSeverity.BLOCKING,
                        dependency=current.requirement_id,
                        required_action=command.reason or "人工驳回",
                    ).model_dump(mode="json", by_alias=True)
                ]
            ),
        )
        successor = DataRequirementRevisionRecord.model_validate(payload)
        payload["contentHash"] = canonical_revision_content_hash(successor)
        return DataRequirementRevisionRecord.model_validate(payload)

    @staticmethod
    def _validate_replayed_request(
        requirement: DataRequirementRevisionRecord,
        command: MissingFactDataSpec,
        run_ref: InvestigationExactRef,
        checkpoint_ref,
    ) -> None:
        if checkpoint_ref is None:
            raise BusinessInvestigationDataCommandConflict("exact Checkpoint is required")
        expected_checkpoint = InvestigationExactRef(
            resource_type="CheckpointRevision",
            resource_id=checkpoint_ref.resource_id,
            revision=checkpoint_ref.sequence,
            content_hash=f"sha256:{checkpoint_ref.state_hash}",
        )
        expected = command.model_dump(mode="json", by_alias=True)
        actual = requirement.model_dump(mode="json", by_alias=True)
        keys = {
            "purposeCode",
            "channelRef",
            "entityRef",
            "requiredFacts",
            "timeWindow",
            "grain",
            "cutoffAt",
            "freshnessMaxAgeSeconds",
            "qualityThreshold",
            "markings",
            "minPopulation",
            "acceptableDegradation",
            "requestedOutputs",
            "budgetMinor",
            "expiresAt",
        }
        if (
            {key: actual[key] for key in keys} != {key: expected[key] for key in keys}
            or requirement.run_ref != run_ref
            or requirement.checkpoint_ref != expected_checkpoint
        ):
            raise BusinessInvestigationDataCommandConflict(
                "DataRequirement request Receipt drifted"
            )

    @staticmethod
    def _validate_command_envelope(
        idempotency_key: str, actor: str, occurred_at: datetime
    ) -> None:
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise BusinessInvestigationDataCommandConflict(
                "idempotency key must be non-empty and bounded"
            )
        if not actor.strip() or occurred_at.utcoffset() is None:
            raise BusinessInvestigationDataCommandConflict(
                "actor and timezone-aware occurredAt are required"
            )

    @staticmethod
    def _tenant(scope: TenantScope) -> TenantContext:
        return TenantContext(org_id=scope.org_id, project_id=scope.project_id)

    @staticmethod
    def _run_ref(authority) -> InvestigationExactRef:
        return InvestigationExactRef(
            resource_type="BusinessInvestigationRun",
            resource_id=authority.run_id,
            revision=authority.version,
            content_hash=authority.content_hash,
        )

    @staticmethod
    def _case_ref(authority) -> InvestigationExactRef:
        return InvestigationExactRef(
            resource_type="BusinessInvestigationCaseRevision",
            resource_id=authority.case_id,
            revision=authority.revision,
            content_hash=authority.content_hash,
        )

    @staticmethod
    def _requirement_ref(
        authority: DataRequirementRevisionRecord,
    ) -> InvestigationExactRef:
        return InvestigationExactRef(
            resource_type="DataRequirementRevision",
            resource_id=authority.requirement_id,
            revision=authority.revision,
            content_hash=authority.content_hash,
        )


__all__ = [
    "BusinessInvestigationDataCommandConflict",
    "BusinessInvestigationDataCommandResponse",
    "ConfirmBusinessInvestigationDataRequirementCommand",
    "EcommerceBusinessInvestigationDataCommandService",
    "RequestBusinessInvestigationMissingDataCommand",
]
