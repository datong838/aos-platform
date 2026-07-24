from aos_api.submission import evaluate_criteria


def test_criteria_required_pass():
    r = evaluate_criteria([{"field": "reason", "op": "required"}], {"reason": "done"})
    assert r["ok"] is True


def test_criteria_required_fail():
    r = evaluate_criteria([{"field": "reason", "op": "required"}], {})
    assert r["ok"] is False


def test_validate_endpoint_rejects(client, auth_headers):
    r = client.post(
        "/v1/actions/validate",
        headers=auth_headers,
        json={"actionTypeId": "CloseWorkOrder", "payload": {}},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "VALIDATION"


def test_validate_endpoint_ok(client, auth_headers):
    r = client.post(
        "/v1/actions/validate",
        headers=auth_headers,
        json={"actionTypeId": "CloseWorkOrder", "payload": {"reason": "fixed"}},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_draft_create_requires_criteria(client, auth_headers):
    r = client.post(
        "/v1/aip/drafts",
        headers=auth_headers,
        json={
            "actionTypeId": "CloseWorkOrder",
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "proposed": {},
        },
    )
    assert r.status_code == 400


def test_draft_crud_isolated_from_production(client, auth_headers):
    r = client.post(
        "/v1/aip/drafts",
        headers=auth_headers,
        json={
            "actionTypeId": "CloseWorkOrder",
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "proposed": {"reason": "done", "status": "closed"},
            "title": "close wo-1001",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "proposed"
    assert body["productionWritten"] is False
    draft_id = body["id"]

    listed = client.get("/v1/aip/drafts", headers=auth_headers)
    assert any(i["id"] == draft_id for i in listed.json()["items"])

    got = client.get(f"/v1/aip/drafts/{draft_id}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["proposed"]["reason"] == "done"

    # production object unchanged
    obj = client.get("/v1/objects/WorkOrder/wo-1001", headers=auth_headers)
    assert obj.json().get("status") != "closed"

    rej = client.post(f"/v1/aip/drafts/{draft_id}/reject", headers=auth_headers)
    assert rej.status_code == 200
    assert rej.json()["status"] == "rejected"
