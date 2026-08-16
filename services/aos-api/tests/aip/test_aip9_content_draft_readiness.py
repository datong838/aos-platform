from __future__ import annotations

from contextlib import contextmanager

from pydantic import ValidationError
import pytest

from aos_api.aip_content_contracts import ContentDraftReadinessRequest
from aos_api.aip_content_draft_readiness import AipContentDraftReadinessService
from aos_api.tenant_scope import TenantScope


HASH = "a" * 64
SCOPE = TenantScope("org-org", "dev-project")


def exact(resource_type: str, resource_id: str) -> dict[str, object]:
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": 1,
        "contentHash": HASH,
    }


def resource(resource_type: str, resource_id: str) -> dict[str, object]:
    return {
        "resourceType": resource_type,
        "resourceId": resource_id,
        "revision": "1",
        "authority": "pytest",
    }


def request_payload() -> dict[str, object]:
    brief_ref = exact("TaskBriefRevision", "brief-1")
    return {
        "briefRef": brief_ref,
        "pipeline": {
            "briefRef": brief_ref,
            "stageTemplateRef": exact("StageTemplateRevision", "stage-1"),
            "responsibilityPlanRef": exact(
                "ResponsibilityPlanRevision", "plan-1"
            ),
            "evalContractRef": exact("EvalContractRevision", "eval-1"),
            "modelRouteRef": None,
            "runtimePolicyRef": None,
            "capabilityRefs": [],
            "toolBindingRefs": [],
            "budgetRef": None,
            "readiness": "blocked",
            "blockers": [
                {
                    "code": "PIPELINE_BINDING_NOT_READY",
                    "message": "runtime binding is not ready",
                }
            ],
        },
        "taskRunRef": resource("TaskRun", "task-run-1"),
        "agentRunRef": resource("AgentRun", "agent-run-1"),
        "variantKey": "weapp-seed-copy-v1",
        "channel": "weapp",
    }


class EmptyResult:
    def fetchone(self):
        return None


class RecordingConnection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, params: tuple[object, ...]):
        self.calls.append((sql, params))
        return EmptyResult()


class ResolverMustNotRun:
    def resolve(self, *_args, **_kwargs):
        raise AssertionError("model resolver must not run without an exact route")


def test_readiness_is_read_only_tenant_scoped_and_fail_closed() -> None:
    connection = RecordingConnection()

    @contextmanager
    def connect_factory(scope: TenantScope):
        assert scope.key == SCOPE.key
        yield connection

    service = AipContentDraftReadinessService(
        connect_factory,
        model_resolver=ResolverMustNotRun(),
    )
    decision = service.evaluate(
        SCOPE,
        ContentDraftReadinessRequest.model_validate(request_payload()),
    )

    assert decision.tenant.org_id == "org-org"
    assert decision.tenant.project_id == "dev-project"
    assert decision.readiness == "blocked"
    codes = {blocker.code for blocker in decision.blockers}
    assert {
        "CONTENT_DRAFT_DEPENDENCY_NOT_FOUND",
        "CONTENT_DRAFT_BUDGET_AUTHORITY_UNAVAILABLE",
        "CONTENT_DRAFT_MODEL_ROUTE_UNAVAILABLE",
        "PIPELINE_BINDING_NOT_READY",
    }.issubset(codes)
    assert len(decision.request_hash) == 64
    assert len(decision.dependency_snapshot_hash) == 64

    assert connection.calls
    assert all(sql.lstrip().upper().startswith("SELECT") for sql, _ in connection.calls)
    tenant_queries = [
        params for sql, params in connection.calls if "org_id=%s" in sql
    ]
    assert tenant_queries
    assert all(params[:2] == SCOPE.key for params in tenant_queries)


def test_budget_reference_does_not_fake_budget_authority() -> None:
    payload = request_payload()
    pipeline = dict(payload["pipeline"])
    pipeline["budgetRef"] = exact("BudgetRevision", "budget-1")
    payload["pipeline"] = pipeline
    connection = RecordingConnection()

    @contextmanager
    def connect_factory(_scope: TenantScope):
        yield connection

    decision = AipContentDraftReadinessService(
        connect_factory,
        model_resolver=ResolverMustNotRun(),
    ).evaluate(SCOPE, ContentDraftReadinessRequest.model_validate(payload))
    blocker = next(
        value
        for value in decision.blockers
        if value.code == "CONTENT_DRAFT_BUDGET_AUTHORITY_UNAVAILABLE"
    )
    assert "exact re-read" in blocker.message


def test_request_rejects_tenant_injection_and_run_or_brief_drift() -> None:
    with pytest.raises(ValidationError):
        ContentDraftReadinessRequest.model_validate(
            {**request_payload(), "orgId": "dev-org"}
        )

    wrong_run = request_payload()
    wrong_run["agentRunRef"] = resource("TaskRun", "agent-run-1")
    with pytest.raises(ValidationError, match="AgentRun"):
        ContentDraftReadinessRequest.model_validate(wrong_run)

    wrong_brief = request_payload()
    wrong_brief["briefRef"] = exact("TaskBriefRevision", "brief-2")
    with pytest.raises(ValidationError, match="must equal briefRef"):
        ContentDraftReadinessRequest.model_validate(wrong_brief)
