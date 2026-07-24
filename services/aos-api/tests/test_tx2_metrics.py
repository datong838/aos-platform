from aos_api.metrics import normalize_path, parse_traceparent, reset_metrics


def test_normalize_path():
    assert normalize_path("/v1/objects/WorkOrder/wo-1") == "/v1/objects/{object_type}/{object_id}"
    assert normalize_path("/v1/health") == "/v1/health"


def test_parse_traceparent():
    tid = "0af7651916cd43dd8448eb211c80319c"
    assert parse_traceparent(f"00-{tid}-b7ad6b7169203331-01") == tid
    assert parse_traceparent("bad") is None


def test_metrics_json_and_prom(client, auth_headers):
    reset_metrics()
    assert client.get("/v1/health").status_code == 200
    assert client.get("/v1/health").status_code == 200
    r = client.get("/v1/metrics", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["count"] >= 2
    health_rows = [
        x
        for x in body["requests"]
        if x["path"] == "/v1/health" and x["method"] == "GET"
    ]
    assert health_rows
    assert sum(x["count"] for x in health_rows) >= 2

    prom = client.get("/v1/metrics?format=prom", headers=auth_headers)
    assert prom.status_code == 200
    assert "aos_http_requests_total" in prom.text
    assert 'path="/v1/health"' in prom.text


def test_metrics_requires_auth(client):
    r = client.get("/v1/metrics")
    assert r.status_code == 401


def test_traceparent_header(client):
    tid = "0af7651916cd43dd8448eb211c80319c"
    r = client.get(
        "/v1/health",
        headers={"traceparent": f"00-{tid}-b7ad6b7169203331-01"},
    )
    assert r.status_code == 200
    assert r.headers.get("X-Trace-Id") == tid
