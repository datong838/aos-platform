"""107 · Canvas Action Form → execute HITL Draft contract."""


def test_canvas_style_execute_creates_hitl_draft(client, auth_headers):
    """画布提交体：autoApprove=false · Idempotency-Key · 不写生产。"""
    headers = {**auth_headers, "Idempotency-Key": "canvas-af-test-107"}
    r = client.post(
        "/v1/actions/execute",
        headers=headers,
        json={
            "actionTypeId": "CloseWorkOrder",
            "objectType": "WorkOrder",
            "objectId": "wo-canvas-107",
            "payload": {"reason": "from-canvas", "status": "pending"},
            "proposed": {"reason": "from-canvas", "status": "pending"},
            "autoApprove": False,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("productionWritten") is False
    assert body.get("status") == "proposed"
    assert body.get("via") in ("hitl-draft", "actions.execute") or body.get("route") == "actions.execute"
    assert body.get("id")
    obj = client.get("/v1/objects/WorkOrder/wo-canvas-107", headers=auth_headers)
    assert obj.status_code == 404


def test_canvas_style_execute_rejects_missing_key(client, auth_headers):
    r = client.post(
        "/v1/actions/execute",
        headers=auth_headers,
        json={
            "actionTypeId": "CloseWorkOrder",
            "objectType": "WorkOrder",
            "objectId": "wo-canvas-nokey",
            "payload": {"reason": "x"},
            "autoApprove": False,
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == "MISSING_IDEMPOTENCY_KEY"
