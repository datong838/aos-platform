def test_module_not_found(client, auth_headers):
    r = client.get("/v1/modules/does-not-exist/runtime", headers=auth_headers)
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


def test_object_not_found(client, auth_headers):
    r = client.get("/v1/objects/WorkOrder/missing", headers=auth_headers)
    assert r.status_code == 404
    assert r.json()["code"] == "NOT_FOUND"


def test_create_object_type_ok(client, auth_headers):
    oid = "AssetX"
    # cleanup if re-run
    from aos_api.db import connect

    with connect() as conn:
        conn.execute("DELETE FROM meta_object_type WHERE id=%s", (oid,))
        conn.commit()
    r = client.post(
        "/v1/ontology/object-types",
        headers=auth_headers,
        json={
            "id": oid,
            "name": "资产",
            "publish": True,
            "properties": [{"name": "code", "type": "string"}],
        },
    )
    assert r.status_code == 200
    assert r.json()["id"] == oid
    listed = client.get("/v1/ontology/object-types", headers=auth_headers)
    assert any(i["id"] == oid for i in listed.json()["items"])
