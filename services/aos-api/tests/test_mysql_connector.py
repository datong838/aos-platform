import os

import pytest


def test_mysql_probe_disabled(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_MYSQL_DISABLED", "1")
    r = client.post(
        "/v1/connectors/mysql/probe",
        headers=auth_headers,
        json={"objectType": "WorkOrder"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "disabled"
    assert "aos_dev_only_change_me" not in r.text


def test_mysql_health_no_secret(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_MYSQL_DISABLED", "1")
    r = client.get("/v1/connectors/mysql/health", headers=auth_headers)
    assert r.status_code == 200
    assert "passwordRef" in r.json()
    assert "aos_dev_only_change_me" not in r.text


def test_map_row_default():
    from aos_api.mysql_connector import map_row

    oid, props = map_row(
        {"id": "mysql-wo-001", "title": "t", "status": "open", "site": "DC-East", "priority": "P1"}
    )
    assert oid == "mysql-wo-001"
    assert props["title"] == "t"
    assert props["site"] == "DC-East"


@pytest.mark.skipif(os.environ.get("AOS_MYSQL_LIVE") != "1", reason="set AOS_MYSQL_LIVE=1")
def test_live_mysql_ingest(client, auth_headers):
    probe = client.post(
        "/v1/connectors/mysql/probe",
        headers=auth_headers,
        json={"limit": 5},
    )
    assert probe.json()["mode"] == "live"
    ing = client.post(
        "/v1/connectors/mysql/ingest",
        headers=auth_headers,
        json={"objectType": "WorkOrder", "limit": 5},
    )
    assert ing.status_code == 200
    body = ing.json()
    assert body["written"] >= 1
    oid = body["objectIds"][0]
    obj = client.get(f"/v1/objects/WorkOrder/{oid}", headers=auth_headers)
    assert obj.status_code == 200
