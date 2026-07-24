def test_list_object_types(client, auth_headers):
    r = client.get("/v1/ontology/object-types", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["id"] == "WorkOrder" for i in items)


def test_list_and_get_object(client, auth_headers):
    r = client.get("/v1/objects/WorkOrder", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    oid = r.json()["items"][0]["id"]
    d = client.get(f"/v1/objects/WorkOrder/{oid}", headers=auth_headers)
    assert d.status_code == 200
    assert d.json()["id"] == oid


def test_neighbors_adjacency(client, auth_headers):
    r = client.get("/v1/objects/WorkOrder/wo-1001/neighbors", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "adjacency_table"
    assert any(i["id"] == "wo-1003" for i in body["items"])


def test_wiki_and_funnel(client, auth_headers):
    w = client.get("/v1/wiki/WorkOrder/wo-1001", headers=auth_headers)
    assert w.status_code == 200
    assert "summary" in w.json()["body"]
    f = client.get("/v1/funnel/WorkOrder/status", headers=auth_headers)
    assert f.status_code == 200
    assert f.json()["stage"]


def test_publish_gate_requires_properties(client, auth_headers):
    r = client.post(
        "/v1/ontology/object-types",
        headers=auth_headers,
        json={"id": "EmptyPub", "name": "x", "publish": True, "properties": []},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "BACKING_NOT_UNIQUE"


def test_put_object_type_properties(client, auth_headers):
    created = client.post(
        "/v1/ontology/object-types",
        headers=auth_headers,
        json={
            "id": "Ot95Edit",
            "name": "OT95",
            "description": "before",
            "publish": False,
            "properties": [{"name": "id", "type": "string"}],
        },
    )
    assert created.status_code == 200
    put = client.put(
        "/v1/ontology/object-types/Ot95Edit",
        headers=auth_headers,
        json={
            "name": "OT95 updated",
            "description": "after",
            "properties": [
                {"name": "id", "type": "string"},
                {"name": "title", "type": "string"},
            ],
            "publish": False,
        },
    )
    assert put.status_code == 200
    assert put.json()["name"] == "OT95 updated"
    assert len(put.json()["properties"]) == 2
    got = client.get("/v1/ontology/object-types/Ot95Edit", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["description"] == "after"
    assert any(p["name"] == "title" for p in got.json()["properties"])


def test_put_object_type_publish_empty_props_422(client, auth_headers):
    client.post(
        "/v1/ontology/object-types",
        headers=auth_headers,
        json={
            "id": "Ot95Empty",
            "name": "empty",
            "publish": False,
            "properties": [{"name": "id", "type": "string"}],
        },
    )
    r = client.put(
        "/v1/ontology/object-types/Ot95Empty",
        headers=auth_headers,
        json={"name": "empty", "description": "", "properties": [], "publish": True},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "BACKING_NOT_UNIQUE"
