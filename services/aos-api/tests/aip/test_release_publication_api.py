from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from aos_api.aip_contracts import ArtifactRef, TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    PublicationEvent,
    PublicationEventType,
    ReleaseGateDecision,
    ReleaseGateStatus,
)
from aos_api.aip_route_release_request_context import (
    RouteReleaseRequestContext,
    optional_route_release_request_context,
)
from aos_api.auth import Principal, require_principal
from aos_api.routers.aip_release_publications import (
    get_aip_release_publication_service,
    router,
)


NOW = datetime(2026, 10, 30, 16, 0, tzinfo=UTC)
H1, H2 = "1" * 64, "2" * 64


@pytest.fixture()
def route_release_api(client):
    client.app.include_router(router)
    tenant = TenantContext(org_id="org-org", project_id="dev-project")
    target = AssetRevisionRef(asset_type=AssetType.MODEL_ROUTE,
        asset_id="route-current", revision="1", content_hash=H1)
    suite = AssetRevisionRef(asset_type=AssetType.EVAL_SUITE,
        asset_id="suite-current", revision="1", content_hash=H2)
    gate = ReleaseGateDecision(tenant=tenant, decision_id="gate-current",
        target=target, suite_ref=suite, eval_run_id="run-current",
        eval_report=ArtifactRef(artifact_id="report-current",
            artifact_type="eval_report", revision="1", content_hash=H2),
        status=ReleaseGateStatus.PASSED, decision_hash=H1,
        decided_by="operator", decided_at=NOW)
    event = PublicationEvent(tenant=tenant, event_id="event-current",
        publication_id="publication-current", target=target,
        event_type=PublicationEventType.PUBLISHED,
        release_gate_decision_id=gate.decision_id, reason_hash=H1,
        actor="operator", occurred_at=NOW)

    class FakeService:
        def __init__(self):
            self.calls = []

        def derive_gate(self, *args, **kwargs):
            self.calls.append(("derive", args, kwargs))
            return gate

        def publish(self, *args, **kwargs):
            self.calls.append(("publish", args, kwargs))
            return event

    service = FakeService()
    context = RouteReleaseRequestContext(
        principal=Principal(subject="operator", org_id="org-org",
            project_id="dev-project", token_kind="oidc"),
        bearer_token=SecretStr("header.payload.signature"))
    client.app.dependency_overrides[get_aip_release_publication_service] = lambda: service
    client.app.dependency_overrides[optional_route_release_request_context] = lambda: context
    client.app.dependency_overrides[require_principal] = lambda: context.principal
    headers = {"Authorization": "Bearer header.payload.signature",
        "X-Org-Id": "org-org", "X-Project-Id": "dev-project"}
    yield client, service, headers, context
    client.app.dependency_overrides.pop(get_aip_release_publication_service, None)
    client.app.dependency_overrides.pop(optional_route_release_request_context, None)
    client.app.dependency_overrides.pop(require_principal, None)


def test_route_release_http_injects_server_context_only(route_release_api):
    client, service, headers, context = route_release_api
    gate = client.post("/v1/aip/release-gates/derive", headers=headers, json={
        "reportId": "report-current", "reportRevision": 1,
        "reportHash": H2, "idempotencyKey": "gate-key"})
    assert gate.status_code == 201
    assert service.calls[-1][2]["route_request_context"] is context

    published = client.post("/v1/aip/publications/logic", headers=headers, json={
        "releaseGateDecisionId": "gate-current", "reasonHash": H1,
        "idempotencyKey": "publish-key"})
    assert published.status_code == 201
    assert service.calls[-1][2]["route_request_context"] is context
    assert "header.payload.signature" not in gate.text + published.text


@pytest.mark.parametrize("secret_field", ["bearerToken", "manifestBytes", "routeEvidence"])
def test_route_release_http_rejects_client_supplied_internal_evidence(
        route_release_api, secret_field):
    client, service, headers, _ = route_release_api
    body = {"reportId": "report-current", "reportRevision": 1,
        "reportHash": H2, "idempotencyKey": "gate-key", secret_field: "forbidden"}
    response = client.post("/v1/aip/release-gates/derive", headers=headers, json=body)
    assert response.status_code in {400, 422}
    assert service.calls == []
    assert "header.payload.signature" not in response.text
