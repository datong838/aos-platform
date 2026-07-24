"""W1-15 · Dataset Preview SQL Console 单元测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.sql_console import SqlConsole

_H = {
    "Authorization": "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "X-Trace-Id": "test-trace-1",
}

_ROWS = [
    {"id": 1, "name": "alice", "age": 30, "dept": "eng"},
    {"id": 2, "name": "bob", "age": 25, "dept": "eng"},
    {"id": 3, "name": "carol", "age": 35, "dept": "sales"},
    {"id": 4, "name": "dave", "age": 28, "dept": "sales"},
]


def _new_console() -> SqlConsole:
    return SqlConsole()


# --- 引擎：validate --- #

def test_validate_select_ok():
    c = _new_console()
    assert c.validate("SELECT * FROM t") == []


def test_validate_with_ok():
    c = _new_console()
    assert c.validate("WITH x AS (SELECT 1) SELECT * FROM x") == []


def test_validate_empty():
    c = _new_console()
    errs = c.validate("")
    assert any("SQL_EMPTY" in e for e in errs)


def test_validate_not_select():
    c = _new_console()
    errs = c.validate("DELETE FROM t")
    assert any("SQL_NOT_SELECT" in e for e in errs)


def test_validate_forbidden_keyword():
    c = _new_console()
    errs = c.validate("SELECT * FROM t; DROP TABLE t")
    assert any("SQL_FORBIDDEN" in e for e in errs)


# --- 引擎：execute --- #

def test_execute_select_all():
    c = _new_console()
    result = c.execute(_ROWS, "users", "SELECT * FROM users")
    assert result.error is None
    assert result.row_count == 4
    assert set(result.columns) == {"id", "name", "age", "dept"}


def test_execute_where():
    c = _new_console()
    result = c.execute(_ROWS, "users", "SELECT * FROM users WHERE dept = 'eng'")
    assert result.row_count == 2


def test_execute_order_by():
    c = _new_console()
    result = c.execute(_ROWS, "users", "SELECT * FROM users ORDER BY age DESC")
    assert result.rows[0]["name"] == "carol"
    assert result.rows[3]["name"] == "bob"


def test_execute_limit():
    c = _new_console()
    result = c.execute(_ROWS, "users", "SELECT * FROM users LIMIT 2")
    assert result.row_count == 2


def test_execute_aggregate_count():
    c = _new_console()
    result = c.execute(_ROWS, "users", "SELECT COUNT(*) AS n FROM users")
    assert result.rows[0]["n"] == 4


def test_execute_group_by():
    c = _new_console()
    result = c.execute(_ROWS, "users",
                       "SELECT dept, COUNT(*) AS n, AVG(age) AS avg_age FROM users GROUP BY dept ORDER BY dept")
    assert result.row_count == 2
    eng = next(r for r in result.rows if r["dept"] == "eng")
    assert eng["n"] == 2
    assert eng["avg_age"] == 27.5


def test_execute_subquery():
    c = _new_console()
    result = c.execute(_ROWS, "users",
                       "SELECT * FROM users WHERE age > (SELECT AVG(age) FROM users)")
    assert result.row_count == 2


def test_execute_error_invalid_sql():
    c = _new_console()
    result = c.execute(_ROWS, "users", "SELECT FROM users")
    assert result.error is not None
    assert "SQL_EXEC_ERROR" in result.error or "SQL_NOT_SELECT" in result.error


def test_execute_forbidden_returns_error():
    c = _new_console()
    result = c.execute(_ROWS, "users", "DELETE FROM users")
    assert result.error is not None


def test_execute_empty_rows():
    c = _new_console()
    result = c.execute([], "users", "SELECT * FROM users")
    assert result.error is not None


def test_execute_column_projection():
    c = _new_console()
    result = c.execute(_ROWS, "users", "SELECT name, age FROM users WHERE age > 28")
    assert result.columns == ["name", "age"]
    assert result.row_count == 2


# --- 引擎：autocomplete --- #

def test_autocomplete_columns():
    c = _new_console()
    suggestions = c.autocomplete(["id", "name", "age"], "")
    texts = {s.text for s in suggestions}
    assert "id" in texts
    assert "name" in texts


def test_autocomplete_with_prefix():
    c = _new_console()
    suggestions = c.autocomplete(["id", "name", "age"], "na")
    texts = {s.text for s in suggestions}
    assert "name" in texts
    assert "id" not in texts


def test_autocomplete_keywords():
    c = _new_console()
    suggestions = c.autocomplete([], "SE")
    texts = {s.text for s in suggestions}
    assert "SELECT" in texts


# --- 引擎：history --- #

def test_history_recorded():
    c = _new_console()
    c.execute(_ROWS, "users", "SELECT * FROM users")
    c.execute(_ROWS, "users", "SELECT bad query syntax")
    history = c.list_history()
    assert len(history) == 2
    assert history[0].success or not history[0].success


def test_history_limit():
    c = _new_console()
    for i in range(10):
        c.execute(_ROWS, "users", "SELECT * FROM users")
    history = c.list_history(limit=3)
    assert len(history) == 3


# --- API --- #

@pytest.fixture()
def client(monkeypatch):
    fresh = SqlConsole()
    monkeypatch.setattr("aos_api.routers.sql_console.get_console", lambda: fresh)
    return TestClient(create_app())


def test_api_execute(client):
    resp = client.post("/v1/sql-console/execute", json={
        "rows": _ROWS, "table_name": "users", "sql": "SELECT * FROM users"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["row_count"] == 4


def test_api_validate_ok(client):
    resp = client.post("/v1/sql-console/validate", json={"sql": "SELECT 1"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_api_validate_forbidden(client):
    resp = client.post("/v1/sql-console/validate", json={"sql": "DROP TABLE x"}, headers=_H)
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_api_autocomplete(client):
    resp = client.post("/v1/sql-console/autocomplete", json={
        "columns": ["id", "name"], "prefix": ""}, headers=_H)
    assert resp.status_code == 200
    assert len(resp.json()["suggestions"]) > 0


def test_api_history(client):
    client.post("/v1/sql-console/execute", json={
        "rows": _ROWS, "table_name": "u", "sql": "SELECT * FROM u"}, headers=_H)
    resp = client.get("/v1/sql-console/history", headers=_H)
    assert resp.status_code == 200
    assert resp.json()["count"] == 1


def test_api_execute_where(client):
    resp = client.post("/v1/sql-console/execute", json={
        "rows": _ROWS, "table_name": "users",
        "sql": "SELECT name FROM users WHERE dept = 'eng' ORDER BY name"}, headers=_H)
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()["rows"]]
    assert names == ["alice", "bob"]
