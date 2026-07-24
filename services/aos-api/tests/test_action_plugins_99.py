def test_list_action_plugins(client, auth_headers):
    r = client.get("/v1/action-plugins", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    ids = {i["id"] for i in items}
    assert "close-work-order" in ids
    assert "update-wiki-card" in ids
    assert "assign-work-order" in ids
    required = [i for i in items if i["id"] in ("close-work-order", "update-wiki-card")]
    assert all(i["installed"] for i in required)
    assert all(i.get("actionTypeId") for i in required)


def test_seed_from_plugins_into_action_types(client, auth_headers):
    # ensure_action_schema 经 list types 触发
    listed = client.get("/v1/actions/types", headers=auth_headers)
    assert listed.status_code == 200
    type_ids = {i["id"] for i in listed.json()["items"]}
    assert "CloseWorkOrder" in type_ids
    assert "UpdateWikiCard" in type_ids


def test_install_assign_work_order_plugin(client, auth_headers):
    inst = client.post(
        "/v1/action-plugins/assign-work-order/install",
        headers=auth_headers,
    )
    assert inst.status_code == 200
    assert inst.json().get("actionTypeId") == "AssignWorkOrder"
    listed = client.get("/v1/actions/types", headers=auth_headers)
    assert any(i["id"] == "AssignWorkOrder" for i in listed.json()["items"])


def test_plugins_catalog_has_action_template(client, auth_headers):
    r = client.get("/v1/plugins", headers=auth_headers)
    assert r.status_code == 200
    kinds = {i["kind"] for i in r.json()["items"]}
    assert "action-template" in kinds
