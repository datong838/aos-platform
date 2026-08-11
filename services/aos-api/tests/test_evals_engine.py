"""W1-12 · Evals 评测门控引擎 单元测试。

详见 docs/palantier/20_tech/220tech_evals-engine.md §6。

LLM 评判单元测试固定使用 mock chat_fn；Agnes 实连仅在显式设置
``AOS_RUN_AGNES_INTEGRATION=1`` 且 AGNES_* 完整时运行。
不写死任何模型名——模型由 llm_gateway 路由。
"""
from __future__ import annotations

import importlib.util
import json
import os
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg import sql

from aos_api.aip_eval_store import EvalEvidenceStore
from aos_api.aip_logic_graph_models import (
    LogicGraphSnapshot,
    ValidateLogicGraphRequest,
    compute_logic_graph_hash,
)
from aos_api.aip_logic_graph_store import LogicGraphStore
from aos_api.db import connect
from aos_api.evals_engine import (
    EvalsEngine,
    EvalSuite,
    TestCase,
)
from aos_api.main import create_app
from aos_api.routers.evals import get_eval_graph_store, get_eval_store

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}
_GRAPH_CONTENT = ValidateLogicGraphRequest(
    name="eval target",
    nodes=[
        {"id": "input", "kind": "input", "label": "Input"},
        {
            "id": "transform",
            "kind": "transform",
            "label": "Add one",
            "config": {"expression": "x + 1"},
        },
    ],
    edges=[
        {
            "id": "input-transform",
            "source_node_id": "input",
            "target_node_id": "transform",
        }
    ],
    entry_node_ids=["input"],
)
_TARGET_HASH = compute_logic_graph_hash(_GRAPH_CONTENT)


def _graph_snapshot() -> LogicGraphSnapshot:
    now = datetime.now(UTC)
    return LogicGraphSnapshot(
        id="logic-eval-test",
        name=_GRAPH_CONTENT.name,
        description="",
        status="draft",
        schema_version=1,
        revision=1,
        graph_hash=_TARGET_HASH,
        nodes=_GRAPH_CONTENT.nodes,
        edges=_GRAPH_CONTENT.edges,
        entry_node_ids=_GRAPH_CONTENT.entry_node_ids,
        created_at=now,
        updated_at=now,
    )


def _target(**overrides) -> dict:
    return {
        "target_type": "logic_graph",
        "target_id": "logic-eval-test",
        "target_revision": 1,
        "target_hash": _TARGET_HASH,
        **overrides,
    }


def _mock_chat_yes(query: str, **kw) -> dict:
    return {"answer": "yes", "provider": "mock"}


def _mock_chat_no(query: str, **kw) -> dict:
    return {"answer": "no", "provider": "mock"}


def _agnes_configured() -> bool:
    return bool(
        os.environ.get("AOS_RUN_AGNES_INTEGRATION") == "1"
        and os.environ.get("AGNES_API_KEY")
        and os.environ.get("AGNES_BASE_URL")
        and os.environ.get("AGNES_TEXT_MODEL")
    )


# --------------------------------------------------------------------------- #
# 评判标准
# --------------------------------------------------------------------------- #
def test_eval_exact_match_pass():
    eng = EvalsEngine(chat_fn=_mock_chat_yes)
    suite = EvalSuite(name="s", cases=[
        TestCase(id="c1", inputs={"x": 1}, expected=2, judge="exact"),
    ])
    eng.create_suite(suite)
    report = eng.run(suite.id, lambda inp: inp["x"] + 1)
    assert report.passed == 1
    assert report.pass_rate == 1.0


def test_eval_exact_match_fail():
    eng = EvalsEngine(chat_fn=_mock_chat_yes)
    suite = EvalSuite(name="s", cases=[
        TestCase(id="c1", inputs={"x": 1}, expected=3, judge="exact"),
    ])
    eng.create_suite(suite)
    report = eng.run(suite.id, lambda inp: inp["x"] + 1)
    assert report.failed == 1
    assert report.pass_rate == 0.0


def test_eval_contains_match():
    eng = EvalsEngine(chat_fn=_mock_chat_yes)
    suite = EvalSuite(name="s", cases=[
        TestCase(id="c1", inputs={}, expected="world", judge="contains"),
    ])
    eng.create_suite(suite)
    report = eng.run(suite.id, lambda inp: "hello world")
    assert report.passed == 1


def test_eval_llm_judge_mock():
    eng = EvalsEngine(chat_fn=_mock_chat_yes)
    suite = EvalSuite(name="s", cases=[
        TestCase(id="c1", inputs={"q": "1+1"}, expected="2", judge="llm"),
    ])
    eng.create_suite(suite)
    report = eng.run(suite.id, lambda inp: "2")
    assert report.results[0].passed is True

    eng2 = EvalsEngine(chat_fn=_mock_chat_no)
    eng2.create_suite(suite)
    report2 = eng2.run(suite.id, lambda inp: "3")
    assert report2.results[0].passed is False


def test_eval_numeric_tolerance():
    eng = EvalsEngine(chat_fn=_mock_chat_yes)
    suite = EvalSuite(name="s", cases=[
        TestCase(id="c1", inputs={}, expected=10.0, judge="numeric", tolerance=0.5),
    ])
    eng.create_suite(suite)
    report_ok = eng.run(suite.id, lambda inp: 10.3)
    assert report_ok.results[0].passed is True

    report_fail = eng.run(suite.id, lambda inp: 11.0)
    assert report_fail.results[0].passed is False


def test_eval_pass_rate_calculation():
    eng = EvalsEngine(chat_fn=_mock_chat_yes)
    suite = EvalSuite(name="s", cases=[
        TestCase(id="c1", inputs={}, expected="a", judge="exact"),
        TestCase(id="c2", inputs={}, expected="b", judge="exact"),
        TestCase(id="c3", inputs={}, expected="c", judge="exact"),
        TestCase(id="c4", inputs={}, expected="d", judge="exact"),
    ])
    eng.create_suite(suite)
    report = eng.run(suite.id, lambda inp: "a")
    assert report.pass_rate == 0.25
    assert report.passed == 1
    assert report.failed == 3
    assert report.total == 4


# --------------------------------------------------------------------------- #
# 门控
# --------------------------------------------------------------------------- #
def test_gate_check_pass():
    eng = EvalsEngine(chat_fn=_mock_chat_yes)
    suite = EvalSuite(name="s", gate_threshold=0.5, cases=[
        TestCase(id="c1", inputs={}, expected="ok", judge="exact"),
        TestCase(id="c2", inputs={}, expected="ok", judge="exact"),
    ])
    eng.create_suite(suite)
    result = eng.gate_check(suite.id, lambda inp: "ok")
    assert result["gate_passed"] is True
    assert result["pass_rate"] == 1.0


def test_gate_check_fail():
    eng = EvalsEngine(chat_fn=_mock_chat_yes)
    suite = EvalSuite(name="s", gate_threshold=0.8, cases=[
        TestCase(id="c1", inputs={}, expected="yes", judge="exact"),
        TestCase(id="c2", inputs={}, expected="yes", judge="exact"),
        TestCase(id="c3", inputs={}, expected="yes", judge="exact"),
        TestCase(id="c4", inputs={}, expected="yes", judge="exact"),
    ])
    eng.create_suite(suite)
    result = eng.gate_check(suite.id, lambda inp: "no")
    assert result["gate_passed"] is False
    assert result["pass_rate"] == 0.0


# --------------------------------------------------------------------------- #
# 报告 + 历史
# --------------------------------------------------------------------------- #
def test_eval_report_generation():
    eng = EvalsEngine(chat_fn=_mock_chat_yes)
    suite = EvalSuite(name="s", cases=[
        TestCase(id="c1", inputs={}, expected=42, judge="exact"),
    ])
    eng.create_suite(suite)
    report = eng.run(suite.id, lambda inp: 42)
    assert report.suite_id == suite.id
    assert len(report.results) == 1
    assert report.results[0].actual == 42
    assert report.run_at


def test_eval_history_trend():
    eng = EvalsEngine(chat_fn=_mock_chat_yes)
    suite = EvalSuite(name="s", cases=[
        TestCase(id="c1", inputs={}, expected=1, judge="exact"),
    ])
    eng.create_suite(suite)
    eng.run(suite.id, lambda inp: 1)
    eng.run(suite.id, lambda inp: 2)
    history = eng.history(suite.id)
    assert len(history) == 2
    assert history[0].pass_rate == 1.0
    assert history[1].pass_rate == 0.0


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = EvalsEngine(chat_fn=_mock_chat_yes)
    monkeypatch.setattr("aos_api.routers.evals.get_engine", lambda: fresh)
    suffix = uuid.uuid4().hex
    schema = f"eval_api_test_{suffix}"
    try:
        with connect() as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            conn.execute(
                """CREATE TABLE aip_logic_graph (
                org_id TEXT NOT NULL, project_id TEXT NOT NULL, graph_id TEXT NOT NULL,
                revision BIGINT NOT NULL,
                deleted_at TIMESTAMPTZ,
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
            spec = importlib.util.spec_from_file_location("eval_api_migration", path)
            migration = importlib.util.module_from_spec(spec)
            assert spec and spec.loader
            spec.loader.exec_module(migration)
            statements: list[str] = []
            monkeypatch.setattr(migration.op, "execute", statements.append)
            migration.upgrade()
            for statement in statements:
                conn.execute(statement)
            conn.execute(
                sql.SQL("GRANT USAGE ON SCHEMA {} TO aos_runtime").format(
                    sql.Identifier(schema)
                )
            )
            conn.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES "
                    "IN SCHEMA {} TO aos_runtime"
                ).format(sql.Identifier(schema))
            )
            conn.execute(
                """INSERT INTO aip_logic_graph
                (org_id,project_id,graph_id,revision) VALUES (%s,%s,%s,1)""",
                (_H["X-Org-Id"], _H["X-Project-Id"], "logic-eval-test"),
            )
            snapshot = _graph_snapshot()
            conn.execute(
                """INSERT INTO aip_logic_graph_revision
                (org_id,project_id,graph_id,revision,graph_hash,snapshot,actor)
                VALUES (%s,%s,%s,1,%s,%s::jsonb,'tester')""",
                (
                    _H["X-Org-Id"],
                    _H["X-Project-Id"],
                    "logic-eval-test",
                    _TARGET_HASH,
                    json.dumps(snapshot.model_dump(mode="json")),
                ),
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PG unavailable: {exc}")

    @contextmanager
    def scoped_connect():
        with connect() as conn:
            conn.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            conn.execute("SELECT set_config('aos.org_id', %s, true)", (_H["X-Org-Id"],))
            conn.execute(
                "SELECT set_config('aos.project_id', %s, true)",
                (_H["X-Project-Id"],),
            )
            yield conn

    app = create_app()
    app.dependency_overrides[get_eval_store] = lambda: EvalEvidenceStore(
        connect_factory=scoped_connect
    )
    app.dependency_overrides[get_eval_graph_store] = lambda: LogicGraphStore(
        connect_factory=scoped_connect
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_eval_store, None)
    app.dependency_overrides.pop(get_eval_graph_store, None)
    with connect() as conn:
        conn.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.commit()


def test_api_create_and_list_suite(client):
    resp = client.post("/v1/evals/suites", json={
        "name": "api-suite",
        "cases": [{"id": "c1", "inputs": {}, "expected": "ok", "judge": "exact"}],
        "gate_threshold": 0.8,
    }, headers=_H)
    assert resp.status_code == 200, resp.json()
    suite_id = resp.json()["id"]

    resp = client.get("/v1/evals/suites", headers=_H)
    assert resp.status_code == 200
    assert any(s["id"] == suite_id for s in resp.json()["items"])


def test_api_run_eval(client):
    create = client.post("/v1/evals/suites", json={
        "name": "run-test",
        "cases": [{"id": "c1", "inputs": {"x": 1}, "expected": 2, "judge": "exact"}],
        "gate_threshold": 0.8,
    }, headers=_H)
    suite_id = create.json()["id"]

    resp = client.post("/v1/evals/run", json={
        "suite_id": suite_id,
        **_target(),
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["pass_rate"] == 1.0
    assert resp.json()["report_id"].startswith("eval-report-")
    assert resp.json()["target_id"] == "logic-eval-test"

    report = client.get(f"/v1/evals/{suite_id}/report", headers=_H)
    assert report.status_code == 200
    assert report.json()["suite_id"] == suite_id
    assert report.json()["gate_passed"] is True


def test_api_gate_check(client):
    create = client.post("/v1/evals/suites", json={
        "name": "gate-test",
        "cases": [
            {"id": "c1", "inputs": {"x": 1}, "expected": 2, "judge": "exact"},
            {"id": "c2", "inputs": {"x": 2}, "expected": 3, "judge": "exact"},
        ],
        "gate_threshold": 1.0,
    }, headers=_H)
    suite_id = create.json()["id"]

    resp = client.post("/v1/evals/gate-check", json={
        "suite_id": suite_id,
        **_target(),
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["gate_passed"] is True


def test_api_gate_check_can_reuse_latest_report_without_second_run(client):
    create = client.post("/v1/evals/suites", json={
        "name": "reuse-report",
        "cases": [{"id": "c1", "inputs": {"x": 1}, "expected": 2, "judge": "exact"}],
        "gate_threshold": 1.0,
    }, headers=_H)
    suite_id = create.json()["id"]

    run = client.post("/v1/evals/run", json={
        "suite_id": suite_id,
        **_target(),
    }, headers=_H)
    assert run.status_code == 200

    gate = client.post("/v1/evals/gate-check", json={
        "suite_id": suite_id,
        **_target(),
        "reuse_latest_report": True,
    }, headers=_H)
    assert gate.status_code == 200
    assert gate.json()["gate_passed"] is True
    assert gate.json()["total"] == run.json()["total"]

    history = client.get(f"/v1/evals/{suite_id}/history", headers=_H)
    assert history.status_code == 200
    assert len(history.json()["items"]) == 1


def test_api_missing_or_forged_expression_target_fails_closed_without_report(client):
    create = client.post(
        "/v1/evals/suites",
        json={
            "name": "fail-closed",
            "cases": [
                {
                    "id": "c1",
                    "inputs": {"expected": "forged"},
                    "expected": "forged",
                    "judge": "exact",
                }
            ],
            "gate_threshold": 1.0,
        },
        headers=_H,
    )
    suite_id = create.json()["id"]
    missing_target = client.post(
        "/v1/evals/run",
        json={"suite_id": suite_id, "target_expr": "expected"},
        headers=_H,
    )
    assert missing_target.status_code == 400
    forged_expression = client.post(
        "/v1/evals/run",
        json={"suite_id": suite_id, **_target(), "target_expr": "expected"},
        headers=_H,
    )
    assert forged_expression.status_code in {400, 422}
    report = client.get(f"/v1/evals/{suite_id}/report", headers=_H)
    assert report.status_code == 404


def test_api_target_hash_mismatch_and_cross_tenant_reads_are_blocked(client):
    create = client.post(
        "/v1/evals/suites",
        json={
            "name": "target-check",
            "cases": [{"id": "c1", "inputs": {"x": 1}, "expected": 2}],
            "gate_threshold": 1.0,
        },
        headers=_H,
    )
    suite_id = create.json()["id"]
    mismatch = client.post(
        "/v1/evals/run",
        json={
            "suite_id": suite_id,
            **_target(target_hash="b" * 64),
        },
        headers=_H,
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "EVAL_TARGET_VERSION_CONFLICT"
    other_headers = {
        **_H,
        "X-Org-Id": "other-org",
        "X-Project-Id": "other-project",
    }
    hidden = client.get(f"/v1/evals/suites/{suite_id}", headers=other_headers)
    assert hidden.status_code == 403
    assert hidden.json()["code"] == "AUTH_TENANT_UNKNOWN"


def test_api_report_not_found(client):
    resp = client.get("/v1/evals/nonexistent/report", headers=_H)
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Agnes LLM 评判实连（读 .env，不写死模型）
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(
    not _agnes_configured(),
    reason="未显式设置 AOS_RUN_AGNES_INTEGRATION=1 或 AGNES_* 不完整",
)
def test_eval_llm_judge_with_agnes():
    from aos_api.env_load import load_dotenv
    load_dotenv(force=True)
    from aos_api.llm_gateway import (
        _openai_chat,
        agnes_api_key,
        agnes_base_url,
        agnes_text_model,
    )

    def _force_agnes_chat(query: str, **kw) -> dict:
        out = _openai_chat(
            base_url=agnes_base_url(),
            api_key=agnes_api_key(),
            model=kw.get("model") or agnes_text_model(),
            query=query,
        )
        return {"answer": out["answer"], "provider": "agnes", "route": "agnes"}

    eng = EvalsEngine(chat_fn=_force_agnes_chat)
    suite = EvalSuite(name="agnes-llm-judge", cases=[
        TestCase(id="c1", inputs={"q": "1+1等于几？"}, expected="2", judge="llm"),
    ])
    eng.create_suite(suite)
    report = eng.run(suite.id, lambda inp: "2")
    assert report.results[0].passed is True
    assert "yes" in report.results[0].detail.lower()
