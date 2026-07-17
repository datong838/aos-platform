from aos_api.constitution import lint_object_type


def test_constitution_lint_ok():
    r = lint_object_type(
        {
            "id": "WorkOrder",
            "published": True,
            "properties": [{"name": "title"}],
        }
    )
    assert r["ok"] is True


def test_constitution_lint_blocks_publish():
    r = lint_object_type({"id": "bad", "published": True, "properties": []})
    assert r["ok"] is False
    assert any(e["rule"] == "C-PROP-01" for e in r["errors"])


def test_constitution_endpoint(client, auth_headers):
    r = client.post(
        "/v1/ontology/constitution/lint",
        headers=auth_headers,
        json={"id": "X", "published": True, "properties": []},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is False


def test_graph_health(client, auth_headers):
    r = client.get("/v1/ontology/graph-health", headers=auth_headers)
    assert r.status_code == 200
    assert "score" in r.json()
    assert r.json()["metrics"]["engine"] == "adjacency_table"


def test_branches(client, auth_headers):
    r = client.get("/v1/ontology/branches", headers=auth_headers)
    assert r.status_code == 200
    ids = [i["id"] for i in r.json()["items"]]
    assert "main" in ids


def test_object_sets_pg_source(client, auth_headers):
    r = client.post(
        "/v1/object-sets/query",
        headers=auth_headers,
        json={
            "objectType": "WorkOrder",
            "source": "pg",
            "filters": [{"field": "site", "value": "DC-East"}],
            "page": 1,
            "pageSize": 10,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "pg"
    assert body["total"] == 2
