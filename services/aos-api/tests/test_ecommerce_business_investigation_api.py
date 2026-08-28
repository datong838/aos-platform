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
    BusinessInvestigationAnalysisType,
    BusinessInvestigationCaseNotFound,
    BusinessInvestigationCaseRevision,
)
from aos_api.ecommerce_business_investigation_case_selection import (
    BusinessInvestigationCaseSelection,
)
from aos_api.ecommerce_business_investigation_run import (
    BusinessInvestigationRunControl,
    BusinessInvestigationRunStateRevision,
)
from aos_api.ecommerce_business_investigation_projection import (
    BusinessInvestigationProjectionNotFound,
)
from aos_api.ecommerce_business_investigation_data_command import (
    BusinessInvestigationDataCommandResponse,
)
from aos_api.ecommerce_business_investigation_review_command import (
    BusinessInvestigationStageReviewItem,
    BusinessInvestigationStageReviewProjection,
    BusinessInvestigationStageReviewResponse,
)
from aos_api.ecommerce_analyst_growth_plan_approval import GrowthPlanApprovalResponse
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.aip_business_investigation_runtime import CanonicalRuntimeRef
from aos_api.aip_production_contracts import ReviewIssueStatus
from aos_api.errors import register_exception_handlers
from aos_api.routers import ecommerce_business_investigations as routes
from aos_api.tenant_scope import TenantScope
from test_ecommerce_business_investigation_lifecycle import HASH_A, draft_case, ref
from test_ecommerce_business_investigation_schedule import case as scheduled_case
from test_ecommerce_business_investigation_schedule import policy as schedule_policy
from test_aip_business_investigation_data_requester import request as missing_data_request
from test_data_requirement_store import requirement as data_requirement


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

    def get_case_selection(self, scope, analysis_type):
        self.calls.append(("get_case_selection", scope, analysis_type))
        return BusinessInvestigationCaseSelection(
            tenant=TENANT,
            analysisType=analysis_type.value,
            sourceReadinessStatus="failed",
            blockers=["SOURCE_READINESS_NOT_READY"],
        )

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

    def request_run_missing_data(self, scope, run_id, request, **kwargs):
        self.calls.append(("request_missing_data", scope, run_id, request, kwargs))
        authority = data_requirement(requirement_id="requirement-command-1")
        requirement_ref = ref(
            "DataRequirementRevision",
            authority.requirement_id,
            revision=authority.revision,
            content_hash=authority.content_hash,
        )
        return BusinessInvestigationDataCommandResponse(
            tenant=TENANT,
            requirementRef=requirement_ref,
            requirementStatus=authority.status,
            runAuthority=state(
                "RUNNING",
                kwargs["expected_version"] + 1,
                lifecycle="WAITING_DATA",
                pending_requirement_ref=requirement_ref,
            ),
            dataReplayed=False,
            runReplayed=False,
        )

    def confirm_run_data_requirement(self, scope, run_id, request, **kwargs):
        self.calls.append(("confirm_data", scope, run_id, request, kwargs))
        authority = data_requirement(requirement_id="requirement-command-1")
        requirement_ref = ref(
            "DataRequirementRevision",
            authority.requirement_id,
            revision=authority.revision,
            content_hash=authority.content_hash,
        )
        return BusinessInvestigationDataCommandResponse(
            tenant=TENANT,
            requirementRef=requirement_ref,
            requirementStatus=authority.status,
            runAuthority=state(
                "RUNNING",
                kwargs["expected_version"] + 1,
                lifecycle="WAITING_DATA",
                pending_requirement_ref=requirement_ref,
            ),
            dataReplayed=True,
            runReplayed=False,
        )

    def get_run_stage_review(self, scope, run_id):
        self.calls.append(("get_stage_review", scope, run_id))
        from test_ecommerce_business_investigation_review_command import issue

        current = issue()
        return BusinessInvestigationStageReviewProjection(
            tenant=TENANT,
            runRef=ref("BusinessInvestigationRun", run_id),
            taskRunRef=CanonicalRuntimeRef(
                resourceType="TaskRun", resourceId="task-run-1", version=3
            ),
            items=[
                BusinessInvestigationStageReviewItem(
                    issue=current,
                    stage="portrait",
                    evalReportRef=current.eval_report_ref,
                    artifactRef={
                        "resourceType": "Artifact",
                        "resourceId": current.artifact_ref.artifact_id,
                        "revision": 1,
                        "contentHash": current.artifact_ref.content_hash,
                    },
                    allowedDecisions=["accept", "return"],
                )
            ],
        )

    def review_run_stage(self, scope, run_id, request, **kwargs):
        self.calls.append(("review_stage", scope, run_id, request, kwargs))
        from test_ecommerce_business_investigation_review_command import issue

        return BusinessInvestigationStageReviewResponse(
            tenant=TENANT,
            decision="accept",
            issue=issue(
                status=ReviewIssueStatus.RESOLVED,
                version=request.expected_issue_version + 1,
            ),
        )

    def approve_growth_plan(self, scope, plan_id, request, **kwargs):
        self.calls.append(("approve_growth_plan", scope, plan_id, request, kwargs))
        return GrowthPlanApprovalResponse(
            tenant=TENANT,
            draftRef=request.draft_ref,
            approvedRef=AnalystExactRef(
                resourceType="GrowthPlanRevision",
                resourceId=plan_id,
                revision=request.draft_ref.revision + 1,
                contentHash="b" * 64,
            ),
            replayed=False,
        )


def client(application: FakeApplication, *, roles=()) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(routes.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user-1", org_id="org-org", project_id="dev-project", roles=list(roles)
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
    assert "/v1/ecommerce/investigations/case-selection" in paths
    assert "/v1/ecommerce/investigations/cases/{case_id}:transition" in paths
    assert "/v1/ecommerce/investigations/cases/{case_id}/runs" in paths
    assert "/v1/ecommerce/investigations/runs/{run_id}:pause" in paths
    assert "/v1/ecommerce/investigations/runs/{run_id}:resume" in paths
    assert "/v1/ecommerce/investigations/runs/{run_id}:cancel" in paths
    assert "/v1/ecommerce/investigations/cases/{case_id}/schedule-policies" in paths
    assert "/v1/ecommerce/investigations/schedule-policies/{schedule_policy_id}" in paths
    assert "/v1/ecommerce/investigations/schedule-policies/{schedule_policy_id}:update" in paths
    assert "/v1/ecommerce/investigations/schedule-policies/{schedule_policy_id}:trigger" in paths
    assert "/v1/ecommerce/investigations/growth-plans/{plan_id}:approve" in paths
    assert "/v1/ecommerce/investigations/runs/{run_id}/handoffs:compile" in paths
    expected_operation_ids = {
        (
            "/v1/ecommerce/investigations/case-selection",
            "get",
        ): "ecommerceInvestigationCaseSelectionGet",
        ("/v1/ecommerce/investigations/cases", "get"): "ecommerceInvestigationCaseList",
        ("/v1/ecommerce/investigations/cases", "post"): "ecommerceInvestigationCaseCreate",
        ("/v1/ecommerce/investigations/cases/{case_id}", "get"): "ecommerceInvestigationCaseGet",
        (
            "/v1/ecommerce/investigations/cases/{case_id}:transition",
            "post",
        ): "ecommerceInvestigationCaseTransition",
        (
            "/v1/ecommerce/investigations/cases/{case_id}/runs",
            "get",
        ): "ecommerceInvestigationRunList",
        (
            "/v1/ecommerce/investigations/cases/{case_id}/runs",
            "post",
        ): "ecommerceInvestigationRunCreate",
        ("/v1/ecommerce/investigations/runs/{run_id}", "get"): "ecommerceInvestigationRunGet",
        (
            "/v1/ecommerce/investigations/runs/{run_id}:pause",
            "post",
        ): "ecommerceInvestigationRunPause",
        (
            "/v1/ecommerce/investigations/runs/{run_id}:resume",
            "post",
        ): "ecommerceInvestigationRunResume",
        (
            "/v1/ecommerce/investigations/runs/{run_id}:cancel",
            "post",
        ): "ecommerceInvestigationRunCancel",
    }
    assert {
        route: paths[route[0]][route[1]]["operationId"]
        for route in expected_operation_ids
    } == expected_operation_ids
    view = paths["/v1/ecommerce/investigations/runs/{run_id}/view"]["get"]
    assert view["operationId"] == "ecommerceInvestigationRunWorkbenchViewGet"
    request_data = paths["/v1/ecommerce/investigations/runs/{run_id}:request-data"]["post"]
    assert request_data["operationId"] == "ecommerceInvestigationRunDataRequest"
    assert paths["/v1/ecommerce/investigations/runs/{run_id}:request-missing-data"]["post"][
        "operationId"
    ] == "ecommerceInvestigationRunMissingDataRequest"
    assert paths[
        "/v1/ecommerce/investigations/runs/{run_id}:confirm-data-requirement"
    ]["post"]["operationId"] == "ecommerceInvestigationRunDataRequirementConfirm"
    assert paths[
        "/v1/ecommerce/investigations/runs/{run_id}/stage-review"
    ]["get"]["operationId"] == "ecommerceInvestigationRunStageReviewGet"
    assert paths[
        "/v1/ecommerce/investigations/runs/{run_id}:review-stage"
    ]["post"]["operationId"] == "ecommerceInvestigationRunStageReview"
    assert paths[
        "/v1/ecommerce/investigations/runs/{run_id}/handoffs:compile"
    ]["post"]["operationId"] == "ecommerceInvestigationHandoffCompile"


def test_case_selection_is_principal_scoped_and_read_only() -> None:
    fake = FakeApplication()
    fake.calls = []
    with client(fake) as api:
        response = api.get(
            "/v1/ecommerce/investigations/case-selection",
            params={"analysisType": "initial_store_analysis"},
        )
    assert response.status_code == 200
    assert response.json()["caseCreatable"] is False
    assert response.json()["blockers"] == ["SOURCE_READINESS_NOT_READY"]
    assert fake.calls == [
        (
            "get_case_selection",
            TenantScope("org-org", "dev-project"),
            BusinessInvestigationAnalysisType.INITIAL_STORE_ANALYSIS,
        )
    ]


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


def test_missing_data_commands_require_role_and_hide_server_derived_lineage() -> None:
    fake = FakeApplication()
    fake.calls = []
    body = missing_data_request().model_dump(mode="json", by_alias=True)
    for key in ("requirementId", "idempotencyKey", "channelRef", "entityRef"):
        body.pop(key)
    with client(fake) as api:
        forbidden = api.post(
            "/v1/ecommerce/investigations/runs/run-1:request-missing-data",
            headers={"Idempotency-Key": "missing-data", "If-Match": '"1"'},
            json=body,
        )
        assert forbidden.status_code == 403 and fake.calls == []

    with client(fake, roles=("data-owner",)) as api:
        created = api.post(
            "/v1/ecommerce/investigations/runs/run-1:request-missing-data",
            headers={"Idempotency-Key": "missing-data", "If-Match": '"1"'},
            json=body,
        )
        assert created.status_code == 200
        assert created.json()["sourceReadPerformed"] is False
        assert created.json()["externalEffectAuthorized"] is False
        assert fake.calls[-1][0] == "request_missing_data"
        injected = api.post(
            "/v1/ecommerce/investigations/runs/run-1:request-missing-data",
            headers={"Idempotency-Key": "injected", "If-Match": '"1"'},
            json={**body, "channelRef": ref("ChannelRevision", "other-channel")},
        )
        assert injected.status_code == 400
        confirmed = api.post(
            "/v1/ecommerce/investigations/runs/run-1:confirm-data-requirement",
            headers={"Idempotency-Key": "confirm", "If-Match": '"2"'},
            json={"decision": "accept"},
        )
        assert confirmed.status_code == 200
        assert fake.calls[-1][0] == "confirm_data"


def test_stage_review_projection_and_command_are_principal_scoped() -> None:
    fake = FakeApplication()
    fake.calls = []
    with client(fake) as api:
        projection = api.get(
            "/v1/ecommerce/investigations/runs/run-1/stage-review"
        )
        assert projection.status_code == 200
        assert projection.json()["items"][0]["allowedDecisions"] == [
            "accept", "return"
        ]
        assert projection.json()["externalEffectsAllowed"] is False
        forbidden = api.post(
            "/v1/ecommerce/investigations/runs/run-1:review-stage",
            headers={"Idempotency-Key": "review-1", "If-Match": '"1"'},
            json={
                "decision": "accept",
                "issueId": "issue-1",
                "expectedIssueVersion": 1,
                "reason": "人工复核通过",
            },
        )
        assert forbidden.status_code == 403
    with client(fake, roles=("reviewer",)) as api:
        accepted = api.post(
            "/v1/ecommerce/investigations/runs/run-1:review-stage",
            headers={"Idempotency-Key": "review-1", "If-Match": '"1"'},
            json={
                "decision": "accept",
                "issueId": "issue-1",
                "expectedIssueVersion": 1,
                "reason": "人工复核通过",
            },
        )
        assert accepted.status_code == 200
        assert accepted.json()["issue"]["status"] == "resolved"
        assert accepted.json()["externalEffectsAllowed"] is False
        assert fake.calls[-1][1] == TenantScope("org-org", "dev-project")
        injected = api.post(
            "/v1/ecommerce/investigations/runs/run-1:review-stage",
            headers={"Idempotency-Key": "review-2", "If-Match": '"1"'},
            json={
                "decision": "accept",
                "issueId": "issue-1",
                "expectedIssueVersion": 1,
                "reason": "人工复核通过",
                "taskRunId": "other-run",
            },
        )
        assert injected.status_code == 400


def test_growth_plan_approval_is_strict_principal_scoped_and_has_no_external_effect() -> None:
    fake = FakeApplication()
    fake.calls = []
    body = {
        "draftRef": {
            "resourceType": "GrowthPlanRevision",
            "resourceId": "plan-1",
            "revision": 1,
            "contentHash": "a" * 64,
        }
    }
    with client(fake) as api:
        forbidden = api.post(
            "/v1/ecommerce/investigations/growth-plans/plan-1:approve",
            headers={"Idempotency-Key": "approve-1", "If-Match": '"1"'},
            json=body,
        )
        assert forbidden.status_code == 403
    with client(fake, roles=("reviewer",)) as api:
        approved = api.post(
            "/v1/ecommerce/investigations/growth-plans/plan-1:approve",
            headers={"Idempotency-Key": "approve-1", "If-Match": '"1"'},
            json=body,
        )
        assert approved.status_code == 200
        assert approved.json()["lifecycle"] == "approved"
        assert approved.json()["externalEffectsAllowed"] is False
        assert fake.calls[-1][0] == "approve_growth_plan"
        assert fake.calls[-1][-1]["expected_version"] == 1
        injected = api.post(
            "/v1/ecommerce/investigations/growth-plans/plan-1:approve",
            headers={"Idempotency-Key": "approve-2", "If-Match": '"1"'},
            json={**body, "approvedAt": NOW.isoformat()},
        )
        assert injected.status_code == 400


def test_handoff_compile_requires_review_role_and_rejects_tenant_injection() -> None:
    fake = FakeApplication()
    fake.calls = []
    body = {
        "handoffId": "handoff-1",
        "approvedPlanRef": {
            "resourceType": "GrowthPlanRevision",
            "resourceId": "plan-1",
            "revision": 2,
            "contentHash": "a" * 64,
        },
        "sourceSlotId": "slot-analyst",
        "targetModuleId": "ecommerce.task-cockpit",
        "targetSlotId": "slot-cockpit",
        "purpose": "受控承接",
        "requestedOutcome": "回写 canonical 决定",
        "markings": ["INTERNAL"],
        "expiresAt": "2026-08-27T06:15:00Z",
    }
    with client(fake) as api:
        forbidden = api.post(
            "/v1/ecommerce/investigations/runs/run-1/handoffs:compile",
            json=body,
        )
        assert forbidden.status_code == 403 and fake.calls == []
        injected = api.post(
            "/v1/ecommerce/investigations/runs/run-1/handoffs:compile",
            json={**body, "tenant": {"orgId": "dev-org", "projectId": "dev-project"}},
        )
        assert injected.status_code == 400 and fake.calls == []
