"""W-L17 ResearchJob/QueryJob list+cancel+retry and AsyncJobProjection."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from aos_api.aip_analyst_contracts import (
    CreateQueryJobRequest,
    SemanticQueryRequest,
)
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_async_job_projection import (
    AsyncJobAuthorityType,
    list_async_job_projection,
)
from aos_api.aip_research_job import (
    CancelResearchJobRequest,
    RecordResearchSubmissionRequest,
    RetryResearchJobRequest,
)
from aos_api.aip_research_job_store import AipResearchJobBlocked
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("dev-org", "dev-project")
QUERY_SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 20, 4, 0, tzinfo=UTC)


@pytest.fixture()
def authority_chain():
    from tests.aip.test_aip_research_job_store import authority_chain as src

    return src.__wrapped__()


def test_research_list_cancel_unsubmitted_and_retry(authority_chain) -> None:
    service = authority_chain["service"]
    job = authority_chain["job"]
    listed = service.list_jobs(SCOPE, limit=20)
    assert listed.count >= 1
    assert any(item.job_id == job.job_id for item in listed.items)
    assert job.resumability == "unsupported"

    cancelled = service.cancel_job(
        SCOPE,
        job.job_id,
        CancelResearchJobRequest(reason="operator_abort"),
        "tester",
        f"cancel-{uuid4().hex[:10]}",
        now=NOW,
    )
    assert cancelled.cancel_requested is True
    assert cancelled.status.value == "cancelled"

    with pytest.raises(AipResearchJobBlocked):
        service.cancel_job(
            SCOPE,
            job.job_id,
            CancelResearchJobRequest(reason="again"),
            "tester",
            f"cancel-again-{uuid4().hex[:8]}",
            now=NOW,
        )

    retried = service.retry_job(
        SCOPE,
        job.job_id,
        RetryResearchJobRequest(
            idempotency_key=f"retry-{uuid4().hex[:12]}",
            reason="retry_after_cancel",
        ),
        "tester",
        now=NOW,
    )
    assert retried.job_id != job.job_id
    assert retried.retry_of_job_id == job.job_id
    assert retried.resumability == "unsupported"


def test_research_cancel_submitted_goes_unknown(authority_chain) -> None:
    service = authority_chain["service"]
    job = authority_chain["job"]
    service.record_submission(
        SCOPE,
        RecordResearchSubmissionRequest(
            job_id=job.job_id,
            provider_execution_id=f"prov-{uuid4().hex[:8]}",
            provider_version="1",
            accepted_manifest_hash=job.manifest_hash,
            source_hash="c" * 64,
            observed_at=NOW,
        ),
        now=NOW,
    )
    cancelled = service.cancel_job(
        SCOPE,
        job.job_id,
        CancelResearchJobRequest(reason="stop_provider"),
        "tester",
        f"cancel-sub-{uuid4().hex[:10]}",
        now=NOW,
    )
    assert cancelled.cancel_requested is True
    assert cancelled.status.value == "unknown"


def test_query_job_list_and_projection_keeps_authority_types(
    authority_chain,
) -> None:
    query_store = AipAnalystQueryStore()
    cutoff = datetime.now(UTC)
    created = query_store.create(
        QUERY_SCOPE,
        CreateQueryJobRequest(
            query=SemanticQueryRequest(object_type="Order", cutoff_at=cutoff),
            deadline_at=cutoff + timedelta(hours=1),
        ),
        idempotency_key=f"qj-{uuid4().hex[:12]}",
        actor="tester",
    )
    listed = query_store.list_jobs(QUERY_SCOPE, limit=20)
    assert any(item.query_id == created.query_id for item in listed.items)

    research_proj = list_async_job_projection(SCOPE, limit=50)
    assert any(
        item.job_ref.authority_type is AsyncJobAuthorityType.RESEARCH_JOB
        and item.job_ref.job_id == authority_chain["job"].job_id
        for item in research_proj.items
    )

    query_proj = list_async_job_projection(QUERY_SCOPE, limit=50)
    query_items = [
        item
        for item in query_proj.items
        if item.job_ref.job_id == created.query_id
    ]
    assert len(query_items) == 1
    assert query_items[0].job_ref.authority_type is AsyncJobAuthorityType.QUERY_JOB
    assert query_items[0].job_ref.authority == "aos.analyst_query_job"
    assert "query_job_is_not_research_job" in query_items[0].blocked_reasons
    assert query_items[0].resumability == "unsupported"
