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


def registration_payload() -> dict[str, object]:
    return {
        "readinessRequest": request_payload(),
        "contentObject": {
            "contentRef": "aos-object://content/draft-1.md",
            "contentHash": HASH,
            "schemaRef": resource("Schema", "content-draft-v1"),
            "byteSize": 128,
            "mediaType": "text/markdown",
            "marking": ["internal"],
        },
        "promptHash": HASH,
        "evidenceBundleRef": exact("EvidenceBundleRevision", "evidence-1"),
        "sourceAssets": [],
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


class FakeRegistrationStore:
    def __init__(self) -> None:
        self.call = None

    def register(self, scope, actor, idempotency_key, body):
        self.call = (scope, actor, idempotency_key, body)
        return {
            "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
            "receiptId": "content-draft-receipt-1",
            "requestHash": HASH,
            "contentRef": body.content_object.content_ref,
            "draft": {
                "artifactRef": {
                    "artifactId": "content-draft-1",
                    "artifactType": "content_draft",
                    "revision": "1",
                    "contentHash": HASH,
                },
                "briefRef": body.readiness_request.brief_ref.model_dump(
                    mode="json", by_alias=True
                ),
                "pipeline": body.readiness_request.pipeline.model_dump(
                    mode="json", by_alias=True
                ),
                "variantKey": body.readiness_request.variant_key,
                "channel": body.readiness_request.channel.value,
                "sourceAssets": [],
                "evidenceBundleRef": exact(
                    "EvidenceBundleRevision", "evidence-1"
                ),
                "evalReportRef": None,
                "reviewIssueRefs": [],
            },
            "createdAt": datetime.now(UTC),
        }


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
    assert set(operations) == {
        ("POST", "/v1/aip/content/drafts/readiness"),
        ("POST", "/v1/aip/content/drafts/registrations"),
    }


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


def test_registration_requires_executor_and_binds_principal_scope() -> None:
    app = FastAPI()
    app.include_router(api.router)
    executor = Principal(
        subject="content-executor",
        org_id="org-org",
        project_id="dev-project",
        roles=["executor"],
        markings=["public"],
    )
    fake = FakeRegistrationStore()
    app.dependency_overrides[require_principal] = lambda: executor
    app.dependency_overrides[api.get_content_draft_store] = lambda: fake
    with TestClient(app) as client:
        response = client.post(
            "/v1/aip/content/drafts/registrations",
            headers={"Idempotency-Key": "draft-key-1"},
            json=registration_payload(),
        )
    assert response.status_code == 200
    scope, actor, key, _ = fake.call
    assert scope.key == ("org-org", "dev-project")
    assert actor == "content-executor" and key == "draft-key-1"


def test_registration_rejects_missing_idempotency_key() -> None:
    app = FastAPI()
    app.include_router(api.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="content-executor",
        org_id="org-org",
        project_id="dev-project",
        roles=["executor"],
        markings=["public"],
    )
    app.dependency_overrides[api.get_content_draft_store] = (
        lambda: FakeRegistrationStore()
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/aip/content/drafts/registrations",
            json=registration_payload(),
        )
    assert response.status_code == 422
