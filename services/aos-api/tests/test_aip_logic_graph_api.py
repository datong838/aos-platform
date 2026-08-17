"""Stage A1 · canonical AIP Logic graph HTTP contract tests."""
from __future__ import annotations

from contextlib import contextmanager
import uuid

import pytest
from psycopg import sql

from aos_api.aip_logic_graph_store import LogicGraphIntegrityError, LogicGraphStore
from aos_api.auth import Principal, require_principal
from aos_api.db import connect
from aos_api.routers.aip_logic_graphs import get_logic_graph_store, router


def _payload(name: str = "API Logic") -> dict:
    return {
        "name": name,
        "nodes": [
            {"id": "input", "kind": "input", "label": "输入", "position_x": 0, "position_y": 0},
            {"id": "llm", "kind": "use_llm", "label": "分析", "position_x": 180, "position_y": 0},
        ],
        "edges": [{"id": "edge", "source_node_id": "input", "target_node_id": "llm"}],
        "entry_node_ids": ["input"],
    }


@pytest.fixture()
def api_store(client):
    client.app.include_router(router)
    suffix = uuid.uuid4().hex
    schema_name = f"logic_graph_api_test_{suffix}"
    org_id = f"logic-api-org-{suffix}"
    project_id = f"logic-api-project-{suffix}"
    with connect() as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name)))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS aip_logic_graph (
              org_id TEXT NOT NULL, project_id TEXT NOT NULL, graph_id TEXT NOT NULL,
              name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'draft',
              schema_version INTEGER NOT NULL DEFAULT 1, revision BIGINT NOT NULL DEFAULT 1,
              published_version BIGINT, graph_hash TEXT NOT NULL, payload JSONB NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              deleted_at TIMESTAMPTZ, PRIMARY KEY (org_id, project_id, graph_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS aip_logic_graph_revision (
              org_id TEXT NOT NULL, project_id TEXT NOT NULL, graph_id TEXT NOT NULL,
              revision BIGINT NOT NULL, graph_hash TEXT NOT NULL, snapshot JSONB NOT NULL,
              actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              PRIMARY KEY (org_id, project_id, graph_id, revision),
              FOREIGN KEY (org_id, project_id, graph_id)
                REFERENCES aip_logic_graph (org_id, project_id, graph_id)
            )
            """
        )
        conn.commit()

    @contextmanager
    def scoped_connect():
        with connect() as conn:
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name))
            )
            yield conn

    store = LogicGraphStore(connect_factory=scoped_connect)
    client.app.dependency_overrides[get_logic_graph_store] = lambda: store
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="logic-api-test",
        org_id=org_id,
        project_id=project_id,
        roles=["developer", "admin"],
        markings=["public", "restricted"],
        token_kind="test",
    )
    headers = {
        "Authorization": "Bearer dev",
        "X-Org-Id": org_id,
        "X-Project-Id": project_id,
        "X-Trace-Id": "logic-api-test",
    }
    yield headers
    client.app.dependency_overrides.pop(get_logic_graph_store, None)
    client.app.dependency_overrides.pop(require_principal, None)
    with connect() as conn:
        conn.execute(
            sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name))
        )
        conn.commit()


def test_create_list_get_replace_round_trip(client, api_store) -> None:
    created = client.post("/v1/aip/logic/graphs", headers=api_store, json=_payload())
    assert created.status_code == 201
    first = created.json()
    assert first["revision"] == 1
    assert first["persisted"] is True

    listed = client.get("/v1/aip/logic/graphs", headers=api_store)
    assert listed.status_code == 200
    assert listed.json()["count"] == 1
    assert listed.json()["items"][0]["id"] == first["id"]

    loaded = client.get(f"/v1/aip/logic/graphs/{first['id']}", headers=api_store)
    assert loaded.status_code == 200
    assert loaded.json() == first

    replacement = {**_payload("API Logic updated"), "expected_revision": 1}
    saved = client.put(
        f"/v1/aip/logic/graphs/{first['id']}", headers=api_store, json=replacement
    )
    assert saved.status_code == 200
    assert saved.json()["revision"] == 2
    assert saved.json()["name"] == "API Logic updated"


def test_stale_replace_is_409_and_does_not_mutate(client, api_store) -> None:
    first = client.post("/v1/aip/logic/graphs", headers=api_store, json=_payload()).json()
    graph_id = first["id"]
    winner = client.put(
        f"/v1/aip/logic/graphs/{graph_id}",
        headers=api_store,
        json={**_payload("winner"), "expected_revision": 1},
    )
    assert winner.status_code == 200
    stale = client.put(
        f"/v1/aip/logic/graphs/{graph_id}",
        headers=api_store,
        json={**_payload("stale"), "expected_revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "LOGIC_GRAPH_REVISION_CONFLICT"
    current = client.get(f"/v1/aip/logic/graphs/{graph_id}", headers=api_store)
    assert current.json()["name"] == "winner"
    assert current.json()["revision"] == 2


def test_validate_returns_structured_issues_without_persisting(client, api_store) -> None:
    invalid = _payload()
    invalid["edges"] = [{"id": "bad", "source_node_id": "input", "target_node_id": "missing"}]
    response = client.post("/v1/aip/logic/graphs/validate", headers=api_store, json=invalid)
    assert response.status_code == 200
    assert response.json()["valid"] is False
    assert response.json()["issues"][0]["code"] == "EDGE_ENDPOINT_NOT_FOUND"
    assert client.get("/v1/aip/logic/graphs", headers=api_store).json()["count"] == 0


def test_unknown_resource_is_404_without_demo(client, api_store) -> None:
    response = client.get("/v1/aip/logic/graphs/missing", headers=api_store)
    assert response.status_code == 404
    assert response.json()["code"] == "LOGIC_GRAPH_NOT_FOUND"
    assert "demo" not in response.json()


def test_tenant_headers_bind_scope_and_body_tenant_is_rejected(client, api_store) -> None:
    forged = client.post(
        "/v1/aip/logic/graphs",
        headers=api_store,
        json={**_payload(), "org_id": "forged", "project_id": "forged"},
    )
    assert forged.status_code == 400
    assert forged.json()["code"] == "VALIDATION"

    first = client.post("/v1/aip/logic/graphs", headers=api_store, json=_payload()).json()
    other_headers = {
        **api_store,
        "X-Org-Id": api_store["X-Org-Id"] + "-other",
        "X-Project-Id": api_store["X-Project-Id"] + "-other",
    }
    client.app.dependency_overrides[require_principal] = lambda: Principal(
        subject="logic-api-other-test",
        org_id=other_headers["X-Org-Id"],
        project_id=other_headers["X-Project-Id"],
        roles=["developer", "admin"],
        markings=["public", "restricted"],
        token_kind="test",
    )
    hidden = client.get(f"/v1/aip/logic/graphs/{first['id']}", headers=other_headers)
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "LOGIC_GRAPH_NOT_FOUND"


def test_invalid_graph_replace_is_422_and_keeps_last_snapshot(client, api_store) -> None:
    first = client.post("/v1/aip/logic/graphs", headers=api_store, json=_payload()).json()
    invalid = {**_payload("invalid"), "expected_revision": 1}
    invalid["edges"] = [{"id": "loop", "source_node_id": "input", "target_node_id": "input"}]
    rejected = client.put(
        f"/v1/aip/logic/graphs/{first['id']}", headers=api_store, json=invalid
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "LOGIC_GRAPH_INVALID"
    loaded = client.get(f"/v1/aip/logic/graphs/{first['id']}", headers=api_store)
    assert loaded.json()["revision"] == 1
    assert loaded.json()["graph_hash"] == first["graph_hash"]


def test_invalid_port_replace_is_422_and_keeps_last_snapshot(client, api_store) -> None:
    first = client.post("/v1/aip/logic/graphs", headers=api_store, json=_payload()).json()
    invalid = {**_payload("invalid-port"), "expected_revision": 1}
    invalid["edges"][0]["source_port"] = "default"
    rejected = client.put(
        f"/v1/aip/logic/graphs/{first['id']}", headers=api_store, json=invalid
    )
    assert rejected.status_code == 422
    assert rejected.json()["code"] == "LOGIC_GRAPH_INVALID"
    loaded = client.get(f"/v1/aip/logic/graphs/{first['id']}", headers=api_store)
    assert loaded.json()["revision"] == 1


def test_create_and_replace_map_checksum_failure_without_leaking_snapshot(
    client, api_store
) -> None:
    class BrokenStore:
        def create(self, *_args, **_kwargs):
            raise LogicGraphIntegrityError("sensitive create mismatch")

        def replace(self, *_args, **_kwargs):
            raise LogicGraphIntegrityError("sensitive replace mismatch")

    client.app.dependency_overrides[get_logic_graph_store] = lambda: BrokenStore()
    created = client.post("/v1/aip/logic/graphs", headers=api_store, json=_payload())
    replaced = client.put(
        "/v1/aip/logic/graphs/graph-id",
        headers=api_store,
        json={**_payload(), "expected_revision": 1},
    )
    assert created.status_code == 500
    assert replaced.status_code == 500
    assert created.json()["code"] == "LOGIC_GRAPH_CHECKSUM_MISMATCH"
    assert replaced.json()["code"] == "LOGIC_GRAPH_CHECKSUM_MISMATCH"
    assert "sensitive" not in str(created.json()) + str(replaced.json())
