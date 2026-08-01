"""PostgreSQL evidence tests for tenant-scoped immutable Logic run history."""

from __future__ import annotations

import importlib.util
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from aos_api.aip_logic_dry_run_executor import LogicDryRunExecutor
from aos_api.aip_logic_dry_run_models import LogicDryRunRequest
from aos_api.aip_logic_graph_models import (
    CreateLogicGraphRequest,
    ReplaceLogicGraphRequest,
)
from aos_api.aip_logic_graph_store import LogicGraphStore
from aos_api.aip_logic_run_store import (
    LogicRunIdempotencyConflict,
    LogicRunNotFound,
    LogicRunPersistenceError,
    LogicRunStore,
)
from aos_api.db import connect
from psycopg import sql


@pytest.fixture()
def run_scope(monkeypatch):
    suffix = uuid.uuid4().hex
    schema = f"logic_run_test_{suffix}"
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            conn.execute(
                """CREATE TABLE aip_logic_graph (org_id TEXT NOT NULL,project_id TEXT NOT NULL,graph_id TEXT NOT NULL,name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'draft',schema_version INTEGER NOT NULL DEFAULT 1,revision BIGINT NOT NULL DEFAULT 1,published_version BIGINT,graph_hash TEXT NOT NULL,payload JSONB NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),deleted_at TIMESTAMPTZ,PRIMARY KEY(org_id,project_id,graph_id))"""
            )
            conn.execute(
                """CREATE TABLE aip_logic_graph_revision (org_id TEXT NOT NULL,project_id TEXT NOT NULL,graph_id TEXT NOT NULL,revision BIGINT NOT NULL,graph_hash TEXT NOT NULL,snapshot JSONB NOT NULL,actor TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),PRIMARY KEY(org_id,project_id,graph_id,revision),FOREIGN KEY(org_id,project_id,graph_id) REFERENCES aip_logic_graph(org_id,project_id,graph_id))"""
            )
            path = (
                Path(__file__).resolve().parents[1]
                / "alembic/versions/228logicrun_aip_logic_runs.py"
            )
            spec = importlib.util.spec_from_file_location("logic_run_migration", path)
            revision = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(revision)
            statements: list[str] = []
            monkeypatch.setattr(revision.op, "execute", statements.append)
            revision.upgrade()
            for statement in statements:
                conn.execute(statement)
            conn.commit()
    except Exception as exc:  # noqa: BLE001 - PostgreSQL is optional in developer CI
        pytest.skip(f"PG unavailable: {exc}")

    @contextmanager
    def scoped_connect():
        with connect() as conn:
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            yield conn

    yield (
        LogicGraphStore(connect_factory=scoped_connect),
        LogicRunStore(connect_factory=scoped_connect),
        scoped_connect,
    )
    with connect() as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.commit()


def _create_graph(store: LogicGraphStore, org: str, project: str):
    return store.create(
        org,
        project,
        "actor",
        CreateLogicGraphRequest(
            name="history",
            nodes=[{"id": "input", "kind": "input", "label": "input"}],
            entry_node_ids=["input"],
        ),
    )


def _create_recovery_graph(store: LogicGraphStore, org: str, project: str):
    return store.create(
        org,
        project,
        "actor",
        CreateLogicGraphRequest(
            name="recovery",
            nodes=[
                {"id": "first", "kind": "input", "label": "first"},
                {
                    "id": "next",
                    "kind": "transform",
                    "label": "next",
                    "config": {"expression": "1"},
                },
                {"id": "orphan", "kind": "input", "label": "orphan"},
            ],
            edges=[
                {
                    "id": "first-next",
                    "source_node_id": "first",
                    "target_node_id": "next",
                }
            ],
            entry_node_ids=["first"],
        ),
    )


def test_start_finalize_get_list_are_durable_and_tenant_scoped(run_scope) -> None:
    graph_store, store, _ = run_scope
    org, project = "org-a", "project-a"
    graph = _create_graph(graph_store, org, project)
    request = LogicDryRunRequest(
        expected_revision=1,
        dry_run=True,
        expected_graph_hash=graph.graph_hash,
        inputs={"password": "never-store", "safe": "ok"},
    )
    start = store.start_run(org, project, "actor", graph, request, "run-1")
    result = LogicDryRunExecutor().execute(
        graph, request.inputs, run_id=start.run_id, started_at=start.started_at
    )
    store.finalize_run(org, project, result)
    loaded = store.get_run(org, project, graph.id, "run-1")
    assert loaded == result
    listed = store.list_runs(org, project, graph.id)
    assert listed.count == 1
    assert listed.items[0].node_counts.executed == 1
    with pytest.raises(LogicRunNotFound):
        store.get_run("other", project, graph.id, "run-1")


def test_sensitive_inputs_are_redacted_and_idempotency_replays_terminal_run(
    run_scope,
) -> None:
    graph_store, store, scoped_connect = run_scope
    graph = _create_graph(graph_store, "org", "project")
    request = LogicDryRunRequest(
        expected_revision=1,
        dry_run=True,
        expected_graph_hash=graph.graph_hash,
        inputs={"nested": {"authorization": "Bearer abc"}},
        idempotency_key="same",
    )
    store.start_run("org", "project", "actor", graph, request, "run-1")
    result = LogicDryRunExecutor().execute(graph, request.inputs, run_id="run-1")
    store.finalize_run("org", "project", result)
    replay = store.start_run("org", "project", "actor", graph, request, "run-2")
    assert replay.replay is not None and replay.run_id == "run-1"
    with scoped_connect() as conn:
        row = conn.execute(
            "SELECT inputs_snapshot FROM aip_logic_graph_runs WHERE run_id='run-1'"
        ).fetchone()
    assert row["inputs_snapshot"]["nested"]["authorization"] == "[REDACTED]"
    changed = request.model_copy(update={"inputs": {"different": True}})
    with pytest.raises(LogicRunIdempotencyConflict):
        store.start_run("org", "project", "actor", graph, changed, "run-3")


def test_stale_running_run_is_recovered_as_failed_interrupted(run_scope) -> None:
    graph_store, store, _ = run_scope
    graph = _create_recovery_graph(graph_store, "org", "project")
    request = LogicDryRunRequest(
        expected_revision=1, dry_run=True, expected_graph_hash=graph.graph_hash
    )
    store.start_run("org", "project", "actor", graph, request, "run-stale")
    assert (
        store.recover_interrupted(
            "org", "project", stale_before=datetime.now(UTC).replace(year=2020)
        )
        == 0
    )
    assert (
        store.recover_interrupted("org", "project", stale_before=datetime.now(UTC)) == 1
    )
    loaded = store.get_run("org", "project", graph.id, "run-stale")
    assert loaded.status == "failed"
    assert loaded.error.code == "INTERRUPTED"
    assert loaded.error.node_id == "first"
    assert [node.node_id for node in loaded.node_results] == [
        "first",
        "next",
        "orphan",
    ]
    assert [node.status for node in loaded.node_results] == [
        "failed",
        "canceled",
        "skipped",
    ]
    assert loaded.node_results[0].error.node_id == "first"
    summary = store.list_runs("org", "project", graph.id).items[0]
    assert summary.status == "failed"
    assert summary.error_code == "INTERRUPTED"
    assert summary.node_counts.failed == 1
    assert summary.node_counts.canceled == 1
    assert summary.node_counts.skipped == 1
    assert (
        store.recover_interrupted("org", "project", stale_before=datetime.now(UTC)) == 0
    )


def test_empty_stale_run_recovery_fails_closed_without_deleting_audit_row(
    run_scope,
) -> None:
    graph_store, store, scoped_connect = run_scope
    graph = graph_store.create(
        "org",
        "project",
        "actor",
        CreateLogicGraphRequest(name="empty"),
    )
    request = LogicDryRunRequest(
        expected_revision=1, dry_run=True, expected_graph_hash=graph.graph_hash
    )
    store.start_run("org", "project", "actor", graph, request, "empty-stale")
    with pytest.raises(LogicRunPersistenceError, match="recover interrupted"):
        store.recover_interrupted("org", "project", stale_before=datetime.now(UTC))
    with scoped_connect() as conn:
        row = conn.execute(
            """SELECT status FROM aip_logic_graph_runs
               WHERE org_id='org' AND project_id='project'
                 AND graph_id=%s AND run_id='empty-stale'""",
            (graph.id,),
        ).fetchone()
    assert row is not None
    assert row["status"] == "running"


def test_multiple_null_idempotency_keys_are_allowed_by_real_postgresql(
    run_scope,
) -> None:
    graph_store, store, _ = run_scope
    graph = _create_graph(graph_store, "org", "project")
    request = LogicDryRunRequest(
        expected_revision=1, dry_run=True, expected_graph_hash=graph.graph_hash
    )
    for index in range(2):
        run_id = f"null-key-{index}"
        started = store.start_run("org", "project", "actor", graph, request, run_id)
        result = LogicDryRunExecutor().execute(
            graph, {}, run_id=run_id, started_at=started.started_at
        )
        store.finalize_run("org", "project", result)
    assert store.list_runs("org", "project", graph.id).count == 2


def test_history_paginates_and_keeps_evaluated_revision_after_graph_update(
    run_scope,
) -> None:
    graph_store, store, _ = run_scope
    graph = _create_graph(graph_store, "org", "project")
    request = LogicDryRunRequest(
        expected_revision=1,
        dry_run=True,
        expected_graph_hash=graph.graph_hash,
    )
    for index in range(3):
        run_id = f"page-{index}"
        started = store.start_run("org", "project", "actor", graph, request, run_id)
        result = LogicDryRunExecutor().execute(
            graph, {}, run_id=run_id, started_at=started.started_at
        )
        store.finalize_run("org", "project", result)
    first = store.list_runs("org", "project", graph.id, limit=2)
    assert first.count == 2 and first.next_cursor is not None
    second = store.list_runs(
        "org", "project", graph.id, limit=2, before=first.next_cursor
    )
    assert second.count == 1
    assert {item.run_id for item in [*first.items, *second.items]} == {
        "page-0",
        "page-1",
        "page-2",
    }
    updated = graph_store.replace(
        "org",
        "project",
        graph.id,
        "actor",
        ReplaceLogicGraphRequest(
            expected_revision=1,
            name="history updated",
            nodes=graph.nodes,
            edges=graph.edges,
            entry_node_ids=graph.entry_node_ids,
        ),
    )
    assert updated.revision == 2
    historical = store.get_run("org", "project", graph.id, "page-0")
    assert historical.evaluated_revision == 1
    assert historical.graph_hash == graph.graph_hash


def test_finalize_is_terminal_once_and_never_overwrites_history(run_scope) -> None:
    graph_store, store, _ = run_scope
    graph = _create_graph(graph_store, "org", "project")
    request = LogicDryRunRequest(
        expected_revision=1, dry_run=True, expected_graph_hash=graph.graph_hash
    )
    started = store.start_run("org", "project", "actor", graph, request, "once")
    result = LogicDryRunExecutor().execute(
        graph, {}, run_id="once", started_at=started.started_at
    )
    store.finalize_run("org", "project", result)
    with pytest.raises(LogicRunPersistenceError):
        store.finalize_run("org", "project", result)
    assert store.get_run("org", "project", graph.id, "once") == result


def test_migration_shape_and_chain(monkeypatch) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/228logicrun_aip_logic_runs.py"
    )
    spec = importlib.util.spec_from_file_location("logic_run_shape", path)
    revision = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(revision)
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)
    revision.upgrade()
    all_sql = "\n".join(statements)
    assert revision.down_revision == "228logicgraph"
    assert "CREATE TABLE aip_logic_graph_runs" in all_sql
    assert "CREATE TABLE aip_logic_graph_run_nodes" in all_sql
    assert "production_written = FALSE" in all_sql
    assert "REFERENCES aip_logic_graph_revision" in all_sql


def test_migration_upgrade_and_downgrade_execute_in_temporary_schema(
    monkeypatch,
) -> None:
    schema = f"logic_run_migration_{uuid.uuid4().hex}"
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/228logicrun_aip_logic_runs.py"
    )
    spec = importlib.util.spec_from_file_location("logic_run_round_trip", path)
    revision = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(revision)
    statements: list[str] = []
    monkeypatch.setattr(revision.op, "execute", statements.append)
    revision.upgrade()
    upgrade_sql = list(statements)
    statements.clear()
    revision.downgrade()
    downgrade_sql = list(statements)
    with connect() as conn:
        conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        conn.execute(
            """CREATE TABLE aip_logic_graph (org_id TEXT NOT NULL,project_id TEXT NOT NULL,graph_id TEXT NOT NULL,PRIMARY KEY(org_id,project_id,graph_id))"""
        )
        conn.execute(
            """CREATE TABLE aip_logic_graph_revision (org_id TEXT NOT NULL,project_id TEXT NOT NULL,graph_id TEXT NOT NULL,revision BIGINT NOT NULL,PRIMARY KEY(org_id,project_id,graph_id,revision),FOREIGN KEY(org_id,project_id,graph_id) REFERENCES aip_logic_graph(org_id,project_id,graph_id))"""
        )
        for statement in upgrade_sql:
            conn.execute(statement)
        assert (
            conn.execute(
                "SELECT to_regclass('aip_logic_graph_runs') AS name"
            ).fetchone()["name"]
            == "aip_logic_graph_runs"
        )
        for statement in downgrade_sql:
            conn.execute(statement)
        assert (
            conn.execute(
                "SELECT to_regclass('aip_logic_graph_runs') AS name"
            ).fetchone()["name"]
            is None
        )
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.commit()
