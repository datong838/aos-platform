"""TB.1 / TB.4 demo story API tests.

注：``/v1/demo/*`` HTTP 路由已在种子数据收敛（v2.2 Phase 5）中下线，
测试改为直接调用 ``aos_api.demo.demo_story`` Python 函数。
"""

from aos_api.demo.demo_story import (
    demo_story_payload,
    ensure_demo_seed_full,
    governance_probe,
    run_capability_mirror,
    run_writeback_story,
)


def test_demo_ensure_seed_and_story(client, auth_headers, dev_principal):
    _ = dev_principal
    e = ensure_demo_seed_full()
    assert e["ok"] is True
    body = e
    assert body["snapshot"]["objectType"] == "WorkOrder"
    assert body["snapshot"]["objectCount"] >= 3
    assert body["snapshot"]["dataSurface"]["datasets"] >= 1
    assert body["snapshot"]["dataSurface"]["dlq"] >= 1
    assert body["snapshot"]["dataSurface"].get("syncs", 0) >= 1

    story = demo_story_payload()
    assert story["storyId"] == "workorder-local-demo"
    assert story["deferred"]["apolloOps"] is False
    assert len(story["steps"]) >= 8
    assert story["snapshot"]["objectCount"] >= 3

    ds = client.get("/v1/datasets", headers=auth_headers)
    assert ds.status_code == 200
    assert len(ds.json()["items"]) >= 1
    builds = client.get("/v1/builds", headers=auth_headers)
    assert builds.status_code == 200
    assert len(builds.json()["items"]) >= 1
    syncs = client.get("/v1/syncs", headers=auth_headers)
    assert syncs.status_code == 200
    assert len(syncs.json()["items"]) >= 1
    assert any(s.get("sourceId") == "demo-file-wo" for s in syncs.json()["items"])
    funnel = client.get("/v1/funnel/WorkOrder/status", headers=auth_headers)
    assert funnel.status_code == 200


def test_demo_run_story_writeback(client, auth_headers, dev_principal):
    _ = auth_headers
    ensure_demo_seed_full()
    b1 = run_writeback_story(dev_principal)
    assert b1["ok"] is True
    assert b1["productionWritten"] is True
    assert b1["before"]["status"] != b1["after"]["status"]
    assert b1["lineageId"]
    assert b1["objectId"] == "wo-1001"
    assert b1["draftId"]


def test_demo_governance_probe(client, auth_headers, dev_principal):
    _ = auth_headers
    ensure_demo_seed_full()
    run_writeback_story(dev_principal)
    body = governance_probe(dev_principal)
    assert body["ok"] is True
    assert body["field"] == "internalCost"
    assert "internalCost" in (body["asPublicViewer"]["redactedFields"] or [])
    assert body["asPublicViewer"].get("internalCost") is None
    assert body["markingForbidden"]["code"] == "FORBIDDEN"
    assert body["latestLineage"] is not None
    assert body["latestLineage"]["objectId"] == "wo-1001"


def test_demo_run_capability_mirror(client, auth_headers, dev_principal):
    _ = auth_headers
    ensure_demo_seed_full()
    body = run_capability_mirror(dev_principal)
    assert body["ok"] is True
    assert body["capabilityId"] == "demo-wo-cap"
    assert body["job"]["mediaRid"]
    assert body["parser"]["ok"] is True
    assert "ocrProbe" in body
