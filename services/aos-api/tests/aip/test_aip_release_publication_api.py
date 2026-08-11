from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aos_api.aip_contracts import ArtifactRef, TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    PublicationEvent,
    PublicationEventType,
    ReleaseGateDecision,
    ReleaseGateStatus,
)
from aos_api.aip_release_publication_service import (
    AipPublicationAlreadyRevoked,
    AipReleaseGateRejected,
)
from aos_api.routers.aip_release_publications import (
    get_aip_release_publication_service,
    router,
)

NOW = datetime(2026, 8, 11, 14, 0, tzinfo=UTC)
H1, H2 = "1" * 64, "2" * 64


@pytest.fixture()
def release_api(client):
    client.app.include_router(router)
    tenant = TenantContext(org_id="dev-org", project_id="dev-project")
    target = AssetRevisionRef(
        asset_type=AssetType.LOGIC_GRAPH,
        asset_id="logic-api",
        revision="1",
        content_hash=H1,
    )
    suite = AssetRevisionRef(
        asset_type=AssetType.EVAL_SUITE,
        asset_id="suite-api",
        revision="1",
        content_hash=H2,
    )
    gate = ReleaseGateDecision(
        tenant=tenant,
        decision_id="gate-api",
        target=target,
        suite_ref=suite,
        eval_run_id="run-api",
        eval_report=ArtifactRef(
            artifact_id="report-api",
            artifact_type="eval_report",
            revision="1",
            content_hash=H2,
        ),
        status=ReleaseGateStatus.PASSED,
        decision_hash=H1,
        decided_by="user:dev",
        decided_at=NOW,
    )
    published = PublicationEvent(
        tenant=tenant,
        event_id="published-api",
        publication_id="publication-api",
        target=target,
        event_type=PublicationEventType.PUBLISHED,
        release_gate_decision_id=gate.decision_id,
        reason_hash=H1,
        actor="user:dev",
        occurred_at=NOW,
    )
    revoked = published.model_copy(
        update={"event_id": "revoked-api", "event_type": PublicationEventType.REVOKED}
    )

    class FakeService:
        def __init__(self) -> None:
            self.error: Exception | None = None
            self.calls: list[tuple[str, tuple, dict]] = []

        def derive_gate(self, *args, **kwargs):
            self.calls.append(("derive", args, kwargs))
            if self.error:
                raise self.error
            return gate

        def publish(self, *args, **kwargs):
            self.calls.append(("publish", args, kwargs))
            if self.error:
                raise self.error
            return published

        def revoke(self, *args, **kwargs):
            self.calls.append(("revoke", args, kwargs))
            if self.error:
                raise self.error
            return revoked

    service = FakeService()
    client.app.dependency_overrides[get_aip_release_publication_service] = lambda: service
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    yield client, service, headers
    client.app.dependency_overrides.pop(get_aip_release_publication_service, None)


def test_gate_publish_revoke_use_authenticated_scope(release_api) -> None:
    client, service, headers = release_api
    gate = client.post(
        "/v1/aip/release-gates/derive",
        headers=headers,
        json={
            "reportId": "report-api",
            "reportRevision": 1,
            "reportHash": H2,
            "idempotencyKey": "gate-key",
        },
    )
    assert gate.status_code == 201
    assert gate.json()["status"] == "passed"
    assert service.calls[-1][1][0].key == ("dev-org", "dev-project")

    published = client.post(
        "/v1/aip/publications/logic",
        headers=headers,
        json={
            "releaseGateDecisionId": "gate-api",
            "reasonHash": H1,
            "idempotencyKey": "publish-key",
        },
    )
    assert published.status_code == 201
    assert published.json()["eventType"] == "published"

    revoked = client.post(
        "/v1/aip/publications/publication-api/revoke",
        headers=headers,
        json={"reasonHash": H2, "idempotencyKey": "revoke-key"},
    )
    assert revoked.status_code == 201
    assert revoked.json()["eventType"] == "revoked"


def test_request_cannot_submit_manual_gate_status(release_api) -> None:
    client, _service, headers = release_api
    response = client.post(
        "/v1/aip/release-gates/derive",
        headers=headers,
        json={
            "reportId": "report-api",
            "reportRevision": 1,
            "reportHash": H2,
            "idempotencyKey": "gate-key",
            "status": "passed",
        },
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (AipReleaseGateRejected("not green"), 422, "AIP_RELEASE_GATE_REJECTED"),
        (
            AipPublicationAlreadyRevoked("already revoked"),
            409,
            "AIP_PUBLICATION_ALREADY_REVOKED",
        ),
    ],
)
def test_release_errors_fail_closed(release_api, error, status_code, code) -> None:
    client, service, headers = release_api
    service.error = error
    response = client.post(
        "/v1/aip/publications/logic",
        headers=headers,
        json={
            "releaseGateDecisionId": "gate-api",
            "reasonHash": H1,
            "idempotencyKey": "publish-key",
        },
    )
    assert response.status_code == status_code
    assert response.json()["code"] == code


def test_release_api_requires_authentication(release_api) -> None:
    client, _service, _headers = release_api
    response = client.post(
        "/v1/aip/release-gates/derive",
        json={
            "reportId": "report-api",
            "reportRevision": 1,
            "reportHash": H2,
            "idempotencyKey": "gate-key",
        },
    )
    assert response.status_code in {401, 403}
