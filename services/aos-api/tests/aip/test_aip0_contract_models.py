from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from aos_api.aip_compatibility import (
    ROUTE_COMPATIBILITY,
    map_legacy_step_run_status,
    map_legacy_task_run_status,
)
from aos_api.aip_contracts import (
    AIP_ERROR_STATUS,
    ActorRef,
    Evidence,
    ResourceRef,
    StepRunStatus,
    TaskContract,
    TaskRunStatus,
)
from aos_api.errors import aip_error
from aos_api.public_contracts import ContractViolation, TaskStatus


def test_contract_serializes_canonical_camel_case_without_tenant_request_fields():
    task = TaskContract(
        id="task-1",
        type="research",
        title="只读研究",
        status=TaskStatus.PENDING,
        priority=50,
        created_by=ActorRef(actor_type="user", actor_id="u-1"),
        created_at=datetime.now(timezone.utc),
        current_plan_revision_id="plan-1",
        version=1,
    )
    payload = task.model_dump(mode="json", by_alias=True)
    assert payload["currentPlanRevisionId"] == "plan-1"
    assert payload["createdBy"]["actorType"] == "user"
    assert "orgId" not in payload and "projectId" not in payload


def test_evidence_requires_sha256_and_freshness():
    with pytest.raises(ValidationError):
        Evidence(
            id="ev-1",
            type="query",
            subject_ref=ResourceRef(resource_type="Object", resource_id="1", authority="O1"),
            content_hash="not-a-hash",
            source="O1",
            freshness_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )


def test_legacy_status_mapping_fails_closed():
    assert map_legacy_task_run_status("completed") is TaskRunStatus.SUCCEEDED
    assert map_legacy_step_run_status("skipped") is StepRunStatus.SKIPPED
    with pytest.raises(ContractViolation):
        map_legacy_task_run_status("mostly-done")


def test_route_compatibility_covers_nine_duplicates_and_unsafe_transition():
    assert len(ROUTE_COMPATIBILITY) == 10
    assert sum(item.disposition == "removed-duplicate" for item in ROUTE_COMPATIBILITY) == 9
    transition = next(item for item in ROUTE_COMPATIBILITY if item.path.endswith("/transition"))
    assert transition.authority == "none"
    assert transition.disposition == "removed-unsafe"


def test_registered_aip_error_codes_have_stable_http_statuses():
    assert AIP_ERROR_STATUS["AIP_SCOPE_FORBIDDEN"] == 403
    assert AIP_ERROR_STATUS["AIP_OUTCOME_UNKNOWN"] == 504
    err = aip_error("AIP_VERSION_CONFLICT", "revision conflict")
    assert err.status_code == 409
    with pytest.raises(ValueError):
        aip_error("AIP_UNREGISTERED", "must fail")

