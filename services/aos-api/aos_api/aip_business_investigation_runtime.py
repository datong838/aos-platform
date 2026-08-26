"""BI-W5-02 read-only binding to the canonical AIP task runtime."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal, Protocol

from pydantic import Field, model_validator

from aos_api.aip_business_investigation_compiler import (
    BusinessInvestigationCompilation,
)
from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceipt,
)
from aos_api.aip_contracts import AipContractModel, TaskRunStatus, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_task_models import TaskRunSnapshot, TaskTimeline
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunView
from aos_api.tenant_scope import TenantScope


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


class CanonicalRuntimeRef(AipContractModel):
    resource_type: Literal["Task", "TaskRun"]
    resource_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)


class CanonicalCheckpointRef(AipContractModel):
    resource_type: Literal["Checkpoint"] = "Checkpoint"
    resource_id: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=1)
    state_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class BusinessInvestigationRuntimeBinding(AipContractModel):
    tenant: TenantContext
    case_ref: ExactRevisionRef
    business_investigation_run_ref: ExactRevisionRef
    compilation_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    task_ref: CanonicalRuntimeRef
    plan_ref: ExactRevisionRef
    task_run_ref: CanonicalRuntimeRef
    checkpoint_ref: CanonicalCheckpointRef | None = None
    task_run_status: TaskRunStatus
    plan_step_count: int = Field(ge=1)
    binding_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_authorized: Literal[False] = False

    @model_validator(mode="after")
    def _canonical_types(self) -> BusinessInvestigationRuntimeBinding:
        if self.task_ref.resource_type != "Task":
            raise ValueError("taskRef must reference Task")
        if self.task_run_ref.resource_type != "TaskRun":
            raise ValueError("taskRunRef must reference TaskRun")
        if self.plan_ref.resource_type != "PlanRevision":
            raise ValueError("planRef must reference PlanRevision")
        return self


class BusinessInvestigationRuntimeBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RuntimeTimelineReader(Protocol):
    def timeline(self, scope: TenantScope, run_id: str) -> TaskTimeline: ...

    def list_runs(
        self,
        scope: TenantScope,
        *,
        task_id: str | None = None,
        limit: int = 100,
    ) -> list[TaskRunSnapshot]: ...


class BusinessInvestigationRuntimeBinder:
    """Validate canonical runtime lineage without mutating runtime authority."""

    def __init__(self, timeline_reader: RuntimeTimelineReader) -> None:
        self._timeline_reader = timeline_reader

    def bind(
        self,
        scope: TenantScope,
        compilation: BusinessInvestigationCompilation,
        task_run_id: str,
    ) -> BusinessInvestigationRuntimeBinding:
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if compilation.tenant != tenant:
            raise BusinessInvestigationRuntimeBlocked("COMPILATION_TENANT_MISMATCH")
        if not task_run_id.strip():
            raise ValueError("task_run_id is required")
        try:
            timeline = self._timeline_reader.timeline(scope, task_run_id.strip())
        except Exception as exc:
            raise BusinessInvestigationRuntimeBlocked(
                "TIMELINE_RESOLUTION_FAILED"
            ) from exc
        return self._binding(tenant, compilation, task_run_id.strip(), timeline)

    def bind_receipt(
        self,
        scope: TenantScope,
        receipt: BusinessInvestigationCompilationReceipt,
        domain_run: BusinessInvestigationRunView,
    ) -> BusinessInvestigationRuntimeBinding:
        """Resolve one paused canonical TaskRun for an exact compilation Receipt."""
        tenant = TenantContext(org_id=scope.org_id, project_id=scope.project_id)
        if receipt.tenant != tenant or domain_run.authority.tenant != tenant:
            raise BusinessInvestigationRuntimeBlocked("COMPILATION_TENANT_MISMATCH")
        run_ref = InvestigationExactRef(
            resource_type="BusinessInvestigationRun",
            resource_id=domain_run.authority.run_id,
            revision=domain_run.authority.version,
            content_hash=domain_run.authority.content_hash,
        )
        if receipt.run_ref != run_ref:
            raise BusinessInvestigationRuntimeBlocked("BUSINESS_RUN_REF_DRIFTED")
        try:
            candidates = self._timeline_reader.list_runs(
                scope, task_id=receipt.task_id, limit=100
            )
        except Exception as exc:
            raise BusinessInvestigationRuntimeBlocked(
                "TASK_RUN_RESOLUTION_FAILED"
            ) from exc
        paused = [
            item
            for item in candidates
            if item.plan_revision_id == receipt.plan_ref.resource_id
            and item.status is TaskRunStatus.PAUSED
        ]
        if len(paused) != 1:
            raise BusinessInvestigationRuntimeBlocked("PAUSED_TASK_RUN_NOT_UNIQUE")
        task_run_id = paused[0].id
        try:
            timeline = self._timeline_reader.timeline(scope, task_run_id)
        except Exception as exc:
            raise BusinessInvestigationRuntimeBlocked(
                "TIMELINE_RESOLUTION_FAILED"
            ) from exc
        return self._binding_from_lineage(
            tenant=tenant,
            case_ref=self._aip_ref(
                domain_run.authority.case_ref,
                expected_type="BusinessInvestigationCaseRevision",
            ),
            run_ref=self._aip_ref(run_ref, expected_type="BusinessInvestigationRun"),
            compilation_hash=receipt.compilation_hash,
            task_id=receipt.task_id,
            expected_plan_ref=receipt.plan_ref,
            task_run_id=task_run_id,
            timeline=timeline,
        )

    @classmethod
    def _binding(
        cls,
        tenant: TenantContext,
        compilation: BusinessInvestigationCompilation,
        task_run_id: str,
        timeline: TaskTimeline,
    ) -> BusinessInvestigationRuntimeBinding:
        return cls._binding_from_lineage(
            tenant=tenant,
            case_ref=compilation.case_ref,
            run_ref=compilation.run_ref,
            compilation_hash=compilation.compilation_hash,
            task_id=compilation.task_id,
            expected_plan_ref=compilation.plan_ref,
            task_run_id=task_run_id,
            timeline=timeline,
        )

    @classmethod
    def _binding_from_lineage(
        cls,
        *,
        tenant: TenantContext,
        case_ref: ExactRevisionRef,
        run_ref: ExactRevisionRef,
        compilation_hash: str,
        task_id: str,
        expected_plan_ref: ExactRevisionRef,
        task_run_id: str,
        timeline: TaskTimeline,
    ) -> BusinessInvestigationRuntimeBinding:
        task = timeline.task
        plan = timeline.plan
        run = timeline.run
        if task.id != task_id:
            raise BusinessInvestigationRuntimeBlocked("TASK_ID_DRIFTED")
        if plan.task_id != task.id or run.task_id != task.id:
            raise BusinessInvestigationRuntimeBlocked("RUNTIME_TASK_LINEAGE_DRIFTED")
        if run.id != task_run_id:
            raise BusinessInvestigationRuntimeBlocked("TASK_RUN_ID_DRIFTED")
        if task.current_plan_revision_id != plan.id:
            raise BusinessInvestigationRuntimeBlocked("CURRENT_PLAN_DRIFTED")
        if plan.approval_status != "approved":
            raise BusinessInvestigationRuntimeBlocked("PLAN_NOT_APPROVED")
        plan_ref = ExactRevisionRef(
            resource_type="PlanRevision",
            resource_id=plan.id,
            revision=plan.revision,
            content_hash=plan.content_hash,
        )
        if plan_ref != expected_plan_ref:
            raise BusinessInvestigationRuntimeBlocked("PLAN_REF_DRIFTED")
        if run.plan_revision_id != plan.id:
            raise BusinessInvestigationRuntimeBlocked("TASK_RUN_PLAN_DRIFTED")

        checkpoint_ref = cls._checkpoint_ref(timeline, task_run_id, plan.id)
        task_ref = CanonicalRuntimeRef(
            resource_type="Task",
            resource_id=task.id,
            version=task.version,
        )
        task_run_ref = CanonicalRuntimeRef(
            resource_type="TaskRun",
            resource_id=run.id,
            version=run.version,
        )
        snapshot = {
            "tenant": tenant.model_dump(mode="json", by_alias=True),
            "caseRef": case_ref.model_dump(mode="json", by_alias=True),
            "businessInvestigationRunRef": run_ref.model_dump(
                mode="json", by_alias=True
            ),
            "compilationHash": compilation_hash,
            "taskRef": task_ref.model_dump(mode="json", by_alias=True),
            "planRef": plan_ref.model_dump(mode="json", by_alias=True),
            "taskRunRef": task_run_ref.model_dump(mode="json", by_alias=True),
            "checkpointRef": (
                checkpoint_ref.model_dump(mode="json", by_alias=True)
                if checkpoint_ref
                else None
            ),
            "taskRunStatus": run.status.value,
            "planStepCount": len(plan.steps),
        }
        return BusinessInvestigationRuntimeBinding(
            tenant=tenant,
            case_ref=case_ref,
            business_investigation_run_ref=run_ref,
            compilation_hash=compilation_hash,
            task_ref=task_ref,
            plan_ref=plan_ref,
            task_run_ref=task_run_ref,
            checkpoint_ref=checkpoint_ref,
            task_run_status=run.status,
            plan_step_count=len(plan.steps),
            binding_hash=_canonical_hash(snapshot),
        )

    @staticmethod
    def _aip_ref(ref, *, expected_type: str) -> ExactRevisionRef:
        if (
            ref.resource_type != expected_type
            or not isinstance(ref.revision, int)
            or not ref.content_hash.startswith("sha256:")
        ):
            raise BusinessInvestigationRuntimeBlocked("DOMAIN_EXACT_REF_DRIFTED")
        return ExactRevisionRef(
            resource_type=ref.resource_type,
            resource_id=ref.resource_id,
            revision=ref.revision,
            content_hash=ref.content_hash.removeprefix("sha256:"),
        )

    @staticmethod
    def _checkpoint_ref(
        timeline: TaskTimeline,
        task_run_id: str,
        plan_revision_id: str,
    ) -> CanonicalCheckpointRef | None:
        checkpoints = timeline.checkpoints
        if not checkpoints:
            if timeline.run.last_checkpoint_id is not None:
                raise BusinessInvestigationRuntimeBlocked("CHECKPOINT_MISSING")
            return None

        sequences: list[int] = []
        for checkpoint in checkpoints:
            if checkpoint.get("run_id") != task_run_id:
                raise BusinessInvestigationRuntimeBlocked("CHECKPOINT_RUN_DRIFTED")
            if checkpoint.get("plan_revision_id") not in {None, plan_revision_id}:
                raise BusinessInvestigationRuntimeBlocked("CHECKPOINT_PLAN_DRIFTED")
            sequence = checkpoint.get("sequence")
            if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
                raise BusinessInvestigationRuntimeBlocked("CHECKPOINT_SEQUENCE_INVALID")
            sequences.append(sequence)
            state_hash = checkpoint.get("state_hash")
            if not isinstance(state_hash, str) or not re.fullmatch(
                r"[0-9a-f]{64}", state_hash
            ):
                raise BusinessInvestigationRuntimeBlocked("CHECKPOINT_HASH_INVALID")
        if sequences != sorted(set(sequences)):
            raise BusinessInvestigationRuntimeBlocked("CHECKPOINT_SEQUENCE_DRIFTED")

        latest = checkpoints[-1]
        checkpoint_id = latest.get("checkpoint_id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id.strip():
            raise BusinessInvestigationRuntimeBlocked("CHECKPOINT_ID_INVALID")
        if timeline.run.last_checkpoint_id != checkpoint_id:
            raise BusinessInvestigationRuntimeBlocked("LATEST_CHECKPOINT_DRIFTED")
        return CanonicalCheckpointRef(
            resource_id=checkpoint_id,
            sequence=latest["sequence"],
            state_hash=latest["state_hash"],
        )
