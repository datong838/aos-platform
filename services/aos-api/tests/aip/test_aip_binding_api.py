from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from aos_api.aip_agent_registry_contracts import (
    BindingHealth,
    CapabilityBinding,
    CapabilityReadiness,
    OperationalBindingDependencies,
    OperationalBindingReadiness,
    RegistryReceipt,
    SkillBinding,
    VersionedAssetRef,
)
from aos_api.aip_binding_api_contracts import (
    CapabilityBindingTransitionRequest,
)
from aos_api.aip_contracts import ResourceRef, TenantContext
from aos_api.auth import Principal
from aos_api.errors import ApiError
from aos_api.main import app
from aos_api.routers.aip_bindings import (
    _transition_capability,
    list_capability_bindings,
)
from fastapi.testclient import TestClient

NOW = datetime(2026, 8, 15, 8, tzinfo=UTC)
PRIMARY = Principal(
    subject="aip-operator",
    org_id="org-org",
    project_id="dev-project",
    roles=["developer"],
)
HASH = "a" * 64


def ref(kind: str, asset_id: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=kind,
        asset_id=asset_id,
        revision=1,
        content_hash=HASH,
    )


def readiness() -> OperationalBindingReadiness:
    return OperationalBindingReadiness(
        readiness=CapabilityReadiness.AVAILABLE,
        reasons=[],
        dependencies=OperationalBindingDependencies(),
        dependency_snapshot_hash=HASH,
        evaluated_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
    )


def capability_binding() -> CapabilityBinding:
    return CapabilityBinding(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        binding_id="cap-binding-1",
        capability=ref("CapabilityRevision", "wiki.search"),
        secret_ref="secret://opaque",
        health=BindingHealth.HEALTHY,
        network_policy_revision="network-r1",
        quota_policy_revision="quota-r1",
        timeout_ms=3000,
        max_concurrency=4,
        dependency_snapshot_hash=HASH,
        status="provisioning",
        version=2,
        created_at=NOW,
        updated_at=NOW,
    )


def skill_binding() -> SkillBinding:
    return SkillBinding(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        binding_id="skill-binding-1",
        instance_id="content-officer-1",
        skill=ref("SkillTemplate", "content.plan"),
        capability_binding_ids=["cap-binding-1"],
        budget_policy_ref=ref("BudgetPolicyRevision", "budget-1"),
        dependency_snapshot_hash=HASH,
        status="provisioning",
        version=2,
        created_at=NOW,
        updated_at=NOW,
    )


def receipt(resource: str) -> RegistryReceipt:
    return RegistryReceipt(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        receipt_id="receipt-1",
        operation="binding.update",
        idempotency_key="idem-1",
        request_hash=HASH,
        resource_ref=ResourceRef(
            resource_type=resource,
            resource_id="binding-1",
            revision="1",
            authority="postgresql",
        ),
        result_ref=ResourceRef(
            resource_type=resource,
            resource_id="binding-1",
            revision="2",
            authority="postgresql",
        ),
        status="committed",
        created_by="aip-operator",
        created_at=NOW,
    )


class _CapabilityService:
    def __init__(self, item: CapabilityBinding):
        self.item = item
        self.scope = None
        self.limit = None

    def list_bindings(self, scope, *, limit):
        self.scope = scope
        self.limit = limit
        return [self.item]

    def get(self, scope, _binding_id):
        self.scope = scope
        return self.item

    def update(self, scope, _binding_id, request, **_kwargs):
        self.scope = scope
        return self.item.model_copy(
            update={"status": request.to_status, "version": request.expected_version + 1}
        ), receipt("CapabilityBinding")


def test_list_is_principal_scoped_and_echoes_tenant():
    service = _CapabilityService(capability_binding())

    response = list_capability_bindings(
        limit=25, principal=PRIMARY, service=service
    )

    assert response.tenant.org_id == "org-org"
    assert response.tenant.project_id == "dev-project"
    assert response.count == 1
    assert service.scope.key == ("org-org", "dev-project")
    assert service.limit == 25


def test_transition_fails_closed_on_dependency_snapshot_drift():
    service = _CapabilityService(capability_binding())
    request = CapabilityBindingTransitionRequest(
        expected_version=2,
        expected_dependency_snapshot_hash="b" * 64,
        health=BindingHealth.HEALTHY,
        observed_at=NOW,
    )

    with pytest.raises(ApiError) as caught:
        _transition_capability(
            "active",
            "cap-binding-1",
            request,
            PRIMARY,
            service,
            "idem-1",
        )

    assert caught.value.status_code == 409
    assert "snapshot" in caught.value.message


def test_canonical_binding_openapi_is_complete_and_write_headers_are_required():
    schema = app.openapi()
    expected_paths = {
        "/v1/aip/capability-bindings",
        "/v1/aip/capability-bindings/preview",
        "/v1/aip/capability-bindings/{binding_id}",
        "/v1/aip/capability-bindings/{binding_id}/evaluate",
        "/v1/aip/capability-bindings/{binding_id}/activate",
        "/v1/aip/capability-bindings/{binding_id}/suspend",
        "/v1/aip/capability-bindings/{binding_id}/revoke",
        "/v1/aip/skill-bindings",
        "/v1/aip/skill-bindings/preview",
        "/v1/aip/skill-bindings/{binding_id}",
        "/v1/aip/skill-bindings/{binding_id}/evaluate",
        "/v1/aip/skill-bindings/{binding_id}/activate",
        "/v1/aip/skill-bindings/{binding_id}/suspend",
        "/v1/aip/skill-bindings/{binding_id}/revoke",
    }
    assert expected_paths <= set(schema["paths"])
    for path in expected_paths:
        for operation in schema["paths"][path].values():
            if operation.get("operationId", "").startswith(("create_", "evaluate_", "activate_", "suspend_", "revoke_")):
                header = next(
                    parameter
                    for parameter in operation["parameters"]
                    if parameter["name"] == "Idempotency-Key"
                )
                assert header["required"] is True


def test_canonical_list_endpoint_rejects_missing_auth():
    client = TestClient(app)
    response = client.get("/v1/aip/capability-bindings")
    assert response.status_code == 401


def test_contract_fixtures_remain_serializable():
    assert readiness().readiness is CapabilityReadiness.AVAILABLE
    assert skill_binding().binding_id == "skill-binding-1"
