"""W1-12 · Evals 评测门控引擎 单元测试。

详见 docs/palantier/20_tech/220tech_evals-engine.md §6。

LLM 评判测试通过 .env 的 AGNES_* 参数自动运行（未配置时用 mock chat_fn）。
不写死任何模型名——模型由 llm_gateway 路由。
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api.evals_engine import (
    EvalsEngine,
    EvalSuite,
    TestCase,
)
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}


def _mock_chat_yes(query: str, **kw) -> dict:
    return {"answer": "yes", "provider": "mock"}


def _mock_chat_no(query: str, **kw) -> dict:
    return {"answer": "no", "provider": "mock"}


def _agnes_configured() -> bool:
    return bool(
        os.environ.get("AGNES_API_KEY")
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
    monkeypatch.setattr("aos_api.routers.evals.EvalsEngine", lambda: fresh)
    return TestClient(create_app())


def test_api_create_and_list_suite(client):
    resp = client.post("/v1/evals/suites", json={
        "name": "api-suite",
        "cases": [{"id": "c1", "inputs": {}, "expected": "ok", "judge": "exact"}],
        "gate_threshold": 0.8,
    }, headers=_H)
    assert resp.status_code == 200
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
        "target_type": "function",
        "target_expr": "x + 1",
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["pass_rate"] == 1.0


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
        "target_expr": "x + 1",
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["gate_passed"] is True


def test_api_report_not_found(client):
    resp = client.get("/v1/evals/nonexistent/report", headers=_H)
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Agnes LLM 评判实连（读 .env，不写死模型）
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not _agnes_configured(), reason="AGNES_* 未配置（读 .env）")
def test_eval_llm_judge_with_agnes():
    from aos_api.env_load import load_dotenv
    load_dotenv(force=True)
    from aos_api.llm_gateway import _openai_chat, agnes_api_key, agnes_base_url, agnes_text_model

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
