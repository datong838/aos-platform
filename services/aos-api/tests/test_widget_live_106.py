def test_action_form_and_graph_live_kinds(client, auth_headers):
    """106 · install 后 palette 为 action/graph · runtime=inproc。"""
    for pid, kind in (("action-form", "action"), ("graph-view", "graph")):
        inst = client.post(f"/v1/widget-plugins/{pid}/install", headers=auth_headers)
        assert inst.status_code == 200, inst.text

    after = client.get("/v1/widget-plugins", headers=auth_headers)
    assert after.status_code == 200
    palette = after.json().get("palette") or []
    by_id = {p.get("pluginId") or p.get("id"): p for p in palette}

    assert "action-form" in by_id
    assert by_id["action-form"]["kind"] == "action"
    assert by_id["action-form"]["runtime"] == "inproc"
    assert by_id["action-form"].get("stub") is False

    assert "graph-view" in by_id
    assert by_id["graph-view"]["kind"] == "graph"
    assert by_id["graph-view"]["runtime"] == "inproc"
    assert by_id["graph-view"].get("stub") is False


def test_metric_card_still_stub(client, auth_headers):
    """已由 108 升为 metric · 保留函数名作兼容别名。"""
    client.post("/v1/widget-plugins/metric-card/install", headers=auth_headers)
    after = client.get("/v1/widget-plugins", headers=auth_headers)
    palette = after.json().get("palette") or []
    hit = [p for p in palette if (p.get("pluginId") or p.get("id")) == "metric-card"]
    assert hit
    assert hit[0]["kind"] == "metric"
    assert hit[0].get("runtime") == "inproc"
    assert hit[0].get("stub") is False


def test_neighbors_still_ok_for_graph_widget(client, auth_headers):
    r = client.get("/v1/objects/WorkOrder/wo-1001/neighbors", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert body.get("engine") == "adjacency_table"


def test_validate_still_ok_for_action_form(client, auth_headers):
    types = client.get("/v1/actions/types", headers=auth_headers)
    assert types.status_code == 200
    items = types.json().get("items") or types.json()
    if isinstance(items, list) and items:
        aid = items[0].get("id") or "CloseWorkOrder"
    else:
        aid = "CloseWorkOrder"
    r = client.post(
        "/v1/actions/validate",
        headers=auth_headers,
        json={"actionTypeId": aid, "payload": {"reason": "ok"}},
    )
    # may be 200 or 400 depending on criteria — must not 404/500
    assert r.status_code in (200, 400), r.text
