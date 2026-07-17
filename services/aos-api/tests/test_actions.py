def test_list_action_types(client, auth_headers):
    r = client.get("/v1/actions/types", headers=auth_headers)
    assert r.status_code == 200
    assert any(i["id"] == "CloseWorkOrder" for i in r.json()["items"])
