"""BI-W4-06/07 canonical Case/Run HTTP API tests."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.aip_contracts import TenantContext
from aos_api.auth import Principal, require_principal
from aos_api.ecommerce_business_investigation_application import (
    BusinessInvestigationCaseCommandResponse,
    BusinessInvestigationCaseListResponse,
    BusinessInvestigationRunListResponse,
    BusinessInvestigationRunStateCommandResponse,
    BusinessInvestigationSchedulePolicyCommandResponse,
    CreateBusinessInvestigationRunRequest,
    EcommerceBusinessInvestigationApplication,
)
from aos_api.ecommerce_business_investigation_case import (
    BusinessInvestigationCaseNotFound,
    BusinessInvestigationCaseRevision,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunControl,
    BusinessInvestigationRunStateRevision,
)
from aos_api.ecommerce_business_investigation_projection import (
    BusinessInvestigationProjectionNotFound,
)
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_business_investigations as routes
from aos_api.tenant_scope import TenantScope
from test_ecommerce_business_investigation_lifecycle import HASH_A, draft_case, ref
from test_ecommerce_business_investigation_schedule import case as scheduled_case
from test_ecommerce_business_investigation_schedule import policy as schedule_policy


NOW = datetime.now(UTC)
TENANT = TenantContext(org_id="org-org", project_id="dev-project")


def state(
    control: str = "PAUSED",
    version: int = 2,
    *,
    lifecycle: str = "PREPARING",
    pending_requirement_ref: dict | None = None,
) -> BusinessInvestigationRunStateRevision:
    payload = {
        "tenant": TENANT.model_dump(by_alias=True, mode="json"),
        "runId": "run-1",
        "version": version,
        "priorRef": ref(
            "BusinessInvestigationRunStateRevision",
            "run-1",
            revision=version - 1,
            content_hash=HASH_A,
        ),
        "lifecycle": lifecycle,
        "control": control,
        "eventSequence": version,
        "contentHash": HASH_A,
        "createdBy": "user-1",
        "createdAt": NOW,
    }
    if pending_requirement_ref is not None:
        payload["pendingRequirementRef"] = pending_requirement_ref
    return BusinessInvestigationRunStateRevision.model_validate(payload)


class FakeApplication:
    calls: list[tuple] = []
    missing = False

    def list_cases(self, scope, *, business_entity_id, limit):
        self.calls.append(("list_cases", scope, business_entity_id, limit))
        item = draft_case()
        return BusinessInvestigationCaseListResponse(tenant=TENANT, items=[item], count=1)

    def create_case(self, scope, request, **kwargs):
        self.calls.append(("create_case", scope, request, kwargs))
        return BusinessInvestigationCaseCommandResponse(
            tenant=TENANT, authority=draft_case(request.case_id), replayed=False
        )

    def get_case(self, scope, case_id) -> BusinessInvestigationCaseRevision:
        self.calls.append(("get_case", scope, case_id))
        if self.missing:
            raise BusinessInvestigationCaseNotFound("secret internal id")
        return draft_case(case_id)

    def transition_case(self, scope, case_id, request, **kwargs):
        self.calls.append(("transition_case", scope, case_id, request, kwargs))
        previous = draft_case(case_id)
        payload = previous.model_dump(by_alias=True, mode="json")
        payload.update(
            revision=2,
            version=2,
            lifecycle=request.target_lifecycle.value,
            priorRef=ref(
                "BusinessInvestigationCaseRevision",
                case_id,
                revision=1,
                content_hash=previous.content_hash,
            ),
            contentHash=HASH_A,
        )
        authority = BusinessInvestigationCaseRevision.model_validate(payload)
        return BusinessInvestigationCaseCommandResponse(
            tenant=TENANT, authority=authority, replayed=False
        )

    def list_runs(self, scope, case_id, *, limit):
        self.calls.append(("list_runs", scope, case_id, limit))
        return BusinessInvestigationRunListResponse(tenant=TENANT, items=[], count=0)

    def create_run(self, scope, case_id, request, **kwargs):
        raise AssertionError("create_run is covered by strict request/path service tests")

    def put_schedule_policy(self, scope, case_id, request, **kwargs):
        self.calls.append(("put_schedule", scope, case_id, request, kwargs))
        return BusinessInvestigationSchedulePolicyCommandResponse(
            tenant=TENANT,
            authority=schedule_policy(),
            caseAuthority=scheduled_case(
                revision=3,
                schedule_ref=ref("SchedulePolicyRevision", "schedule-1"),
            ),
            replayed=False,
        )

    def get_schedule_policy(self, scope, schedule_policy_id):
        self.calls.append(("get_schedule", scope, schedule_policy_id))
        return schedule_policy()

    def get_run(self, scope, run_id):
        raise BusinessInvestigationCaseNotFound("not visible")

    def get_run_view(self, scope, run_id, *, observed_at):
        self.calls.append(("get_run_view", scope, run_id, observed_at))
        if self.missing:
            raise BusinessInvestigationProjectionNotFound("secret projection id")
        from test_ecommerce_business_investigation_projection import projection_view

        return projection_view(observed_at=observed_at)

    def transition_run_control(self, scope, run_id, target, **kwargs):
        self.calls.append(("transition_run", scope, run_id, target, kwargs))
        return BusinessInvestigationRunStateCommandResponse(
            tenant=TENANT,
            authority=state(target.value, kwargs["expected_version"] + 1),
            replayed=False,
        )

    def request_run_data(self, scope, run_id, request, **kwargs):
        self.calls.append(("request_data", scope, run_id, request, kwargs))
        return BusinessInvestigationRunStateCommandResponse(
            tenant=TENANT,
            authority=state(
                "RUNNING",
                kwargs["expected_version"] + 1,
                lifecycle="WAITING_DATA",
                pending_requirement_ref=request.requirement_ref.model_dump(
                    by_alias=True, mode="json"
                ),
            ),
            replayed=False,
        )


def client(application: FakeApplication) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(routes.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user-1", org_id="org-org", project_id="dev-project"
    )
    app.dependency_overrides[routes.get_business_investigation_application] = lambda: application
    return TestClient(app)


def create_case_body() -> dict:
    return {
        "caseId": "case-1",
        "analysisType": "initial_store_analysis",
        "title": "首次全店经营分析",
        "purposeCode": "business.investigation.initial",
        "channelRef": ref("ChannelRevision", "private-mall"),
        "businessEntityRef": ref("BusinessEntityRevision", "store-1"),
        "entityChannelBindingRef": ref("BusinessEntityChannelBindingRevision", "binding-1"),
        "investigationProfileRef": ref("InvestigationProfileRevision", "profile-1"),
        "scopeRef": ref("InvestigationScopeRevision", "scope-1"),
    }


def test_router_exposes_only_canonical_case_run_surface_and_manifest_registration() -> None:
    app = FastAPI()
    app.include_router(routes.router)
    paths = app.openapi()["paths"]
    assert "/v1/ecommerce/investigations/cases" in paths
    assert "/v1/ecommerce/investigations/cases/{case_id}:transition" in paths
    assert "/v1/ecommerce/investigations/cases/{case_id}/runs" in paths
    assert "/v1/ecommerce/investigations/runs/{run_id}:pause" in paths
    assert "/v1/ecommerce/investigations/runs/{run_id}:resume" in paths
    assert "/v1/ecommerce/investigations/runs/{run_id}:cancel" in paths
    assert "/v1/ecommerce/investigations/cases/{case_id}/schedule-policies" in paths
    assert "/v1/ecommerce/investigations/schedule-policies/{schedule_policy_id}" in paths
    assert "/v1/ecommerce/investigations/schedule-policies/{schedule_policy_id}:update" in paths
    assert "/v1/ecommerce/investigations/schedule-policies/{schedule_policy_id}:trigger" in paths
    view = paths["/v1/ecommerce/investigations/runs/{run_id}/view"]["get"]
    assert view["operationId"] == "ecommerceInvestigationRunWorkbenchViewGet"
    request_data = paths["/v1/ecommerce/investigations/runs/{run_id}:request-data"]["post"]
    assert request_data["operationId"] == "ecommerceInvestigationRunDataRequest"


def test_schedule_policy_http_uses_principal_and_two_exact_versions() -> None:
    fake = FakeApplication()
    fake.calls = []
    current = scheduled_case()
    body = {
        "schedulePolicyId": "schedule-1",
        "caseRef": ref(
            "BusinessInvestigationCaseRevision",
            "case-1",
            revision=2,
            content_hash=current.content_hash,
        ),
        "analysisType": "weekly_business_review",
        "policyKind": "weekly_review",
        "cadence": "weekly",
        "enabled": True,
        "overlapPolicy": "skip",
        "timezone": "Asia/Shanghai",
        "weeklyDay": 1,
        "localTime": "09:00",
    }
    with client(fake) as api:
        created = api.post(
            "/v1/ecommerce/investigations/cases/case-1/schedule-policies",
            headers={"Idempotency-Key": "schedule-create", "If-Match": '"2"'},
            json=body,
        )
        assert created.status_code == 201
        assert fake.calls[-1][1] == TenantScope("org-org", "dev-project")
        assert fake.calls[-1][-1]["expected_policy_revision"] == 0
        assert fake.calls[-1][-1]["expected_case_version"] == 2
        updated_body = {
            **body,
            "caseRef": ref(
                "BusinessInvestigationCaseRevision",
                "case-1",
                revision=3,
                content_hash=scheduled_case(
                    revision=3,
                    schedule_ref=ref("SchedulePolicyRevision", "schedule-1"),
                ).content_hash,
            ),
            "enabled": False,
        }
        updated = api.post(
            "/v1/ecommerce/investigations/schedule-policies/schedule-1:update",
            headers={
                "Idempotency-Key": "schedule-update",
                "If-Match": '"1"',
                "X-Case-If-Match": '"3"',
            },
            json=updated_body,
        )
        assert updated.status_code == 200
        assert fake.calls[-1][-1]["expected_policy_revision"] == 1
        assert fake.calls[-1][-1]["expected_case_version"] == 3


def test_workbench_view_http_uses_principal_tenant_and_hides_non_visible_source() -> None:
    fake = FakeApplication()
    fake.calls = []
    fake.missing = False
    with client(fake) as api:
        response = api.get("/v1/ecommerce/investigations/runs/run-1/view")
        assert response.status_code == 200
        assert response.json()["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
        assert response.json()["artifacts"][0]["status"] == "missing"
        assert response.json()["schemaVersion"].endswith("/v5")
        assert response.json()["commandProjection"] == {
            "expectedStateVersion": 1,
            "allowedCommands": ["PAUSE_RUN", "CANCEL_RUN"],
            "externalEffectsAllowed": False,
        }
        assert response.json()["evidence"]["status"] == "missing"
        assert len(response.json()["timeline"]) >= 3
        assert all(item["exactRef"]["contentHash"].startswith("sha256:") for item in response.json()["timeline"])
        assert fake.calls[-1][1] == TenantScope("org-org", "dev-project")
        unknown_query = api.get("/v1/ecommerce/investigations/runs/run-1/view?tenant=dev-org")
        assert unknown_query.status_code == 400
        fake.missing = True
        hidden = api.get("/v1/ecommerce/investigations/runs/run-1/view")
        assert hidden.status_code == 404 and "secret projection id" not in hidden.text
    fake.missing = False


def test_case_query_and_create_use_principal_tenant_and_strict_body() -> None:
    fake = FakeApplication()
    fake.calls = []
    with client(fake) as api:
        response = api.get(
            "/v1/ecommerce/investigations/cases?businessEntityId=store-1&limit=7"
        )
        assert response.status_code == 200 and response.json()["tenant"] == {
            "orgId": "org-org",
            "projectId": "dev-project",
        }
        created = api.post(
            "/v1/ecommerce/investigations/cases",
            headers={"Idempotency-Key": "create-case"},
            json=create_case_body(),
        )
        assert created.status_code == 201 and created.json()["authority"]["caseId"] == "case-1"
        unsafe = api.post(
            "/v1/ecommerce/investigations/cases",
            headers={"Idempotency-Key": "unsafe"},
            json={**create_case_body(), "tenant": {"orgId": "dev-org", "projectId": "dev-project"}},
        )
        assert unsafe.status_code == 400
    assert fake.calls[0] == ("list_cases", TenantScope("org-org", "dev-project"), "store-1", 7)
    assert fake.calls[1][0] == "create_case"
    assert "tenant" not in fake.calls[1][2].model_fields_set


def test_case_transition_requires_if_match_and_idempotency_headers() -> None:
    fake = FakeApplication()
    fake.calls = []
    with client(fake) as api:
        response = api.post(
            "/v1/ecommerce/investigations/cases/case-1:transition",
            headers={"Idempotency-Key": "activate", "If-Match": '"1"'},
            json={"targetLifecycle": "ACTIVE"},
        )
        assert response.status_code == 200
        assert fake.calls[-1][4]["expected_version"] == 1
        invalid = api.post(
            "/v1/ecommerce/investigations/cases/case-1:transition",
            headers={"Idempotency-Key": "activate-2", "If-Match": "W/1"},
            json={"targetLifecycle": "ACTIVE"},
        )
        assert invalid.status_code == 400
        missing = api.post(
            "/v1/ecommerce/investigations/cases/case-1:transition",
            headers={"Idempotency-Key": "activate-3"},
            json={"targetLifecycle": "ACTIVE"},
        )
        assert missing.status_code == 400


def test_run_control_is_command_query_separated_and_not_found_does_not_leak() -> None:
    fake = FakeApplication()
    fake.calls = []
    fake.missing = True
    with client(fake) as api:
        response = api.post(
            "/v1/ecommerce/investigations/runs/run-1:pause",
            headers={"Idempotency-Key": "pause", "If-Match": "1"},
            json={},
        )
        assert response.status_code == 200
        assert response.json()["authority"]["control"] == "PAUSED"
        assert fake.calls[-1][3] is BusinessInvestigationRunControl.PAUSED
        hidden = api.get("/v1/ecommerce/investigations/cases/hidden-case")
        assert hidden.status_code == 404
        assert "secret internal id" not in hidden.text


def test_create_run_service_requires_case_path_exact_ref_before_store_access() -> None:
    class NeverStore:
        def __getattr__(self, name):
            raise AssertionError(f"store must not be accessed: {name}")

    application = EcommerceBusinessInvestigationApplication(
        case_store=NeverStore(), run_store=NeverStore()
    )
    request = CreateBusinessInvestigationRunRequest.model_validate(
        {
            "runId": "run-1",
            "caseRef": ref("BusinessInvestigationCaseRevision", "other-case"),
            "analysisType": "initial_store_analysis",
            "triggerKind": "manual",
            "triggerKey": "manual:run-1",
        }
    )
    try:
        application.create_run(
            TenantScope("org-org", "dev-project"),
            "case-1",
            request,
            idempotency_key="run-create",
            actor="user-1",
            occurred_at=NOW,
        )
    except ValueError as exc:
        assert "exactly match" in str(exc)
    else:  # pragma: no cover - explicit fail-closed assertion
        raise AssertionError("mismatched caseRef was accepted")


def test_request_data_requires_exact_ref_headers_and_principal_scope() -> None:
    fake = FakeApplication()
    fake.calls = []
    body = {
        "requirementRef": ref("DataRequirementRevision", "requirement-1")
    }
    with client(fake) as api:
        response = api.post(
            "/v1/ecommerce/investigations/runs/run-1:request-data",
            headers={"Idempotency-Key": "request-data", "If-Match": '"1"'},
            json=body,
        )
        assert response.status_code == 200
        assert response.json()["authority"]["lifecycle"] == "WAITING_DATA"
        assert fake.calls[-1][1] == TenantScope("org-org", "dev-project")
        assert fake.calls[-1][4]["expected_version"] == 1
        wrong_ref = api.post(
            "/v1/ecommerce/investigations/runs/run-1:request-data",
            headers={"Idempotency-Key": "wrong", "If-Match": "1"},
            json={"requirementRef": ref("ArtifactRevision", "artifact-1")},
        )
        assert wrong_ref.status_code == 400
        missing_header = api.post(
            "/v1/ecommerce/investigations/runs/run-1:request-data",
            headers={"Idempotency-Key": "missing"},
            json=body,
        )
        assert missing_header.status_code == 400
        tenant_injection = api.post(
            "/v1/ecommerce/investigations/runs/run-1:request-data",
            headers={"Idempotency-Key": "tenant", "If-Match": "1"},
            json={**body, "tenant": {"orgId": "dev-org", "projectId": "dev-project"}},
        )
        assert tenant_injection.status_code == 400
