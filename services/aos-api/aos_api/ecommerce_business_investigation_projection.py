"""BI-W4-08 rebuildable read model for one business investigation Run."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, Self

import psycopg
from pydantic import Field, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel, PlanStep, ResourceRef, TenantContext
from aos_api.aip_contracts import StepRunStatus, TaskRunStatus
from aos_api.aip_business_investigation_compiler import STAGE_ORDER
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.db import connect as db_connect
from aos_api.ecommerce_business_investigation_artifact import (
    BusinessInvestigationArtifactBinding,
    BusinessInvestigationArtifactType,
)
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationAnalysisType,
    BusinessInvestigationCaseLifecycle,
    BusinessInvestigationCaseRevision,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunControl,
    BusinessInvestigationRunLifecycle,
    BusinessInvestigationRunRecord,
    BusinessInvestigationRunStateRevision,
    BusinessInvestigationUncertainCommand,
)
from aos_api.tenant_scope import TenantScope


PROJECTION_SCHEMA = "aos.ecommerce.business-investigation-workbench-view/v3"
SHA256 = r"^sha256:[0-9a-f]{64}$"

STAGE_TITLES = {
    "portrait": "经营画像",
    "diagnosis": "问题与机会",
    "solution-design": "方案设计",
}
STAGE_QUESTIONS = {
    "portrait": "当前经营基本盘、覆盖、质量与未知是什么？",
    "diagnosis": "哪些问题与机会被证据支持，哪些替代解释仍需保留？",
    "solution-design": "哪些候选方案、约束、风险与验证条件可进入评审？",
}


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


class BusinessInvestigationArtifactSlot(AipContractModel):
    artifact_type: BusinessInvestigationArtifactType
    status: Literal["bound", "missing"]
    artifact_ref: InvestigationExactRef | None = None
    binding_id: str | None = Field(default=None, min_length=1, max_length=200)
    binding_hash: str | None = Field(default=None, pattern=SHA256)
    selection_revision: int | None = Field(default=None, ge=1)
    data_cutoff: datetime | None = None
    lineage_ref: InvestigationExactRef | None = None

    @field_validator("data_cutoff")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("artifact slot dataCutoff must include timezone")
        return value

    @model_validator(mode="after")
    def _honest_status(self) -> Self:
        values = (
            self.artifact_ref,
            self.binding_id,
            self.binding_hash,
            self.selection_revision,
            self.data_cutoff,
            self.lineage_ref,
        )
        if self.status == "missing" and any(item is not None for item in values):
            raise ValueError("missing artifact slot cannot expose stale binding data")
        if self.status == "bound":
            if any(item is None for item in values):
                raise ValueError("bound artifact slot requires exact binding data")
            if self.artifact_ref is None or self.artifact_ref.resource_type != self.artifact_type.value:
                raise ValueError("artifact slot type must match artifactRef")
        return self


class BusinessInvestigationSourceWatermark(AipContractModel):
    case_revision: int = Field(ge=1)
    run_version: int = Field(ge=1)
    state_version: int = Field(ge=1)
    binding_hashes: list[str] = Field(default_factory=list, max_length=4)
    runtime_hash: str | None = Field(default=None, pattern=SHA256)
    content_hash: str = Field(pattern=SHA256)

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        if self.binding_hashes != sorted(set(self.binding_hashes)):
            raise ValueError("source watermark binding hashes must be unique and sorted")
        value = self.model_dump(by_alias=True, mode="json")
        value.pop("contentHash")
        if self.content_hash != _canonical_hash(value):
            raise ValueError("source watermark contentHash drifted")
        return self


class BusinessInvestigationCaseEnvelope(AipContractModel):
    title: str = Field(min_length=1, max_length=500)
    analysis_type: BusinessInvestigationAnalysisType
    lifecycle: BusinessInvestigationCaseLifecycle
    channel_ref: InvestigationExactRef
    business_entity_ref: InvestigationExactRef
    investigation_profile_ref: InvestigationExactRef
    scope_ref: InvestigationExactRef
    schedule_policy_ref: InvestigationExactRef | None = None
    created_by: str = Field(min_length=1, max_length=200)
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _created_at(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Case envelope createdAt must include timezone")
        return value


class BusinessInvestigationRuntimeRef(AipContractModel):
    resource_type: Literal["TaskRun"] = "TaskRun"
    resource_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)


class BusinessInvestigationCheckpointProjection(AipContractModel):
    checkpoint_id: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=1)
    step_key: str | None = Field(default=None, max_length=200)
    state_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _created_at(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Checkpoint createdAt must include timezone")
        return value


class BusinessInvestigationStageRailItem(AipContractModel):
    stage_id: Literal["portrait", "diagnosis", "solution-design"]
    title: str = Field(min_length=1, max_length=120)
    status: Literal[
        "not_started", "running", "waiting_data", "waiting_human", "blocked",
        "review", "accepted", "returned", "completed",
    ]
    step_run_id: str | None = Field(default=None, max_length=200)
    attempt: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _honest_binding(self) -> Self:
        if (self.step_run_id is None) != (self.attempt is None):
            raise ValueError("Stage StepRun identity must be complete")
        if self.title != STAGE_TITLES[self.stage_id]:
            raise ValueError("Stage title drifted")
        return self


class BusinessInvestigationRuntimeProjection(AipContractModel):
    binding_status: Literal["unbound", "task_pending", "bound"]
    task_id: str | None = Field(default=None, max_length=200)
    plan_ref: InvestigationExactRef | None = None
    task_run_ref: BusinessInvestigationRuntimeRef | None = None
    task_run_status: TaskRunStatus | None = None
    checkpoint: BusinessInvestigationCheckpointProjection | None = None
    stages: list[BusinessInvestigationStageRailItem] = Field(min_length=3, max_length=3)
    completed: int = Field(ge=0, le=3)
    total: Literal[3] = 3
    current_stage_id: Literal["portrait", "diagnosis", "solution-design"] | None = None

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if tuple(item.stage_id for item in self.stages) != STAGE_ORDER:
            raise ValueError("StageRail order drifted")
        if self.completed != sum(item.status == "completed" for item in self.stages):
            raise ValueError("StageRail progress drifted")
        runtime_values = (self.task_id, self.plan_ref, self.task_run_ref, self.task_run_status)
        if self.binding_status == "unbound" and any(item is not None for item in runtime_values):
            raise ValueError("unbound runtime cannot expose stale lineage")
        if self.binding_status == "task_pending":
            if self.task_id is None or self.plan_ref is None or any(
                item is not None for item in (self.task_run_ref, self.task_run_status, self.checkpoint)
            ):
                raise ValueError("task_pending runtime lineage drifted")
        if self.binding_status == "bound" and any(item is None for item in runtime_values):
            raise ValueError("bound runtime requires exact lineage")
        return self


class BusinessInvestigationContributionArea(AipContractModel):
    area: Literal["known", "unknown", "assumption", "counter_evidence"]
    title: str = Field(min_length=1, max_length=120)
    status: Literal["reference_only", "present", "unknown"]
    summary: str = Field(min_length=1, max_length=500)
    resource_refs: list[ResourceRef] = Field(default_factory=list, max_length=200)
    exact_refs: list[InvestigationExactRef] = Field(default_factory=list, max_length=20)


class BusinessInvestigationCurrentWorkspace(AipContractModel):
    stage_id: Literal["portrait", "diagnosis", "solution-design"] | None = None
    title: str = Field(min_length=1, max_length=120)
    question: str = Field(min_length=1, max_length=500)
    status: Literal["unbound", "task_pending", "not_started", "running", "blocked", "completed"]
    responsibility_slot_ids: list[str] = Field(default_factory=list, max_length=50)
    assignee_refs: list[ResourceRef] = Field(default_factory=list, max_length=50)
    input_refs: list[ResourceRef] = Field(default_factory=list, max_length=200)
    output_refs: list[ResourceRef] = Field(default_factory=list, max_length=200)
    areas: list[BusinessInvestigationContributionArea] = Field(min_length=4, max_length=4)
    non_claims: list[str] = Field(min_length=3, max_length=10)

    @model_validator(mode="after")
    def _canonical(self) -> Self:
        if [item.area for item in self.areas] != [
            "known", "unknown", "assumption", "counter_evidence"
        ]:
            raise ValueError("current workspace contribution area order drifted")
        for values, label in (
            (self.responsibility_slot_ids, "responsibilitySlotIds"),
            ([item.model_dump_json() for item in self.assignee_refs], "assigneeRefs"),
            ([item.model_dump_json() for item in self.input_refs], "inputRefs"),
            ([item.model_dump_json() for item in self.output_refs], "outputRefs"),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"current workspace {label} must be unique")
        if self.stage_id is None:
            if self.status != "unbound" or any(
                (self.responsibility_slot_ids, self.assignee_refs, self.input_refs, self.output_refs)
            ):
                raise ValueError("unbound current workspace cannot expose stale stage data")
        elif self.title != STAGE_TITLES[self.stage_id] or self.question != STAGE_QUESTIONS[self.stage_id]:
            raise ValueError("current workspace stage copy drifted")
        return self


class BusinessInvestigationWorkbenchView(AipContractModel):
    schema_version: Literal[PROJECTION_SCHEMA] = PROJECTION_SCHEMA
    tenant: TenantContext
    projection_hash: str = Field(pattern=SHA256)
    source_watermark: BusinessInvestigationSourceWatermark
    observed_at: datetime
    case_ref: InvestigationExactRef
    run_ref: InvestigationExactRef
    state_ref: InvestigationExactRef
    case_envelope: BusinessInvestigationCaseEnvelope
    lifecycle: BusinessInvestigationRunLifecycle
    control: BusinessInvestigationRunControl
    pending_requirement_ref: InvestigationExactRef | None = None
    uncertain_command: BusinessInvestigationUncertainCommand | None = None
    runtime: BusinessInvestigationRuntimeProjection
    current_workspace: BusinessInvestigationCurrentWorkspace
    artifacts: list[BusinessInvestigationArtifactSlot] = Field(min_length=4, max_length=4)

    @field_validator("observed_at")
    @classmethod
    def _observed_at(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("observedAt must include timezone")
        return value

    @model_validator(mode="after")
    def _integrity(self) -> Self:
        if [item.artifact_type for item in self.artifacts] != list(BusinessInvestigationArtifactType):
            raise ValueError("artifact slots require canonical order")
        expected = (
            (self.case_ref, "BusinessInvestigationCaseRevision"),
            (self.run_ref, "BusinessInvestigationRun"),
            (self.state_ref, "BusinessInvestigationRunStateRevision"),
        )
        if any(ref.resource_type != resource_type for ref, resource_type in expected):
            raise ValueError("workbench view exact ref type drifted")
        if self.run_ref.resource_id != self.state_ref.resource_id:
            raise ValueError("Run and state refs must retain identity")
        if self.source_watermark.case_revision != self.case_ref.revision:
            raise ValueError("case watermark drifted")
        if self.source_watermark.run_version != self.run_ref.revision:
            raise ValueError("Run watermark drifted")
        if self.source_watermark.state_version != self.state_ref.revision:
            raise ValueError("state watermark drifted")
        if self.projection_hash != self.calculated_projection_hash():
            raise ValueError("projectionHash drifted")
        return self

    def calculated_projection_hash(self) -> str:
        payload = self.model_dump(by_alias=True, mode="json")
        payload.pop("projectionHash")
        payload.pop("observedAt")
        return _canonical_hash(payload)


@dataclass(frozen=True, slots=True)
class BusinessInvestigationProjectionSource:
    case: BusinessInvestigationCaseRevision
    run: BusinessInvestigationRunRecord
    state: BusinessInvestigationRunStateRevision
    bindings: tuple[BusinessInvestigationArtifactBinding, ...] = ()
    runtime: "BusinessInvestigationRuntimeSource | None" = None


@dataclass(frozen=True, slots=True)
class BusinessInvestigationStageRunSource:
    stage_id: str
    step_run_id: str
    attempt: int
    status: StepRunStatus
    input_refs: tuple[ResourceRef, ...] = ()
    output_refs: tuple[ResourceRef, ...] = ()


@dataclass(frozen=True, slots=True)
class BusinessInvestigationStagePlanSource:
    stage_id: str
    responsibility_slot_ids: tuple[str, ...] = ()
    assignee_refs: tuple[ResourceRef, ...] = ()
    input_refs: tuple[ResourceRef, ...] = ()


@dataclass(frozen=True, slots=True)
class BusinessInvestigationCheckpointSource:
    checkpoint_id: str
    sequence: int
    step_key: str | None
    state_hash: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BusinessInvestigationRuntimeSource:
    task_id: str
    plan_ref: InvestigationExactRef
    task_run_id: str | None = None
    task_run_version: int | None = None
    task_run_status: TaskRunStatus | None = None
    plan_stages: tuple[BusinessInvestigationStagePlanSource, ...] = ()
    stages: tuple[BusinessInvestigationStageRunSource, ...] = ()
    checkpoint: BusinessInvestigationCheckpointSource | None = None


class BusinessInvestigationProjectionReader(Protocol):
    def read(self, scope: TenantScope, run_id: str) -> BusinessInvestigationProjectionSource: ...


class BusinessInvestigationProjectionError(RuntimeError):
    pass


class BusinessInvestigationProjectionNotFound(BusinessInvestigationProjectionError):
    pass


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class CanonicalBusinessInvestigationProjectionReader:
    """Read canonical heads and bindings without persisting a projection."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def read(self, scope: TenantScope, run_id: str) -> BusinessInvestigationProjectionSource:
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT c.authority_data AS case_authority,
                              r.authority_data AS run_authority,
                              s.authority_data AS state_authority
                       FROM ecommerce_investigation_run r
                       JOIN ecommerce_investigation_run_state_head s
                         ON s.org_id=r.org_id AND s.project_id=r.project_id AND s.run_id=r.run_id
                       JOIN ecommerce_investigation_case_head h
                         ON h.org_id=r.org_id AND h.project_id=r.project_id AND h.case_id=r.case_id
                       JOIN ecommerce_investigation_case_revision c
                         ON c.org_id=h.org_id AND c.project_id=h.project_id
                        AND c.case_id=h.case_id AND c.revision=h.current_revision
                       WHERE r.org_id=%s AND r.project_id=%s AND r.run_id=%s""",
                    (*scope.key, run_id),
                ).fetchone()
                if row is None:
                    raise BusinessInvestigationProjectionNotFound(
                        "BusinessInvestigationRun projection source is not visible"
                    )
                binding_rows = conn.execute(
                    """SELECT DISTINCT ON (artifact_type) binding_data
                       FROM ecommerce_investigation_artifact_binding
                       WHERE org_id=%s AND project_id=%s AND run_id=%s
                       ORDER BY artifact_type,selection_revision DESC,
                                artifact_revision DESC,bound_at DESC,binding_id DESC""",
                    (*scope.key, run_id),
                ).fetchall()
                compilation_rows = conn.execute(
                    """SELECT task_id,plan_revision_id,plan_revision,plan_content_hash
                       FROM aip_business_investigation_compile_receipt
                       WHERE org_id=%s AND project_id=%s AND run_id=%s
                         AND run_version=%s AND run_content_hash=%s
                       ORDER BY created_at DESC,receipt_id DESC""",
                    (*scope.key, run_id, int(row["run_authority"]["version"]), row["run_authority"]["contentHash"]),
                ).fetchall()
                runtime = self._read_runtime(
                    conn, scope=scope, compilation_rows=compilation_rows
                )
        except BusinessInvestigationProjectionNotFound:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError) as exc:
            raise BusinessInvestigationProjectionError(
                "canonical Workbench projection read failed closed"
            ) from exc
        try:
            return BusinessInvestigationProjectionSource(
                case=BusinessInvestigationCaseRevision.model_validate(row["case_authority"]),
                run=BusinessInvestigationRunRecord.model_validate(row["run_authority"]),
                state=BusinessInvestigationRunStateRevision.model_validate(row["state_authority"]),
                bindings=tuple(
                    BusinessInvestigationArtifactBinding.model_validate(item["binding_data"])
                    for item in binding_rows
                ),
                runtime=runtime,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise BusinessInvestigationProjectionError(
                "canonical Workbench projection contract failed closed"
            ) from exc

    @staticmethod
    def _read_runtime(
        conn: Any, *, scope: TenantScope, compilation_rows: list[Any]
    ) -> BusinessInvestigationRuntimeSource | None:
        if not compilation_rows:
            return None
        identities = {
            (
                str(item["task_id"]), str(item["plan_revision_id"]),
                int(item["plan_revision"]), str(item["plan_content_hash"]),
            )
            for item in compilation_rows
        }
        if len(identities) != 1:
            raise ValueError("Business Investigation compilation lineage is ambiguous")
        task_id, plan_id, plan_revision, plan_hash = next(iter(identities))
        runtime_row = conn.execute(
            """SELECT p.steps,r.run_id,r.version AS run_version,r.status AS run_status
               FROM aip_plan_revision p
               LEFT JOIN LATERAL (
                 SELECT run_id,version,status FROM aip_task_run r
                  WHERE r.org_id=p.org_id AND r.project_id=p.project_id
                    AND r.task_id=p.task_id AND r.plan_revision_id=p.plan_revision_id
                  ORDER BY r.created_at DESC,r.run_id DESC LIMIT 1
               ) r ON TRUE
               WHERE p.org_id=%s AND p.project_id=%s AND p.task_id=%s
                 AND p.plan_revision_id=%s AND p.revision=%s AND p.content_hash=%s""",
            (*scope.key, task_id, plan_id, plan_revision, plan_hash),
        ).fetchone()
        if runtime_row is None:
            raise ValueError("Business Investigation exact Plan is not visible")
        steps = runtime_row["steps"]
        if not isinstance(steps, list) or [item.get("stepKey") for item in steps] != list(STAGE_ORDER):
            raise ValueError("Business Investigation Plan stages drifted")
        plan_steps = tuple(PlanStep.model_validate(item) for item in steps)
        plan_stages = tuple(
            BusinessInvestigationStagePlanSource(
                stage_id=item.step_key,
                responsibility_slot_ids=tuple(item.responsibility_slot_ids),
                assignee_refs=tuple(item.assignee_refs),
                input_refs=tuple(item.input_refs),
            )
            for item in plan_steps
        )
        plan_ref = InvestigationExactRef(
            resource_type="PlanRevision", resource_id=plan_id,
            revision=plan_revision, content_hash=f"sha256:{plan_hash}",
        )
        task_run_id = runtime_row["run_id"]
        if task_run_id is None:
            return BusinessInvestigationRuntimeSource(
                task_id=task_id, plan_ref=plan_ref, plan_stages=plan_stages
            )
        stage_rows = conn.execute(
            """SELECT DISTINCT ON (step_key) step_key,step_run_id,attempt,status,
                              input_refs,output_refs
               FROM aip_step_run
               WHERE org_id=%s AND project_id=%s AND run_id=%s
                 AND step_key=ANY(%s)
               ORDER BY step_key,attempt DESC,created_at DESC,step_run_id DESC""",
            (*scope.key, task_run_id, list(STAGE_ORDER)),
        ).fetchall()
        checkpoint_row = conn.execute(
            """SELECT checkpoint_id,sequence,step_key,state_hash,created_at
               FROM aip_checkpoint
               WHERE org_id=%s AND project_id=%s AND run_id=%s
               ORDER BY sequence DESC,checkpoint_id DESC LIMIT 1""",
            (*scope.key, task_run_id),
        ).fetchone()
        checkpoint = None if checkpoint_row is None else BusinessInvestigationCheckpointSource(
            checkpoint_id=str(checkpoint_row["checkpoint_id"]),
            sequence=int(checkpoint_row["sequence"]),
            step_key=checkpoint_row["step_key"],
            state_hash=str(checkpoint_row["state_hash"]),
            created_at=checkpoint_row["created_at"],
        )
        return BusinessInvestigationRuntimeSource(
            task_id=task_id,
            plan_ref=plan_ref,
            task_run_id=str(task_run_id),
            task_run_version=int(runtime_row["run_version"]),
            task_run_status=TaskRunStatus(str(runtime_row["run_status"])),
            plan_stages=plan_stages,
            stages=tuple(
                BusinessInvestigationStageRunSource(
                    stage_id=str(item["step_key"]),
                    step_run_id=str(item["step_run_id"]),
                    attempt=int(item["attempt"]),
                    status=StepRunStatus(str(item["status"])),
                    input_refs=tuple(ResourceRef.model_validate(ref) for ref in item["input_refs"]),
                    output_refs=tuple(ResourceRef.model_validate(ref) for ref in item["output_refs"]),
                )
                for item in stage_rows
            ),
            checkpoint=checkpoint,
        )


class BusinessInvestigationProjectionBuilder:
    def __init__(self, reader: BusinessInvestigationProjectionReader) -> None:
        self._reader = reader

    def build(
        self, scope: TenantScope, run_id: str, *, observed_at: datetime
    ) -> BusinessInvestigationWorkbenchView:
        source = self._reader.read(scope, run_id)
        self._validate_source(source, scope=scope, run_id=run_id)
        bindings = {item.artifact_ref.resource_type: item for item in source.bindings}
        artifacts = [self._slot(kind, bindings.get(kind.value)) for kind in BusinessInvestigationArtifactType]
        runtime = self._runtime(source.runtime)
        current_workspace = self._current_workspace(source.runtime, runtime, artifacts)
        binding_hashes = sorted(item.binding_hash for item in source.bindings)
        watermark_value = {
            "caseRevision": source.case.revision,
            "runVersion": source.run.version,
            "stateVersion": source.state.version,
            "bindingHashes": binding_hashes,
            "runtimeHash": _canonical_hash(runtime.model_dump(by_alias=True, mode="json")) if source.runtime else None,
        }
        watermark = BusinessInvestigationSourceWatermark.model_validate(
            {**watermark_value, "contentHash": _canonical_hash(watermark_value)}
        )
        draft = BusinessInvestigationWorkbenchView.model_construct(
            schema_version=PROJECTION_SCHEMA,
            tenant=source.case.tenant,
            projection_hash="sha256:" + "0" * 64,
            source_watermark=watermark,
            observed_at=observed_at,
            case_ref=InvestigationExactRef.model_validate(
                self._ref(
                    "BusinessInvestigationCaseRevision",
                    source.case.case_id,
                    source.case.revision,
                    source.case.content_hash,
                )
            ),
            run_ref=InvestigationExactRef.model_validate(
                self._ref(
                    "BusinessInvestigationRun",
                    source.run.run_id,
                    source.run.version,
                    source.run.content_hash,
                )
            ),
            state_ref=InvestigationExactRef.model_validate(
                self._ref(
                    "BusinessInvestigationRunStateRevision",
                    source.state.run_id,
                    source.state.version,
                    source.state.content_hash,
                )
            ),
            case_envelope=BusinessInvestigationCaseEnvelope(
                title=source.case.title,
                analysis_type=source.case.analysis_type.value,
                lifecycle=source.case.lifecycle.value,
                channel_ref=source.case.channel_ref,
                business_entity_ref=source.case.business_entity_ref,
                investigation_profile_ref=source.case.investigation_profile_ref,
                scope_ref=source.case.scope_ref,
                schedule_policy_ref=source.case.schedule_policy_ref,
                created_by=source.case.created_by,
                created_at=source.case.created_at,
            ),
            lifecycle=source.state.lifecycle,
            control=source.state.control,
            pending_requirement_ref=source.state.pending_requirement_ref,
            uncertain_command=source.state.uncertain_command,
            runtime=runtime,
            current_workspace=current_workspace,
            artifacts=artifacts,
        )
        payload = draft.model_dump(by_alias=True, mode="json")
        payload["projectionHash"] = draft.calculated_projection_hash()
        return BusinessInvestigationWorkbenchView.model_validate(payload)

    @staticmethod
    def _runtime(
        source: BusinessInvestigationRuntimeSource | None,
    ) -> BusinessInvestigationRuntimeProjection:
        rows = {} if source is None else {item.stage_id: item for item in source.stages}
        status_map = {
            StepRunStatus.QUEUED: "not_started",
            StepRunStatus.RUNNING: "running",
            StepRunStatus.SUCCEEDED: "completed",
            StepRunStatus.FAILED: "blocked",
            StepRunStatus.SKIPPED: "completed",
            StepRunStatus.UNKNOWN: "blocked",
        }
        stages = [
            BusinessInvestigationStageRailItem(
                stage_id=stage_id,
                title=STAGE_TITLES[stage_id],
                status="not_started" if rows.get(stage_id) is None else status_map[rows[stage_id].status],
                step_run_id=None if rows.get(stage_id) is None else rows[stage_id].step_run_id,
                attempt=None if rows.get(stage_id) is None else rows[stage_id].attempt,
            )
            for stage_id in STAGE_ORDER
        ]
        current = next((item.stage_id for item in stages if item.status != "completed"), None)
        if source is None:
            return BusinessInvestigationRuntimeProjection(
                binding_status="unbound", stages=stages, completed=0, current_stage_id=None
            )
        if source.task_run_id is None:
            return BusinessInvestigationRuntimeProjection(
                binding_status="task_pending", task_id=source.task_id,
                plan_ref=source.plan_ref, stages=stages, completed=0, current_stage_id=None,
            )
        checkpoint = None if source.checkpoint is None else BusinessInvestigationCheckpointProjection(
            checkpoint_id=source.checkpoint.checkpoint_id,
            sequence=source.checkpoint.sequence,
            step_key=source.checkpoint.step_key,
            state_hash=source.checkpoint.state_hash,
            created_at=source.checkpoint.created_at,
        )
        return BusinessInvestigationRuntimeProjection(
            binding_status="bound", task_id=source.task_id, plan_ref=source.plan_ref,
            task_run_ref=BusinessInvestigationRuntimeRef(
                resource_id=source.task_run_id, version=source.task_run_version
            ),
            task_run_status=source.task_run_status, checkpoint=checkpoint, stages=stages,
            completed=sum(item.status == "completed" for item in stages),
            current_stage_id=current,
        )

    @staticmethod
    def _current_workspace(
        source: BusinessInvestigationRuntimeSource | None,
        runtime: BusinessInvestigationRuntimeProjection,
        artifacts: list[BusinessInvestigationArtifactSlot],
    ) -> BusinessInvestigationCurrentWorkspace:
        non_claims = [
            "可回链输入不等于已确认经营事实。",
            "当前阶段状态不代表方案已在真实业务系统执行。",
            "不展示或持久化模型私有过程。",
        ]
        if source is None:
            return BusinessInvestigationCurrentWorkspace(
                title="尚无当前阶段",
                question="尚未建立 canonical Plan 绑定，当前经营问题未知。",
                status="unbound",
                areas=BusinessInvestigationProjectionBuilder._areas([], [], "尚未绑定 canonical Plan。"),
                non_claims=non_claims,
            )
        plan_by_stage = {item.stage_id: item for item in source.plan_stages}
        run_by_stage = {item.stage_id: item for item in source.stages}
        if source.task_run_id is None:
            stage_id = STAGE_ORDER[0]
            status = "task_pending"
        elif runtime.current_stage_id is None:
            stage_id = STAGE_ORDER[-1]
            status = "completed"
        else:
            stage_id = runtime.current_stage_id
            stage_status = next(item.status for item in runtime.stages if item.stage_id == stage_id)
            status = {
                "running": "running",
                "blocked": "blocked",
                "completed": "completed",
            }.get(stage_status, "not_started")
        plan = plan_by_stage.get(stage_id)
        stage_run = run_by_stage.get(stage_id)
        plan_inputs = [] if plan is None else list(plan.input_refs)
        run_inputs = [] if stage_run is None else list(stage_run.input_refs)
        inputs = BusinessInvestigationProjectionBuilder._unique_resource_refs(plan_inputs + run_inputs)
        outputs = BusinessInvestigationProjectionBuilder._unique_resource_refs(
            [] if stage_run is None else list(stage_run.output_refs)
        )
        exact_inputs = [
            item.artifact_ref for item in artifacts
            if item.status == "bound" and item.artifact_ref is not None
        ]
        unknown_reason = {
            "task_pending": "Plan 已绑定，但尚未创建 TaskRun。",
            "not_started": "当前阶段尚未启动，经营结论仍未知。",
            "running": "当前阶段运行中，未形成专门权威的内容仍保持未知。",
            "blocked": "当前阶段已阻断，缺失条件不得推演为经营结论。",
            "completed": "阶段已完成，但未绑定专门内容权威的分类仍保持未知。",
        }[status]
        return BusinessInvestigationCurrentWorkspace(
            stage_id=stage_id,
            title=STAGE_TITLES[stage_id],
            question=STAGE_QUESTIONS[stage_id],
            status=status,
            responsibility_slot_ids=[] if plan is None else list(plan.responsibility_slot_ids),
            assignee_refs=[] if plan is None else list(plan.assignee_refs),
            input_refs=inputs,
            output_refs=outputs,
            areas=BusinessInvestigationProjectionBuilder._areas(inputs + outputs, exact_inputs, unknown_reason),
            non_claims=non_claims,
        )

    @staticmethod
    def _areas(
        resource_refs: list[ResourceRef],
        exact_refs: list[InvestigationExactRef],
        unknown_reason: str,
    ) -> list[BusinessInvestigationContributionArea]:
        has_refs = bool(resource_refs or exact_refs)
        return [
            BusinessInvestigationContributionArea(
                area="known", title="已知与可回链输入",
                status="reference_only" if has_refs else "unknown",
                summary=("仅确认存在可回链输入；其内容尚不能自动声称为经营事实。" if has_refs else "缺少可回链输入，已知事实保持未知。"),
                resource_refs=resource_refs, exact_refs=exact_refs,
            ),
            BusinessInvestigationContributionArea(
                area="unknown", title="未知与缺口", status="present", summary=unknown_reason,
            ),
            BusinessInvestigationContributionArea(
                area="assumption", title="关键假设", status="unknown",
                summary="尚无专门的假设 authority，禁止从模型输出或阶段状态推演。",
            ),
            BusinessInvestigationContributionArea(
                area="counter_evidence", title="反证与替代解释", status="unknown",
                summary="尚无专门的反证 authority，一般 Evidence 不自动归类为反证。",
            ),
        ]

    @staticmethod
    def _unique_resource_refs(values: list[ResourceRef]) -> list[ResourceRef]:
        unique: dict[str, ResourceRef] = {}
        for item in values:
            key = item.model_dump_json(by_alias=True)
            unique[key] = item
        return list(unique.values())

    @staticmethod
    def _ref(resource_type: str, resource_id: str, revision: int, content_hash: str) -> dict[str, Any]:
        return {
            "resourceType": resource_type,
            "resourceId": resource_id,
            "revision": revision,
            "contentHash": content_hash,
        }

    @staticmethod
    def _slot(
        kind: BusinessInvestigationArtifactType,
        binding: BusinessInvestigationArtifactBinding | None,
    ) -> BusinessInvestigationArtifactSlot:
        if binding is None:
            return BusinessInvestigationArtifactSlot(artifact_type=kind, status="missing")
        return BusinessInvestigationArtifactSlot(
            artifact_type=kind,
            status="bound",
            artifact_ref=binding.artifact_ref,
            binding_id=binding.binding_id,
            binding_hash=binding.binding_hash,
            selection_revision=binding.selection_revision,
            data_cutoff=binding.data_cutoff,
            lineage_ref=binding.lineage_ref,
        )

    @staticmethod
    def _validate_source(
        source: BusinessInvestigationProjectionSource, *, scope: TenantScope, run_id: str
    ) -> None:
        tenant = (source.case.tenant.org_id, source.case.tenant.project_id)
        if tenant != scope.key or any(
            (item.tenant.org_id, item.tenant.project_id) != scope.key
            for item in (source.run, source.state, *source.bindings)
        ):
            raise BusinessInvestigationProjectionError("projection source tenant drifted")
        if source.run.run_id != run_id or source.state.run_id != run_id:
            raise BusinessInvestigationProjectionError("projection source Run identity drifted")
        if source.run.case_ref.resource_id != source.case.case_id:
            raise BusinessInvestigationProjectionError("projection source Case identity drifted")
        types = [item.artifact_ref.resource_type for item in source.bindings]
        if len(types) != len(set(types)) or any(
            item.run_ref.resource_id != run_id
            or item.case_ref.resource_id != source.case.case_id
            for item in source.bindings
        ):
            raise BusinessInvestigationProjectionError("projection artifact binding drifted")
        if source.runtime is not None:
            stage_ids = [item.stage_id for item in source.runtime.stages]
            if len(stage_ids) != len(set(stage_ids)) or any(item not in STAGE_ORDER for item in stage_ids):
                raise BusinessInvestigationProjectionError("projection runtime Stage lineage drifted")
            run_values = (
                source.runtime.task_run_id,
                source.runtime.task_run_version,
                source.runtime.task_run_status,
            )
            if any(item is None for item in run_values) != all(item is None for item in run_values):
                raise BusinessInvestigationProjectionError("projection TaskRun lineage drifted")


__all__ = [
    "BusinessInvestigationArtifactSlot",
    "BusinessInvestigationProjectionBuilder",
    "BusinessInvestigationProjectionError",
    "BusinessInvestigationProjectionNotFound",
    "BusinessInvestigationProjectionReader",
    "BusinessInvestigationProjectionSource",
    "BusinessInvestigationRuntimeSource",
    "BusinessInvestigationStageRunSource",
    "BusinessInvestigationCheckpointSource",
    "BusinessInvestigationSourceWatermark",
    "BusinessInvestigationWorkbenchView",
    "CanonicalBusinessInvestigationProjectionReader",
    "PROJECTION_SCHEMA",
]
