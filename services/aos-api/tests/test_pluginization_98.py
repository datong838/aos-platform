def test_list_parser_plugins(client, auth_headers):
    r = client.get("/v1/parser-plugins", headers=auth_headers)
    assert r.status_code == 200
    ids = {i["id"] for i in r.json()["items"]}
    assert "parser-text" in ids
    assert "parser-pdf-ocr" in ids
    assert all(i["installed"] for i in r.json()["items"] if i["id"].startswith("parser-"))


def test_list_widget_plugins_palette(client, auth_headers):
    r = client.get("/v1/widget-plugins", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) >= 4
    kinds = {p["kind"] for p in body["palette"]}
    assert "filter" in kinds
    assert "table" in kinds


def test_list_channel_and_embedding_plugins(client, auth_headers):
    ch = client.get("/v1/channel-plugins", headers=auth_headers)
    assert ch.status_code == 200
    assert any(i["id"] == "channel-webhook" for i in ch.json()["items"])
    em = client.get("/v1/embedding-plugins", headers=auth_headers)
    assert em.status_code == 200
    assert any(i["runtime"] == "stub" for i in em.json()["items"])
    inst = client.post(
        "/v1/embedding-plugins/embed-openai-compatible/install",
        headers=auth_headers,
    )
    assert inst.status_code == 200


def test_plugins_catalog_includes_new_kinds(client, auth_headers):
    r = client.get("/v1/plugins", headers=auth_headers)
    assert r.status_code == 200
    kinds = {i["kind"] for i in r.json()["items"]}
    assert "parser" in kinds
    assert "connector" in kinds
    assert "widget" in kinds
    assert "channel" in kinds
    assert "embedding" in kinds
