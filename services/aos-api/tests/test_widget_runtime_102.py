def test_stub_widget_enters_palette_after_install(client, auth_headers):
    """102 回归：无剩余默认 stub 调色板项时，install 任意可选插件仍进 palette。
    metric-card 已由 108 升为 metric；此处验证 install 路径仍可用。
    """
    before = client.get("/v1/widget-plugins", headers=auth_headers)
    assert before.status_code == 200

    inst = client.post("/v1/widget-plugins/metric-card/install", headers=auth_headers)
    assert inst.status_code == 200

    after = client.get("/v1/widget-plugins", headers=auth_headers)
    assert after.status_code == 200
    palette = after.json().get("palette") or []
    hit = [p for p in palette if (p.get("pluginId") or p.get("id")) == "metric-card"]
    assert hit, "metric-card should appear in palette after install"
    assert hit[0]["kind"] == "metric"
    assert hit[0].get("runtime") == "inproc"


def test_p0_widgets_still_in_default_palette(client, auth_headers):
    r = client.get("/v1/widget-plugins", headers=auth_headers)
    assert r.status_code == 200
    kinds = {p["kind"] for p in r.json().get("palette") or []}
    assert "filter" in kinds
    assert "table" in kinds
    assert "buddy" in kinds
    assert "overlay" in kinds
