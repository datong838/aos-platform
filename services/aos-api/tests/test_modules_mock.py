def test_list_modules_mock(client, auth_headers):
    r = client.get("/v1/modules", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert any(i["id"] == "mod-ops-inbox" for i in items)


def test_module_components_field(client, auth_headers):
    r = client.get("/v1/modules", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    order_mod = next((i for i in items if i["id"] == "mod-order-management"), None)
    assert order_mod is not None, "订单管理模块不存在"
    assert "components" in order_mod, "缺少 components 字段"
    assert isinstance(order_mod["components"], dict), "components 不是对象"
    assert "root" in order_mod["components"], "缺少 root 节点"
    assert order_mod["components"]["root"]["type"] == "page-layout", "root 类型不对"


def test_order_components_field_keys_match_order_api(client, auth_headers):
    """契约：_ORDER_COMPONENTS 中 object-table.columns 的 key 必须出现在 /v1/objects/Order 字段集合里"""
    mod = client.get("/v1/modules/mod-order-management", headers=auth_headers).json()
    table_cols = mod["components"]["order-table"]["config"]["columns"]
    col_keys = {c["key"] for c in table_cols}

    obj = client.get("/v1/objects/Order", headers=auth_headers).json()
    items = obj.get("items") or obj.get("objects") or []
    assert items, "Order 种子数据为空，无法验证字段契约"
    api_keys = set(items[0].keys())

    missing = col_keys - api_keys
    assert not missing, f"order-table.columns 配置的 key 不在 Order API 返回字段里: {missing}"


def test_order_components_drawer_field_keys_match_order_api(client, auth_headers):
    """契约：detail-drawer sections 中 field.key 必须出现在 /v1/objects/Order 字段里"""
    mod = client.get("/v1/modules/mod-order-management", headers=auth_headers).json()
    sections = mod["components"]["detail-drawer"]["config"]["sections"]
    field_keys: set[str] = set()
    for s in sections:
        if s.get("type") == "table":
            continue
        for f in s.get("fields") or []:
            field_keys.add(f["key"])

    obj = client.get("/v1/objects/Order", headers=auth_headers).json()
    items = obj.get("items") or obj.get("objects") or []
    api_keys = set(items[0].keys())

    missing = field_keys - api_keys
    assert not missing, f"detail-drawer 配置的 key 不在 Order API 返回字段里: {missing}"


def test_order_components_has_trend_chart(client, auth_headers):
    """契约：root.children 必须包含 trend-chart，且 components['trend-chart'].type == 'trend-chart'"""
    mod = client.get("/v1/modules/mod-order-management", headers=auth_headers).json()
    comps = mod["components"]
    assert "trend-chart" in comps["root"]["children"], "root.children 缺少 trend-chart"
    assert comps["trend-chart"]["type"] == "trend-chart"
    assert comps["trend-chart"]["config"]["objectType"] == "Order"
    assert comps["trend-chart"]["config"]["dateField"] == "order_date"


def test_order_components_stat_revenue_uses_total_amount(client, auth_headers):
    """契约：营收总额卡片用 total_amount 求和，而不是 amount"""
    mod = client.get("/v1/modules/mod-order-management", headers=auth_headers).json()
    stat_revenue = mod["components"]["stat-revenue"]["config"]
    assert stat_revenue["field"] == "total_amount", "营收字段必须用 total_amount（对齐 Order API）"


def test_order_components_stat_pending_includes_paid(client, auth_headers):
    """契约：待处理卡片 filter 必须是 in op + 同时包含 pending 和 paid（对齐 OrderManagementPage）"""
    mod = client.get("/v1/modules/mod-order-management", headers=auth_headers).json()
    stat_pending = mod["components"]["stat-pending"]["config"]
    f = stat_pending["filter"]
    assert f.get("op") == "in", "待处理卡片 filter op 必须是 in"
    assert "pending" in f["value"] and "paid" in f["value"], "待处理必须包含 pending + paid"


def test_order_components_stat_filters_have_explicit_op(client, auth_headers):
    """契约：所有 stat-card 的 filter 必须显式声明 op（eq/in）"""
    mod = client.get("/v1/modules/mod-order-management", headers=auth_headers).json()
    for key in ("stat-total", "stat-pending", "stat-shipped", "stat-revenue"):
        cfg = mod["components"][key]["config"]
        f = cfg.get("filter")
        if f:
            assert "op" in f, f"{key} filter 缺少 op 字段"
            assert f["op"] in ("eq", "in"), f"{key} filter op 必须是 eq/in"


def test_module_runtime_includes_components(client, auth_headers):
    r = client.get("/v1/modules/mod-order-management/runtime", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["moduleId"] == "mod-order-management"
    assert "layout" in body
    assert "components" in body["layout"], "runtime layout 缺少 components"
    assert isinstance(body["layout"]["components"], dict)
    assert "root" in body["layout"]["components"]


def test_module_update_components(client, auth_headers):
    r = client.patch(
        "/v1/modules/mod-order-management",
        headers=auth_headers,
        json={"components": {"root": {"type": "page-layout", "children": ["foo"]}}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["components"]["root"]["children"] == ["foo"]


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
