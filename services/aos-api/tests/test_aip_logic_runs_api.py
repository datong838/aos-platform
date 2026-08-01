"""HTTP contract tests for trusted Logic dry-run preflight and history routes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from aos_api.aip_logic_dry_run_models import (
    LogicNodeCounts,
    LogicRunListResponse,
    LogicRunSummary,
)
from aos_api.aip_logic_graph_models import (
    LogicGraphSnapshot,
    ValidateLogicGraphRequest,
    compute_logic_graph_hash,
)
from aos_api.aip_logic_graph_store import LogicGraphNotFound
from aos_api.aip_logic_run_store import (
    LogicRunNotFound,
    LogicRunPersistenceError,
    LogicRunStart,
)
from aos_api.aip_logic_runtime_adapters import RuntimeAdapterRegistry
from aos_api.routers.aip_logic_runs import (
    get_logic_run_graph_store,
    get_logic_run_store,
    get_logic_runtime_adapters,
    router,
)


def _graph(*, config=None, status="draft") -> LogicGraphSnapshot:
    content = ValidateLogicGraphRequest(
        name="api",
        status="archived" if status == "archived" else "draft",
        nodes=[
            {"id": "input", "kind": "input", "label": "input", "config": config or {}}
        ],
        entry_node_ids=["input"],
    )
    now = datetime.now(UTC)
    return LogicGraphSnapshot(
        id="graph",
        name="api",
        description="",
        status=status,
        schema_version=1,
        revision=2,
        graph_hash=compute_logic_graph_hash(content),
        nodes=content.nodes,
        edges=[],
        entry_node_ids=["input"],
        created_at=now,
        updated_at=now,
    )


def _empty_graph() -> LogicGraphSnapshot:
    content = ValidateLogicGraphRequest(name="empty")
    now = datetime.now(UTC)
    return LogicGraphSnapshot(
        id="empty",
        name="empty",
        description="",
        status="draft",
        schema_version=1,
        revision=1,
        graph_hash=compute_logic_graph_hash(content),
        nodes=[],
        edges=[],
        entry_node_ids=[],
        created_at=now,
        updated_at=now,
    )


class _GraphStore:
    def __init__(self, graph):
        self.graph = graph

    def get(self, org, project, graph_id):
        if graph_id != self.graph.id or org.endswith("other"):
            raise LogicGraphNotFound("missing")
        return self.graph


class _RunStore:
    def __init__(self):
        self.start_count = 0
        self.result = None

    def start_run(self, _org, _project, _actor, _graph, _request, run_id):
        self.start_count += 1
        return LogicRunStart(run_id=run_id, started_at=datetime.now(UTC))

    def finalize_run(self, _org, _project, result):
        self.result = result

    def get_run(self, _org, _project, _graph_id, run_id):
        if self.result is None or self.result.run_id != run_id:
            raise LogicRunNotFound("missing")
        return self.result

    def list_runs(self, *_args, **_kwargs):
        if self.result is None:
            return LogicRunListResponse(items=[], count=0, next_cursor=None)
        counts = {
            status: sum(node.status == status for node in self.result.node_results)
            for status in ("executed", "skipped", "failed", "canceled")
        }
        summary = LogicRunSummary(
            run_id=self.result.run_id,
            graph_id=self.result.graph_id,
            status=self.result.status,
            evaluated_revision=self.result.evaluated_revision,
            graph_hash=self.result.graph_hash,
            started_at=self.result.started_at,
            finished_at=self.result.finished_at,
            elapsed_ms=self.result.elapsed_ms,
            total_tokens=self.result.total_tokens,
            node_counts=LogicNodeCounts(**counts),
            error_code=self.result.error.code if self.result.error else None,
        )
        return LogicRunListResponse(items=[summary], count=1, next_cursor=None)

    def recover_interrupted(self, *_args, **_kwargs):
        return 0


@pytest.fixture()
def logic_api(client):
    client.app.include_router(router)
    graph_store = _GraphStore(_graph())
    run_store = _RunStore()
    client.app.dependency_overrides[get_logic_run_graph_store] = lambda: graph_store
    client.app.dependency_overrides[get_logic_run_store] = lambda: run_store
    client.app.dependency_overrides[get_logic_runtime_adapters] = RuntimeAdapterRegistry
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "org",
        "X-Project-Id": "project",
    }
    yield headers, graph_store, run_store
    for dependency in (
        get_logic_run_graph_store,
        get_logic_run_store,
        get_logic_runtime_adapters,
    ):
        client.app.dependency_overrides.pop(dependency, None)


def _body(graph):
    return {
        "expected_revision": graph.revision,
        "dry_run": True,
        "expected_graph_hash": graph.graph_hash,
        "inputs": {"safe": True},
    }


@pytest.mark.parametrize(
    "patch", [{"dry_run": False}, {"dry_run": 1}, {"dryRun": True, "dry_run": None}]
)
def test_non_literal_dry_run_is_422_and_does_not_create_run(
    client, logic_api, patch
) -> None:
    headers, graph_store, run_store = logic_api
    body = {**_body(graph_store.graph), **patch}
    if patch.get("dry_run") is None:
        body.pop("dry_run")
    response = client.post(
        "/v1/aip/logic/graphs/graph/dry-run", headers=headers, json=body
    )
    assert response.status_code == 422
    assert run_store.start_count == 0


def test_revision_conflict_and_invalid_config_are_preflight_without_run(
    client, logic_api
) -> None:
    headers, graph_store, run_store = logic_api
    conflict = client.post(
        "/v1/aip/logic/graphs/graph/dry-run",
        headers=headers,
        json={**_body(graph_store.graph), "expected_revision": 1},
    )
    assert conflict.status_code == 409
    graph_store.graph = _graph(config={"legacy": True})
    invalid = client.post(
        "/v1/aip/logic/graphs/graph/dry-run",
        headers=headers,
        json=_body(graph_store.graph),
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "NODE_CONFIG_INVALID"
    assert run_store.start_count == 0


def test_empty_graph_is_rejected_before_a_run_is_created(client, logic_api) -> None:
    headers, graph_store, run_store = logic_api
    graph_store.graph = _empty_graph()
    response = client.post(
        "/v1/aip/logic/graphs/empty/dry-run",
        headers=headers,
        json=_body(graph_store.graph),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "LOGIC_GRAPH_EMPTY"
    assert run_store.start_count == 0


def test_success_is_read_back_from_history_and_production_write_is_false(
    client, logic_api
) -> None:
    headers, graph_store, run_store = logic_api
    response = client.post(
        "/v1/aip/logic/graphs/graph/dry-run",
        headers=headers,
        json=_body(graph_store.graph),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "succeeded"
    assert body["production_written"] is False
    assert run_store.start_count == 1
    detail = client.get(
        f"/v1/aip/logic/graphs/graph/runs/{body['run_id']}", headers=headers
    )
    assert detail.json() == body


def test_archived_and_cross_tenant_graphs_do_not_create_run(client, logic_api) -> None:
    headers, graph_store, run_store = logic_api
    graph_store.graph = _graph(status="archived")
    archived = client.post(
        "/v1/aip/logic/graphs/graph/dry-run",
        headers=headers,
        json=_body(graph_store.graph),
    )
    assert archived.status_code == 422
    other = client.post(
        "/v1/aip/logic/graphs/graph/dry-run",
        headers={**headers, "X-Org-Id": "org-other"},
        json=_body(graph_store.graph),
    )
    assert other.status_code == 404
    assert run_store.start_count == 0


def test_unexpected_executor_exception_becomes_persisted_failed_run(
    client, logic_api, monkeypatch
) -> None:
    headers, graph_store, run_store = logic_api

    def explode(*_args, **_kwargs):
        raise RuntimeError("sensitive unexpected payload")

    monkeypatch.setattr(
        "aos_api.aip_logic_dry_run_executor.LogicDryRunExecutor.execute", explode
    )
    response = client.post(
        "/v1/aip/logic/graphs/graph/dry-run",
        headers=headers,
        json=_body(graph_store.graph),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["error"]["code"] == "INTERNAL_EXECUTION_ERROR"
    assert response.json()["error"]["node_id"] == "input"
    assert len(response.json()["node_results"]) == 1
    assert response.json()["node_results"][0]["status"] == "failed"
    assert response.json()["node_results"][0]["error"]["node_id"] == "input"
    assert "sensitive" not in str(response.json())
    assert run_store.result is not None
    detail = client.get(
        f"/v1/aip/logic/graphs/graph/runs/{response.json()['run_id']}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json() == response.json()
    listed = client.get("/v1/aip/logic/graphs/graph/runs", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["node_counts"]["failed"] == 1


def test_invalid_get_query_uses_history_query_error_code(client, logic_api) -> None:
    headers, _graph_store, run_store = logic_api
    response = client.get("/v1/aip/logic/graphs/graph/runs?limit=101", headers=headers)
    assert response.status_code == 422
    assert response.json()["code"] == "LOGIC_RUN_QUERY_INVALID"
    assert run_store.start_count == 0


def test_finalize_failure_returns_503_without_false_success(
    client, logic_api, monkeypatch
) -> None:
    headers, graph_store, run_store = logic_api

    def fail_finalize(*_args, **_kwargs):
        raise LogicRunPersistenceError("sensitive database detail")

    monkeypatch.setattr(run_store, "finalize_run", fail_finalize)
    response = client.post(
        "/v1/aip/logic/graphs/graph/dry-run",
        headers=headers,
        json=_body(graph_store.graph),
    )
    assert response.status_code == 503
    assert response.json()["code"] == "LOGIC_RUN_PERSISTENCE_FAILED"
    assert "sensitive" not in str(response.json())
