def test_list_connector_plugins(client, auth_headers):
    r = client.get("/v1/connector-plugins", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    ids = {i["id"] for i in body["items"]}
    assert "file-local" in ids
    assert "jdbc-mysql" in ids
    assert "jdbc-postgres" in ids
    assert len(body["items"]) >= 6
    required = [i for i in body["items"] if i["id"] in ("file-local", "file-object-store", "jdbc-mysql")]
    assert all(i["installed"] for i in required)


def test_install_uninstall_optional_connector(client, auth_headers):
    u = client.post("/v1/connector-plugins/jdbc-postgres/uninstall", headers=auth_headers)
    # may already be uninstalled
    assert u.status_code in (200, 403)
    inst = client.post("/v1/connector-plugins/jdbc-postgres/install", headers=auth_headers)
    assert inst.status_code == 200
    assert inst.json()["installed"] is True
    listed = client.get("/v1/connector-plugins", headers=auth_headers)
    hit = next(i for i in listed.json()["items"] if i["id"] == "jdbc-postgres")
    assert hit["installed"] is True


def test_cannot_uninstall_required_connector(client, auth_headers):
    r = client.post("/v1/connector-plugins/jdbc-mysql/uninstall", headers=auth_headers)
    assert r.status_code == 403


def test_create_source_requires_installed_plugin(client, auth_headers):
    ok = client.post(
        "/v1/sources",
        headers=auth_headers,
        json={"id": "src-97-mysql", "type": "jdbc-mysql"},
    )
    assert ok.status_code == 200
    assert ok.json()["type"] == "jdbc-mysql"
    assert ok.json()["pluginId"] == "jdbc-mysql"

    alias = client.post(
        "/v1/sources",
        headers=auth_headers,
        json={"id": "src-97-file", "type": "file"},
    )
    assert alias.status_code == 200
    assert alias.json()["type"] == "file-local"

    client.post("/v1/connector-plugins/rest-generic/uninstall", headers=auth_headers)
    # ensure not installed
    listed = client.get("/v1/connector-plugins", headers=auth_headers)
    rest = next(i for i in listed.json()["items"] if i["id"] == "rest-generic")
    if rest["installed"]:
        client.post("/v1/connector-plugins/rest-generic/uninstall", headers=auth_headers)
    bad = client.post(
        "/v1/sources",
        headers=auth_headers,
        json={"id": "src-97-rest", "type": "rest-generic"},
    )
    assert bad.status_code == 400
    assert bad.json()["code"] == "PLUGIN_NOT_INSTALLED"
