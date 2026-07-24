"""AI OS substance — models · plugins · tools · modules."""


def test_plugins_catalog(client, auth_headers):
    r = client.get("/v1/plugins", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["all"] >= 4
    kinds = {i["kind"] for i in body["items"]}
    assert "tool" in kinds
    assert "parser" in kinds


def test_models_list(client, auth_headers):
    r = client.get("/v1/aip/models", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert items[0]["id"]


def test_tool_invoke_query_objects(client, auth_headers):
    r = client.post(
        "/v1/aip/tools/query.objects/invoke",
        headers=auth_headers,
        json={"objectType": "WorkOrder"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["result"]["total"] >= 1


def test_chat_with_tools_executes(client, auth_headers):
    r = client.post(
        "/v1/aip/chat",
        headers=auth_headers,
        json={"query": "list work orders", "withTools": True, "tools": ["query.objects"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["toolCalls"]
    assert body["toolCalls"][0]["toolId"] == "query.objects"
    assert body["toolCalls"][0].get("ok") is True
    assert "tools executed" in body["answer"]


def test_module_entry_path_and_runtime(client, auth_headers):
    listed = client.get("/v1/modules", headers=auth_headers)
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(m.get("entryPath") for m in items)
    mid = next(m["id"] for m in items if m.get("entryPath"))
    rt = client.get(f"/v1/modules/{mid}/runtime", headers=auth_headers)
    assert rt.status_code == 200
    assert rt.json()["entryPath"]


def test_capability_job_media(client, auth_headers):
    client.post(
        "/v1/aip/capabilities",
        headers=auth_headers,
        json={"id": "cap-os-demo", "kind": "job"},
    )
    job = client.post(
        "/v1/aip/capabilities/cap-os-demo/submit",
        headers=auth_headers,
        json={"capabilityId": "cap-os-demo", "input": {}},
    )
    assert job.status_code == 200
    rid = job.json()["artifact"]["mediaRid"]
    media = client.get(f"/v1/media-sets/{rid}", headers=auth_headers)
    assert media.status_code == 200
    assert media.json()["fromCapability"] == "cap-os-demo"
