def test_approve_writes_production(client, auth_headers):
    create = client.post(
        "/v1/aip/drafts",
        headers=auth_headers,
        json={
            "actionTypeId": "CloseWorkOrder",
            "objectType": "WorkOrder",
            "objectId": "wo-new-approve",
            "proposed": {"reason": "closed-by-test", "status": "closed"},
        },
    )
    assert create.status_code == 201
    draft_id = create.json()["id"]
    key = {"Idempotency-Key": f"approve-{draft_id}"}
    headers = {**auth_headers, **key}
    a1 = client.post(f"/v1/aip/drafts/{draft_id}/approve", headers=headers)
    assert a1.status_code == 200
    assert a1.json()["productionWritten"] is True
    obj = client.get("/v1/objects/WorkOrder/wo-new-approve", headers=auth_headers)
    assert obj.json()["status"] == "closed"
    lin = client.get(f"/v1/aip/lineage/{a1.json()['lineageId']}", headers=auth_headers)
    assert lin.status_code == 200
    a2 = client.post(f"/v1/aip/drafts/{draft_id}/approve", headers=headers)
    assert a2.json().get("idempotentReplay") is True


def test_field_conflict_requires_header(client, auth_headers):
    # seed exists wo-1001; propose different site → conflict
    create = client.post(
        "/v1/aip/drafts",
        headers=auth_headers,
        json={
            "actionTypeId": "CloseWorkOrder",
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "proposed": {"reason": "x", "site": "DC-West"},
        },
    )
    draft_id = create.json()["id"]
    blocked = client.post(
        f"/v1/aip/drafts/{draft_id}/approve",
        headers={**auth_headers, "Idempotency-Key": f"c1-{draft_id}"},
    )
    assert blocked.status_code == 409
    forced = client.post(
        f"/v1/aip/drafts/{draft_id}/approve",
        headers={
            **auth_headers,
            "Idempotency-Key": f"c2-{draft_id}",
            "X-Allow-Conflicts": "true",
        },
    )
    assert forced.status_code == 200
    assert "site" in forced.json()["conflicts"]


def test_function_timeout_and_tools(client, auth_headers):
    # normal invoke
    ok = client.post(
        "/v1/functions/invoke",
        headers=auth_headers,
        json={"payload": {"x": 1}, "timeoutSec": 2},
    )
    assert ok.status_code == 200
    tools = client.get("/v1/aip/tools", headers=auth_headers)
    assert any(t["kind"] == "Action" for t in tools.json()["items"])


def test_logic_dry_run_and_wiki_block(client, auth_headers):
    r = client.post(
        "/v1/aip/logic/run",
        headers=auth_headers,
        json={"dryRun": True, "edits": [{"objectType": "WorkOrder", "objectId": "wo-1001", "set": {"a": 1}}]},
    )
    assert r.status_code == 200
    assert r.json()["productionWritten"] is False
    w = client.put("/v1/wiki/WorkOrder/wo-1001", headers=auth_headers, json={"body": {}})
    assert w.status_code == 409


def test_circuit_and_evals(client, auth_headers):
    client.post("/v1/aip/circuit/reset", headers=auth_headers)
    client.post("/v1/aip/evals/set", headers=auth_headers, json={"green": True})
    chat = client.post("/v1/aip/chat", headers=auth_headers, json={"query": "hi"})
    assert chat.status_code == 200
    client.post("/v1/aip/circuit/trip", headers=auth_headers, json={"failureRate": 0.1})
    blocked = client.post("/v1/aip/chat", headers=auth_headers, json={"query": "hi"})
    assert blocked.status_code == 503
    client.post("/v1/aip/circuit/reset", headers=auth_headers)


def test_capability_job_media_pipeline_apollo(client, auth_headers):
    cap = client.post(
        "/v1/aip/capabilities",
        headers=auth_headers,
        json={"id": "video-job", "kind": "job"},
    )
    assert cap.status_code == 200
    job = client.post(
        "/v1/aip/capabilities/video-job/submit",
        headers=auth_headers,
        json={"capabilityId": "video-job", "input": {}},
    )
    assert job.json()["status"] == "succeeded"
    media = client.post(
        "/v1/media-sets",
        headers=auth_headers,
        json={"name": "clip.bin", "bytesBase64": "aGVsbG8="},
    )
    assert "rid" in media.json()
    client.post("/v1/sources", headers=auth_headers, json={"id": "file-1", "type": "file"})
    pipe = client.post(
        "/v1/pipelines",
        headers=auth_headers,
        json={"id": "p1", "sourceId": "file-1"},
    )
    assert pipe.json()["lastBuild"]["status"] == "SUCCEEDED"
    spoke = client.get("/v1/apollo/spokes/local", headers=auth_headers)
    assert spoke.json()["heartbeatOk"] is True
    bundle = client.post(
        "/v1/apollo/assets",
        headers=auth_headers,
        json={"hotfix": True, "contents": ["WorkOrder"]},
    )
    assert bundle.json()["validated"] is True


def test_backfill_docintel_mysql_upgrade(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_MYSQL_DISABLED", "1")
    bf = client.post(
        "/v1/aip/insights/backfill",
        headers=auth_headers,
        json={"objectId": "wo-1001", "confidence": 0.95},
    )
    assert bf.status_code == 200
    assert bf.json()["status"] == "proposed"
    mysql = client.post(
        "/v1/connectors/mysql/probe",
        headers=auth_headers,
        json={"objectType": "WorkOrder"},
    )
    assert mysql.status_code == 200
    assert mysql.json()["mode"] in {"disabled", "live", "error", "stub"}
    assert "passwordRef" in mysql.json() or mysql.json().get("ok") is True
    di = client.post(
        "/v1/docintel/pipeline",
        headers=auth_headers,
        json={"fail": True},
    )
    assert di.json()["failedIsolated"] is True
    up = client.post(
        "/v1/apollo/upgrade",
        headers=auth_headers,
        json={"to": "0.3.0-dev"},
    )
    assert up.json()["status"] == "succeeded"


def test_buddy_uses_facade(client, auth_headers):
    r = client.post(
        "/v1/buddy/ask",
        headers=auth_headers,
        json={"query": "facade-ping"},
    )
    assert r.status_code == 200
    assert "mock-llm" in r.json()["answer"] or "facade-ping" in r.json()["answer"]
