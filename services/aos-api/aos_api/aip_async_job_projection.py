"""Read-only projection over the three existing async-job authorities.

The projection never accepts commands and never writes back to source stores.
ResearchJob, QueryJob and KnowledgePipelineRun remain separate authorities.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_contracts import AipContractModel, ResourceRef, TenantContext
from aos_api.aip_memory_pipeline_store import AipMemoryPipelineStore
from aos_api.aip_research_job_store import AipResearchJobStore
from aos_api.tenant_scope import TenantScope


class AsyncJobAuthorityType(StrEnum):
    RESEARCH_JOB = "research_job"
    QUERY_JOB = "query_job"
    KNOWLEDGE_PIPELINE_RUN = "knowledge_pipeline_run"


class AsyncJobRef(AipContractModel):
    authority: str
    authority_type: AsyncJobAuthorityType
    job_id: str
    version: str = "1"


class AsyncJobPermissions(AipContractModel):
    can_cancel: bool = False
    can_retry: bool = False
    can_reconcile: bool = False


class AsyncJobProgress(AipContractModel):
    state: str = Field(pattern=r"^(unknown|measured|partial|complete)$")
    completed_units: int | None = Field(default=None, ge=0)
    total_units: int | None = Field(default=None, ge=0)


class AsyncJobProjectionItem(AipContractModel):
    job_ref: AsyncJobRef
    task_ref: ResourceRef | None = None
    subject_refs: list[ResourceRef] = Field(default_factory=list)
    status: str
    display_status: str
    progress: AsyncJobProgress
    partial_refs: list[ResourceRef] = Field(default_factory=list)
    cancelability: str
    resumability: str
    reconcile_required: bool = False
    cancel_requested: bool = False
    checkpoint_ref: ResourceRef | None = None
    receipt_refs: list[ResourceRef] = Field(default_factory=list)
    lineage_ref: str | None = None
    started_at: datetime | None = None
    updated_at: datetime | None = None
    deadline: datetime | None = None
    next_poll_at: datetime | None = None
    owner: str | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    permissions: AsyncJobPermissions = Field(default_factory=AsyncJobPermissions)


class AsyncJobProjectionResponse(AipContractModel):
    tenant: TenantContext
    items: list[AsyncJobProjectionItem]
    count: int = Field(ge=0)


_TERMINAL = {"succeeded", "failed", "cancelled", "timed_out", "partial"}
_CONTROL_ROLES = {"admin", "executor", "aip_executor"}


def _cancelability(status: str, *, requested: bool = False) -> str:
    if requested:
        return "cancel_requested"
    if status in _TERMINAL:
        return "terminal"
    return "cancelable"


def _progress(
    status: str,
    *,
    completed: int | None = None,
    total: int | None = None,
) -> AsyncJobProgress:
    if status == "succeeded":
        return AsyncJobProgress(
            state="complete", completed_units=completed, total_units=total
        )
    if status == "partial":
        return AsyncJobProgress(
            state="partial", completed_units=completed, total_units=total
        )
    if completed is not None or total is not None:
        return AsyncJobProgress(
            state="measured", completed_units=completed, total_units=total
        )
    return AsyncJobProgress(state="unknown")


def _can_control(roles: list[str] | None) -> bool:
    return bool(_CONTROL_ROLES.intersection(roles or []))


def list_async_job_projection(
    scope: TenantScope,
    *,
    limit: int = 50,
    roles: list[str] | None = None,
    research_store: AipResearchJobStore | None = None,
    query_store: AipAnalystQueryStore | None = None,
    pipeline_store: AipMemoryPipelineStore | None = None,
) -> AsyncJobProjectionResponse:
    """Merge three source authorities into one tenant-scoped display projection."""
    limit = max(1, min(int(limit), 200))
    research_store = research_store or AipResearchJobStore()
    query_store = query_store or AipAnalystQueryStore()
    pipeline_store = pipeline_store or AipMemoryPipelineStore()
    can_control = _can_control(roles)
    items: list[AsyncJobProjectionItem] = []

    for job in research_store.list_jobs(scope, limit=limit).items:
        facts = research_store.projection_facts(scope, job.job_id)
        raw_status = job.status.value
        display_status = (
            "partial" if facts.partial_refs and raw_status not in _TERMINAL else raw_status
        )
        blockers = []
        if job.resumability == "unsupported":
            blockers.append("research_job_not_resumable")
        if raw_status == "unknown":
            blockers.append("research_job_reconcile_required")
        items.append(
            AsyncJobProjectionItem(
                job_ref=AsyncJobRef(
                    authority="aos.research_job",
                    authority_type=AsyncJobAuthorityType.RESEARCH_JOB,
                    job_id=job.job_id,
                    version=str(job.last_sequence),
                ),
                # ResearchJob stores run_id but not the exact TaskRun revision.
                task_ref=None,
                subject_refs=[job.capability_ref],
                status=raw_status,
                display_status=display_status,
                progress=_progress(display_status),
                partial_refs=facts.partial_refs,
                cancelability=_cancelability(
                    raw_status, requested=job.cancel_requested
                ),
                resumability=job.resumability,
                reconcile_required=raw_status == "unknown",
                cancel_requested=job.cancel_requested,
                receipt_refs=facts.receipt_refs,
                lineage_ref=(
                    f"{job.lineage_ref.resource_type}/{job.lineage_ref.resource_id}"
                    f"@{job.lineage_ref.revision}"
                ),
                started_at=job.created_at,
                updated_at=facts.updated_at,
                deadline=facts.deadline,
                owner=facts.owner,
                blocked_reasons=blockers,
                permissions=AsyncJobPermissions(
                    can_cancel=can_control
                    and _cancelability(raw_status, requested=job.cancel_requested)
                    == "cancelable",
                    can_retry=can_control and raw_status in _TERMINAL,
                    can_reconcile=can_control and raw_status == "unknown",
                ),
            )
        )

    for job in query_store.list_jobs(scope, limit=limit).items:
        raw_status = job.status.value
        result = job.latest_result
        display_status = (
            "partial"
            if result is not None and result.status.value in {"partial", "degraded"}
            else raw_status
        )
        result_ref = (
            ResourceRef(
                resource_type="aip.query_result_revision",
                resource_id=job.query_id,
                revision=str(result.revision),
                authority="aos.analyst_query_job",
            )
            if result is not None
            else None
        )
        items.append(
            AsyncJobProjectionItem(
                job_ref=AsyncJobRef(
                    authority="aos.analyst_query_job",
                    authority_type=AsyncJobAuthorityType.QUERY_JOB,
                    job_id=job.query_id,
                    version=str(job.latest_sequence),
                ),
                subject_refs=list(result.lineage_refs) if result is not None else [],
                status=raw_status,
                display_status=display_status,
                progress=_progress(display_status),
                partial_refs=[result_ref] if result_ref is not None else [],
                cancelability=_cancelability(raw_status),
                resumability="unsupported",
                cancel_requested=raw_status == "cancelled",
                # Query result revision is an output ref, not a command Receipt.
                receipt_refs=[],
                started_at=job.created_at,
                updated_at=result.created_at if result is not None else job.created_at,
                deadline=job.deadline_at,
                owner=job.created_by,
                blocked_reasons=[
                    "query_job_is_not_research_job",
                    "query_job_not_resumable",
                ],
                permissions=AsyncJobPermissions(
                    can_cancel=can_control and raw_status not in _TERMINAL,
                ),
            )
        )

    for run in pipeline_store.list_runs(scope, limit=limit):
        raw_status = run.status.value
        receipt = pipeline_store.get_receipt_for_run(
            scope, run.pipeline_run_id, required=False
        )
        checkpoint = pipeline_store.get_checkpoint(scope, run.schedule_id)
        receipt_ref = (
            ResourceRef(
                resource_type="aip.knowledge_pipeline_receipt",
                resource_id=receipt.receipt_id,
                revision=receipt.receipt_hash,
                authority="aos.knowledge_pipeline",
            )
            if receipt is not None
            else None
        )
        checkpoint_ref = (
            ResourceRef(
                resource_type="aip.knowledge_pipeline_checkpoint_revision",
                resource_id=checkpoint.schedule_id,
                revision=str(checkpoint.revision),
                authority="aos.knowledge_pipeline",
            )
            if checkpoint is not None
            and checkpoint.pipeline_run_id == run.pipeline_run_id
            else None
        )
        partial_refs = list(receipt.candidate_refs) if receipt is not None else []
        resumable = raw_status == "paused" and checkpoint_ref is not None
        blockers = ["knowledge_pipeline_commands_owned_by_pipeline_authority"]
        if raw_status == "unknown":
            blockers.append("knowledge_pipeline_reconcile_required")
        if raw_status == "paused" and checkpoint_ref is None:
            blockers.append("knowledge_pipeline_checkpoint_missing")
        items.append(
            AsyncJobProjectionItem(
                job_ref=AsyncJobRef(
                    authority="aos.knowledge_pipeline",
                    authority_type=AsyncJobAuthorityType.KNOWLEDGE_PIPELINE_RUN,
                    job_id=run.pipeline_run_id,
                    version=str(run.version),
                ),
                # PipelineRun stores task_id but not an exact Task revision.
                task_ref=None,
                subject_refs=[
                    ResourceRef(
                        resource_type="aip.knowledge_pipeline_schedule",
                        resource_id=run.schedule_id,
                        revision=str(run.expected_checkpoint_version),
                        authority="aos.knowledge_pipeline",
                    )
                ],
                status=raw_status,
                display_status=raw_status,
                progress=_progress(
                    raw_status,
                    completed=receipt.produced_count if receipt is not None else None,
                    total=(
                        receipt.produced_count + receipt.failed_count
                        if receipt is not None
                        else None
                    ),
                ),
                partial_refs=partial_refs,
                cancelability=("terminal" if raw_status in _TERMINAL else "authority_owned"),
                resumability="supported" if resumable else "unsupported",
                reconcile_required=raw_status == "unknown",
                checkpoint_ref=checkpoint_ref,
                receipt_refs=[receipt_ref] if receipt_ref is not None else [],
                started_at=run.started_at or run.created_at,
                updated_at=run.updated_at,
                deadline=run.lease_expires_at,
                next_poll_at=None,
                owner=run.lease_owner,
                blocked_reasons=blockers,
                permissions=AsyncJobPermissions(),
            )
        )

    items.sort(
        key=lambda item: item.updated_at
        or item.started_at
        or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )
    items = items[:limit]
    return AsyncJobProjectionResponse(
        tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
        items=items,
        count=len(items),
    )


__all__ = [
    "AsyncJobAuthorityType",
    "AsyncJobPermissions",
    "AsyncJobProgress",
    "AsyncJobProjectionItem",
    "AsyncJobProjectionResponse",
    "AsyncJobRef",
    "list_async_job_projection",
]
