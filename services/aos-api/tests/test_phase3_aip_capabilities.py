"""Phase 3 · AIP Capabilities — 单元测试。"""
import pytest

from aos_api.aip_capabilities_engine import get_engine, CapabilitiesEngine


@pytest.fixture(autouse=True)
def reset_engine():
    get_engine().reset()
    yield


def test_create_and_get_capability():
    eng = get_engine()
    cap = eng.create_capability("Test Cap", category="data", description="desc")
    assert cap.name == "Test Cap"
    fetched = eng.get_capability(cap.id)
    assert fetched is not None


def test_list_capabilities_filter():
    eng = get_engine()
    eng.create_capability("C1", category="data")
    eng.create_capability("C2", category="ai")
    eng.create_capability("C3", category="data", enabled=False)
    data_caps = eng.list_capabilities(category="data")
    assert len(data_caps) == 2
    enabled_only = eng.list_capabilities(enabled=True)
    assert len(enabled_only) == 2


def test_update_capability():
    eng = get_engine()
    cap = eng.create_capability("Cap", config={"k": "v"})
    updated = eng.update_capability(cap.id, description="New", enabled=False)
    assert updated.description == "New"
    assert updated.enabled is False


def test_ensure_plugin_defaults_and_upsert():
    eng = get_engine()
    n = eng.ensure_plugin_defaults()
    assert n >= 4
    assert eng.get_capability("video-job") is not None
    # 幂等
    assert eng.ensure_plugin_defaults() == 0
    up = eng.upsert_capability(
        "video-job",
        config={"kind": "job", "endpoint": "https://x/v2", "concurrency": 8},
        enabled=True,
        name="短视频生成",
    )
    assert up.config["endpoint"] == "https://x/v2"
    assert up.config["concurrency"] == 8
    fresh = eng.upsert_capability("custom-cap-x", name="Custom", category="ai", config={"endpoint": "https://y"})
    assert fresh.id == "custom-cap-x"


def test_connectivity():
    eng = get_engine()
    r = eng.test_connectivity(cap_id="video-job")
    assert r["ok"] is True
    assert r["status"] == "healthy"
    assert r["capabilityId"] == "video-job"
    assert r["endpoint"]
    r2 = eng.test_connectivity(endpoint="https://probe.example/health")
    assert r2["ok"] is True
    assert "probe.example" in r2["endpoint"]


def test_delete_capability():
    eng = get_engine()
    cap = eng.create_capability("ToDelete")
    assert eng.delete_capability(cap.id) is True
    assert eng.get_capability(cap.id) is None


def test_registry_create():
    eng = get_engine()
    entry = eng.register("agent-1", "Agent One", ["cap-1"], scope="org")
    assert entry.agent_name == "Agent One"
    fetched = eng.get_registry_entry(entry.id)
    assert fetched is not None


def test_registry_list_filter():
    eng = get_engine()
    eng.register("a1", "A1", [], scope="org", status="registered")
    eng.register("a2", "A2", [], scope="project", status="pending")
    org_items = eng.list_registry(scope="org")
    assert len(org_items) == 1
    pending = eng.list_registry(status="pending")
    assert len(pending) == 1


def test_registry_update():
    eng = get_engine()
    entry = eng.register("a1", "A1", [])
    updated = eng.update_registry(entry.id, status="revoked")
    assert updated.status == "revoked"


def test_registry_stats():
    eng = get_engine()
    eng.create_capability("C1", enabled=True)
    eng.create_capability("C2", enabled=False)
    eng.register("a1", "A1", [], scope="org")
    eng.register("a2", "A2", [], scope="project")
    stats = eng.registry_stats()
    assert stats["total_agents"] == 2
    assert stats["total_capabilities"] == 2
    assert stats["enabled_capabilities"] == 1


def test_singleton():
    e1 = get_engine()
    e2 = CapabilitiesEngine()
    assert e1 is e2
