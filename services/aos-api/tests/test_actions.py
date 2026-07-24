def test_list_action_types(client, auth_headers):
    r = client.get("/v1/actions/types", headers=auth_headers)
    assert r.status_code == 200
    assert any(i["id"] == "CloseWorkOrder" for i in r.json()["items"])


def test_get_and_put_action_type(client, auth_headers):
    g = client.get("/v1/actions/types/CloseWorkOrder", headers=auth_headers)
    assert g.status_code == 200
    body = g.json()
    assert body["id"] == "CloseWorkOrder"
    new_name = body["name"] + " ·95"
    put = client.put(
        "/v1/actions/types/CloseWorkOrder",
        headers=auth_headers,
        json={
            "id": "CloseWorkOrder",
            "name": new_name,
            "objectType": body["objectType"],
            "parameters": body["parameters"],
            "requiredMarkings": body["requiredMarkings"],
            "submissionCriteria": body.get("submissionCriteria") or [],
        },
    )
    assert put.status_code == 200
    assert put.json()["name"] == new_name
    listed = client.get("/v1/actions/types", headers=auth_headers)
    hit = next(i for i in listed.json()["items"] if i["id"] == "CloseWorkOrder")
    assert hit["name"] == new_name
    # restore
    client.put(
        "/v1/actions/types/CloseWorkOrder",
        headers=auth_headers,
        json={
            "id": "CloseWorkOrder",
            "name": body["name"],
            "objectType": body["objectType"],
            "parameters": body["parameters"],
            "requiredMarkings": body["requiredMarkings"],
            "submissionCriteria": body.get("submissionCriteria") or [],
        },
    )
