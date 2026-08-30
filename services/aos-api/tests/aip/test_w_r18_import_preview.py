import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aos_api.aip_import_preview import preview_import
from aos_api.aip_import_job_service import AipImportJobService
from aos_api.aip_marketplace_import_contracts import (
    ApplyImportJobRequest,
    ApproveImportJobRequest,
    CreateImportJobRequest,
    ImportPreviewRequest,
    RollbackImportJobRequest,
)
from aos_api.aip_contracts import ResourceRef
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.routers.phase3_aip_agents import _require_import_role, router
from aos_api.tenant_scope import TenantScope


def _principal(org_id: str = "org-org") -> Principal:
    return Principal(subject="pytest", org_id=org_id, project_id="dev-project")


def _request(*, kind: str = "agent", content: str = "def run(value):\n    return value\n", risk: str = "low") -> ImportPreviewRequest:
    return ImportPreviewRequest.model_validate(
        {
            "kind": kind,
            "source": {
                "sourceRef": {
                    "resourceType": "GitRepository",
                    "resourceId": "approved/ecommerce-agent",
                    "revision": "abcdef1",
                    "authority": "user-supplied",
                },
                "sourceCommit": "abcdef1",
                "licenseId": "MIT",
                "signatureRef": {
                    "resourceType": "PackageSignatureVerification",
                    "resourceId": "signature/ecommerce-agent",
                    "revision": "1",
                    "authority": "user-supplied",
                },
                "sbomRef": {
                    "resourceType": "SBOM",
                    "resourceId": "sbom/ecommerce-agent",
                    "revision": "1",
                    "authority": "user-supplied",
                },
                "dependencyRefs": [],
                "files": [{"path": "agent.py", "content": content}],
            },
            "mapping": {
                "targetId": "ecommerce.agent.imported",
                "displayName": "导入智能体",
                "toolMappings": {},
                "permissionMappings": {},
                "inputSchema": {"type": "object"} if kind == "capability" else {},
                "outputSchema": {"type": "object"} if kind == "capability" else {},
            },
            "security": {"riskLevel": risk},
        }
    )


def test_preview_is_deterministic_and_does_not_create_import_authority() -> None:
    request = _request(kind="capability")

    first = preview_import(_principal(), request)
    second = preview_import(_principal(), request)

    assert first.preview_id == second.preview_id
    assert first.content_hash == second.content_hash
    assert first.tenant.org_id == "org-org"
    assert first.status == "external_required"
    assert first.import_job_authority == "not_created"
    assert first.approval_required is True
    assert [step.status.value for step in first.steps] == [
        "passed",
        "passed",
        "passed",
        "passed",
        "external_required",
    ]
    assert first.steps[-1].summary.endswith("需要独立授权")


def test_dangerous_source_fails_closed_before_external_test() -> None:
    result = preview_import(_principal(), _request(content="eval(user_input)"))

    assert result.status == "blocked"
    assert result.scan_artifact.accepted is False
    assert "SKILL.DYNAMIC_EXEC" in result.steps[1].blocker_codes
    assert result.steps[-1].status.value == "blocked"
    assert result.steps[-1].blocker_codes == ["IMPORT_PRECONDITION_BLOCKED"]


def test_capability_requires_input_and_output_schema() -> None:
    request = _request(kind="capability")
    request.mapping.output_schema = {}

    result = preview_import(_principal(), request)

    assert result.status == "blocked"
    assert result.steps[2].blocker_codes == ["IMPORT_SCHEMA_MAPPING_REQUIRED"]


def test_high_risk_preview_requires_network_policy_reference() -> None:
    result = preview_import(_principal(), _request(risk="high"))

    assert result.status == "blocked"
    assert "IMPORT_NETWORK_POLICY_REQUIRED" in result.steps[3].blocker_codes


def test_plaintext_secret_is_rejected_and_never_enters_preview() -> None:
    payload = _request().model_dump(mode="json", by_alias=True)
    payload["security"]["secretRef"] = "plain-api-key"

    with pytest.raises(ValidationError, match="opaque secret reference"):
        ImportPreviewRequest.model_validate(payload)


def test_negative_canary_keeps_its_own_tenant_context() -> None:
    result = preview_import(_principal("dev-org"), _request())

    assert result.tenant.org_id == "dev-org"
    assert result.tenant.project_id == "dev-project"


def test_import_preview_http_contract_remains_preview_only() -> None:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_principal] = _principal

    with TestClient(app) as client:
        response = client.post(
            "/v1/aip/import-previews",
            json=_request().model_dump(mode="json", by_alias=True),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["tenant"] == {"orgId": "org-org", "projectId": "dev-project"}
    assert body["status"] == "external_required"
    assert body["importJobAuthority"] == "not_created"
    assert body["approvalRequired"] is True
    assert body["steps"][-1]["status"] == "external_required"


def test_import_job_full_control_plane_lifecycle_is_receipted_and_reversible() -> None:
    principal = _principal("dev-org")
    request = _request()
    preview = preview_import(principal, request)
    service = AipImportJobService()

    created = service.create(
        principal,
        CreateImportJobRequest(
            preview_request=request,
            expected_preview_id=preview.preview_id,
            expected_content_hash=preview.content_hash,
        ),
        idempotency_key="pytest-create-import-job",
    )
    assert created.job.status.value == "awaiting_approval"
    assert created.candidate is None
    assert created.receipt.operation == "import_job.create"

    approved = service.approve(
        TenantScope("dev-org", "dev-project"),
        created.job.job_id,
        ApproveImportJobRequest(
            expected_version=created.job.version,
            test_evidence_ref=ResourceRef(
                resource_type="ImportTestEvidence",
                resource_id="pytest/import-test/evidence",
                revision=preview.content_hash,
                authority="pytest",
            ),
            decision_reason="deterministic integration test reviewed",
        ),
        actor="pytest-reviewer",
        idempotency_key="pytest-approve-import-job",
    )
    assert approved.job.status.value == "approved"
    assert approved.job.approval_reason == "deterministic integration test reviewed"

    applied = service.apply(
        TenantScope("dev-org", "dev-project"),
        created.job.job_id,
        ApplyImportJobRequest(expected_version=approved.job.version),
        actor="pytest-executor",
        idempotency_key="pytest-apply-import-job",
    )
    assert applied.job.status.value == "applied"
    assert applied.candidate is not None
    assert applied.candidate.status == "active"
    assert applied.job.created_refs[0].resource_id == applied.candidate.candidate_id

    rolled_back = service.rollback(
        TenantScope("dev-org", "dev-project"),
        created.job.job_id,
        RollbackImportJobRequest(expected_version=applied.job.version, reason="pytest acceptance rollback"),
        actor="pytest-executor",
        idempotency_key="pytest-rollback-import-job",
    )
    assert rolled_back.job.status.value == "rolled_back"
    assert rolled_back.candidate is not None
    assert rolled_back.candidate.status == "rolled_back"
    assert rolled_back.job.compensated_refs == rolled_back.job.created_refs
    assert rolled_back.job.rollback_reason == "pytest acceptance rollback"


def test_import_job_http_lifecycle_enforces_roles_and_exact_readback() -> None:
    active = {"roles": ["developer"]}

    def principal() -> Principal:
        return Principal(
            subject="pytest-http",
            org_id="dev-org",
            project_id="dev-project",
            roles=active["roles"],
        )

    request = _request(kind="capability")
    preview = preview_import(principal(), request)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_principal] = principal
    with TestClient(app) as client:
        created = client.post(
            "/v1/aip/import-jobs",
            headers={"Idempotency-Key": "pytest-http-create-import"},
            json=CreateImportJobRequest(
                preview_request=request,
                expected_preview_id=preview.preview_id,
                expected_content_hash=preview.content_hash,
                conflict_decisions={"ecommerce.capability.external": "create-new"},
            ).model_dump(mode="json", by_alias=True),
        )
        assert created.status_code == 201
        body = created.json()
        job_id = body["job"]["jobId"]
        assert body["job"]["conflictDecisions"] == {"ecommerce.capability.external": "create-new"}

        active["roles"] = ["developer"]
        with pytest.raises(ApiError) as denied:
            _require_import_role(principal(), approval=True)
        assert denied.value.status_code == 403

        active["roles"] = ["reviewer"]
        approved = client.post(
            f"/v1/aip/import-jobs/{job_id}/approval",
            headers={"Idempotency-Key": "pytest-http-approve-import"},
            json=ApproveImportJobRequest(
                expected_version=body["job"]["version"],
                test_evidence_ref=ResourceRef(
                    resource_type="ImportTestEvidence",
                    resource_id="pytest/http/evidence",
                    revision=preview.content_hash,
                    authority="pytest",
                ),
                decision_reason="http evidence reviewed",
            ).model_dump(mode="json", by_alias=True),
        )
        assert approved.status_code == 200
        assert approved.json()["job"]["approvalReason"] == "http evidence reviewed"

        active["roles"] = ["developer"]
        applied = client.post(
            f"/v1/aip/import-jobs/{job_id}/apply",
            headers={"Idempotency-Key": "pytest-http-apply-import"},
            json={"expectedVersion": approved.json()["job"]["version"]},
        )
        assert applied.status_code == 200
        assert applied.json()["candidate"]["status"] == "active"
        assert client.get(f"/v1/aip/import-jobs/{job_id}").json()["status"] == "applied"
        assert client.get("/v1/aip/import-jobs").json()["count"] >= 1

        rolled_back = client.post(
            f"/v1/aip/import-jobs/{job_id}/rollback",
            headers={"Idempotency-Key": "pytest-http-rollback-import"},
            json={"expectedVersion": applied.json()["job"]["version"], "reason": "http acceptance rollback"},
        )
        assert rolled_back.status_code == 200
        assert rolled_back.json()["job"]["rollbackReason"] == "http acceptance rollback"
        assert rolled_back.json()["candidate"]["status"] == "rolled_back"
