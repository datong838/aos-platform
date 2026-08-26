"""BI-W5-03 canonical ResearchJob reuse tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from aos_api.aip_business_investigation_research import (
    BusinessInvestigationResearchAdapter,
    BusinessInvestigationResearchBlocked,
    InvestigationResearchRoute,
    InvestigationResearchStepRequest,
)
from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinding,
    CanonicalRuntimeRef,
)
from aos_api.aip_contracts import ResourceRef, TaskRunStatus, TenantContext
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.aip_research_job import (
    ResearchJobSnapshot,
    ResearchJobStatus,
    canonical_research_manifest_hash,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
OTHER_SCOPE = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 8, 26, 12, 0, tzinfo=UTC)


def exact(kind: str, identity: str, fill: str) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind,
        resource_id=identity,
        revision=1,
        content_hash=fill * 64,
    )


def resource(kind: str, identity: str, authority: str) -> ResourceRef:
    return ResourceRef(
        resource_type=kind,
        resource_id=identity,
        revision="1",
        authority=authority,
    )


def runtime() -> BusinessInvestigationRuntimeBinding:
    return BusinessInvestigationRuntimeBinding(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        case_ref=exact("BusinessInvestigationCaseRevision", "case-1", "1"),
        business_investigation_run_ref=exact(
            "BusinessInvestigationRun", "investigation-run-1", "2"
        ),
        compilation_hash="3" * 64,
        task_ref=CanonicalRuntimeRef(
            resource_type="Task", resource_id="task-1", version=3
        ),
        plan_ref=exact("PlanRevision", "plan-1", "4"),
        task_run_ref=CanonicalRuntimeRef(
            resource_type="TaskRun", resource_id="task-run-1", version=5
        ),
        task_run_status=TaskRunStatus.RUNNING,
        plan_step_count=3,
        binding_hash="5" * 64,
        start_authorized=False,
    )


ROUTES = {
    "data": InvestigationResearchRoute(
        research_kind="data",
        provider_id="data-research-adapter",
        provider_revision=3,
        source_authority="aos.data",
        allowed_source_resource_types=["DataSourceRevision", "DataRequirementRevision"],
    ),
    "ontology": InvestigationResearchRoute(
        research_kind="ontology",
        provider_id="ontology-research-adapter",
        provider_revision=2,
        source_authority="aos.ontology",
        allowed_source_resource_types=["OntologySnapshotRevision"],
    ),
    "human": InvestigationResearchRoute(
        research_kind="human",
        provider_id="human-work-queue-adapter",
        provider_revision=1,
        source_authority="aos.identity",
        allowed_source_resource_types=["HumanPrincipalRevision"],
    ),
}


def step(kind="data", owner=None, **changes):
    owners = {
        "data": resource("DataSourceRevision", "source-1", "aos.data"),
        "ontology": resource(
            "OntologySnapshotRevision", "ontology-1", "aos.ontology"
        ),
        "human": resource("HumanPrincipalRevision", "human-1", "aos.identity"),
    }
    value = {
        "researchKind": kind,
        "stepKey": f"research-{kind}",
        "sourceOwnerRef": owner or owners[kind],
        "inputRefs": [resource("EvidenceBundleRevision", "evidence-1", "aos.evidence")],
        "lineageRef": resource("aip.lineage", "lineage-1", "aos.lineage"),
        "outputSchemaHash": "a" * 64,
        "budget": {
            "maxTokens": 2000,
            "maxCostMicros": 100000,
            "maxDurationSeconds": 600,
        },
        "traceparent": f"00-{'1' * 32}-{'2' * 16}-01",
        "deadline": NOW + timedelta(hours=1),
        "idempotencyKey": f"research-{kind}-1",
    }
    value.update(changes)
    return InvestigationResearchStepRequest.model_validate(value)


class FixedCreator:
    def __init__(self) -> None:
        self.calls = []

    def create_job(self, scope, request, actor, *, now=None):
        self.calls.append((scope, request, actor, now))
        return ResearchJobSnapshot(
            tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
            job_id="research-job-1",
            run_id=request.run_id,
            plan_revision_id="plan-1",
            step_key=request.step_key,
            provider_id=request.provider_id,
            provider_revision=request.provider_revision,
            capability_ref=resource("capability", "research", "aos.capability"),
            lineage_ref=request.manifest.lineage_ref,
            manifest_hash=request.manifest.manifest_hash,
            output_schema_hash=request.manifest.output_schema_hash,
            status=ResearchJobStatus.QUEUED,
            created_at=now or NOW,
        )


@pytest.mark.parametrize("kind", ["data", "ontology", "human"])
def test_three_research_kinds_delegate_to_canonical_job(kind) -> None:
    creator = FixedCreator()
    adapter = BusinessInvestigationResearchAdapter(
        lambda scope, requested: ROUTES[requested], creator
    )
    result = adapter.create_job(SCOPE, runtime(), step(kind), "owner", now=NOW)

    assert result.status is ResearchJobStatus.QUEUED
    assert len(creator.calls) == 1
    scope, request, actor, observed_at = creator.calls[0]
    assert (scope, actor, observed_at) == (SCOPE, "owner", NOW)
    assert request.run_id == runtime().task_run_ref.resource_id
    assert request.provider_id == ROUTES[kind].provider_id
    assert request.manifest.task_run_ref == resource(
        "aos.task_run", "task-run-1", "aos.task"
    ).model_copy(update={"revision": "5"})
    assert request.manifest.scoped_refs[0] == step(kind).source_owner_ref
    assert request.manifest.budget["researchKind"] == kind
    assert request.manifest.manifest_hash == canonical_research_manifest_hash(
        request.manifest
    )


def test_source_owner_authority_or_type_drift_blocks_before_job_creation() -> None:
    creator = FixedCreator()
    adapter = BusinessInvestigationResearchAdapter(
        lambda _scope, kind: ROUTES[kind], creator
    )
    with pytest.raises(
        BusinessInvestigationResearchBlocked, match="SOURCE_OWNER_AUTHORITY_DRIFTED"
    ):
        adapter.create_job(
            SCOPE,
            runtime(),
            step(owner=resource("DataSourceRevision", "source-1", "aos.ontology")),
            "owner",
            now=NOW,
        )
    with pytest.raises(
        BusinessInvestigationResearchBlocked, match="SOURCE_OWNER_TYPE_BLOCKED"
    ):
        adapter.create_job(
            SCOPE,
            runtime(),
            step(owner=resource("BusinessInvestigationCase", "case-1", "aos.data")),
            "owner",
            now=NOW,
        )
    assert creator.calls == []


def test_cross_tenant_route_failure_or_expired_deadline_fails_closed() -> None:
    creator = FixedCreator()
    adapter = BusinessInvestigationResearchAdapter(
        lambda _scope, kind: ROUTES[kind], creator
    )
    with pytest.raises(
        BusinessInvestigationResearchBlocked, match="RUNTIME_TENANT_MISMATCH"
    ):
        adapter.create_job(OTHER_SCOPE, runtime(), step(), "owner", now=NOW)
    with pytest.raises(
        BusinessInvestigationResearchBlocked, match="RESEARCH_DEADLINE_EXPIRED"
    ):
        adapter.create_job(
            SCOPE,
            runtime(),
            step(deadline=NOW),
            "owner",
            now=NOW,
        )
    failing = BusinessInvestigationResearchAdapter(
        lambda _scope, _kind: (_ for _ in ()).throw(RuntimeError("missing")), creator
    )
    with pytest.raises(
        BusinessInvestigationResearchBlocked,
        match="RESEARCH_ROUTE_RESOLUTION_FAILED",
    ):
        failing.create_job(SCOPE, runtime(), step(), "owner", now=NOW)
    assert creator.calls == []


def test_secret_refs_duplicate_refs_and_non_exact_lineage_are_rejected() -> None:
    with pytest.raises(ValidationError, match="secret material"):
        step(
            inputRefs=[resource("SecretRevision", "secret-1", "aos.secret")]
        )
    duplicate = resource("EvidenceBundleRevision", "evidence-1", "aos.evidence")
    with pytest.raises(ValidationError, match="must be unique"):
        step(inputRefs=[duplicate, duplicate])
    with pytest.raises(ValidationError, match="exact aos.lineage"):
        step(
            lineageRef=resource("Trace", "lineage-1", "aos.telemetry")
        )
