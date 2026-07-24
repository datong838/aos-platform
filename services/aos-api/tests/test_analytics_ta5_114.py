"""114 · TA.5 analytics writeback propose → Draft (no self-approve)."""


def test_propose_creates_draft_not_production(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "ta5-propose-1"}
    r = client.post(
        "/v1/analytics/writeback/propose",
        headers=headers,
        json={
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "actionTypeId": "CloseWorkOrder",
            "proposed": {"reason": "from-analytics-test", "status": "closed"},
            "autoApprove": False,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["mode"] == "ta5-writeback"
    assert body["status"] == "proposed"
    assert body["productionWritten"] is False
    assert body["id"]
    assert body["approvePath"] == "/aip/drafts"

    # object not yet rewritten by propose alone (status may already be anything;
    # critical: draft exists and productionWritten false)
    g = client.get(f"/v1/aip/drafts/{body['id']}", headers=auth_headers)
    assert g.status_code == 200
    assert g.json()["status"] == "proposed"


def test_propose_rejects_auto_approve(client, auth_headers):
    r = client.post(
        "/v1/analytics/writeback/propose",
        headers={**auth_headers, "Idempotency-Key": "ta5-auto"},
        json={
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "proposed": {"reason": "x"},
            "autoApprove": True,
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == "ANALYTICS_SELF_APPROVE_FORBIDDEN"


def test_propose_requires_idempotency_key(client, auth_headers):
    r = client.post(
        "/v1/analytics/writeback/propose",
        headers=auth_headers,
        json={
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "proposed": {"reason": "x"},
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == "MISSING_IDEMPOTENCY_KEY"


def test_propose_idempotent_replay(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "ta5-replay"}
    body = {
        "objectType": "WorkOrder",
        "objectId": "wo-1001",
        "proposed": {"reason": "replay", "status": "open"},
    }
    a = client.post("/v1/analytics/writeback/propose", headers=headers, json=body)
    b = client.post("/v1/analytics/writeback/propose", headers=headers, json=body)
    assert a.status_code == 201
    assert b.status_code == 201
    assert a.json()["id"] == b.json()["id"]
    assert b.json().get("idempotentReplay") is True


def test_approve_after_propose_writes_lineage(client, auth_headers):
    """Full loop: propose (analytics) → approve (inbox path) → lineage."""
    prop = client.post(
        "/v1/analytics/writeback/propose",
        headers={**auth_headers, "Idempotency-Key": "ta5-loop-p"},
        json={
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "proposed": {"reason": "ta5-loop", "status": "closed"},
        },
    )
    assert prop.status_code == 201
    draft_id = prop.json()["id"]
    appr = client.post(
        f"/v1/aip/drafts/{draft_id}/approve",
        headers={**auth_headers, "Idempotency-Key": "ta5-loop-a", "X-Allow-Conflicts": "1"},
    )
    assert appr.status_code == 200, appr.text
    body = appr.json()
    assert body.get("productionWritten") is True or body.get("status") == "approved"
    assert body.get("lineageId") or body.get("lineage") or "lineage" in str(body).lower()
