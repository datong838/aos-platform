"""Compose W8-05 FULL video production and recovery without side effects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Protocol

from aos_api.ecommerce_workshop_full_video_scenario_contracts import (
    FullVideoBlocker,
    FullVideoCommands,
    FullVideoComposition,
    FullVideoExactRef,
    FullVideoFaultId,
    FullVideoFaultRecovery,
    FullVideoLedger,
    FullVideoResponsibility,
    FullVideoResponsibilityId,
    FullVideoScenarioContribution,
    FullVideoStage,
    FullVideoStageId,
)
from aos_api.tenant_scope import TenantScope


@dataclass(frozen=True, slots=True)
class FullVideoScenarioObservation:
    scope: TenantScope
    cutoff: datetime
    root_brief_ref: FullVideoExactRef
    task_run_ref: FullVideoExactRef
    full_production_binding_hash: str
    composition: FullVideoComposition
    responsibilities: tuple[FullVideoResponsibility, ...]
    stages: tuple[FullVideoStage, ...]
    fault_recovery: tuple[FullVideoFaultRecovery, ...]
    ledger: FullVideoLedger


class FullVideoScenarioCanonicalReader(Protocol):
    def read_scenario(self, scope: TenantScope, *, cutoff: datetime) -> FullVideoScenarioObservation | None: ...


def full_production_binding_hash(observation: FullVideoScenarioObservation) -> str:
    values = [
        f"brief:{observation.root_brief_ref.resource_id}:{observation.root_brief_ref.revision}:{observation.root_brief_ref.content_hash}",
        f"run:{observation.task_run_ref.resource_id}:{observation.task_run_ref.revision}:{observation.task_run_ref.content_hash}",
        f"logic:{observation.composition.logic_revision_ref.resource_id}:{observation.composition.logic_revision_ref.revision}:{observation.composition.logic_revision_ref.content_hash}",
    ]
    values.extend(f"skill:{ref.resource_id}:{ref.revision}:{ref.content_hash}" for ref in observation.composition.atomic_skill_refs)
    values.extend(
        f"role:{item.role_ref.resource_id}:{item.assignee_ref.resource_id}:{item.skill_binding_ref.resource_id}:{item.skill_binding_ref.revision}:{item.skill_binding_ref.content_hash}"
        for item in observation.composition.role_bindings
    )
    values.extend(
        f"responsibility:{item.responsibility_id}:{item.status}:{item.assignee_ref.resource_id if item.assignee_ref else 'blocked'}:{item.skill_binding_ref.resource_id if item.skill_binding_ref else 'blocked'}"
        for item in observation.responsibilities
    )
    for stage in observation.stages:
        values.append(f"stage:{stage.stage_id}:{stage.status}")
        values.extend(f"ref:{ref.resource_type}:{ref.resource_id}:{ref.revision}:{ref.content_hash}" for ref in stage.exact_refs)
    for fault in observation.fault_recovery:
        values.append(f"fault:{fault.fault_id}:{fault.status}:{fault.recovery_decision}")
        values.extend(f"ref:{ref.resource_type}:{ref.resource_id}:{ref.revision}:{ref.content_hash}" for ref in fault.authority_refs)
    return sha256("|".join(values).encode()).hexdigest()


class EcommerceWorkshopFullVideoScenario:
    def __init__(self, *, reader: FullVideoScenarioCanonicalReader | None = None) -> None:
        self._reader = reader

    def read(self, *, scope: TenantScope, cutoff: datetime) -> FullVideoScenarioContribution:
        if cutoff.utcoffset() is None:
            raise ValueError("FULL video scenario cutoff requires timezone")
        observation = self._reader.read_scenario(scope, cutoff=cutoff) if self._reader is not None else None
        if observation is None:
            return self._blocked(cutoff, "FULL_VIDEO_EXACT_ROOT_REQUIRED", "aip.media-production-authority")
        if observation.scope != scope or observation.cutoff != cutoff:
            return self._blocked(cutoff, "FULL_VIDEO_SCOPE_OR_CUTOFF_DRIFT", "workshop.full-video-reader")
        if observation.full_production_binding_hash != full_production_binding_hash(observation):
            return self._blocked(cutoff, "FULL_VIDEO_BINDING_DRIFT", "workshop.full-video-binding")
        brief_stage, run_stage = observation.stages[:2]
        if observation.root_brief_ref not in brief_stage.exact_refs or observation.task_run_ref not in run_stage.exact_refs:
            return self._blocked(cutoff, "FULL_VIDEO_ROOT_STAGE_DRIFT", "aip.media-production-authority")
        blockers = [item.blocker for item in observation.responsibilities if item.blocker is not None]
        blockers.extend(item.blocker for item in observation.stages if item.blocker is not None)
        blockers.extend(item.blocker for item in observation.fault_recovery if item.blocker is not None)
        if not blockers:
            return self._blocked(cutoff, "FULL_VIDEO_OPERATIONAL_AUTHORIZATION_REQUIRED", "workshop.full-video-operational-gate")
        return FullVideoScenarioContribution(
            rootBriefRef=observation.root_brief_ref,
            taskRunRef=observation.task_run_ref,
            fullProductionBindingHash=observation.full_production_binding_hash,
            composition=observation.composition,
            evaluatedAt=cutoff,
            responsibilities=list(observation.responsibilities),
            stages=list(observation.stages),
            faultRecovery=list(observation.fault_recovery),
            ledger=observation.ledger,
            blockers=blockers,
            commands=FullVideoCommands(),
        )

    @staticmethod
    def _blocked(cutoff: datetime, code: str, dependency: str) -> FullVideoScenarioContribution:
        blocker = FullVideoBlocker(
            code=code,
            dependency=dependency,
            requiredAction="provide tenant-bound exact FULL production, responsibility, stage, artifact, usage and recovery refs at one cutoff",
        )
        responsibilities = [
            FullVideoResponsibility(
                responsibilityId=item,
                label=item.value,
                status="blocked",
                independentReviewRequired=item is FullVideoResponsibilityId.REVIEW,
                blocker=blocker,
            )
            for item in FullVideoResponsibilityId
        ]
        stages = [
            FullVideoStage(
                stageId=item,
                status="blocked",
                contribution="等待 exact authority；不制造 TaskRun、Artifact、Usage 或发布事实",
                blocker=blocker,
            )
            for item in FullVideoStageId
        ]
        faults = [
            FullVideoFaultRecovery(
                faultId=item,
                status="blocked",
                recoveryDecision="等待 durable authority；不自动重试或切换 Provider",
                blocker=blocker,
            )
            for item in FullVideoFaultId
        ]
        return FullVideoScenarioContribution(
            evaluatedAt=cutoff,
            responsibilities=responsibilities,
            stages=stages,
            faultRecovery=faults,
            ledger=FullVideoLedger(
                responsibilitiesObserved=0,
                stagesObserved=0,
                attemptsExpected=0,
                attemptsObserved=0,
                artifactsExpected=0,
                artifactsObserved=0,
                mediaGatesObserved=0,
                faultCasesObserved=0,
                usageBucketsExpected=0,
                usageBucketsObserved=0,
            ),
            blockers=[blocker],
        )


__all__ = [
    "EcommerceWorkshopFullVideoScenario",
    "FullVideoScenarioCanonicalReader",
    "FullVideoScenarioObservation",
    "full_production_binding_hash",
]
