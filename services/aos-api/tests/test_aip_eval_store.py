"""Persistence and integrity tests for tenant-scoped Logic Eval evidence."""

from __future__ import annotations

import importlib.util
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from psycopg import sql

from aos_api.aip_eval_models import EvalReportEvidence, LogicGraphEvalTarget
from aos_api.aip_eval_store import (
    EvalConflict,
    EvalEvidenceStore,
    EvalIntegrityError,
    EvalNotFound,
    EvalTargetConflict,
    EvalTargetNotFound,
    LogicEvalEvidenceReader,
)
from aos_api.db import connect
from aos_api.evals_engine import CaseResult, EvalSuite, TestCase

TARGET_HASH = "a" * 64


@pytest.fixture()
def eval_scope(monkeypatch):
    suffix = uuid.uuid4().hex
    schema = f"logic_eval_test_{suffix}"
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            conn.execute(
                """CREATE TABLE aip_logic_graph (
                org_id TEXT NOT NULL, project_id TEXT NOT NULL, graph_id TEXT NOT NULL,
                PRIMARY KEY (org_id, project_id, graph_id))"""
            )
            conn.execute(
                """CREATE TABLE aip_logic_graph_revision (
                org_id TEXT NOT NULL, project_id TEXT NOT NULL, graph_id TEXT NOT NULL,
                revision BIGINT NOT NULL, graph_hash TEXT NOT NULL, snapshot JSONB NOT NULL,
                actor TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY (org_id, project_id, graph_id, revision),
                FOREIGN KEY (org_id, project_id, graph_id)
                  REFERENCES aip_logic_graph (org_id, project_id, graph_id))"""
            )
            path = (
                Path(__file__).resolve().parents[1]
                / "alembic/versions/228logiceval_aip_eval_evidence.py"
            )
            spec = importlib.util.spec_from_file_location("logic_eval_migration", path)
            migration = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(migration)
            statements: list[str] = []
            monkeypatch.setattr(migration.op, "execute", statements.append)
            migration.upgrade()
            for statement in statements:
                conn.execute(statement)
            for org, project in (("org-a", "project-a"), ("org-b", "project-b")):
                conn.execute(
                    "INSERT INTO aip_logic_graph VALUES (%s,%s,'logic-1')",
                    (org, project),
                )
                conn.execute(
                    """INSERT INTO aip_logic_graph_revision
                    (org_id,project_id,graph_id,revision,graph_hash,snapshot,actor)
                    VALUES (%s,%s,'logic-1',1,%s,'{}'::jsonb,'actor')""",
                    (org, project, TARGET_HASH),
                )
            conn.commit()
    except Exception as exc:  # noqa: BLE001 - PostgreSQL optional in developer CI
        pytest.skip(f"PG unavailable: {exc}")

    @contextmanager
    def scoped_connect():
        with connect() as conn:
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            yield conn

    yield EvalEvidenceStore(connect_factory=scoped_connect), scoped_connect
    with connect() as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.commit()


def _suite() -> EvalSuite:
    return EvalSuite(
        id="suite-1",
        name="logic suite",
        gate_threshold=1.0,
        cases=[TestCase(id="case-1", inputs={"x": 1}, expected=2, judge="exact")],
    )


def _report(*, target_hash: str = TARGET_HASH, passed: bool = True) -> EvalReportEvidence:
    return EvalReportEvidence(
        report_id="report-1",
        suite_id="suite-1",
        target_type="logic_graph",
        target_id="logic-1",
        target_revision=1,
        target_hash=target_hash,
        results=[
            CaseResult(
                case_id="case-1",
                passed=passed,
                actual=2 if passed else 1,
                expected=2,
                judge="exact",
            )
        ],
        pass_rate=1.0 if passed else 0.0,
        passed=1 if passed else 0,
        failed=0 if passed else 1,
        total=1,
        gate_passed=passed,
        run_at="2026-08-02T00:00:00+00:00",
    )


def test_suite_and_report_survive_store_recreation_and_are_tenant_scoped(
    eval_scope,
) -> None:
    store, scoped_connect = eval_scope
    store.create_suite("org-a", "project-a", "alice", _suite())
    saved = store.save_report("org-a", "project-a", "alice", _report())
    assert saved.report_id == "report-1"
    restarted = EvalEvidenceStore(connect_factory=scoped_connect)
    assert restarted.get_suite("org-a", "project-a", "suite-1") == _suite()
    assert restarted.get_report("org-a", "project-a", "report-1") == saved
    assert restarted.latest_report("org-a", "project-a", "suite-1") == saved
    assert restarted.history("org-a", "project-a", "suite-1") == [saved]
    with pytest.raises(EvalNotFound):
        restarted.get_suite("org-b", "project-b", "suite-1")
    with pytest.raises(EvalNotFound):
        restarted.get_report("org-b", "project-b", "report-1")


def test_target_revision_and_hash_are_verified_before_report_insert(eval_scope) -> None:
    store, _ = eval_scope
    store.create_suite("org-a", "project-a", "alice", _suite())
    with pytest.raises(EvalTargetConflict):
        store.save_report(
            "org-a", "project-a", "alice", _report(target_hash="b" * 64)
        )
    missing = LogicGraphEvalTarget(
        target_type="logic_graph",
        target_id="missing",
        target_revision=1,
        target_hash=TARGET_HASH,
    )
    with pytest.raises(EvalTargetNotFound):
        store.require_logic_target("org-a", "project-a", missing)
    assert store.history("org-a", "project-a", "suite-1") == []


def test_report_is_immutable_and_gate_must_match_persisted_suite(eval_scope) -> None:
    store, _ = eval_scope
    store.create_suite("org-a", "project-a", "alice", _suite())
    store.save_report("org-a", "project-a", "alice", _report())
    with pytest.raises(EvalConflict):
        store.save_report("org-a", "project-a", "alice", _report())
    contradictory = _report(passed=False).model_copy(
        update={"report_id": "report-2", "gate_passed": True}
    )
    with pytest.raises(EvalIntegrityError):
        store.save_report("org-a", "project-a", "alice", contradictory)
    assert len(store.history("org-a", "project-a", "suite-1")) == 1


def test_publication_reader_uses_caller_transaction_and_fails_closed(eval_scope) -> None:
    store, scoped_connect = eval_scope
    store.create_suite("org-a", "project-a", "alice", _suite())
    store.save_report("org-a", "project-a", "alice", _report())
    with scoped_connect() as conn:
        evidence = LogicEvalEvidenceReader.get_evidence(
            conn,
            org_id="org-a",
            project_id="project-a",
            suite_id="suite-1",
            report_id="report-1",
        )
        assert evidence is not None
        assert evidence.target_type == "logic_graph"
        assert evidence.target_id == "logic-1"
        assert evidence.target_revision == 1
        assert evidence.target_hash == TARGET_HASH
        assert evidence.threshold == 1.0
        assert LogicEvalEvidenceReader.get_evidence(
            conn,
            org_id="org-b",
            project_id="project-b",
            suite_id="suite-1",
            report_id="report-1",
        ) is None
        conn.execute(
            """UPDATE aip_logic_graph_revision SET graph_hash=%s
            WHERE org_id='org-a' AND project_id='project-a'
              AND graph_id='logic-1' AND revision=1""",
            ("c" * 64,),
        )
        assert LogicEvalEvidenceReader.get_evidence(
            conn,
            org_id="org-a",
            project_id="project-a",
            suite_id="suite-1",
            report_id="report-1",
        ) is None


def test_migration_chain_and_downgrade_order(monkeypatch) -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/228logiceval_aip_eval_evidence.py"
    )
    spec = importlib.util.spec_from_file_location("logic_eval_migration_meta", path)
    migration = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(migration)
    statements: list[str] = []
    monkeypatch.setattr(migration.op, "execute", statements.append)
    migration.upgrade()
    assert migration.revision == "228logiceval"
    assert migration.down_revision == "228logicrun"
    assert any("CREATE TABLE aip_eval_suite" in statement for statement in statements)
    assert any("CREATE TABLE aip_eval_report" in statement for statement in statements)
    assert any("REFERENCES aip_logic_graph_revision" in statement for statement in statements)
    statements.clear()
    migration.downgrade()
    assert statements == [
        "DROP TABLE IF EXISTS aip_eval_report",
        "DROP TABLE IF EXISTS aip_eval_suite",
    ]
