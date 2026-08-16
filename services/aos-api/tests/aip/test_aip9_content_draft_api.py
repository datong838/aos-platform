from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.aip_content_contracts import ContentDraftReadinessDecision
from aos_api.auth import Principal, require_principal
from aos_api.routers import aip_content_drafts as api


HASH = "a" * 64
PRINCIPAL = Principal(
    subject="content-reviewer",
    org_id="org-org",
    project_id="dev-project",
    roles=["viewer"],
    markings=["public"],
)


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


class FakeReadinessService:
    def __init__(self) -> None:
        self.scope = None
        self.body = None

    def evaluate(self, scope, body) -> ContentDraftReadinessDecision:
        self.scope = scope
        self.body = body
        return ContentDraftReadinessDecision(
            tenant={"orgId": scope.org_id, "projectId": scope.project_id},
            readiness="blocked",
            requestHash=HASH,
            dependencySnapshotHash=HASH,
            blockers=[
                {
                    "code": "CONTENT_DRAFT_BUDGET_AUTHORITY_UNAVAILABLE",
                    "message": "BudgetRevision authority is unavailable",
                }
            ],
            evaluatedAt=datetime.now(UTC),
        )


def test_api_derives_tenant_from_principal_and_freezes_one_read_only_operation() -> None:
    app = FastAPI()
    app.include_router(api.router)
    fake = FakeReadinessService()
    app.dependency_overrides[require_principal] = lambda: PRINCIPAL
    app.dependency_overrides[api.get_content_draft_readiness_service] = lambda: fake

    with TestClient(app) as client:
        response = client.post(
            "/v1/aip/content/drafts/readiness",
            json=request_payload(),
        )

    assert response.status_code == 200
    assert response.json()["tenant"] == {
        "orgId": "org-org",
        "projectId": "dev-project",
    }
    assert fake.scope.key == ("org-org", "dev-project")
    assert fake.body.variant_key == "weapp-seed-copy-v1"
    operations = [
        (method, route.path)
        for route in api.router.routes
        for method in route.methods or set()
        if method in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    ]
    assert operations == [("POST", "/v1/aip/content/drafts/readiness")]


def test_api_rejects_caller_supplied_tenant() -> None:
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[require_principal] = lambda: PRINCIPAL
    app.dependency_overrides[api.get_content_draft_readiness_service] = (
        lambda: FakeReadinessService()
    )
    payload = {**request_payload(), "orgId": "dev-org"}
    with TestClient(app) as client:
        response = client.post(
            "/v1/aip/content/drafts/readiness",
            json=payload,
        )
    assert response.status_code == 422
