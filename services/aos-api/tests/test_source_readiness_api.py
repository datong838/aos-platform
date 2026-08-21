"""XU1: principal-scoped SourceReadiness HTTP contract."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from aos_api.auth import Principal, require_principal
from aos_api.errors import register_exception_handlers
from aos_api.routers import source_readiness
from aos_api.source_readiness_contracts import (
    CANONICAL_QYH_SOURCES,
    SourceReadinessEnvelope,
)


NOW = datetime(2026, 8, 21, 12, 0, tzinfo=UTC)


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def read(self, *, org_id: str, project_id: str) -> SourceReadinessEnvelope:
        self.calls.append((org_id, project_id))
        return SourceReadinessEnvelope.model_validate(
            {
                "tenant": {"orgId": org_id, "projectId": project_id},
                "checkedAt": NOW,
                "cutoffAt": NOW,
                "status": "blocked",
                "sources": [
                    {
                        "tenant": {"orgId": org_id, "projectId": project_id},
                        "sourceId": "niushop-qyh",
                        "pipelineId": source.pipeline_id,
                        "objectType": source.object_type,
                        "status": "blocked",
                        "checkedAt": NOW,
                        "reasons": ["QUALITY_POLICY_REF_MISSING"],
                        "blockers": ["QUALITY_POLICY_REF_MISSING"],
                    }
                    for source in CANONICAL_QYH_SOURCES
                ],
            }
        )


def _client(service: FakeService) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(source_readiness.router)
    app.dependency_overrides[require_principal] = lambda: Principal(
        subject="user:test",
        org_id="org-org",
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )
    app.dependency_overrides[source_readiness.get_source_readiness_service] = lambda: service
    return TestClient(app, raise_server_exceptions=False)


def test_api_uses_principal_scope_and_rejects_scope_injection() -> None:
    service = FakeService()
    with _client(service) as client:
        response = client.get("/v1/data/source-readiness")
        assert response.status_code == 200
        assert response.json()["tenant"] == {
            "orgId": "org-org",
            "projectId": "dev-project",
        }
        injected = client.get(
            "/v1/data/source-readiness?orgId=dev-org&projectId=dev-project"
        )
        assert injected.status_code == 400
        assert injected.json()["code"] == "VALIDATION"

    assert service.calls == [("org-org", "dev-project")]
