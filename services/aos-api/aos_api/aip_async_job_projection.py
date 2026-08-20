"""Read-only AsyncJobProjection over ResearchJob + QueryJob authorities.

Does not accept commands or write back to source stores. Authority types stay
distinct so local analyst query tooling cannot be presented as ResearchJob.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field

from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_contracts import AipContractModel, TenantContext
from aos_api.aip_research_job_store import AipResearchJobStore
from aos_api.tenant_scope import TenantScope


class AsyncJobAuthorityType(StrEnum):
    RESEARCH_JOB = "research_job"
    QUERY_JOB = "query_job"


class AsyncJobRef(AipContractModel):
    authority: str
    authority_type: AsyncJobAuthorityType
    job_id: str
    version: str = "1"


class AsyncJobProjectionItem(AipContractModel):
    job_ref: AsyncJobRef
    status: str
    cancelability: str
    resumability: str
    reconcile_required: bool = False
    cancel_requested: bool = False
    lineage_ref: str | None = None
    started_at: datetime | None = None
    deadline: datetime | None = None
    owner: str | None = None
    blocked_reasons: list[str] = Field(default_factory=list)


class AsyncJobProjectionResponse(AipContractModel):
    tenant: TenantContext
    items: list[AsyncJobProjectionItem]
    count: int = Field(ge=0)


def _research_cancelability(status: str, cancel_requested: bool) -> str:
    if cancel_requested:
        return "cancel_requested"
    if status in {"succeeded", "failed", "cancelled"}:
        return "terminal"
    return "cancelable"


def _query_cancelability(status: str) -> str:
    if status in {"succeeded", "failed", "cancelled", "timed_out"}:
        return "terminal"
    return "cancelable"


def list_async_job_projection(
    scope: TenantScope,
    *,
    limit: int = 50,
    research_store: AipResearchJobStore | None = None,
    query_store: AipAnalystQueryStore | None = None,
) -> AsyncJobProjectionResponse:
    """Merge ResearchJob and QueryJob into a read-only display projection."""
    limit = max(1, min(int(limit), 200))
    research_store = research_store or AipResearchJobStore()
    query_store = query_store or AipAnalystQueryStore()
    research = research_store.list_jobs(scope, limit=limit)
    queries = query_store.list_jobs(scope, limit=limit)
    items: list[AsyncJobProjectionItem] = []
    for job in research.items:
        items.append(
            AsyncJobProjectionItem(
                job_ref=AsyncJobRef(
                    authority="aos.research_job",
                    authority_type=AsyncJobAuthorityType.RESEARCH_JOB,
                    job_id=job.job_id,
                    version=str(job.last_sequence),
                ),
                status=job.status.value,
                cancelability=_research_cancelability(
                    job.status.value, job.cancel_requested
                ),
                resumability=job.resumability,
                reconcile_required=job.status.value == "unknown",
                cancel_requested=job.cancel_requested,
                lineage_ref=(
                    f"{job.lineage_ref.resource_type}/{job.lineage_ref.resource_id}"
                    f"@{job.lineage_ref.revision}"
                ),
                started_at=job.created_at,
                owner=None,
                blocked_reasons=(
                    ["research_job_not_resumable"]
                    if job.resumability == "unsupported"
                    else []
                ),
            )
        )
    for job in queries.items:
        items.append(
            AsyncJobProjectionItem(
                job_ref=AsyncJobRef(
                    authority="aos.analyst_query_job",
                    authority_type=AsyncJobAuthorityType.QUERY_JOB,
                    job_id=job.query_id,
                    version=str(job.latest_sequence),
                ),
                status=job.status.value,
                cancelability=_query_cancelability(job.status.value),
                resumability="unsupported",
                reconcile_required=False,
                cancel_requested=job.status.value == "cancelled",
                lineage_ref=None,
                started_at=job.created_at,
                deadline=job.deadline_at,
                owner=job.created_by,
                blocked_reasons=["query_job_is_not_research_job"],
            )
        )
    items.sort(
        key=lambda item: item.started_at or datetime.min.replace(tzinfo=UTC),
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
    "AsyncJobProjectionItem",
    "AsyncJobProjectionResponse",
    "AsyncJobRef",
    "list_async_job_projection",
]
