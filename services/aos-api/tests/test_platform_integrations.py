"""W2-AV · Platform Integrations 测试（#142 / #159 / #160）.

覆盖 HealthAppEngine / FunctionIntegrationEngine / FerryPackageEngine 三引擎。
"""
from __future__ import annotations

import threading

import pytest

from aos_api.platform_integrations import (
    FerryPackage,
    FerryPackageEngine,
    FerryPackageError,
    FunctionIntegration,
    FunctionIntegrationEngine,
    FunctionIntegrationError,
    HealthAppEntry,
    HealthAppEngine,
    HealthAppError,
    PlatformIntegrationError,
    get_function_integration_engine,
    get_ferry_package_engine,
    get_health_app_engine,
    _MAX_HEALTH_APP_ENTRIES,
    _MAX_FUNCTION_INTEGRATIONS,
    _MAX_FERRY_PACKAGES,
)


# ════════════════════ HealthAppEngine ════════════════════

class TestHealthApp:
    def setup_method(self) -> None:
        self.eng = HealthAppEngine()
        self.eng._entries = {}

    def _mk(self, **kw: object) -> HealthAppEntry:
        defaults: dict[str, object] = {
            "app_name": "health-app",
            "path": "/health/app",
            "category": "data_health",
            "status": "active",
            "order_index": 0,
        }
        defaults.update(kw)
        return HealthAppEntry(**defaults)

    def test_register_entry(self) -> None:
        e = self.eng.register_entry(self._mk())
        assert e.entry_id.startswith("ha-")
        assert e.app_name == "health-app"

    def test_get_entry(self) -> None:
        e = self.eng.register_entry(self._mk())
        fetched = self.eng.get_entry(e.entry_id)
        assert fetched.entry_id == e.entry_id

    def test_list_entries(self) -> None:
        self.eng.register_entry(self._mk(app_name="a"))
        self.eng.register_entry(self._mk(app_name="b"))
        assert len(self.eng.list_entries()) == 2

    def test_list_filter_category(self) -> None:
        self.eng.register_entry(self._mk(app_name="a", category="monitoring"))
        self.eng.register_entry(self._mk(app_name="b", category="data_health"))
        items = self.eng.list_entries(category="monitoring")
        assert len(items) == 1
        assert items[0].category == "monitoring"

    def test_list_filter_status(self) -> None:
        self.eng.register_entry(self._mk(app_name="a", status="active"))
        self.eng.register_entry(self._mk(app_name="b", status="inactive"))
        items = self.eng.list_entries(status="active")
        assert len(items) == 1
        assert items[0].status == "active"

    def test_update_entry(self) -> None:
        e = self.eng.register_entry(self._mk())
        updated = self.eng.update_entry(e.entry_id, {"app_name": "new-name", "path": "/new/path"})
        assert updated.app_name == "new-name"
        assert updated.path == "/new/path"

    def test_delete_entry(self) -> None:
        e = self.eng.register_entry(self._mk())
        assert self.eng.delete_entry(e.entry_id) is True
        assert self.eng.delete_entry(e.entry_id) is False

    def test_reorder_entries(self) -> None:
        e1 = self.eng.register_entry(self._mk(app_name="a", order_index=0))
        e2 = self.eng.register_entry(self._mk(app_name="b", order_index=1))
        self.eng.reorder_entries({e1.entry_id: 5, e2.entry_id: 2})
        assert self.eng.get_entry(e1.entry_id).order_index == 5
        assert self.eng.get_entry(e2.entry_id).order_index == 2

    def test_get_sidebar_items(self) -> None:
        e1 = self.eng.register_entry(self._mk(app_name="a", status="active", order_index=2))
        e2 = self.eng.register_entry(self._mk(app_name="b", status="active", order_index=1))
        self.eng.register_entry(self._mk(app_name="c", status="inactive", order_index=0))
        items = self.eng.get_sidebar_items()
        assert len(items) == 2
        assert items[0].order_index == 1
        assert items[1].order_index == 2

    def test_missing_app_name(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.register_entry(self._mk(app_name=""))
        assert exc.value.code == "MISSING_APP_NAME"

    def test_missing_path(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.register_entry(self._mk(path=""))
        assert exc.value.code == "MISSING_PATH"

    def test_invalid_category(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.register_entry(self._mk(category="unknown"))
        assert exc.value.code == "INVALID_CATEGORY"

    def test_invalid_status(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.register_entry(self._mk(status="unknown"))
        assert exc.value.code == "INVALID_STATUS"

    def test_not_found_get(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.get_entry("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_update(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.update_entry("nope", {"app_name": "x"})
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_delete(self) -> None:
        assert self.eng.delete_entry("nope") is False

    def test_max_entries_eviction(self) -> None:
        for i in range(_MAX_HEALTH_APP_ENTRIES + 5):
            self.eng.register_entry(self._mk(app_name=f"app-{i}", path=f"/path/{i}"))
        assert len(self.eng.list_entries()) == _MAX_HEALTH_APP_ENTRIES


# ════════════════════ FunctionIntegrationEngine ════════════════════

class TestFunctionIntegration:
    def setup_method(self) -> None:
        self.eng = FunctionIntegrationEngine()
        self.eng._integrations = {}

    def _mk(self, **kw: object) -> FunctionIntegration:
        defaults: dict[str, object] = {
            "module_id": "mod-a",
            "function_id": "func-a",
            "backend_type": "python",
            "trigger_type": "direct",
            "status": "active",
        }
        defaults.update(kw)
        return FunctionIntegration(**defaults)

    def test_register_integration(self) -> None:
        i = self.eng.register_integration(self._mk())
        assert i.integration_id.startswith("fi-")
        assert i.module_id == "mod-a"

    def test_get_integration(self) -> None:
        i = self.eng.register_integration(self._mk())
        fetched = self.eng.get_integration(i.integration_id)
        assert fetched.integration_id == i.integration_id

    def test_list_integrations(self) -> None:
        self.eng.register_integration(self._mk(module_id="m1"))
        self.eng.register_integration(self._mk(module_id="m2"))
        assert len(self.eng.list_integrations()) == 2

    def test_list_filter_module(self) -> None:
        self.eng.register_integration(self._mk(module_id="m1"))
        self.eng.register_integration(self._mk(module_id="m2"))
        items = self.eng.list_integrations(module_id="m1")
        assert len(items) == 1
        assert items[0].module_id == "m1"

    def test_list_filter_backend(self) -> None:
        self.eng.register_integration(self._mk(backend_type="python"))
        self.eng.register_integration(self._mk(backend_type="typescript"))
        items = self.eng.list_integrations(backend_type="python")
        assert len(items) == 1
        assert items[0].backend_type == "python"

    def test_list_filter_trigger(self) -> None:
        self.eng.register_integration(self._mk(trigger_type="workshop"))
        self.eng.register_integration(self._mk(trigger_type="direct"))
        items = self.eng.list_integrations(trigger_type="workshop")
        assert len(items) == 1
        assert items[0].trigger_type == "workshop"

    def test_list_filter_status(self) -> None:
        self.eng.register_integration(self._mk(status="active"))
        self.eng.register_integration(self._mk(status="inactive"))
        items = self.eng.list_integrations(status="active")
        assert len(items) == 1
        assert items[0].status == "active"

    def test_update_integration(self) -> None:
        i = self.eng.register_integration(self._mk())
        updated = self.eng.update_integration(i.integration_id, {"function_id": "new-func", "backend_type": "container"})
        assert updated.function_id == "new-func"
        assert updated.backend_type == "container"

    def test_delete_integration(self) -> None:
        i = self.eng.register_integration(self._mk())
        assert self.eng.delete_integration(i.integration_id) is True
        assert self.eng.delete_integration(i.integration_id) is False

    def test_invoke(self) -> None:
        i = self.eng.register_integration(self._mk(module_id="m", function_id="f"))
        result = self.eng.invoke(i.integration_id, {"arg": 1})
        assert result["integration_id"] == i.integration_id
        assert result["module_id"] == "m"
        assert result["function_id"] == "f"
        assert result["result"] == {"arg": 1}

    def test_list_by_function(self) -> None:
        self.eng.register_integration(self._mk(function_id="f1"))
        self.eng.register_integration(self._mk(function_id="f2"))
        self.eng.register_integration(self._mk(function_id="f1"))
        items = self.eng.list_by_function("f1")
        assert len(items) == 2

    def test_missing_module(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.register_integration(self._mk(module_id=""))
        assert exc.value.code == "MISSING_MODULE"

    def test_missing_function(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.register_integration(self._mk(function_id=""))
        assert exc.value.code == "MISSING_FUNCTION"

    def test_missing_backend_type(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.register_integration(self._mk(backend_type=""))
        assert exc.value.code == "MISSING_BACKEND_TYPE"

    def test_invalid_backend_type(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.register_integration(self._mk(backend_type="unknown"))
        assert exc.value.code == "INVALID_BACKEND_TYPE"

    def test_invalid_trigger_type(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.register_integration(self._mk(trigger_type="unknown"))
        assert exc.value.code == "INVALID_TRIGGER_TYPE"

    def test_invalid_status(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.register_integration(self._mk(status="unknown"))
        assert exc.value.code == "INVALID_STATUS"

    def test_not_found_get(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.get_integration("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_invoke(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.invoke("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_delete(self) -> None:
        assert self.eng.delete_integration("nope") is False

    def test_max_integrations_eviction(self) -> None:
        for i in range(_MAX_FUNCTION_INTEGRATIONS + 5):
            self.eng.register_integration(self._mk(module_id=f"mod-{i}", function_id=f"func-{i}"))
        assert len(self.eng.list_integrations()) == _MAX_FUNCTION_INTEGRATIONS


# ════════════════════ FerryPackageEngine ════════════════════

class TestFerryPackage:
    def setup_method(self) -> None:
        self.eng = FerryPackageEngine()
        self.eng._packages = {}

    def _mk(self, **kw: object) -> FerryPackage:
        defaults: dict[str, object] = {
            "source_dataset_rid": "src-1",
            "target_dataset_rid": "tgt-1",
            "package_type": "incremental",
            "status": "pending",
        }
        defaults.update(kw)
        return FerryPackage(**defaults)

    def test_create_package(self) -> None:
        p = self.eng.create_package(self._mk())
        assert p.package_id.startswith("fp-")
        assert p.source_dataset_rid == "src-1"

    def test_get_package(self) -> None:
        p = self.eng.create_package(self._mk())
        fetched = self.eng.get_package(p.package_id)
        assert fetched.package_id == p.package_id

    def test_list_packages(self) -> None:
        self.eng.create_package(self._mk(source_dataset_rid="s1"))
        self.eng.create_package(self._mk(source_dataset_rid="s2"))
        assert len(self.eng.list_packages()) == 2

    def test_list_filter_source(self) -> None:
        self.eng.create_package(self._mk(source_dataset_rid="s1"))
        self.eng.create_package(self._mk(source_dataset_rid="s2"))
        items = self.eng.list_packages(source_dataset_rid="s1")
        assert len(items) == 1
        assert items[0].source_dataset_rid == "s1"

    def test_list_filter_target(self) -> None:
        self.eng.create_package(self._mk(target_dataset_rid="t1"))
        self.eng.create_package(self._mk(target_dataset_rid="t2"))
        items = self.eng.list_packages(target_dataset_rid="t1")
        assert len(items) == 1
        assert items[0].target_dataset_rid == "t1"

    def test_list_filter_type(self) -> None:
        self.eng.create_package(self._mk(package_type="full"))
        self.eng.create_package(self._mk(package_type="incremental"))
        items = self.eng.list_packages(package_type="full")
        assert len(items) == 1
        assert items[0].package_type == "full"

    def test_list_filter_status(self) -> None:
        self.eng.create_package(self._mk(status="pending"))
        self.eng.create_package(self._mk(status="ready"))
        items = self.eng.list_packages(status="ready")
        assert len(items) == 1
        assert items[0].status == "ready"

    def test_update_package(self) -> None:
        p = self.eng.create_package(self._mk())
        updated = self.eng.update_package(p.package_id, {"target_dataset_rid": "new-target", "package_type": "full"})
        assert updated.target_dataset_rid == "new-target"
        assert updated.package_type == "full"

    def test_delete_package(self) -> None:
        p = self.eng.create_package(self._mk())
        assert self.eng.delete_package(p.package_id) is True
        assert self.eng.delete_package(p.package_id) is False

    def test_build_package(self) -> None:
        p = self.eng.create_package(self._mk(status="pending"))
        built = self.eng.build_package(p.package_id)
        assert built.status == "ready"

    def test_fail_package(self) -> None:
        p = self.eng.create_package(self._mk(status="pending"))
        self.eng.build_package(p.package_id)
        # Manually set to packaging to test fail transition
        self.eng.update_package(p.package_id, {"status": "packaging"})
        failed = self.eng.fail_package(p.package_id)
        assert failed.status == "failed"

    def test_apply_package(self) -> None:
        p = self.eng.create_package(self._mk(status="ready"))
        result = self.eng.apply_package(p.package_id)
        assert result["package_id"] == p.package_id
        assert result["applied"] is True
        assert self.eng.get_package(p.package_id).status == "applied"

    def test_missing_source(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.create_package(self._mk(source_dataset_rid=""))
        assert exc.value.code == "MISSING_SOURCE"

    def test_missing_target(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.create_package(self._mk(target_dataset_rid=""))
        assert exc.value.code == "MISSING_TARGET"

    def test_invalid_package_type(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.create_package(self._mk(package_type="unknown"))
        assert exc.value.code == "INVALID_PACKAGE_TYPE"

    def test_invalid_status(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.create_package(self._mk(status="unknown"))
        assert exc.value.code == "INVALID_STATUS"

    def test_not_found_get(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.get_package("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_build(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.build_package("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_apply(self) -> None:
        with pytest.raises(PlatformIntegrationError) as exc:
            self.eng.apply_package("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_max_packages_eviction(self) -> None:
        for i in range(_MAX_FERRY_PACKAGES + 5):
            self.eng.create_package(self._mk(source_dataset_rid=f"src-{i}", target_dataset_rid=f"tgt-{i}"))
        assert len(self.eng.list_packages()) == _MAX_FERRY_PACKAGES


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_health_app_singleton(self) -> None:
        a = get_health_app_engine()
        b = get_health_app_engine()
        assert a is b

    def test_function_integration_singleton(self) -> None:
        a = get_function_integration_engine()
        b = get_function_integration_engine()
        assert a is b

    def test_ferry_package_singleton(self) -> None:
        a = get_ferry_package_engine()
        b = get_ferry_package_engine()
        assert a is b
