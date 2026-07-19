def test_model_routes_and_tools_config(client, auth_headers):
    g = client.get("/v1/aip/model-routes", headers=auth_headers)
    assert g.status_code == 200
    items = g.json()["items"]
    assert len(items) >= 1
    items[0]["primary"] = "test-model-primary"
    p = client.put("/v1/aip/model-routes", headers=auth_headers, json={"items": items})
    assert p.status_code == 200
    g2 = client.get("/v1/aip/model-routes", headers=auth_headers)
    assert g2.json()["items"][0]["primary"] == "test-model-primary"
    d = client.post("/v1/aip/model-routes/circuit-drill", headers=auth_headers, json={"items": items})
    assert d.status_code == 200
    assert d.json().get("ok") is True

    tc = client.get("/v1/aip/tools/config", headers=auth_headers)
    assert tc.status_code == 200
    body = tc.json()
    body["mode"] = "prompted"
    body["categories"] = ["action", "query"]
    put = client.put("/v1/aip/tools/config", headers=auth_headers, json=body)
    assert put.status_code == 200
    assert put.json()["mode"] == "prompted"
    tc2 = client.get("/v1/aip/tools/config", headers=auth_headers)
    assert tc2.json()["mode"] == "prompted"
    assert "action" in tc2.json()["categories"]
