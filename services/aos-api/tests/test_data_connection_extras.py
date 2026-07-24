"""W2-AW · Data Connection 扩展组测试（#128 / #129 / #5）.

覆盖 CloudIdentityEngine / VirtualTableEngine / AgentMetricsEngine 三引擎。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pytest

from aos_api.data_connection_extras import (
    AgentMetrics,
    AgentMetricsEngine,
    AgentMetricsError,
    CloudIdentity,
    CloudIdentityEngine,
    CloudIdentityError,
    VirtualTable,
    VirtualTableEngine,
    VirtualTableError,
    get_agent_metrics_engine,
    get_cloud_identity_engine,
    get_virtual_table_engine,
)


# ════════════════════ CloudIdentityEngine ════════════════════

class TestCloudIdentity:
    def setup_method(self) -> None:
        self.eng = CloudIdentityEngine()
        self.eng._identities = {}

    def _mk(self, **kw: object) -> CloudIdentity:
        defaults: dict[str, object] = {
            "name": "dev-account",
            "provider": "aws",
            "status": "active",
            "config": {"region": "us-east-1"},
        }
        defaults.update(kw)
        return CloudIdentity(**defaults)

    def test_register_identity(self) -> None:
        i = self.eng.register_identity(self._mk())
        assert i.identity_id.startswith("ci-")
        assert i.name == "dev-account"

    def test_get_identity(self) -> None:
        i = self.eng.register_identity(self._mk())
        got = self.eng.get_identity(i.identity_id)
        assert got.identity_id == i.identity_id

    def test_list_identities(self) -> None:
        self.eng.register_identity(self._mk(name="a"))
        self.eng.register_identity(self._mk(name="b"))
        assert len(self.eng.list_identities()) == 2

    def test_list_filter_provider(self) -> None:
        self.eng.register_identity(self._mk(name="a", provider="aws"))
        self.eng.register_identity(self._mk(name="b", provider="gcp"))
        items = self.eng.list_identities(provider="aws")
        assert len(items) == 1
        assert items[0].provider == "aws"

    def test_list_filter_status(self) -> None:
        self.eng.register_identity(self._mk(name="a", status="active"))
        self.eng.register_identity(self._mk(name="b", status="inactive"))
        items = self.eng.list_identities(status="inactive")
        assert len(items) == 1
        assert items[0].status == "inactive"

    def test_update_identity(self) -> None:
        i = self.eng.register_identity(self._mk())
        updated = self.eng.update_identity(
            i.identity_id, {"name": "new-name", "status": "inactive"}
        )
        assert updated.name == "new-name"
        assert updated.status == "inactive"

    def test_update_identity_provider_validation(self) -> None:
        i = self.eng.register_identity(self._mk())
        with pytest.raises(CloudIdentityError) as exc:
            self.eng.update_identity(i.identity_id, {"provider": "bad"})
        assert exc.value.code == "INVALID_PROVIDER"

    def test_update_identity_status_validation(self) -> None:
        i = self.eng.register_identity(self._mk())
        with pytest.raises(CloudIdentityError) as exc:
            self.eng.update_identity(i.identity_id, {"status": "bad"})
        assert exc.value.code == "INVALID_STATUS"

    def test_delete_identity(self) -> None:
        i = self.eng.register_identity(self._mk())
        assert self.eng.delete_identity(i.identity_id) is True
        assert self.eng.delete_identity(i.identity_id) is False

    def test_validate_config_ok(self) -> None:
        result = self.eng.validate_config(
            "oidc", {"issuer_url": "https://idp.example.com", "client_id": "cli"}
        )
        assert result["ok"] is True
        assert result["errors"] == []

    def test_validate_config_invalid_provider(self) -> None:
        result = self.eng.validate_config("bad", {})
        assert result["ok"] is False
        assert "provider must be one of" in result["errors"][0]

    def test_validate_config_missing_oidc_fields(self) -> None:
        result = self.eng.validate_config("oidc", {})
        assert result["ok"] is False
        assert any("issuer_url" in e for e in result["errors"])
        assert any("client_id" in e for e in result["errors"])

    def test_missing_name(self) -> None:
        with pytest.raises(CloudIdentityError) as exc:
            self.eng.register_identity(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_missing_provider(self) -> None:
        with pytest.raises(CloudIdentityError) as exc:
            self.eng.register_identity(self._mk(provider=""))
        assert exc.value.code == "MISSING_PROVIDER"

    def test_invalid_provider(self) -> None:
        with pytest.raises(CloudIdentityError) as exc:
            self.eng.register_identity(self._mk(provider="unknown"))
        assert exc.value.code == "INVALID_PROVIDER"

    def test_invalid_status(self) -> None:
        with pytest.raises(CloudIdentityError) as exc:
            self.eng.register_identity(self._mk(status="unknown"))
        assert exc.value.code == "INVALID_STATUS"

    def test_not_found_get(self) -> None:
        with pytest.raises(CloudIdentityError) as exc:
            self.eng.get_identity("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_update(self) -> None:
        with pytest.raises(CloudIdentityError) as exc:
            self.eng.update_identity("nope", {"name": "x"})
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_delete(self) -> None:
        assert self.eng.delete_identity("nope") is False

    def test_max_identities_eviction(self) -> None:
        from aos_api.data_connection_extras import _MAX_CLOUD_IDENTITIES

        for idx in range(_MAX_CLOUD_IDENTITIES + 5):
            self.eng.register_identity(self._mk(name=f"id-{idx}"))
        assert len(self.eng._identities) == _MAX_CLOUD_IDENTITIES


# ════════════════════ VirtualTableEngine ════════════════════

class TestVirtualTable:
    def setup_method(self) -> None:
        self.eng = VirtualTableEngine()
        self.eng._tables = {}

    def _mk(self, **kw: object) -> VirtualTable:
        defaults: dict[str, object] = {
            "name": "orders",
            "source_connection_id": "pg-1",
            "source_table": "orders",
            "sync_mode": "snapshot",
            "status": "active",
        }
        defaults.update(kw)
        return VirtualTable(**defaults)

    def test_register_table(self) -> None:
        t = self.eng.register_table(self._mk())
        assert t.table_id.startswith("vt-")
        assert t.name == "orders"

    def test_get_table(self) -> None:
        t = self.eng.register_table(self._mk())
        got = self.eng.get_table(t.table_id)
        assert got.table_id == t.table_id

    def test_list_tables(self) -> None:
        self.eng.register_table(self._mk(name="a"))
        self.eng.register_table(self._mk(name="b"))
        assert len(self.eng.list_tables()) == 2

    def test_list_filter_source_connection_id(self) -> None:
        self.eng.register_table(self._mk(name="a", source_connection_id="pg-1"))
        self.eng.register_table(self._mk(name="b", source_connection_id="pg-2"))
        items = self.eng.list_tables(source_connection_id="pg-1")
        assert len(items) == 1
        assert items[0].source_connection_id == "pg-1"

    def test_list_filter_sync_mode(self) -> None:
        self.eng.register_table(self._mk(name="a", sync_mode="snapshot"))
        self.eng.register_table(self._mk(name="b", sync_mode="incremental"))
        items = self.eng.list_tables(sync_mode="incremental")
        assert len(items) == 1
        assert items[0].sync_mode == "incremental"

    def test_list_filter_status(self) -> None:
        self.eng.register_table(self._mk(name="a", status="active"))
        self.eng.register_table(self._mk(name="b", status="inactive"))
        items = self.eng.list_tables(status="inactive")
        assert len(items) == 1
        assert items[0].status == "inactive"

    def test_update_table(self) -> None:
        t = self.eng.register_table(self._mk())
        updated = self.eng.update_table(
            t.table_id, {"name": "new-orders", "sync_mode": "incremental"}
        )
        assert updated.name == "new-orders"
        assert updated.sync_mode == "incremental"

    def test_update_table_sync_mode_validation(self) -> None:
        t = self.eng.register_table(self._mk())
        with pytest.raises(VirtualTableError) as exc:
            self.eng.update_table(t.table_id, {"sync_mode": "bad"})
        assert exc.value.code == "INVALID_SYNC_MODE"

    def test_update_table_status_validation(self) -> None:
        t = self.eng.register_table(self._mk())
        with pytest.raises(VirtualTableError) as exc:
            self.eng.update_table(t.table_id, {"status": "bad"})
        assert exc.value.code == "INVALID_STATUS"

    def test_delete_table(self) -> None:
        t = self.eng.register_table(self._mk())
        assert self.eng.delete_table(t.table_id) is True
        assert self.eng.delete_table(t.table_id) is False

    def test_sync_table(self) -> None:
        t = self.eng.register_table(self._mk())
        synced = self.eng.sync_table(t.table_id)
        assert synced.last_sync_at is not None
        assert synced.updated_at is not None

    def test_not_found_sync(self) -> None:
        with pytest.raises(VirtualTableError) as exc:
            self.eng.sync_table("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_missing_name(self) -> None:
        with pytest.raises(VirtualTableError) as exc:
            self.eng.register_table(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_missing_source_connection(self) -> None:
        with pytest.raises(VirtualTableError) as exc:
            self.eng.register_table(self._mk(source_connection_id=""))
        assert exc.value.code == "MISSING_SOURCE_CONNECTION"

    def test_invalid_sync_mode(self) -> None:
        with pytest.raises(VirtualTableError) as exc:
            self.eng.register_table(self._mk(sync_mode="bad"))
        assert exc.value.code == "INVALID_SYNC_MODE"

    def test_invalid_status(self) -> None:
        with pytest.raises(VirtualTableError) as exc:
            self.eng.register_table(self._mk(status="bad"))
        assert exc.value.code == "INVALID_STATUS"

    def test_not_found_get(self) -> None:
        with pytest.raises(VirtualTableError) as exc:
            self.eng.get_table("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_update(self) -> None:
        with pytest.raises(VirtualTableError) as exc:
            self.eng.update_table("nope", {"name": "x"})
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_delete(self) -> None:
        assert self.eng.delete_table("nope") is False

    def test_max_tables_eviction(self) -> None:
        from aos_api.data_connection_extras import _MAX_VIRTUAL_TABLES

        for idx in range(_MAX_VIRTUAL_TABLES + 5):
            self.eng.register_table(self._mk(name=f"tbl-{idx}"))
        assert len(self.eng._tables) == _MAX_VIRTUAL_TABLES


# ════════════════════ AgentMetricsEngine ════════════════════

class TestAgentMetrics:
    def setup_method(self) -> None:
        self.eng = AgentMetricsEngine()
        self.eng._metrics = {}

    def _mk(self, **kw: object) -> AgentMetrics:
        defaults: dict[str, object] = {
            "agent_id": "agent-1",
            "status": "ok",
            "memory_mb": 128.0,
            "disk_gb": 10.0,
            "cpu_percent": 50.0,
            "queue_depth": 5,
            "uptime_seconds": 3600,
        }
        defaults.update(kw)
        return AgentMetrics(**defaults)

    def test_record_metrics(self) -> None:
        m = self.eng.record_metrics(self._mk())
        assert m.metrics_id.startswith("am-")
        assert m.agent_id == "agent-1"

    def test_get_metrics(self) -> None:
        m = self.eng.record_metrics(self._mk())
        got = self.eng.get_metrics(m.metrics_id)
        assert got.metrics_id == m.metrics_id

    def test_list_metrics(self) -> None:
        self.eng.record_metrics(self._mk(agent_id="a"))
        self.eng.record_metrics(self._mk(agent_id="b"))
        assert len(self.eng.list_metrics()) == 2

    def test_list_filter_agent(self) -> None:
        self.eng.record_metrics(self._mk(agent_id="a"))
        self.eng.record_metrics(self._mk(agent_id="b"))
        items = self.eng.list_metrics(agent_id="a")
        assert len(items) == 1
        assert items[0].agent_id == "a"

    def test_list_filter_status(self) -> None:
        self.eng.record_metrics(self._mk(agent_id="a", status="ok"))
        self.eng.record_metrics(self._mk(agent_id="b", status="critical"))
        items = self.eng.list_metrics(status="critical")
        assert len(items) == 1
        assert items[0].status == "critical"

    def test_list_latest_by_agent(self) -> None:
        old = self._mk(agent_id="a", status="ok")
        old.created_at = datetime.utcnow() - timedelta(minutes=10)
        new = self._mk(agent_id="a", status="warning")
        new.created_at = datetime.utcnow()
        self.eng.record_metrics(old)
        self.eng.record_metrics(new)
        self.eng.record_metrics(self._mk(agent_id="b", status="ok"))
        latest = self.eng.list_latest_by_agent()
        assert len(latest) == 2
        a_items = [m for m in latest if m.agent_id == "a"]
        assert len(a_items) == 1
        assert a_items[0].status == "warning"

    def test_get_agent_summary(self) -> None:
        self.eng.record_metrics(self._mk(agent_id="a", memory_mb=100.0, cpu_percent=10.0))
        self.eng.record_metrics(self._mk(agent_id="a", memory_mb=200.0, cpu_percent=30.0))
        summary = self.eng.get_agent_summary("a")
        assert summary["agent_id"] == "a"
        assert summary["count"] == 2
        assert summary["avg_memory_mb"] == 150.0
        assert summary["avg_cpu_percent"] == 20.0

    def test_get_agent_summary_empty(self) -> None:
        summary = self.eng.get_agent_summary("nonexistent")
        assert summary["agent_id"] == "nonexistent"
        assert summary["count"] == 0
        assert summary["avg_memory_mb"] == 0.0

    def test_prune_old(self) -> None:
        old = self.eng.record_metrics(self._mk(agent_id="a"))
        new = self.eng.record_metrics(self._mk(agent_id="a"))
        # record_metrics 会覆盖 created_at，因此手动将 old 设为 31 天前
        with self.eng._lock:
            self.eng._metrics[old.metrics_id].created_at = (
                datetime.utcnow() - timedelta(days=31)
            )
        deleted = self.eng.prune_old(days=30)
        assert deleted == 1
        assert len(self.eng._metrics) == 1

    def test_missing_agent(self) -> None:
        with pytest.raises(AgentMetricsError) as exc:
            self.eng.record_metrics(self._mk(agent_id=""))
        assert exc.value.code == "MISSING_AGENT"

    def test_invalid_status(self) -> None:
        with pytest.raises(AgentMetricsError) as exc:
            self.eng.record_metrics(self._mk(status="bad"))
        assert exc.value.code == "INVALID_STATUS"

    def test_not_found_get(self) -> None:
        with pytest.raises(AgentMetricsError) as exc:
            self.eng.get_metrics("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_max_metrics_eviction(self) -> None:
        from aos_api.data_connection_extras import _MAX_AGENT_METRICS

        for idx in range(_MAX_AGENT_METRICS + 5):
            self.eng.record_metrics(self._mk(agent_id=f"agent-{idx}"))
        assert len(self.eng._metrics) == _MAX_AGENT_METRICS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_cloud_identity_singleton(self) -> None:
        a = get_cloud_identity_engine()
        b = get_cloud_identity_engine()
        assert a is b

    def test_virtual_table_singleton(self) -> None:
        a = get_virtual_table_engine()
        b = get_virtual_table_engine()
        assert a is b

    def test_agent_metrics_singleton(self) -> None:
        a = get_agent_metrics_engine()
        b = get_agent_metrics_engine()
        assert a is b
