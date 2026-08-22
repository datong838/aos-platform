import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from aos_api.aip_import_preview import preview_import
from aos_api.aip_marketplace_import_contracts import ImportPreviewRequest
from aos_api.auth import Principal, require_principal
from aos_api.routers.phase3_aip_agents import router


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
                "sbomRef": {
                    "resourceType": "SBOM",
                    "resourceId": "sbom/ecommerce-agent",
                    "revision": "1",
                    "authority": "user-supplied",
                },
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
