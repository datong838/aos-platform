"""HTTP contract tests for governed AIP Logic publications."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aos_api.aip_logic_graph_models import LogicGraphSnapshot
from aos_api.aip_logic_publication_models import (
    LogicPublication,
    LogicPublicationGateSummary,
    LogicPublicationListResponse,
)
from aos_api.aip_logic_publication_store import (
    LogicPublicationDryRunRequired,
    LogicPublicationNotFound,
    LogicPublicationVersionConflict,
)
from aos_api.routers.aip_logic_publications import (
    get_logic_graph_store,
    get_logic_eval_evidence_reader,
    get_logic_publication_store,
    router,
)


@pytest.fixture()
def publication_api(client):
    client.app.include_router(router)
    graph_hash = "a" * 64
    snapshot = LogicGraphSnapshot(
        id="logic-api",
        name="Logic API",
        description="",
        status="draft",
        schema_version=1,
        revision=1,
        published_version=None,
        graph_hash=graph_hash,
        nodes=[{"id": "input", "kind": "input", "label": "Input"}],
        edges=[],
        entry_node_ids=["input"],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        persisted=True,
    )
    publication = LogicPublication(
        publication_id="logic-pub-api",
        graph_id=snapshot.id,
        graph_revision=1,
        graph_hash=graph_hash,
        graph_snapshot=snapshot,
        dry_run_id="run-api",
        eval_suite_id="suite-api",
        eval_report_id="report-api",
        eval_gate=LogicPublicationGateSummary(
            pass_rate=1,
            threshold=0.8,
            passed=1,
            failed=0,
            total=1,
            run_at=datetime.now(UTC),
        ),
        actor="dev-user",
        created_at=datetime.now(UTC),
    )

    class FakeStore:
        error: Exception | None = None
        publish_args: tuple | None = None

        def publish(self, *args):
            self.publish_args = args
            if self.error:
                raise self.error
            return publication

        def list(self, *_args):
            if self.error:
                raise self.error
            return LogicPublicationListResponse(items=[publication], count=1)

        def get(self, *_args):
            if self.error:
                raise self.error
            return publication

    store = FakeStore()
    reader = object()
    client.app.dependency_overrides[get_logic_publication_store] = lambda: store
    client.app.dependency_overrides[get_logic_eval_evidence_reader] = lambda: reader
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    yield client, store, reader, headers, publication
    client.app.dependency_overrides.pop(get_logic_publication_store, None)
    client.app.dependency_overrides.pop(get_logic_eval_evidence_reader, None)


def _request() -> dict:
    return {
        "expected_revision": 1,
        "expected_graph_hash": "a" * 64,
        "eval_suite_id": "suite-api",
        "eval_report_id": "report-api",
        "idempotency_key": "publish-api-once",
    }


def test_publish_list_and_get_use_tenant_scope(publication_api) -> None:
    client, store, reader, headers, publication = publication_api
    published = client.post(
        "/v1/aip/logic/graphs/logic-api/publish",
        headers=headers,
        json=_request(),
    )
    assert published.status_code == 201
    assert published.json()["publication_id"] == publication.publication_id
    assert store.publish_args[:5] == (
        "dev-org",
        "dev-project",
        "user:dev",
        "logic-api",
        store.publish_args[4],
    )
    assert store.publish_args[-1] is reader

    listed = client.get(
        "/v1/aip/logic/graphs/logic-api/publications", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    loaded = client.get(
        "/v1/aip/logic/graphs/logic-api/publications/logic-pub-api",
        headers=headers,
    )
    assert loaded.status_code == 200
    assert loaded.json()["dry_run_id"] == "run-api"


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (LogicPublicationNotFound("missing"), 404, "LOGIC_PUBLICATION_NOT_FOUND"),
        (
            LogicPublicationVersionConflict(
                expected_revision=1,
                expected_graph_hash="a" * 64,
                current_revision=2,
                current_graph_hash="b" * 64,
            ),
            409,
            "LOGIC_GRAPH_VERSION_CONFLICT",
        ),
        (
            LogicPublicationDryRunRequired("dry-run required"),
            422,
            "LOGIC_PUBLICATION_DRY_RUN_REQUIRED",
        ),
    ],
)
def test_publish_errors_are_fail_closed(publication_api, error, status_code, code) -> None:
    client, store, _reader, headers, _publication = publication_api
    store.error = error
    response = client.post(
        "/v1/aip/logic/graphs/logic-api/publish",
        headers=headers,
        json=_request(),
    )
    assert response.status_code == status_code
    assert response.json()["code"] == code


def test_publish_requires_authentication(publication_api) -> None:
    client, _store, _reader, _headers, _publication = publication_api
    response = client.post(
        "/v1/aip/logic/graphs/logic-api/publish",
        json=_request(),
    )
    assert response.status_code in {401, 403}


def test_restore_publication_creates_new_draft_revision_without_mutating_release(publication_api) -> None:
    client, _store, _reader, headers, publication = publication_api

    class FakeGraphStore:
        replace_args: tuple | None = None

        def get(self, *_args):
            return publication.graph_snapshot

        def replace(self, *args):
            self.replace_args = args
            request = args[-1]
            return publication.graph_snapshot.model_copy(
                update={
                    "status": "draft",
                    "revision": publication.graph_snapshot.revision + 1,
                    "graph_hash": "c" * 64,
                }
            )

    graph_store = FakeGraphStore()
    client.app.dependency_overrides[get_logic_graph_store] = lambda: graph_store
    try:
        response = client.post(
            "/v1/aip/logic/graphs/logic-api/publications/logic-pub-api/restore",
            headers=headers,
            json={"expected_revision": 1, "expected_graph_hash": "a" * 64},
        )
    finally:
        client.app.dependency_overrides.pop(get_logic_graph_store, None)

    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert response.json()["status"] == "draft"
    assert graph_store.replace_args[:4] == (
        "dev-org",
        "dev-project",
        "logic-api",
        "user:dev",
    )
    request = graph_store.replace_args[-1]
    assert request.expected_revision == 1
    assert request.nodes == publication.graph_snapshot.nodes
    assert publication.graph_revision == 1


def test_restore_publication_rejects_stale_current_hash(publication_api) -> None:
    client, _store, _reader, headers, publication = publication_api

    class FakeGraphStore:
        def get(self, *_args):
            return publication.graph_snapshot.model_copy(update={"graph_hash": "d" * 64})

    client.app.dependency_overrides[get_logic_graph_store] = lambda: FakeGraphStore()
    try:
        response = client.post(
            "/v1/aip/logic/graphs/logic-api/publications/logic-pub-api/restore",
            headers=headers,
            json={"expected_revision": 1, "expected_graph_hash": "a" * 64},
        )
    finally:
        client.app.dependency_overrides.pop(get_logic_graph_store, None)
    assert response.status_code == 409
    assert response.json()["code"] == "LOGIC_GRAPH_VERSION_CONFLICT"
