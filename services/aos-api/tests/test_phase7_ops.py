"""Phase 7 · Ops Delivery 测试."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.main import create_app
from aos_api.phase7_ops_engine import get_engine
from aos_api.demo.seed_phase7_ops import seed_ops_data


@pytest.fixture()
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_and_seed():
    eng = get_engine()
    eng.reset()
    yield
    eng.reset()


# ───────────────────────── Hub ─────────────────────────

class TestHub:
    def test_get_hub(self, client):
        resp = client.get("/api/v1/ops/hub")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "hub-001"
        assert body["cluster"] == "aos-prod"
        assert body["status"] == "healthy"

    def test_update_hub(self, client):
        resp = client.put("/api/v1/ops/hub", json={"status": "degraded", "version": "3.14.1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["version"] == "3.14.1"

    def test_update_hub_partial(self, client):
        resp = client.put("/api/v1/ops/hub", json={"region": "eu-west-1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["region"] == "eu-west-1"


# ───────────────────────── Spokes ─────────────────────────

class TestSpokes:
    def test_create_spoke(self, client):
        resp = client.post("/api/v1/ops/spokes", json={
            "name": "spoke-test", "region": "us-east-1", "status": "healthy",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "spoke-test"
        assert body["id"].startswith("spoke-")

    def test_list_spokes_empty(self, client):
        resp = client.get("/api/v1/ops/spokes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 0

    def test_list_spokes_with_data(self, client):
        client.post("/api/v1/ops/spokes", json={"name": "s1", "status": "healthy"})
        client.post("/api/v1/ops/spokes", json={"name": "s2", "status": "degraded"})
        resp = client.get("/api/v1/ops/spokes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_list_spokes_filter_status(self, client):
        client.post("/api/v1/ops/spokes", json={"name": "s1", "status": "healthy"})
        client.post("/api/v1/ops/spokes", json={"name": "s2", "status": "degraded"})
        resp = client.get("/api/v1/ops/spokes?status=healthy")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["status"] == "healthy"

    def test_get_spoke_not_found(self, client):
        resp = client.get("/api/v1/ops/spokes/nonexistent")
        assert resp.status_code == 404

    def test_get_spoke_detail(self, client):
        create = client.post("/api/v1/ops/spokes", json={"name": "s1", "description": "test spoke"})
        sid = create.json()["id"]
        resp = client.get(f"/api/v1/ops/spokes/{sid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "s1"
        assert body["description"] == "test spoke"

    def test_update_spoke(self, client):
        create = client.post("/api/v1/ops/spokes", json={"name": "s1"})
        sid = create.json()["id"]
        resp = client.put(f"/api/v1/ops/spokes/{sid}", json={"status": "maintenance"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "maintenance"

    def test_delete_spoke(self, client):
        create = client.post("/api/v1/ops/spokes", json={"name": "s1"})
        sid = create.json()["id"]
        resp = client.delete(f"/api/v1/ops/spokes/{sid}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] is True
        # Verify gone
        resp2 = client.get(f"/api/v1/ops/spokes/{sid}")
        assert resp2.status_code == 404


# ───────────────────────── Plan ─────────────────────────

class TestPlan:
    def test_get_plan_empty(self, client):
        create = client.post("/api/v1/ops/spokes", json={"name": "s1"})
        sid = create.json()["id"]
        resp = client.get(f"/api/v1/ops/spokes/{sid}/plan")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_plan_not_found(self, client):
        resp = client.get("/api/v1/ops/spokes/nonexistent/plan")
        assert resp.status_code == 404

    def test_get_plan_diff_empty(self, client):
        create = client.post("/api/v1/ops/spokes", json={"name": "s1"})
        sid = create.json()["id"]
        resp = client.get(f"/api/v1/ops/spokes/{sid}/plan-diff")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_plan_diff_not_found(self, client):
        resp = client.get("/api/v1/ops/spokes/nonexistent/plan-diff")
        assert resp.status_code == 404


# ───────────────────────── Config ─────────────────────────

class TestConfig:
    def test_get_config_default(self, client):
        create = client.post("/api/v1/ops/spokes", json={"name": "s1"})
        sid = create.json()["id"]
        resp = client.get(f"/api/v1/ops/spokes/{sid}/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["spoke_id"] == sid

    def test_update_config(self, client):
        create = client.post("/api/v1/ops/spokes", json={"name": "s1"})
        sid = create.json()["id"]
        resp = client.put(f"/api/v1/ops/spokes/{sid}/config", json={
            "overrides": {"log_level": "DEBUG"}, "updated_by": "admin1",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["overrides"]["log_level"] == "DEBUG"
        assert body["updated_by"] == "admin1"

    def test_get_config_not_found(self, client):
        resp = client.get("/api/v1/ops/spokes/nonexistent/config")
        assert resp.status_code == 404


# ───────────────────────── Maintenance Windows ─────────────────────────

class TestMaintenanceWindow:
    def test_get_mw_empty(self, client):
        create = client.post("/api/v1/ops/spokes", json={"name": "s1"})
        sid = create.json()["id"]
        resp = client.get(f"/api/v1/ops/spokes/{sid}/maintenance-window")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_get_mw_not_found(self, client):
        resp = client.get("/api/v1/ops/spokes/nonexistent/maintenance-window")
        assert resp.status_code == 404


# ───────────────────────── Releases ─────────────────────────

class TestReleases:
    def test_list_releases_empty(self, client):
        resp = client.get("/api/v1/ops/releases")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_create_release(self, client):
        resp = client.post("/api/v1/ops/releases", json={
            "channel": "stable", "version": "3.14.0",
            "changelog": ["fix1", "fix2"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["channel"] == "stable"
        assert body["version"] == "3.14.0"

    def test_list_releases_filter_channel(self, client):
        client.post("/api/v1/ops/releases", json={"channel": "stable", "version": "3.14.0"})
        client.post("/api/v1/ops/releases", json={"channel": "beta", "version": "3.14.1-beta"})
        resp = client.get("/api/v1/ops/releases?channel=stable")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["channel"] == "stable"


# ───────────────────────── Hotfix ─────────────────────────

class TestHotfix:
    def test_get_hotfix_none(self, client):
        resp = client.get("/api/v1/ops/releases/hotfix")
        assert resp.status_code == 200
        assert resp.json()["hotfix"] is None

    def test_push_hotfix(self, client):
        eng = get_engine()
        h = eng.create_hotfix(version="3.14.0-hotfix.1", base_version="3.14.0")
        resp = client.post("/api/v1/ops/releases/hotfix/push", json={"hotfix_id": h.id})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pushed"
        assert body["pushed_at"] > 0

    def test_push_hotfix_not_found(self, client):
        resp = client.post("/api/v1/ops/releases/hotfix/push", json={"hotfix_id": "nonexistent"})
        assert resp.status_code == 404


# ───────────────────────── Recall ─────────────────────────

class TestRecall:
    def test_list_recalls_empty(self, client):
        resp = client.get("/api/v1/ops/releases/recall")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_execute_recall(self, client):
        resp = client.post("/api/v1/ops/releases/recall/execute", json={
            "target_version": "3.13.1", "from_version": "3.13.2", "reason": "memory leak",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "completed"
        assert body["to_version"] == "3.13.1"

    def test_list_recalls_after_execute(self, client):
        client.post("/api/v1/ops/releases/recall/execute", json={
            "target_version": "3.13.1", "from_version": "3.13.2",
        })
        resp = client.get("/api/v1/ops/releases/recall")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1


# ───────────────────────── Ferry ─────────────────────────

class TestFerry:
    def test_list_bundles_empty(self, client):
        resp = client.get("/api/v1/ops/ferry/bundles")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_create_bundle(self, client):
        resp = client.post("/api/v1/ops/ferry/bundles", json={
            "name": "test-bundle", "version": "1.0.0", "size_mb": 50.5,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "test-bundle"
        assert body["size_mb"] == 50.5

    def test_submit_ferry(self, client):
        b = client.post("/api/v1/ops/ferry/bundles", json={"name": "b1"})
        s = client.post("/api/v1/ops/spokes", json={"name": "s1"})
        resp = client.post("/api/v1/ops/ferry/submit", json={
            "bundle_id": b.json()["id"], "spoke_ids": [s.json()["id"]],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "submitted"

    def test_submit_ferry_bad_bundle(self, client):
        s = client.post("/api/v1/ops/spokes", json={"name": "s1"})
        resp = client.post("/api/v1/ops/ferry/submit", json={
            "bundle_id": "nonexistent", "spoke_ids": [s.json()["id"]],
        })
        assert resp.status_code == 404

    def test_submit_ferry_bad_spoke(self, client):
        b = client.post("/api/v1/ops/ferry/bundles", json={"name": "b1"})
        resp = client.post("/api/v1/ops/ferry/submit", json={
            "bundle_id": b.json()["id"], "spoke_ids": ["nonexistent"],
        })
        assert resp.status_code == 404


# ───────────────────────── Seed Data ─────────────────────────

class TestSeedData:
    def test_seed_loads(self, client):
        seed_ops_data()
        # Hub should exist
        resp = client.get("/api/v1/ops/hub")
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == "3.14.0"
        assert body["spokes_count"] == 5

    def test_seed_spokes(self, client):
        seed_ops_data()
        resp = client.get("/api/v1/ops/spokes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    def test_seed_releases(self, client):
        seed_ops_data()
        resp = client.get("/api/v1/ops/releases")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        channels = [r["channel"] for r in body["items"]]
        assert "stable" in channels
        assert "beta" in channels
        assert "rc" in channels

    def test_seed_hotfix(self, client):
        seed_ops_data()
        resp = client.get("/api/v1/ops/releases/hotfix")
        assert resp.status_code == 200
        body = resp.json()
        assert body["version"] == "3.14.0-hotfix.1"

    def test_seed_bundles(self, client):
        seed_ops_data()
        resp = client.get("/api/v1/ops/ferry/bundles")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2
