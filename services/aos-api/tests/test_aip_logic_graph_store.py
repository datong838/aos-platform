"""Stage A1 · canonical AIP Logic graph models and PostgreSQL store tests."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import uuid

import pytest
from psycopg import sql
from pydantic import ValidationError

from aos_api.aip_logic_graph_models import (
    CreateLogicGraphRequest,
    LogicGraphEdge,
    LogicGraphNode,
    MAX_GRAPH_NODES,
    MAX_NODE_CONFIG_BYTES,
    ReplaceLogicGraphRequest,
    ValidateLogicGraphRequest,
    validate_logic_graph,
)
from aos_api.aip_logic_graph_store import (
    LogicGraphConflict,
    LogicGraphNotFound,
    LogicGraphStore,
)
from aos_api.db import connect


_MIGRATION = "228logicgraph_aip_logic_graphs.py"


def _install_schema(schema_name: str) -> None:
    with connect() as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name)))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS aip_logic_graph (
              org_id TEXT NOT NULL,
              project_id TEXT NOT NULL,
              graph_id TEXT NOT NULL,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              status TEXT NOT NULL DEFAULT 'draft',
              schema_version INTEGER NOT NULL DEFAULT 1,
              revision BIGINT NOT NULL DEFAULT 1,
              published_version BIGINT,
              graph_hash TEXT NOT NULL,
              payload JSONB NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              deleted_at TIMESTAMPTZ,
              PRIMARY KEY (org_id, project_id, graph_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS aip_logic_graph_revision (
              org_id TEXT NOT NULL,
              project_id TEXT NOT NULL,
              graph_id TEXT NOT NULL,
              revision BIGINT NOT NULL,
              graph_hash TEXT NOT NULL,
              snapshot JSONB NOT NULL,
              actor TEXT NOT NULL,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              PRIMARY KEY (org_id, project_id, graph_id, revision),
              FOREIGN KEY (org_id, project_id, graph_id)
                REFERENCES aip_logic_graph (org_id, project_id, graph_id)
            )
            """
        )
        conn.commit()


def _scoped_connect(schema_name: str):
    @contextmanager
    def factory():
        with connect() as conn:
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name))
            )
            yield conn

    return factory


@pytest.fixture()
def graph_scope() -> tuple[LogicGraphStore, str, str, str, object]:
    suffix = uuid.uuid4().hex
    schema_name = f"logic_graph_test_{suffix}"
    try:
        _install_schema(schema_name)
    except Exception as exc:  # pragma: no cover - local PG availability
        pytest.skip(f"PG unavailable: {exc}")
    org_id = f"logic-test-org-{suffix}"
    project_id = f"logic-test-project-{suffix}"
    actor = f"logic-test-user-{suffix}"
    connect_factory = _scoped_connect(schema_name)
    store = LogicGraphStore(connect_factory=connect_factory)
    yield store, org_id, project_id, actor, connect_factory
    with connect() as conn:
        conn.execute(
            sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name))
        )
        conn.commit()


def _linear_create(name: str = "可信 Logic") -> CreateLogicGraphRequest:
    return CreateLogicGraphRequest(
        name=name,
        nodes=[
            {"id": "input", "kind": "input", "label": "输入", "position_x": 10, "position_y": 20},
            {"id": "action", "kind": "apply_action", "label": "提议", "position_x": 210, "position_y": 20},
        ],
        edges=[
            {"id": "edge-1", "source_node_id": "input", "target_node_id": "action"},
        ],
        entry_node_ids=["input"],
    )


def _replacement(revision: int, *, label: str) -> ReplaceLogicGraphRequest:
    created = _linear_create()
    nodes = [node.model_copy(deep=True) for node in created.nodes]
    nodes[1].label = label
    return ReplaceLogicGraphRequest(
        expected_revision=revision,
        name=created.name,
        description=created.description,
        status=created.status,
        schema_version=created.schema_version,
        nodes=nodes,
        edges=created.edges,
        entry_node_ids=created.entry_node_ids,
    )


def test_models_forbid_extra_fields_and_unknown_kinds() -> None:
    with pytest.raises(ValidationError):
        LogicGraphNode.model_validate(
            {"id": "n1", "kind": "input", "label": "x", "tenant": "forged"}
        )
    with pytest.raises(ValidationError):
        LogicGraphNode.model_validate({"id": "n1", "kind": "task", "label": "x"})
    with pytest.raises(ValidationError):
        ReplaceLogicGraphRequest.model_validate(
            {"expected_revision": 1, "name": "x", "dry_run": False}
        )


def test_models_accept_exactly_the_ten_canonical_block_kinds() -> None:
    kinds = [
        "input",
        "create_variable",
        "get_property",
        "use_llm",
        "use_tool",
        "transform",
        "apply_action",
        "execute",
        "branch",
        "handoff",
    ]
    assert [
        LogicGraphNode(id=f"node-{index}", kind=kind, label=kind).kind
        for index, kind in enumerate(kinds)
    ] == kinds


def test_edge_defaults_are_canonical_out_to_in_and_ports_are_not_blank() -> None:
    edge = LogicGraphEdge(id="e", source_node_id="a", target_node_id="b")
    assert edge.source_port == "out"
    assert edge.target_port == "in"
    with pytest.raises(ValidationError):
        LogicGraphEdge(
            id="blank", source_node_id="a", source_port=" ", target_node_id="b"
        )


def test_node_count_and_config_size_limits_are_enforced() -> None:
    with pytest.raises(ValidationError):
        ValidateLogicGraphRequest(
            name="too-many",
            nodes=[
                {"id": f"n-{index}", "kind": "input", "label": str(index)}
                for index in range(MAX_GRAPH_NODES + 1)
            ],
        )
    request = ValidateLogicGraphRequest(
        name="large-config",
        nodes=[
            {
                "id": "n",
                "kind": "input",
                "label": "n",
                "config": {"blob": "x" * MAX_NODE_CONFIG_BYTES},
            }
        ],
        entry_node_ids=["n"],
    )
    result = validate_logic_graph(request)
    assert "NODE_CONFIG_TOO_LARGE" in {issue.code for issue in result.issues}


@pytest.mark.parametrize(
    ("body", "code"),
    [
        (
            {
                "name": "duplicate",
                "nodes": [
                    {"id": "n", "kind": "input", "label": "1"},
                    {"id": "n", "kind": "execute", "label": "2"},
                ],
            },
            "DUPLICATE_NODE_ID",
        ),
        (
            {
                "name": "dangling",
                "nodes": [{"id": "n", "kind": "input", "label": "1"}],
                "edges": [{"id": "e", "source_node_id": "n", "target_node_id": "missing"}],
            },
            "EDGE_ENDPOINT_NOT_FOUND",
        ),
        (
            {
                "name": "cycle",
                "nodes": [
                    {"id": "a", "kind": "input", "label": "a"},
                    {"id": "b", "kind": "execute", "label": "b"},
                ],
                "edges": [
                    {"id": "ab", "source_node_id": "a", "target_node_id": "b"},
                    {"id": "ba", "source_node_id": "b", "target_node_id": "a"},
                ],
                "entry_node_ids": ["a"],
            },
            "GRAPH_CYCLE",
        ),
        (
            {
                "name": "branch-default",
                "nodes": [
                    {
                        "id": "b",
                        "kind": "branch",
                        "label": "branch",
                        "config": {
                            "paths": [
                                {"id": "path-a", "default": True},
                                {"id": "path-b", "default": True},
                            ]
                        },
                    },
                    {"id": "x", "kind": "execute", "label": "x"},
                    {"id": "y", "kind": "execute", "label": "y"},
                ],
                "edges": [
                    {
                        "id": "bx", "source_node_id": "b", "source_port": "path-a",
                        "target_node_id": "x", "branch_path": "path-a",
                    },
                    {
                        "id": "by", "source_node_id": "b", "source_port": "path-b",
                        "target_node_id": "y", "branch_path": "path-b",
                    },
                ],
                "entry_node_ids": ["b"],
            },
            "BRANCH_MULTIPLE_DEFAULTS",
        ),
        (
            {
                "name": "handoff",
                "nodes": [{"id": "h", "kind": "handoff", "label": "handoff"}],
                "entry_node_ids": ["h"],
            },
            "HANDOFF_REQUIRES_UPSTREAMS",
        ),
    ],
)
def test_validate_graph_reports_structural_errors(body: dict, code: str) -> None:
    request = ValidateLogicGraphRequest.model_validate(body)
    result = validate_logic_graph(request)
    assert result.valid is False
    assert code in {issue.code for issue in result.issues}


def test_empty_graph_is_valid() -> None:
    result = validate_logic_graph(ValidateLogicGraphRequest(name="empty"))
    assert result.valid is True
    assert len(result.graph_hash) == 64


@pytest.mark.parametrize(
    ("node", "edge", "code"),
    [
        (
            {"id": "a", "kind": "input", "label": "a"},
            {
                "id": "e", "source_node_id": "a", "source_port": "custom",
                "target_node_id": "z",
            },
            "INVALID_SOURCE_PORT",
        ),
        (
            {"id": "a", "kind": "input", "label": "a"},
            {
                "id": "e", "source_node_id": "a", "target_node_id": "z",
                "target_port": "custom",
            },
            "INVALID_TARGET_PORT",
        ),
        (
            {"id": "a", "kind": "input", "label": "a"},
            {
                "id": "e", "source_node_id": "a", "target_node_id": "z",
                "branch_path": "not-allowed",
            },
            "NON_BRANCH_PATH_NOT_ALLOWED",
        ),
        (
            {
                "id": "a", "kind": "branch", "label": "a",
                "config": {"paths": [{"id": "yes"}, {"id": "no", "default": True}]},
            },
            {
                "id": "e", "source_node_id": "a", "source_port": "yes",
                "target_node_id": "z", "branch_path": "no",
            },
            "BRANCH_PATH_PORT_MISMATCH",
        ),
        (
            {"id": "a", "kind": "branch", "label": "a", "config": {"paths": []}},
            {"id": "e", "source_node_id": "a", "target_node_id": "z"},
            "BRANCH_PATHS_REQUIRED",
        ),
    ],
)
def test_validate_graph_enforces_port_and_branch_path_semantics(
    node: dict, edge: dict, code: str
) -> None:
    request = ValidateLogicGraphRequest(
        name="ports",
        nodes=[node, {"id": "z", "kind": "execute", "label": "z"}],
        edges=[edge],
        entry_node_ids=["a"],
    )
    result = validate_logic_graph(request)
    assert code in {issue.code for issue in result.issues}


def test_valid_branch_edges_match_declared_path_ids() -> None:
    request = ValidateLogicGraphRequest(
        name="valid-branch",
        nodes=[
            {
                "id": "branch", "kind": "branch", "label": "branch",
                "config": {"paths": [{"id": "yes"}, {"id": "no", "default": True}]},
            },
            {"id": "yes-node", "kind": "execute", "label": "yes"},
            {"id": "no-node", "kind": "execute", "label": "no"},
        ],
        edges=[
            {
                "id": "yes-edge", "source_node_id": "branch", "source_port": "yes",
                "target_node_id": "yes-node", "branch_path": "yes",
            },
            {
                "id": "no-edge", "source_node_id": "branch", "source_port": "no",
                "target_node_id": "no-node", "branch_path": "no",
            },
        ],
        entry_node_ids=["branch"],
    )
    assert validate_logic_graph(request).valid is True


def test_round_trip_revision_history_and_restart_recovery(graph_scope) -> None:
    store, org_id, project_id, actor, connect_factory = graph_scope
    created = store.create(org_id, project_id, actor, _linear_create())
    assert created.persisted is True
    assert created.revision == 1
    assert len(created.graph_hash) == 64

    updated = store.replace(
        org_id,
        project_id,
        created.id,
        actor,
        _replacement(1, label="已更新"),
    )
    assert updated.revision == 2
    assert updated.nodes[1].label == "已更新"
    assert updated.graph_hash != created.graph_hash

    restarted_store = LogicGraphStore(connect_factory=connect_factory)
    loaded = restarted_store.get(org_id, project_id, created.id)
    assert loaded == updated
    revisions = restarted_store.list_revisions(org_id, project_id, created.id)
    assert [item.revision for item in revisions] == [1, 2]
    assert revisions[0].graph_hash == created.graph_hash


def test_tenant_isolation_and_no_demo_fallback(graph_scope) -> None:
    store, org_id, project_id, actor, _connect_factory = graph_scope
    request = _linear_create()
    request.id = "same-id-across-tenants"
    created = store.create(org_id, project_id, actor, request)
    other = store.create(org_id + "-other", project_id, actor, request)
    assert other.id == created.id
    with pytest.raises(LogicGraphNotFound):
        store.get(org_id + "-hidden", project_id, created.id)
    with pytest.raises(LogicGraphNotFound):
        store.get(org_id, project_id, "missing")
    assert [item.id for item in store.list(org_id + "-other", project_id)] == [created.id]


def test_concurrent_same_revision_has_one_winner_and_one_conflict(graph_scope) -> None:
    store, org_id, project_id, actor, connect_factory = graph_scope
    created = store.create(org_id, project_id, actor, _linear_create())

    def write(label: str):
        local = LogicGraphStore(connect_factory=connect_factory)
        try:
            saved = local.replace(
                org_id,
                project_id,
                created.id,
                actor,
                _replacement(created.revision, label=label),
            )
            return "saved", saved
        except LogicGraphConflict as exc:
            return "conflict", exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ["writer-a", "writer-b"]))

    assert sorted(kind for kind, _ in results) == ["conflict", "saved"]
    loaded = store.get(org_id, project_id, created.id)
    assert loaded.revision == 2
    assert loaded.nodes[1].label in {"writer-a", "writer-b"}
    assert [item.revision for item in store.list_revisions(org_id, project_id, created.id)] == [1, 2]


def test_revision_insert_failure_rolls_back_current_snapshot(graph_scope, monkeypatch) -> None:
    store, org_id, project_id, actor, connect_factory = graph_scope
    created = store.create(org_id, project_id, actor, _linear_create())

    def fail_revision(*_args, **_kwargs):
        raise RuntimeError("forced history failure")

    monkeypatch.setattr(store, "_insert_revision", fail_revision)
    with pytest.raises(RuntimeError, match="forced history failure"):
        store.replace(
            org_id,
            project_id,
            created.id,
            actor,
            _replacement(1, label="must-not-commit"),
        )

    loaded = LogicGraphStore(connect_factory=connect_factory).get(
        org_id, project_id, created.id
    )
    assert loaded.revision == 1
    assert loaded.graph_hash == created.graph_hash


def test_migration_is_single_head_and_creates_scoped_current_and_revision_tables(monkeypatch) -> None:
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / _MIGRATION
    spec = importlib.util.spec_from_file_location("aip_logic_graph_revision", path)
    assert spec and spec.loader
    revision = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(revision)
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)
    revision.upgrade()
    sql = "\n".join(statements)
    assert revision.down_revision == "228ec03linkguard"
    assert "CREATE TABLE aip_logic_graph (" in sql
    assert "CREATE TABLE aip_logic_graph_revision (" in sql
    assert "PRIMARY KEY (org_id, project_id, graph_id)" in sql
    assert "PRIMARY KEY (org_id, project_id, graph_id, revision)" in sql
    assert "CREATE INDEX" in sql

    statements.clear()
    revision.downgrade()
    assert statements == [
        "DROP TABLE IF EXISTS aip_logic_graph_revision",
        "DROP TABLE IF EXISTS aip_logic_graph",
    ]
