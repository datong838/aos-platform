"""W2-#15 · Expectation 数据期望 单元测试。

详见 docs/palantier/20_tech/220tech_w2-g-expectation-writemode-txn.md §2.1。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.expectation import (
    Expectation,
    ExpectationEngine,
    ExpectationType,
    get_engine,
)
from aos_api.main import create_app

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-exp",
}


# --------------------------------------------------------------------------- #
# PK 唯一检查
# --------------------------------------------------------------------------- #
def test_pk_unique_pass():
    eng = ExpectationEngine()
    exp = Expectation(name="pk", type=ExpectationType.PK_UNIQUE, config={"primary_key": "id"})
    result = eng.check(exp, [{"id": 1}, {"id": 2}, {"id": 3}])
    assert result.passed is True
    assert len(result.violations) == 0


def test_pk_unique_fail_with_duplicates():
    eng = ExpectationEngine()
    exp = Expectation(name="pk", type=ExpectationType.PK_UNIQUE, config={"primary_key": "id"})
    result = eng.check(exp, [{"id": 1}, {"id": 2}, {"id": 1}, {"id": 2}, {"id": 2}])
    assert result.passed is False
    assert len(result.violations) == 2
    dup_ids = {v["primary_key"] for v in result.violations}
    assert dup_ids == {1, 2}


def test_pk_unique_custom_field():
    eng = ExpectationEngine()
    exp = Expectation(name="pk", type=ExpectationType.PK_UNIQUE, config={"primary_key": "uid"})
    result = eng.check(exp, [{"uid": "a"}, {"uid": "b"}, {"uid": "a"}])
    assert result.passed is False


def test_pk_unique_null_pk_skipped():
    eng = ExpectationEngine()
    exp = Expectation(name="pk", type=ExpectationType.PK_UNIQUE, config={"primary_key": "id"})
    result = eng.check(exp, [{"id": None}, {"id": None}, {"id": 1}])
    assert result.passed is True  # None 不参与唯一性检查


def test_pk_unique_empty_rows():
    eng = ExpectationEngine()
    exp = Expectation(name="pk", type=ExpectationType.PK_UNIQUE)
    result = eng.check(exp, [])
    assert result.passed is True


# --------------------------------------------------------------------------- #
# 行数检查
# --------------------------------------------------------------------------- #
def test_row_count_in_range():
    eng = ExpectationEngine()
    exp = Expectation(name="rc", type=ExpectationType.ROW_COUNT, config={"min": 1, "max": 5})
    result = eng.check(exp, [{"id": 1}, {"id": 2}, {"id": 3}])
    assert result.passed is True


def test_row_count_below_min():
    eng = ExpectationEngine()
    exp = Expectation(name="rc", type=ExpectationType.ROW_COUNT, config={"min": 5, "max": 10})
    result = eng.check(exp, [{"id": 1}])
    assert result.passed is False
    assert any("低于最小行数" in v["reason"] for v in result.violations)


def test_row_count_above_max():
    eng = ExpectationEngine()
    exp = Expectation(name="rc", type=ExpectationType.ROW_COUNT, config={"min": 0, "max": 2})
    result = eng.check(exp, [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}])
    assert result.passed is False
    assert any("超过最大行数" in v["reason"] for v in result.violations)


def test_row_count_no_max():
    eng = ExpectationEngine()
    exp = Expectation(name="rc", type=ExpectationType.ROW_COUNT, config={"min": 1})
    result = eng.check(exp, [{"id": i} for i in range(100)])
    assert result.passed is True


# --------------------------------------------------------------------------- #
# severity / check_all / disabled
# --------------------------------------------------------------------------- #
def test_severity_warn_does_not_block():
    eng = ExpectationEngine()
    exp = Expectation(name="pk", type=ExpectationType.PK_UNIQUE, severity="warn")
    result = eng.check(exp, [{"id": 1}, {"id": 1}])
    assert result.passed is False
    assert result.severity == "warn"
    assert eng.has_blocking_failure([result]) is False


def test_severity_error_blocks():
    eng = ExpectationEngine()
    exp = Expectation(name="pk", type=ExpectationType.PK_UNIQUE, severity="error")
    result = eng.check(exp, [{"id": 1}, {"id": 1}])
    assert result.passed is False
    assert eng.has_blocking_failure([result]) is True


def test_disabled_expectation_skipped():
    eng = ExpectationEngine()
    exp = Expectation(name="pk", type=ExpectationType.PK_UNIQUE, enabled=False)
    result = eng.check(exp, [{"id": 1}, {"id": 1}])
    assert result.passed is True  # 禁用 → 跳过 → 通过


def test_check_all_multiple():
    eng = ExpectationEngine()
    exps = [
        Expectation(name="pk", type=ExpectationType.PK_UNIQUE, config={"primary_key": "id"}),
        Expectation(name="rc", type=ExpectationType.ROW_COUNT, config={"min": 1, "max": 10}),
    ]
    results = eng.check_all(exps, [{"id": 1}, {"id": 2}])
    assert len(results) == 2
    assert all(r.passed for r in results)


# --------------------------------------------------------------------------- #
# API 层
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(monkeypatch):
    fresh = ExpectationEngine()
    monkeypatch.setattr("aos_api.routers.expectation.get_engine", lambda: fresh)
    return TestClient(create_app())


def test_api_create_and_check(client):
    create = client.post("/v1/expectations", json={
        "name": "pk-check",
        "type": "pk_unique",
        "config": {"primary_key": "id"},
    }, headers=_H)
    assert create.status_code == 200
    eid = create.json()["id"]

    check = client.post(f"/v1/expectations/{eid}/check", json={
        "rows": [{"id": 1}, {"id": 1}],
    }, headers=_H)
    assert check.status_code == 200
    assert check.json()["passed"] is False


def test_api_list_and_delete(client):
    client.post("/v1/expectations", json={
        "name": "rc", "type": "row_count", "config": {"min": 0, "max": 100},
    }, headers=_H)
    lst = client.get("/v1/expectations", headers=_H)
    assert lst.status_code == 200
    assert len(lst.json()["expectations"]) == 1

    eid = lst.json()["expectations"][0]["id"]
    dele = client.delete(f"/v1/expectations/{eid}", headers=_H)
    assert dele.status_code == 200


def test_api_check_all(client):
    client.post("/v1/expectations", json={
        "name": "pk", "type": "pk_unique", "config": {"primary_key": "id"},
    }, headers=_H)
    resp = client.post("/v1/expectations/check-all", json={
        "rows": [{"id": 1}, {"id": 2}],
    }, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["all_passed"] is True


def test_api_unknown_type_400(client):
    resp = client.post("/v1/expectations", json={
        "name": "bad", "type": "nonexistent",
    }, headers=_H)
    assert resp.status_code == 400
