"""Publication governance contracts and PostgreSQL evidence tests."""
from __future__ import annotations

import importlib.util
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from psycopg import errors, sql
from pydantic import ValidationError

from aos_api.aip_logic_dry_run_executor import LogicDryRunExecutor
from aos_api.aip_logic_dry_run_models import LogicDryRunRequest
from aos_api.aip_logic_graph_models import (
    CreateLogicGraphRequest,
    ReplaceLogicGraphRequest,
)
from aos_api.aip_logic_graph_store import LogicGraphStore
from aos_api.aip_logic_publication_models import (
    LogicEvalEvidence,
    PublishLogicGraphRequest,
)
from aos_api.aip_logic_publication_store import (
    LogicPublicationDryRunRequired,
    LogicPublicationEvalEvidenceExpired,
    LogicPublicationEvalGateRejected,
    LogicPublicationEvalTargetMismatch,
    LogicPublicationIdempotencyConflict,
    LogicPublicationIntegrityError,
    LogicPublicationNotFound,
    LogicPublicationPersistenceError,
    LogicPublicationStore,
    LogicPublicationVersionConflict,
)
from aos_api.aip_logic_run_store import LogicRunStore
from aos_api.db import connect

API_ROOT = Path(__file__).resolve().parents[1]


def _migration_statements(filename: str) -> list[str]:
    path = API_ROOT / "alembic" / "versions" / filename
    spec = importlib.util.spec_from_file_location(f"test_{path.stem}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements: list[str] = []
    with patch.object(module.op, "execute", statements.append):
        module.upgrade()
    return statements


@pytest.fixture()
def publication_scope():
    suffix = uuid.uuid4().hex
    schema = f"logic_publish_test_{suffix}"
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(
                sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
            )
            conn.execute(
                """CREATE TABLE aip_logic_graph (
                org_id TEXT NOT NULL,project_id TEXT NOT NULL,graph_id TEXT NOT NULL,
                name TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'draft',
                schema_version INTEGER NOT NULL DEFAULT 1,revision BIGINT NOT NULL DEFAULT 1,
                published_version BIGINT,graph_hash TEXT NOT NULL,payload JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                deleted_at TIMESTAMPTZ,PRIMARY KEY(org_id,project_id,graph_id))"""
            )
            conn.execute(
                """CREATE TABLE aip_logic_graph_revision (
                org_id TEXT NOT NULL,project_id TEXT NOT NULL,graph_id TEXT NOT NULL,
                revision BIGINT NOT NULL,graph_hash TEXT NOT NULL,snapshot JSONB NOT NULL,
                actor TEXT NOT NULL,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                PRIMARY KEY(org_id,project_id,graph_id,revision),
                FOREIGN KEY(org_id,project_id,graph_id)
                  REFERENCES aip_logic_graph(org_id,project_id,graph_id))"""
            )
            for filename in (
                "228logicrun_aip_logic_runs.py",
                "228logiceval_aip_eval_evidence.py",
                "228logicpublish_aip_logic_publications.py",
            ):
                for statement in _migration_statements(filename):
                    conn.execute(statement)
            conn.commit()
    except Exception as exc:  # noqa: BLE001 - PostgreSQL is optional locally
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
        LogicPublicationStore(connect_factory=scoped_connect),
        scoped_connect,
    )
    with connect() as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.commit()


def _create_graph(store: LogicGraphStore, org: str, project: str):
    return store.create(
        org,
        project,
        "author",
        CreateLogicGraphRequest(
            name="publishable",
            nodes=[{"id": "input", "kind": "input", "label": "Input"}],
            entry_node_ids=["input"],
        ),
    )


def _succeed_dry_run(
    run_store: LogicRunStore, graph, org: str, project: str, *, run_id: str = "run-1"
):
    request = LogicDryRunRequest(
        expected_revision=graph.revision,
        expected_graph_hash=graph.graph_hash,
        dry_run=True,
        inputs={"sample": True},
    )
    started = run_store.start_run(org, project, "runner", graph, request, run_id)
    result = LogicDryRunExecutor().execute(
        graph, request.inputs, run_id=run_id, started_at=started.started_at
    )
    run_store.finalize_run(org, project, result)
    return result


def _request(graph, *, key: str = "publish-once", report_id: str = "report-1"):
    return PublishLogicGraphRequest(
        expected_revision=graph.revision,
        expected_graph_hash=graph.graph_hash,
        eval_suite_id="suite-1",
        eval_report_id=report_id,
        idempotency_key=key,
    )


class FakeEvidenceReader:
    def __init__(self, evidence: LogicEvalEvidence | None) -> None:
        self.evidence = evidence
        self.connections: list[object] = []

    def get_evidence(self, conn, **kwargs):
        self.connections.append(conn)
        if self.evidence is not None:
            conn.execute(
                """INSERT INTO aip_eval_suite
                   (org_id,project_id,suite_id,name,cases,gate_threshold,actor)
                   VALUES (%s,%s,%s,'publication fixture','[]'::jsonb,%s,'test')
                   ON CONFLICT DO NOTHING""",
                (
                    kwargs["org_id"],
                    kwargs["project_id"],
                    self.evidence.suite_id,
                    self.evidence.threshold,
                ),
            )
            conn.execute(
                """INSERT INTO aip_eval_report
                   (org_id,project_id,report_id,suite_id,target_type,target_id,
                    target_revision,target_hash,results,pass_rate,passed,failed,
                    total,gate_passed,run_at,actor)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'[]'::jsonb,%s,%s,%s,%s,%s,%s,'test')
                   ON CONFLICT DO NOTHING""",
                (
                    kwargs["org_id"],
                    kwargs["project_id"],
                    self.evidence.report_id,
                    self.evidence.suite_id,
                    self.evidence.target_type,
                    self.evidence.target_id,
                    self.evidence.target_revision,
                    self.evidence.target_hash,
                    self.evidence.pass_rate,
                    self.evidence.passed,
                    self.evidence.failed,
                    self.evidence.total,
                    self.evidence.gate_passed,
                    self.evidence.run_at,
                ),
            )
        return self.evidence


def _evidence(graph, **changes) -> LogicEvalEvidence:
    values = {
        "suite_id": "suite-1",
        "report_id": "report-1",
        "target_type": "logic_graph",
        "target_id": graph.id,
        "target_revision": graph.revision,
        "target_hash": graph.graph_hash,
        "gate_passed": True,
        "pass_rate": 1.0,
        "threshold": 0.8,
        "passed": 5,
        "failed": 0,
        "total": 5,
        "run_at": datetime.now(UTC),
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
    }
    values.update(changes)
    return LogicEvalEvidence(**values)


def test_contracts_are_strict_and_truthful() -> None:
    with pytest.raises(ValidationError):
        PublishLogicGraphRequest(
            expected_revision=1,
            expected_graph_hash="a" * 64,
            eval_suite_id="suite",
            eval_report_id="report",
            idempotency_key="key",
            forged_tenant="org",
        )
    with pytest.raises(ValidationError, match=r"passed \+ failed"):
        LogicEvalEvidence(
            suite_id="suite",
            report_id="report",
            target_id="graph",
            target_revision=1,
            target_hash="a" * 64,
            gate_passed=True,
            pass_rate=1,
            threshold=0.8,
            passed=1,
            failed=1,
            total=1,
            run_at=datetime.now(UTC),
        )


def test_publish_is_atomic_durable_and_updates_published_version(
    publication_scope,
) -> None:
    graph_store, run_store, store, scoped_connect = publication_scope
    graph = _create_graph(graph_store, "org", "project")
    dry_run = _succeed_dry_run(run_store, graph, "org", "project")
    provider = FakeEvidenceReader(_evidence(graph))

    published = store.publish(
        "org", "project", "publisher", graph.id, _request(graph), provider
    )

    assert published.graph_revision == graph.revision
    assert published.graph_hash == graph.graph_hash
    assert published.graph_snapshot == graph
    assert published.dry_run_id == dry_run.run_id
    assert published.eval_gate.gate_passed is True
    assert provider.connections
    assert store.get("org", "project", graph.id, published.publication_id) == published
    listed = store.list("org", "project", graph.id)
    assert listed.count == 1 and listed.items == [published]
    with scoped_connect() as conn:
        current = conn.execute(
            "SELECT published_version FROM aip_logic_graph WHERE graph_id=%s",
            (graph.id,),
        ).fetchone()
    assert current["published_version"] == graph.revision


def test_same_request_replays_and_changed_request_conflicts(publication_scope) -> None:
    graph_store, run_store, store, _ = publication_scope
    graph = _create_graph(graph_store, "org", "project")
    _succeed_dry_run(run_store, graph, "org", "project")
    provider = FakeEvidenceReader(_evidence(graph))
    request = _request(graph)
    first = store.publish("org", "project", "publisher", graph.id, request, provider)
    replay = store.publish("org", "project", "publisher", graph.id, request, provider)
    assert replay == first
    changed = _request(graph, report_id="report-2")
    with pytest.raises(LogicPublicationIdempotencyConflict):
        store.publish("org", "project", "publisher", graph.id, changed, provider)


def test_concurrent_semantic_retries_return_one_publication(publication_scope) -> None:
    graph_store, run_store, store, _ = publication_scope
    graph = _create_graph(graph_store, "org", "project")
    _succeed_dry_run(run_store, graph, "org", "project")
    provider = FakeEvidenceReader(_evidence(graph))

    def publish(index: int):
        return store.publish(
            "org",
            "project",
            "publisher",
            graph.id,
            _request(graph, key=f"key-{index}"),
            provider,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(publish, range(2)))
    assert results[0].publication_id == results[1].publication_id
    assert store.list("org", "project", graph.id).count == 1


def test_publish_requires_exact_successful_canonical_dry_run(publication_scope) -> None:
    graph_store, _, store, _ = publication_scope
    graph = _create_graph(graph_store, "org", "project")
    with pytest.raises(LogicPublicationDryRunRequired):
        store.publish(
            "org",
            "project",
            "publisher",
            graph.id,
            _request(graph),
            FakeEvidenceReader(_evidence(graph)),
        )


@pytest.mark.parametrize(
    ("changes", "error"),
    [
        ({"target_hash": "f" * 64}, LogicPublicationEvalTargetMismatch),
        ({"gate_passed": False, "pass_rate": 0.6}, LogicPublicationEvalGateRejected),
        (
            {
                "run_at": datetime.now(UTC) - timedelta(hours=2),
                "expires_at": datetime.now(UTC) - timedelta(hours=1),
            },
            LogicPublicationEvalEvidenceExpired,
        ),
    ],
)
def test_publish_rejects_untrusted_eval_evidence(
    publication_scope, changes, error
) -> None:
    graph_store, run_store, store, _ = publication_scope
    graph = _create_graph(graph_store, "org", "project")
    _succeed_dry_run(run_store, graph, "org", "project")
    with pytest.raises(error):
        store.publish(
            "org",
            "project",
            "publisher",
            graph.id,
            _request(graph),
            FakeEvidenceReader(_evidence(graph, **changes)),
        )
    assert store.list("org", "project", graph.id).count == 0


def test_version_conflict_and_tenant_isolation_fail_closed(publication_scope) -> None:
    graph_store, run_store, store, _ = publication_scope
    graph = _create_graph(graph_store, "org", "project")
    _succeed_dry_run(run_store, graph, "org", "project")
    request = _request(graph).model_copy(update={"expected_revision": 2})
    with pytest.raises(LogicPublicationVersionConflict):
        store.publish(
            "org",
            "project",
            "publisher",
            graph.id,
            request,
            FakeEvidenceReader(_evidence(graph)),
        )
    with pytest.raises(LogicPublicationNotFound):
        store.list("other-org", "project", graph.id)


def test_publication_snapshot_and_database_row_are_immutable(publication_scope) -> None:
    graph_store, run_store, store, scoped_connect = publication_scope
    graph = _create_graph(graph_store, "org", "project")
    _succeed_dry_run(run_store, graph, "org", "project")
    publication = store.publish(
        "org",
        "project",
        "publisher",
        graph.id,
        _request(graph),
        FakeEvidenceReader(_evidence(graph)),
    )
    graph_store.replace(
        "org",
        "project",
        graph.id,
        "editor",
        ReplaceLogicGraphRequest(
            expected_revision=1,
            name="edited draft",
            nodes=[{"id": "input", "kind": "input", "label": "Input"}],
            entry_node_ids=["input"],
        ),
    )
    reloaded = store.get("org", "project", graph.id, publication.publication_id)
    assert reloaded.graph_revision == 1
    assert reloaded.graph_snapshot.name == "publishable"
    with pytest.raises(errors.RaiseException), scoped_connect() as conn:
        conn.execute(
            "UPDATE aip_logic_publication SET actor='attacker' "
            "WHERE publication_id=%s",
            (publication.publication_id,),
        )
        conn.commit()


def test_provider_failure_rolls_back_without_false_publication(publication_scope) -> None:
    graph_store, run_store, store, scoped_connect = publication_scope
    graph = _create_graph(graph_store, "org", "project")
    _succeed_dry_run(run_store, graph, "org", "project")

    class FailingProvider:
        def get_evidence(self, _conn, **_kwargs):
            raise RuntimeError("eval store unavailable")

    with pytest.raises(LogicPublicationPersistenceError):
        store.publish(
            "org", "project", "publisher", graph.id, _request(graph), FailingProvider()
        )
    with scoped_connect() as conn:
        count = conn.execute("SELECT count(*) AS n FROM aip_logic_publication").fetchone()
        current = conn.execute(
            "SELECT published_version FROM aip_logic_graph WHERE graph_id=%s",
            (graph.id,),
        ).fetchone()
    assert count["n"] == 0
    assert current["published_version"] is None


def test_corrupt_stored_snapshot_is_detected(publication_scope) -> None:
    graph_store, run_store, store, scoped_connect = publication_scope
    graph = _create_graph(graph_store, "org", "project")
    _succeed_dry_run(run_store, graph, "org", "project")
    with scoped_connect() as conn:
        conn.execute(
            "UPDATE aip_logic_graph_revision SET snapshot=jsonb_set(snapshot,'{name}',to_jsonb('tampered'::text))"
        )
        conn.commit()
    with pytest.raises(LogicPublicationIntegrityError):
        store.publish(
            "org",
            "project",
            "publisher",
            graph.id,
            _request(graph),
            FakeEvidenceReader(_evidence(graph)),
        )


def test_migration_metadata_forms_single_stage_c_head() -> None:
    path = API_ROOT / "alembic/versions/228logicpublish_aip_logic_publications.py"
    spec = importlib.util.spec_from_file_location("publication_migration_meta", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "228logicpublish"
    assert module.down_revision == "228logiceval"
