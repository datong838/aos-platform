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
    body = r.json()
    assert "score" in body
    assert body["metrics"]["engine"] == "adjacency_table"
    assert "danglingEdges" in body["metrics"]
    assert "propConflicts" in body["metrics"]
    assert "issues" in body
    # GH-02 must not be frontend-hardcoded; server may emit 0 issues
    assert all("code" in i for i in body["issues"])


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
    # seed has ≥2 DC-East; PG may accumulate extras from demo smoke — assert filter semantics
    assert body["total"] >= 2
    assert all(i.get("site") == "DC-East" for i in body["items"])
