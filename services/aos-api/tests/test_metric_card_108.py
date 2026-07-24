def test_metric_card_live_kind(client, auth_headers):
    """108 · metric-card 升为 metric / inproc。"""
    inst = client.post("/v1/widget-plugins/metric-card/install", headers=auth_headers)
    assert inst.status_code == 200, inst.text
    after = client.get("/v1/widget-plugins", headers=auth_headers)
    assert after.status_code == 200
    palette = after.json().get("palette") or []
    hit = [p for p in palette if (p.get("pluginId") or p.get("id")) == "metric-card"]
    assert hit, "metric-card should be in palette"
    assert hit[0]["kind"] == "metric"
    assert hit[0].get("runtime") == "inproc"
    assert hit[0].get("stub") is False


def test_object_sets_query_for_metric(client, auth_headers):
    r = client.post(
        "/v1/object-sets/query",
        headers=auth_headers,
        json={"objectType": "WorkOrder", "filters": [], "page": 1, "pageSize": 50, "source": "pg"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
