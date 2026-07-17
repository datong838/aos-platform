"""TB.1 / TB.4 demo story API tests."""


def test_demo_ensure_seed_and_story(client, auth_headers):
    e = client.post("/v1/demo/ensure-seed", headers=auth_headers)
    assert e.status_code == 200
    body = e.json()
    assert body["ok"] is True
    assert body["snapshot"]["objectType"] == "WorkOrder"
    assert body["snapshot"]["objectCount"] >= 3
    assert body["snapshot"]["dataSurface"]["datasets"] >= 1
    assert body["snapshot"]["dataSurface"]["dlq"] >= 1

    s = client.get("/v1/demo/story", headers=auth_headers)
    assert s.status_code == 200
    story = s.json()
    assert story["storyId"] == "workorder-local-demo"
    assert story["deferred"]["apolloOps"] is True
    assert len(story["steps"]) >= 8
    assert story["snapshot"]["objectCount"] >= 3

    ds = client.get("/v1/datasets", headers=auth_headers)
    assert ds.status_code == 200
    assert len(ds.json()["items"]) >= 1
    builds = client.get("/v1/builds", headers=auth_headers)
    assert builds.status_code == 200
    assert len(builds.json()["items"]) >= 1
    funnel = client.get("/v1/funnel/WorkOrder/status", headers=auth_headers)
    assert funnel.status_code == 200


def test_demo_run_story_writeback(client, auth_headers):
    client.post("/v1/demo/ensure-seed", headers=auth_headers)
    r1 = client.post("/v1/demo/run-story", headers=auth_headers)
    assert r1.status_code == 200, r1.text
    b1 = r1.json()
    assert b1["ok"] is True
    assert b1["productionWritten"] is True
    assert b1["before"]["status"] != b1["after"]["status"]
    assert b1["lineageId"]
    assert b1["objectId"] == "wo-1001"
    assert b1["draftId"]


def test_demo_governance_probe(client, auth_headers):
    client.post("/v1/demo/ensure-seed", headers=auth_headers)
    client.post("/v1/demo/run-story", headers=auth_headers)
    g = client.get("/v1/demo/governance", headers=auth_headers)
    assert g.status_code == 200, g.text
    body = g.json()
    assert body["ok"] is True
    assert body["field"] == "internalCost"
    assert "internalCost" in (body["asPublicViewer"]["redactedFields"] or [])
    assert body["asPublicViewer"].get("internalCost") is None
    assert body["markingForbidden"]["code"] == "FORBIDDEN"
    assert body["latestLineage"] is not None
    assert body["latestLineage"]["objectId"] == "wo-1001"


def test_demo_run_capability_mirror(client, auth_headers):
    client.post("/v1/demo/ensure-seed", headers=auth_headers)
    r = client.post("/v1/demo/run-capability", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["capabilityId"] == "demo-wo-cap"
    assert body["job"]["mediaRid"]
    assert body["parser"]["ok"] is True
    assert "ocrProbe" in body
