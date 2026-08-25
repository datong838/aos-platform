"""Canonical W7-09 Media Studio lifecycle composer.

The composer joins existing tenant authorities. It does not create or advance
TaskRun, Stage, Artifact, Review, Usage, Action, or Effect state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aos_api.aip_media_responsibility_capability_map import (
    MEDIA_RESPONSIBILITY_CAPABILITY_MAP,
)
from aos_api.ecommerce_workshop_media_studio_lifecycle_contracts import (
    MediaArtifactFamilyContribution,
    MediaCommandCapability,
    MediaContributionStatus,
    MediaLifecycleAuthorityRef,
    MediaLifecycleNodeContribution,
    MediaLifecycleNodeId,
    MediaResponsibilityContribution,
    MediaReviewIssueContribution,
    MediaStageContribution,
    MediaStudioLifecycleContribution,
)
from aos_api.tenant_scope import TenantScope


class MediaStudioLifecycleError(RuntimeError):
    """A canonical dependency could not produce one bounded context."""


class MediaStudioLifecycleConflict(MediaStudioLifecycleError):
    """More than one production context was found without an exact selector."""


SLOT_LABELS = {
    "media.producer": "制片 / 统筹",
    "media.director": "导演 / 创意",
    "media.screenwriter": "编剧",
    "media.art": "美术",
    "media.storyboard": "分镜",
    "media.capture": "摄影 / 生成",
    "media.post": "剪辑 / 后期",
    "media.review": "评估 / 审核",
}


class EcommerceWorkshopMediaStudioLifecycle:
    def __init__(
        self,
        *,
        production_store: Any,
        production_start_service: Any,
        provider_job_store: Any,
        media_finance_store: Any,
    ) -> None:
        self._production = production_store
        self._starts = production_start_service
        self._jobs = provider_job_store
        self._finance = media_finance_store

    @staticmethod
    def _ref(value: Any, *, resource_type: str | None = None) -> MediaLifecycleAuthorityRef:
        return MediaLifecycleAuthorityRef(
            resourceType=resource_type or value.resource_type,
            resourceId=value.resource_id,
            revision=int(value.revision),
            contentHash=getattr(value, "content_hash", None),
        )

    @staticmethod
    def _context_ref(context: Any) -> MediaLifecycleAuthorityRef:
        return MediaLifecycleAuthorityRef(
            resourceType="ProductionContextRevision",
            resourceId=context.context_id,
            revision=context.revision,
            contentHash=context.content_hash,
        )

    @staticmethod
    def _node(
        node_id: MediaLifecycleNodeId,
        label: str,
        status: MediaContributionStatus,
        *,
        refs: list[MediaLifecycleAuthorityRef] | None = None,
        blockers: list[str] | None = None,
        observed_at: datetime | None = None,
    ) -> MediaLifecycleNodeContribution:
        return MediaLifecycleNodeContribution(
            nodeId=node_id,
            label=label,
            status=status,
            authorityRefs=refs or [],
            blockerCodes=blockers or [],
            observedAt=observed_at,
        )

    def read(self, scope: TenantScope, *, cutoff: datetime) -> MediaStudioLifecycleContribution | None:
        if cutoff.utcoffset() is None:
            raise MediaStudioLifecycleError("media lifecycle cutoff requires timezone")
        contexts = [item for item in self._production.list_production_contexts(scope).items if item.created_at <= cutoff]
        if not contexts:
            return None
        if len(contexts) != 1:
            raise MediaStudioLifecycleConflict("MEDIA_PRODUCTION_CONTEXT_SELECTOR_REQUIRED")
        context = contexts[0]
        context_ref = self._context_ref(context)

        plan = self._production.get_responsibility_plan(
            scope,
            context.responsibility_plan_ref.resource_id,
            context.responsibility_plan_ref.revision,
        )
        plan_slots = {slot.slot_id: slot for slot in plan.slots}
        responsibilities: list[MediaResponsibilityContribution] = []
        blockers: list[str] = []
        for slot_id, capabilities in MEDIA_RESPONSIBILITY_CAPABILITY_MAP.items():
            slot = plan_slots.get(slot_id)
            if slot is None or slot.assignee_resolution_receipt_id is None:
                code = f"MEDIA_RESPONSIBILITY_{slot_id.split('.')[-1].upper()}_NOT_RESOLVED"
                blockers.append(code)
                responsibilities.append(
                    MediaResponsibilityContribution(
                        slotId=slot_id,
                        label=SLOT_LABELS[slot_id],
                        responsibilityType=slot.responsibility_type if slot is not None else slot_id,
                        status="blocked",
                        requiredCapabilityIds=list(capabilities),
                        blockerCodes=[code],
                    )
                )
                continue
            responsibilities.append(
                MediaResponsibilityContribution(
                    slotId=slot_id,
                    label=SLOT_LABELS[slot_id],
                    responsibilityType=slot.responsibility_type,
                    status="assigned",
                    requiredCapabilityIds=slot.required_capability_ids,
                    assigneeKind=slot.assignee.kind.value,
                    assigneeId=slot.assignee.resource_id,
                    assigneeVersion=slot.assignee.version,
                    resolutionReceiptId=slot.assignee_resolution_receipt_id,
                )
            )

        starts = [
            item
            for item in self._starts.list(scope).items
            if item.production_context_ref is not None
            and item.production_context_ref.resource_id == context.context_id
            and item.production_context_ref.revision == context.revision
            and item.created_at <= cutoff
        ]
        run_ids = {
            item.task_run_ref.resource_id
            for item in starts
            if item.task_run_ref is not None and item.status.value == "started"
        }
        jobs = [item for item in self._jobs.list_jobs(scope, limit=100).items if item.task_run_ref.resource_id in run_ids]
        finances = [item for item in self._finance.list(scope, limit=100).items if item.task_run_ref.resource_id in run_ids]
        finance_by_job = {item.job_ref.resource_id: item for item in finances}
        stages: list[MediaStageContribution] = []
        for job in jobs:
            finance = finance_by_job.get(job.job_id)
            stages.append(
                MediaStageContribution(
                    stageId=(finance.step_run_ref.resource_id if finance is not None else job.step_run_ref.resource_id),
                    taskRunId=job.task_run_ref.resource_id,
                    attempt=(finance.step_run_ref.revision if finance is not None else job.step_run_ref.revision),
                    status=job.status.value,
                    capabilityRef=self._ref(job.binding.capability_ref),
                    colleagueBindingRef=self._ref(job.binding.binding_ref),
                    providerRef=self._ref(job.binding.provider_ref),
                    providerJobId=job.job_id,
                    blockerCodes=job.blocker_codes,
                )
            )

        families = self._production.list_artifact_families(scope).items
        related_families: list[Any] = []
        for family in families:
            linked = any(
                ref.resource_type == "TaskRun" and ref.resource_id in run_ids
                for member in family.members
                for ref in member.lineage_refs
            )
            if linked:
                related_families.append(family)
        family_ids = {item.family_id for item in related_families}
        gate_sets = [item for item in self._production.list_media_gate_sets(scope).items if item.family_id in family_ids and item.created_at <= cutoff]
        artifact_ids = {member.artifact_ref.artifact_id for family in related_families for member in family.members}
        issues = [item for item in self._production.list_review_issues(scope).items if item.artifact_ref.artifact_id in artifact_ids and item.updated_at <= cutoff]
        issue_ids = {item.issue_id for item in issues}
        return_decisions = [item for item in self._production.list_return_decisions(scope).items if item.issue_id in issue_ids and item.created_at <= cutoff]

        artifacts: list[MediaArtifactFamilyContribution] = []
        for family in related_families:
            family_gates = [item for item in gate_sets if item.family_id == family.family_id]
            family_artifacts = {member.artifact_ref.artifact_id for member in family.members}
            family_issues = [item for item in issues if item.artifact_ref.artifact_id in family_artifacts]
            readiness = None
            if len(family_gates) == 1:
                readiness = family_gates[0].readiness.value
            elif len(family_gates) > 1:
                readiness = "conflict"
            artifacts.append(
                MediaArtifactFamilyContribution(
                    familyId=family.family_id,
                    version=family.version,
                    topologyStatus=family.topology_status.value,
                    memberCount=len(family.members),
                    conflictCount=sum(group.status.value == "conflict" for group in family.candidate_groups),
                    gateSetCount=len(family_gates),
                    latestGateReadiness=readiness,
                    issueCount=len(family_issues),
                )
            )

        review_issues = [
            MediaReviewIssueContribution(
                issueId=item.issue_id,
                version=item.version,
                status=item.status.value,
                severity=item.severity.value,
                artifactId=item.artifact_ref.artifact_id,
                artifactHash=item.artifact_ref.content_hash,
                returnStage=item.return_stage,
                returnDecisionCount=sum(decision.issue_id == item.issue_id for decision in return_decisions),
            )
            for item in issues
        ]

        start_refs = [
            MediaLifecycleAuthorityRef(
                resourceType="ProductionStartDecision",
                resourceId=item.decision_id,
                revision=1,
                contentHash=item.dependency_snapshot_hash,
            )
            for item in starts
        ]
        review_refs = [
            MediaLifecycleAuthorityRef(
                resourceType="MediaGateSetDecision",
                resourceId=item.gate_set_id,
                revision=1,
                contentHash=item.content_hash,
            )
            for item in gate_sets
        ]
        settled = [item for item in finances if item.settlement_status.value == "settled"]
        lifecycle = [
            self._node(MediaLifecycleNodeId.PREPARE, "准备", MediaContributionStatus.READY, refs=[context_ref], observed_at=context.created_at),
            self._node(MediaLifecycleNodeId.FREEZE_CONFIRM, "冻结 / 确认", MediaContributionStatus.READY, refs=[context_ref, self._ref(context.responsibility_plan_ref)], observed_at=context.created_at),
            self._node(MediaLifecycleNodeId.COMPILE_APPROVE, "编译 / 批准", MediaContributionStatus.ACTIVE if starts else MediaContributionStatus.BLOCKED, refs=start_refs, blockers=[] if starts else ["MEDIA_PLAN_START_DECISION_NOT_AVAILABLE"]),
            self._node(MediaLifecycleNodeId.START_RUN, "启动 / 运行", MediaContributionStatus.ACTIVE if run_ids else MediaContributionStatus.BLOCKED, refs=start_refs, blockers=[] if run_ids else ["MEDIA_TASK_RUN_NOT_STARTED"]),
            self._node(MediaLifecycleNodeId.REVIEW_RETURN, "评审 / 退回", MediaContributionStatus.READY if review_refs else MediaContributionStatus.NOT_STARTED, refs=review_refs),
            self._node(MediaLifecycleNodeId.DELIVER_PUBLISH, "交付 / 发布", MediaContributionStatus.BLOCKED, blockers=["MEDIA_PUBLICATION_NOT_AUTHORIZED"]),
            self._node(MediaLifecycleNodeId.RECONCILE_EFFECT, "对账 / 效果", MediaContributionStatus.BLOCKED, refs=[self._ref(item.settlement_decision_ref) for item in settled if item.settlement_decision_ref is not None], blockers=["MEDIA_EFFECT_REVIEW_NOT_AUTHORIZED"]),
        ]
        blockers.extend(["MEDIA_PUBLICATION_NOT_AUTHORIZED", "MEDIA_EFFECT_REVIEW_NOT_AUTHORIZED"])
        required_refs = [context_ref, self._ref(context.responsibility_plan_ref)]
        commands = [
            MediaCommandCapability(commandId=command, reasonCode="MEDIA_STUDIO_W7_09_READ_ONLY_NO_EXTERNAL_EFFECT", expectedVersion=context.revision, requiredExactRefs=required_refs)
            for command in ("freeze", "start", "pause_resume", "return", "publish", "settle_reconcile")
        ]
        status = "partial" if any(item.status == "blocked" for item in responsibilities) or blockers else "ready"
        return MediaStudioLifecycleContribution(
            contextId=context.context_id,
            contextRevision=context.revision,
            contextHash=context.content_hash,
            taskId=context.task_id,
            status=status,
            lifecycle=lifecycle,
            responsibilities=responsibilities,
            stages=stages,
            artifactFamilies=artifacts,
            reviewIssues=review_issues,
            commandCapabilities=commands,
            blockerCodes=sorted(set(blockers)),
        )


__all__ = [
    "EcommerceWorkshopMediaStudioLifecycle",
    "MediaStudioLifecycleConflict",
    "MediaStudioLifecycleError",
]
