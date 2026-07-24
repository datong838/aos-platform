"""W2-AG · Data Connection 管理组测试（#114 / #115）.

覆盖 AgentAdminEngine / SourceExplorerEngine 两引擎。
"""
from __future__ import annotations

import threading

import pytest

from aos_api.data_connection_admin import (
    AgentAdmin,
    AgentAdminEngine,
    AgentCertificate,
    AgentDriver,
    AgentLogEntry,
    DataConnectionAdminError,
    ERRelation,
    ResourceNode,
    SourceExplorerEngine,
    SourceSchema,
    get_admin_engine,
    get_explorer_engine,
)


# ════════════════════ AgentAdminEngine ════════════════════

class TestAgentAdmin:
    def setup_method(self) -> None:
        self.eng = AgentAdminEngine.__new__(AgentAdminEngine)
        self.eng._admins = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> AgentAdmin:
        defaults: dict[str, object] = {
            "agent_id": "agent-1",
            "name": "dc-agent",
            "version": "1.0.0",
            "status": "registered",
            "download_url": "https://example.com/agent.jar",
            "drivers": [
                AgentDriver(name="mysql", version="8.0", type="jdbc"),
                AgentDriver(name="pg", version="14", type="python"),
            ],
            "certificates": [
                AgentCertificate(name="tls-cert", issuer="ca-1"),
            ],
            "auto_upgrade": False,
        }
        defaults.update(kw)
        return AgentAdmin(**defaults)

    def test_register_returns_with_id(self) -> None:
        a = self.eng.register(self._mk())
        assert a.id.startswith("adm-")

    def test_register_missing_agent_id(self) -> None:
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.register(self._mk(agent_id=""))
        assert exc.value.code == "MISSING_AGENT"

    def test_register_missing_name(self) -> None:
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.register(self._mk(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_register_invalid_driver_type(self) -> None:
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.register(self._mk(
                drivers=[AgentDriver(name="bad", version="1", type="unknown")],
            ))
        assert exc.value.code == "INVALID_DRIVER_TYPE"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(agent_id="a1", name="a"))
        self.eng.register(self._mk(agent_id="a2", name="b"))
        assert len(self.eng.list()) == 2

    def test_list_filter_by_agent_id(self) -> None:
        self.eng.register(self._mk(agent_id="a1", name="a"))
        self.eng.register(self._mk(agent_id="a2", name="b"))
        items = self.eng.list(agent_id="a1")
        assert len(items) == 1
        assert items[0].agent_id == "a1"

    def test_list_filter_by_status(self) -> None:
        a = self.eng.register(self._mk(agent_id="a1", status="registered"))
        self.eng.heartbeat(a.id)  # → active
        items = self.eng.list(status="active")
        assert len(items) == 1

    def test_update(self) -> None:
        a = self.eng.register(self._mk())
        updated = self.eng.update(a.id, {"version": "2.0.0", "name": "new-name"})
        assert updated.version == "2.0.0"
        assert updated.name == "new-name"

    def test_delete(self) -> None:
        a = self.eng.register(self._mk())
        assert self.eng.delete(a.id) is True
        assert self.eng.delete(a.id) is False

    def test_heartbeat(self) -> None:
        a = self.eng.register(self._mk())
        import time
        time.sleep(0.01)
        updated = self.eng.heartbeat(a.id)
        assert updated.last_heartbeat > 0
        assert updated.status == "active"

    def test_push_log(self) -> None:
        a = self.eng.register(self._mk())
        result = self.eng.push_log(a.id, "info", "hello")
        assert len(result.logs) == 1
        assert result.logs[0].message == "hello"
        assert result.logs[0].level == "info"

    def test_push_log_200_entry_rolling(self) -> None:
        from aos_api.data_connection_admin import _MAX_LOGS
        a = self.eng.register(self._mk())
        for i in range(_MAX_LOGS + 10):
            self.eng.push_log(a.id, "info", f"log-{i}")
        assert len(self.eng.get(a.id).logs) == _MAX_LOGS
        assert self.eng.get(a.id).logs[0].message == f"log-10"

    def test_push_log_invalid_level(self) -> None:
        a = self.eng.register(self._mk())
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.push_log(a.id, "debug", "bad level")
        assert exc.value.code == "INVALID_LOG_LEVEL"

    def test_upgrade(self) -> None:
        a = self.eng.register(self._mk(status="registered"))
        upgraded = self.eng.upgrade(a.id, "2.0.0")
        assert upgraded.version == "2.0.0"
        assert upgraded.status == "active"

    def test_list_drivers(self) -> None:
        a = self.eng.register(self._mk())
        drivers = self.eng.list_drivers(a.id)
        assert len(drivers) == 2
        assert drivers[0].name == "mysql"

    def test_list_certificates(self) -> None:
        a = self.eng.register(self._mk())
        certs = self.eng.list_certificates(a.id)
        assert len(certs) == 1
        assert certs[0].name == "tls-cert"

    def test_get_download_url_deprecated(self) -> None:
        a = self.eng.register(self._mk(status="deprecated"))
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.get_download_url(a.id)
        assert exc.value.code == "AGENT_DEPRECATED"

    def test_get_download_url_active(self) -> None:
        a = self.eng.register(self._mk(status="active"))
        url = self.eng.get_download_url(a.id)
        assert url == "https://example.com/agent.jar"


# ════════════════════ SourceExplorerEngine ════════════════════

class TestSourceExplorer:
    def setup_method(self) -> None:
        self.eng = SourceExplorerEngine.__new__(SourceExplorerEngine)
        self.eng._schemas = {}
        self.eng._lock = threading.Lock()

    def _mk(self, **kw: object) -> SourceSchema:
        defaults: dict[str, object] = {
            "source_id": "src-1",
            "dataset_name": "sales",
            "er_diagram": [
                ERRelation(
                    from_table="orders", to_table="customers",
                    from_column="customer_id", to_column="id",
                    relation_type="many_to_one",
                ),
            ],
            "resource_tree": [
                ResourceNode(name="db", type="database", children=["schema1"]),
                ResourceNode(name="schema1", type="schema", children=["orders"]),
                ResourceNode(name="orders", type="table", children=["id", "amount"]),
            ],
            "sample_preview": [
                {"id": 1, "amount": 100},
                {"id": 2, "amount": 200},
                {"id": 3, "amount": 300},
            ],
        }
        defaults.update(kw)
        return SourceSchema(**defaults)

    def test_register_returns_with_id(self) -> None:
        s = self.eng.register(self._mk())
        assert s.id.startswith("sch-")

    def test_register_missing_source_id(self) -> None:
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.register(self._mk(source_id=""))
        assert exc.value.code == "MISSING_SOURCE"

    def test_register_missing_dataset_name(self) -> None:
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.register(self._mk(dataset_name=""))
        assert exc.value.code == "MISSING_DATASET_NAME"

    def test_register_invalid_relation_type(self) -> None:
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.register(self._mk(
                er_diagram=[ERRelation(
                    from_table="a", to_table="b",
                    from_column="x", to_column="y",
                    relation_type="bad_type",
                )],
            ))
        assert exc.value.code == "INVALID_RELATION_TYPE"

    def test_register_invalid_resource_type(self) -> None:
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.register(self._mk(
                resource_tree=[ResourceNode(name="x", type="unknown")],
            ))
        assert exc.value.code == "INVALID_RESOURCE_TYPE"

    def test_get_not_found(self) -> None:
        with pytest.raises(DataConnectionAdminError) as exc:
            self.eng.get("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_default(self) -> None:
        self.eng.register(self._mk(dataset_name="a"))
        self.eng.register(self._mk(dataset_name="b"))
        assert len(self.eng.list()) == 2

    def test_list_filter_by_source_id(self) -> None:
        self.eng.register(self._mk(source_id="s1", dataset_name="a"))
        self.eng.register(self._mk(source_id="s2", dataset_name="b"))
        items = self.eng.list(source_id="s1")
        assert len(items) == 1
        assert items[0].source_id == "s1"

    def test_update(self) -> None:
        s = self.eng.register(self._mk())
        updated = self.eng.update(s.id, {"dataset_name": "new-name"})
        assert updated.dataset_name == "new-name"

    def test_delete(self) -> None:
        s = self.eng.register(self._mk())
        assert self.eng.delete(s.id) is True
        assert self.eng.delete(s.id) is False

    def test_explore_er(self) -> None:
        s = self.eng.register(self._mk())
        er = self.eng.explore_er(s.id)
        assert len(er) == 1
        assert er[0].from_table == "orders"
        assert er[0].relation_type == "many_to_one"

    def test_explore_resource_tree(self) -> None:
        s = self.eng.register(self._mk())
        tree = self.eng.explore_resource_tree(s.id)
        assert len(tree) == 3
        assert tree[0].type == "database"

    def test_preview_sample_limit(self) -> None:
        s = self.eng.register(self._mk())
        result = self.eng.preview_sample(s.id, limit=2)
        assert len(result) == 2
        assert result[0]["id"] == 1

    def test_preview_sample_full(self) -> None:
        s = self.eng.register(self._mk())
        result = self.eng.preview_sample(s.id, limit=0)
        assert len(result) == 3


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_admin_singleton(self) -> None:
        a = get_admin_engine()
        b = get_admin_engine()
        assert a is b

    def test_explorer_singleton(self) -> None:
        a = get_explorer_engine()
        b = get_explorer_engine()
        assert a is b
