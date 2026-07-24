"""116 · TA.7 analytics demo story: read → propose → approve → lineage."""


def test_run_analytics_story(client, auth_headers):
    client.post("/v1/demo/ensure-seed", headers=auth_headers)
    r = client.post("/v1/demo/run-analytics-story", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "ta7-analytics-story"
    assert body["productionWritten"] is True
    assert body["objectId"] == "wo-1001"
    assert body["draftId"]
    assert body["lineageId"]
    assert int((body.get("read") or {}).get("total") or 0) >= 1
    assert body["before"]["status"] != body["after"]["status"]
    assert (body.get("exportProbePublic") or {}).get("expected") is True
    assert (body.get("exportProbePublic") or {}).get("code") == "ANALYTICS_EXPORT_FORBIDDEN"
    assert body["uiPaths"]["analytics"] == "/analytics"


def test_demo_story_lists_ta7_step(client, auth_headers):
    s = client.get("/v1/demo/story", headers=auth_headers)
    assert s.status_code == 200
    story = s.json()
    steps = story.get("steps") or []
    assert any(st.get("id") == "TA.7" for st in steps)
    assert story["deferred"]["analyticsNotebook"] is False
    assert story["deferred"]["apolloOps"] is False


def test_analytics_propose_still_forbids_self_approve(client, auth_headers):
    """Product path must remain HITL-only after TA.7 demo story lands."""
    r = client.post(
        "/v1/analytics/writeback/propose",
        headers={**auth_headers, "Idempotency-Key": "ta7-self-approve-guard"},
        json={
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "actionTypeId": "CloseWorkOrder",
            "autoApprove": True,
            "proposed": {"reason": "should-fail", "status": "closed"},
        },
    )
    assert r.status_code == 400
    assert r.json()["code"] == "ANALYTICS_SELF_APPROVE_FORBIDDEN"
