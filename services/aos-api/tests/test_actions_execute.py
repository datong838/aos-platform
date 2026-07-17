def test_execute_requires_idempotency_key(client, auth_headers):
    r = client.post(
        "/v1/actions/execute",
        headers=auth_headers,
        json={"actionTypeId": "CloseWorkOrder", "payload": {"reason": "x"}},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "MISSING_IDEMPOTENCY_KEY"


def test_execute_hitl_creates_draft_only(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "exec-hitl-1"}
    r = client.post(
        "/v1/actions/execute",
        headers=headers,
        json={
            "actionTypeId": "CloseWorkOrder",
            "objectType": "WorkOrder",
            "objectId": "wo-exec-hitl",
            "payload": {"reason": "need-review", "status": "pending"},
            "autoApprove": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["productionWritten"] is False
    assert body["status"] == "proposed"
    assert body["route"] == "actions.execute"
    obj = client.get("/v1/objects/WorkOrder/wo-exec-hitl", headers=auth_headers)
    assert obj.status_code == 404


def test_execute_draft_id_writes(client, auth_headers):
    create = client.post(
        "/v1/aip/drafts",
        headers=auth_headers,
        json={
            "actionTypeId": "CloseWorkOrder",
            "objectType": "WorkOrder",
            "objectId": "wo-exec-approve",
            "proposed": {"reason": "via-execute", "status": "closed"},
        },
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]
    headers = {**auth_headers, "Idempotency-Key": f"exec-appr-{draft_id}"}
    r = client.post(
        "/v1/actions/execute",
        headers=headers,
        json={"draftId": draft_id},
    )
    assert r.status_code == 200
    assert r.json()["productionWritten"] is True
    assert r.json()["via"] == "draftId"
    obj = client.get("/v1/objects/WorkOrder/wo-exec-approve", headers=auth_headers)
    assert obj.json()["status"] == "closed"
    # replay
    r2 = client.post(
        "/v1/actions/execute",
        headers=headers,
        json={"draftId": draft_id},
    )
    assert r2.json().get("idempotentReplay") is True


def test_execute_auto_approve(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "exec-auto-1"}
    r = client.post(
        "/v1/actions/execute",
        headers=headers,
        json={
            "actionTypeId": "CloseWorkOrder",
            "objectType": "WorkOrder",
            "objectId": "wo-exec-auto",
            "payload": {"reason": "auto", "status": "closed"},
            "autoApprove": True,
        },
    )
    assert r.status_code == 200
    assert r.json()["productionWritten"] is True
    assert r.json()["via"] == "autoApprove"
    obj = client.get("/v1/objects/WorkOrder/wo-exec-auto", headers=auth_headers)
    assert obj.json()["status"] == "closed"
