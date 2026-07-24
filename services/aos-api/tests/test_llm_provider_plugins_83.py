def test_llm_provider_plugins_catalog_and_install(client, auth_headers):
    g = client.get("/v1/aip/llm-provider-plugins", headers=auth_headers)
    assert g.status_code == 200
    body = g.json()
    assert body["totals"]["all"] >= 30
    ids = {i["id"] for i in body["items"]}
    assert "deepseek" in ids
    assert "openai" in ids
    assert "kling-video" in ids

    inst = client.post("/v1/aip/llm-provider-plugins/deepseek/install", headers=auth_headers)
    assert inst.status_code == 200
    assert inst.json()["installed"] is True
    g2 = client.get("/v1/aip/llm-provider-plugins", headers=auth_headers)
    deep = next(i for i in g2.json()["items"] if i["id"] == "deepseek")
    assert deep["installed"] is True

    pub = client.put(
        "/v1/aip/llm-provider-plugins/custom",
        headers=auth_headers,
        json={
            "id": "corp-test-llm",
            "name": "Corp Test",
            "nameZh": "企业测试模型",
            "tier": "mid",
            "modalities": ["text"],
            "formFamily": "openai_compatible",
        },
    )
    assert pub.status_code == 200
    assert pub.json()["item"]["id"] == "corp-test-llm"

    plugins = client.get("/v1/plugins", headers=auth_headers)
    assert plugins.status_code == 200
    kinds = {i.get("kind") for i in plugins.json()["items"]}
    assert "llm-provider" in kinds
