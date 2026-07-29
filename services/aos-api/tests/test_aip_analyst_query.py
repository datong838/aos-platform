"""W2-A4 · AIP Analyst query 单测。"""
from __future__ import annotations

import pytest

from aos_api.aip_analyst_query import (
    is_select_query,
    nl_to_sql,
    run_analyst_query,
    validate_select,
)


def test_is_select_query():
    assert is_select_query("SELECT * FROM shops")
    assert is_select_query("  select 1")
    assert not is_select_query("DELETE FROM shops")


def test_validate_rejects_dangerous():
    assert validate_select("DELETE FROM shops") is not None
    assert validate_select("SELECT * FROM t; DROP TABLE t") is not None
    assert validate_select("SELECT * FROM shops") is None


def test_nl_to_sql_shops():
    sql = nl_to_sql("北安普顿咖啡店")
    assert "shops" in sql.lower()
    assert is_select_query(sql)


def test_nl_to_sql_inventory():
    sql = nl_to_sql("库存预警")
    assert "inventory" in sql.lower()


def test_run_live_shops():
    r = run_analyst_query(sql="SELECT name, coords, rating FROM shops WHERE city = 'Northampton'")
    assert r["source"] == "live"
    assert r["ok"] is True
    assert len(r["rows"]) >= 1
    assert {c["name"] for c in r["columns"]} >= {"name", "coords", "rating"}
    assert all("Birmingham" not in str(row.get("city", "")) for row in r["rows"])


def test_run_nl_live():
    r = run_analyst_query(natural_language="高评分店铺")
    assert r["source"] == "live"
    assert r["table"] == "shops"
    assert all(float(row["rating"]) >= 4 for row in r["rows"])


def test_run_fallback_unknown_table():
    r = run_analyst_query(sql="SELECT * FROM unknown_table")
    assert r["source"] == "fallback"
    assert len(r["rows"]) >= 1


def test_run_requires_input():
    with pytest.raises(ValueError):
        run_analyst_query()


def test_http_query_endpoint(client):
    r = client.post(
        "/v1/aip/analyst/query",
        json={"sql": "SELECT name, rating FROM shops WHERE rating >= 4"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "live"
    assert body["durationMs"] >= 1
    assert len(body["rows"]) >= 1


def test_http_nl_endpoint(client):
    r = client.post(
        "/v1/aip/analyst/query",
        json={"naturalLanguage": "库存低于10"},
    )
    assert r.status_code == 200
    assert r.json()["source"] == "live"
    assert r.json()["table"] == "inventory"


def test_http_rejects_delete(client):
    r = client.post(
        "/v1/aip/analyst/query",
        json={"sql": "DELETE FROM shops"},
    )
    assert r.status_code == 400
