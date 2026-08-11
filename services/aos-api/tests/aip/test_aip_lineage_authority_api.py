from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import (
    EvidenceQuality,
    LineageEvent,
    LineageEventType,
    LineageRootType,
    LineageSourceKind,
)
from aos_api.aip_lineage_service import (
    AipLineageNotFound,
    AipLineagePersistenceError,
)
from aos_api.routers.aip_lineage_authority import (
    get_aip_lineage_service,
    router,
)
from aos_api.tenant_scope import TenantScope

HASH = "a" * 64
NOW = datetime(2026, 8, 11, tzinfo=UTC)


@pytest.fixture()
def lineage_api(client):
    client.app.include_router(router)
    event = LineageEvent(
        tenant=TenantContext(org_id="dev-org", project_id="dev-project"),
        event_id="event-1",
        lineage_id="lineage-1",
        root_type=LineageRootType.TASK_RUN,
        root_id="run-1",
        sequence=1,
        event_type=LineageEventType.INPUT,
        payload_hash=HASH,
        quality=EvidenceQuality.MEASURED,
        occurred_at=NOW,
        observed_at=NOW,
        source_kind=LineageSourceKind.TASK_RUN,
        source_id="run-1:v1",
        source_hash=HASH,
    )

    class FakeService:
        def __init__(self) -> None:
            self.error: Exception | None = None
            self.calls: list[tuple[str, TenantScope, LineageRootType, str]] = []

        def _call(self, kind, scope, root_type, root_id):
            self.calls.append((kind, scope, root_type, root_id))
            if self.error:
                raise self.error
            return [event]

        def list_events(self, scope, root_type, root_id):
            return self._call("list", scope, root_type, root_id)

        def reconcile(self, scope, root_type, root_id):
            return self._call("reconcile", scope, root_type, root_id)

    service = FakeService()
    client.app.dependency_overrides[get_aip_lineage_service] = lambda: service
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    yield client, service, headers
    client.app.dependency_overrides.pop(get_aip_lineage_service, None)


def test_lineage_api_uses_authenticated_scope_and_has_no_manual_event_body(
    lineage_api,
) -> None:
    client, service, headers = lineage_api
    listed = client.get(
        "/v1/aip/lineage-authority/roots/task_run/run-1", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()[0]["sourceKind"] == "task_run"
    reconciled = client.post(
        "/v1/aip/lineage-authority/roots/task_run/run-1/reconcile",
        headers=headers,
    )
    assert reconciled.status_code == 200
    assert service.calls == [
        (
            "list",
            TenantScope("dev-org", "dev-project"),
            LineageRootType.TASK_RUN,
            "run-1",
        ),
        (
            "reconcile",
            TenantScope("dev-org", "dev-project"),
            LineageRootType.TASK_RUN,
            "run-1",
        ),
    ]


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (AipLineageNotFound("missing"), 404, "AIP_LINEAGE_NOT_FOUND"),
        (
            AipLineagePersistenceError("db"),
            503,
            "AIP_LINEAGE_PERSISTENCE_ERROR",
        ),
    ],
)
def test_lineage_api_errors_fail_closed(lineage_api, error, status_code, code) -> None:
    client, service, headers = lineage_api
    service.error = error
    response = client.post(
        "/v1/aip/lineage-authority/roots/action/proposal-1/reconcile",
        headers=headers,
    )
    assert response.status_code == status_code
    assert response.json()["code"] == code


def test_lineage_api_requires_authentication(lineage_api) -> None:
    client, _service, _headers = lineage_api
    response = client.get("/v1/aip/lineage-authority/roots/task_run/run-1")
    assert response.status_code in {401, 403}
