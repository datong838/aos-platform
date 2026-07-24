def test_jdbc_mysql_health_via_plugin_id(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_MYSQL_DISABLED", "1")
    r = client.get("/v1/connectors/jdbc-mysql/health", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["pluginId"] == "jdbc-mysql"
    assert "passwordRef" in body
    assert "aos_dev_only_change_me" not in r.text


def test_mysql_alias_still_works(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_MYSQL_DISABLED", "1")
    r = client.get("/v1/connectors/mysql/health", headers=auth_headers)
    assert r.status_code == 200
    assert r.json().get("pluginId") == "jdbc-mysql"


def test_stub_connector_probe_501(client, auth_headers):
    client.post("/v1/connector-plugins/jdbc-postgres/install", headers=auth_headers)
    r = client.post(
        "/v1/connectors/jdbc-postgres/probe",
        headers=auth_headers,
        json={"limit": 1},
    )
    assert r.status_code == 501
    assert r.json()["code"] == "CONNECTOR_STUB"


def test_uninstalled_connector_400(client, auth_headers):
    client.post("/v1/connector-plugins/rest-generic/uninstall", headers=auth_headers)
    listed = client.get("/v1/connector-plugins", headers=auth_headers)
    rest = next(i for i in listed.json()["items"] if i["id"] == "rest-generic")
    if rest["installed"]:
        client.post("/v1/connector-plugins/rest-generic/uninstall", headers=auth_headers)
    r = client.get("/v1/connectors/rest-generic/health", headers=auth_headers)
    assert r.status_code == 400
    assert r.json()["code"] == "PLUGIN_NOT_INSTALLED"
