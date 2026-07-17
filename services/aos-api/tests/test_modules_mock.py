def test_list_modules_mock(client, auth_headers):
    r = client.get("/v1/modules", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert any(i["id"] == "mod-ops-inbox" for i in items)


def test_module_runtime(client, auth_headers):
    r = client.get("/v1/modules/mod-ops-inbox/runtime", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["moduleId"] == "mod-ops-inbox"
    assert body["variables"]["selectionLimit"] == 10


def test_object_sets_query_and_filter(client, auth_headers):
    r = client.post(
        "/v1/object-sets/query",
        headers=auth_headers,
        json={"filters": [{"field": "site", "value": "DC-East"}], "page": 1, "pageSize": 10},
    )
    assert r.status_code == 200
    body = r.json()
    # seed has ≥2 DC-East; PG may accumulate extras — assert filter semantics
    assert body["total"] >= 2
    assert body["selectionLimit"] == 10
    assert all(i["site"] == "DC-East" for i in body["items"])


def test_object_sets_filters_over_limit(client, auth_headers):
    filters = [{"field": f"f{i}", "value": i} for i in range(11)]
    r = client.post(
        "/v1/object-sets/query",
        headers=auth_headers,
        json={"filters": filters, "page": 1, "pageSize": 10},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION"


def test_validation_error_shape(client, auth_headers):
    r = client.post("/v1/buddy/ask", headers=auth_headers, json={})
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION"
    assert "traceId" in r.json()
