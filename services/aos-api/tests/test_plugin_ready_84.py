def test_plugin_enable_appears_in_models(client, auth_headers):
    en = client.post("/v1/aip/llm-provider-plugins/deepseek/enable", headers=auth_headers)
    assert en.status_code == 200
    assert en.json()["ready"] is True
    models = client.get("/v1/aip/models", headers=auth_headers)
    assert models.status_code == 200
    ids = {m["id"] for m in models.json()["items"]}
    assert "deepseek-chat" in ids or "deepseek-reasoner" in ids

    dis = client.post("/v1/aip/llm-provider-plugins/deepseek/disable", headers=auth_headers)
    assert dis.status_code == 200
    models2 = client.get("/v1/aip/models", headers=auth_headers)
    ids2 = {m["id"] for m in models2.json()["items"]}
    # after disable plugin models should not remain (unless also runtime)
    assert "deepseek-chat" not in ids2
