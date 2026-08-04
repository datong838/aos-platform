"""Phase 5 · Worker-4 回归集成测试.

跨模块集成测试，验证 Phase 1-4 的核心功能协同工作。
覆盖：路由注册完整性、种子数据一致性、引擎 Singleton/线程安全、CRUD 数据完整性。
"""
from __future__ import annotations

import threading

import pytest
from fastapi import APIRouter, FastAPI


# ────────────────────────────────────────────────────────────────────
# 1. 路由注册完整性：main.py 中所有路由都能正常加载
# ────────────────────────────────────────────────────────────────────


class TestRouteRegistration:
    """验证 create_app() 成功注册所有 Phase 1-4 路由。"""

    def test_create_app_returns_fastapi(self) -> None:
        from aos_api.main import create_app

        app = create_app()
        assert isinstance(app, FastAPI)

    def test_phase1_routers_importable(self) -> None:
        """Phase 1 Workshop 路由模块可以成功导入。"""
        from aos_api.routers import workshop_phase1
        from aos_api.routers import widgets_registry
        from aos_api.routers import themes
        from aos_api.routers import modules_widgets

        assert isinstance(workshop_phase1.router, APIRouter)
        assert isinstance(widgets_registry.router, APIRouter)
        assert isinstance(themes.router, APIRouter)
        assert isinstance(modules_widgets.router, APIRouter)

    def test_phase2_routers_importable(self) -> None:
        """Phase 2 Model Management 路由模块可以成功导入。"""
        from aos_api.routers import model_catalog
        from aos_api.routers import model_capacity
        from aos_api.routers import model_providers
        from aos_api.routers import model_routes

        assert isinstance(model_catalog.router, APIRouter)
        assert isinstance(model_capacity.router, APIRouter)
        assert isinstance(model_providers.router, APIRouter)
        assert isinstance(model_routes.router, APIRouter)

    def test_phase3_routers_importable(self) -> None:
        """Phase 3 AIP 路由模块可以成功导入。"""
        from aos_api.routers.phase3_aip_agents import router as agents_router
        from aos_api.routers.phase3_aip_assist import router as assist_router
        from aos_api.routers.phase3_aip_capabilities import router as cap_router
        from aos_api.routers.phase3_aip_logic import router as logic_router
        from aos_api.routers.phase3_aip_tools import router as tools_router
        from aos_api.routers.phase3_aip_drafts import router as drafts_router
        from aos_api.routers.phase3_aip_lineage import router as lineage_router

        for r in (agents_router, assist_router, cap_router, logic_router, tools_router, drafts_router, lineage_router):
            assert isinstance(r, APIRouter)

    def test_phase4_routers_importable(self) -> None:
        """Phase 4 Ontology 路由模块可以成功导入。"""
        from aos_api.routers.phase4_ontology_types import router as types_router
        from aos_api.routers.phase4_ontology_branches import router as branches_router
        from aos_api.routers.phase4_ontology_wikis import router as wikis_router
        from aos_api.routers.phase4_ontology_functions import router as functions_router
        from aos_api.routers.phase4_ontology_actions import router as actions_router
        from aos_api.routers.phase4_ontology_links import router as links_router

        for r in (types_router, branches_router, wikis_router, functions_router, actions_router, links_router):
            assert isinstance(r, APIRouter)

    def test_phase3_router_prefixes(self) -> None:
        """Phase 3 路由都有 /v1/aip 前缀。"""
        from aos_api.routers.phase3_aip_agents import router as agents_router
        from aos_api.routers.phase3_aip_capabilities import router as cap_router

        assert agents_router.prefix == "/v1/aip"
        assert cap_router.prefix == "/v1/aip"

    def test_phase4_router_prefixes(self) -> None:
        """Phase 4 路由都有 /v1/ontology 前缀。"""
        from aos_api.routers.phase4_ontology_types import router as types_router
        from aos_api.routers.phase4_ontology_branches import router as branches_router

        assert types_router.prefix == "/v1/ontology"
        assert branches_router.prefix == "/v1/ontology"

    def test_health_router_has_endpoints(self) -> None:
        from aos_api.routers.health import router

        assert isinstance(router, APIRouter)
        # health router 有至少 2 个路由（/v1/health + /v1/ready）
        assert len(router.routes) >= 2

    def test_workshop_phase1_aggregates_sub_routers(self) -> None:
        """workshop_phase1 聚合了 widgets/themes/modules 等子路由。"""
        from aos_api.routers.workshop_phase1 import router

        # 聚合了 8 个子路由
        assert len(router.routes) >= 8


# ────────────────────────────────────────────────────────────────────
# 2. 种子数据加载后数据一致性
# ────────────────────────────────────────────────────────────────────


class TestSeedDataConsistency:
    """验证种子数据加载后的数据一致性。"""

    def test_seed_modules_loaded(self) -> None:
        """种子模块数据存在。"""
        from aos_api.module_store import list_modules
        from aos_api.tenant_scope import TenantScope

        items = list_modules(TenantScope("dev-org", "dev-project"))
        assert len(items) > 0
        for m in items:
            assert "id" in m
            assert "title" in m or "name" in m

    def test_seed_widget_catalog_loaded(self) -> None:
        """种子 widget 目录数据存在。"""
        from aos_api.tenant_scope import TenantScope
        from aos_api.widget_catalog import list_widgets

        items = list_widgets(TenantScope("dev-org", "dev-project"))
        assert len(items) > 0
        for w in items:
            assert "id" in w
            assert "name" in w
            assert "source" in w

    def test_seed_model_catalog_loaded(self) -> None:
        """种子模型目录数据存在。"""
        from aos_api.model_catalog import list_catalog

        items = list_catalog()
        assert len(items) > 0
        for m in items:
            assert "id" in m
            assert "provider" in m

    def test_seed_themes_loaded(self) -> None:
        """种子主题数据存在。"""
        from aos_api.tenant_scope import TenantScope
        from aos_api.themes import list_themes

        items = list_themes(TenantScope("dev-org", "dev-project"))
        assert len(items) > 0
        for t in items:
            assert "id" in t
            assert "name" in t
            assert "mode" in t


# ────────────────────────────────────────────────────────────────────
# 3. 引擎 Singleton 模式正确性
# ────────────────────────────────────────────────────────────────────


class TestEngineSingleton:
    """验证引擎的 Singleton 模式。"""

    def test_ontology_engine_singleton(self) -> None:
        from aos_api.ontology_engine import get_engine

        eng1 = get_engine()
        eng2 = get_engine()
        assert eng1 is eng2

    def test_vs_events_engine_singleton(self) -> None:
        from aos_api.vs_events import VsEventsEngine

        e1 = VsEventsEngine()
        e2 = VsEventsEngine()
        assert e1 is e2

    def test_aip_agents_engine_singleton(self) -> None:
        from aos_api.aip_agents_engine import get_engine

        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2

    def test_singleton_reset_works(self) -> None:
        """reset 后 singleton 实例不变，但数据被清空。"""
        from aos_api.ontology_engine import get_engine

        eng = get_engine()
        eng.create_object_type(name="before_reset")
        eng.reset()

        same_eng = get_engine()
        assert eng is same_eng
        items, total = eng.list_object_types()
        assert total == 0


# ────────────────────────────────────────────────────────────────────
# 4. 并发访问安全性（threading.Lock 正确性）
# ────────────────────────────────────────────────────────────────────


class TestConcurrencySafety:
    """验证并发操作下数据不丢失。"""

    def test_concurrent_create_object_types(self) -> None:
        """并发创建 ObjectType 不丢失数据。"""
        from aos_api.ontology_engine import get_engine

        eng = get_engine()
        eng.reset()

        results: list[str] = []
        errors: list[Exception] = []

        def worker(idx: int) -> None:
            try:
                ot = eng.create_object_type(name=f"concurrent_type_{idx}")
                results.append(ot.id)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert len(set(results)) == 10
        items, total = eng.list_object_types()
        assert total == 10
        eng.reset()

    def test_concurrent_vs_events_register(self) -> None:
        """并发注册 Events 不丢失数据。"""
        from aos_api.vs_events import VsEvents, VsEventsEngine

        eng = VsEventsEngine()
        eng.reset()

        results: list[str] = []
        errors: list[Exception] = []

        def worker(idx: int) -> None:
            try:
                item = VsEvents(name=f"event_{idx}")
                eng.register(item)
                results.append(item.id)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert len(eng.list()) == 10
        eng.reset()


# ────────────────────────────────────────────────────────────────────
# 5. CRUD 数据完整性
# ────────────────────────────────────────────────────────────────────


class TestCRUDIntegrity:
    """验证 CRUD 操作的数据完整性。"""

    def test_ontology_type_full_lifecycle(self) -> None:
        """创建 → 更新 → 删除 ObjectType 全流程。"""
        from aos_api.ontology_engine import get_engine

        eng = get_engine()
        eng.reset()

        ot = eng.create_object_type(name="lifecycle_test", display_name="Test")
        assert ot.name == "lifecycle_test"

        fetched = eng.get_object_type(ot.id)
        assert fetched is not None
        assert fetched.id == ot.id

        updated = eng.update_object_type(ot.id, display_name="Updated")
        assert updated.display_name == "Updated"

        assert eng.delete_object_type(ot.id) is True
        assert eng.get_object_type(ot.id) is None
        eng.reset()

    def test_ontology_objects_with_properties(self) -> None:
        """创建 Type → 添加 Property → 创建 Object → 检查 Preview。"""
        from aos_api.ontology_engine import get_engine

        eng = get_engine()
        eng.reset()

        ot = eng.create_object_type(name="product")
        eng.add_property(ot.id, name="sku", datatype="string")
        eng.add_property(ot.id, name="price", datatype="double")

        obj = eng.create_object(ot.id, name="P1", properties={"sku": "X1", "price": 9.9})
        assert obj.properties["sku"] == "X1"

        preview = eng.preview(ot.id)
        assert "sku" in preview["columns"]
        assert "price" in preview["columns"]
        assert preview["total"] == 1
        eng.reset()

    def test_model_catalog_to_registered_flow(self) -> None:
        """从 model-catalog 列表 → 注册到 registered-models。"""
        from aos_api.model_catalog import list_catalog, get_catalog
        from aos_api.registered_models import register_model, list_registered

        catalog_items = list_catalog()
        assert len(catalog_items) > 0
        model_id = catalog_items[0]["id"]

        cat_detail = get_catalog(model_id)
        assert cat_detail is not None

        reg = register_model({
            "modelId": model_id,
            "alias": "reg-test-alias",
            "quota": {"rpm": 100},
            "status": "enabled",
        })
        assert reg["modelId"] == model_id

        all_reg = list_registered()
        assert len(all_reg) > 0

    def test_widget_create_and_query(self) -> None:
        """Widget CRUD：创建 → 查列表 → 查详情。"""
        from aos_api.tenant_scope import TenantScope
        from aos_api.widget_catalog import create_widget, get_widget, list_widgets

        scope = TenantScope("dev-org", "dev-project")
        w = create_widget(scope, {
            "name": "regression_test_widget",
            "nameZh": "回归测试组件",
            "type": "stat-card",
            "source": "custom",
            "category": "test",
        })
        wid = w["id"]

        items = list_widgets(scope, source="custom")
        assert any(item["id"] == wid for item in items)

        detail = get_widget(scope, wid)
        assert detail is not None
        assert detail["name"] == "regression_test_widget"

    def test_theme_crud_lifecycle(self) -> None:
        """Theme CRUD：创建 → 更新 → 删除。"""
        from aos_api.tenant_scope import TenantScope
        from aos_api.themes import create_theme, delete_theme, get_theme, update_theme

        scope = TenantScope("dev-org", "dev-project")
        t = create_theme(scope, {
            "name": "reg_test_theme",
            "mode": "dark",
            "tokens": {"color": "#333"},
        })
        tid = t["id"]

        updated = update_theme(scope, tid, {"name": "updated_theme"})
        assert updated["name"] == "updated_theme"

        assert delete_theme(scope, tid) is True
        assert get_theme(scope, tid) is None

    def test_capacity_limits_crud(self) -> None:
        """Capacity limits：读取默认 → 设置 → 读取更新值。"""
        from aos_api.model_capacity import (
            get_or_default_limit,
            upsert_limit,
            SCOPE_PROJECT,
        )

        key = "reg-test-project"
        default = get_or_default_limit(SCOPE_PROJECT, key)
        assert "rpmLimit" in default

        updated = upsert_limit(SCOPE_PROJECT, key, {"rpmLimit": 200, "tpmLimit": 200000})
        assert updated["rpmLimit"] == 200

        reread = get_or_default_limit(SCOPE_PROJECT, key)
        assert reread["rpmLimit"] == 200


# ────────────────────────────────────────────────────────────────────
# 6. 跨模块集成测试
# ────────────────────────────────────────────────────────────────────


class TestCrossModuleIntegration:
    """跨模块功能协同验证。"""

    def test_ontology_type_to_branch_flow(self) -> None:
        """创建 ontology type → 创建 branch → 在 branch 中操作。"""
        from aos_api.ontology_engine import get_engine

        eng = get_engine()
        eng.reset()

        ot = eng.create_object_type(name="customer")
        eng.add_property(ot.id, name="name", datatype="string")

        branch = eng.create_branch("feature-1", parent_branch="main")
        assert branch.name == "feature-1"
        assert branch.parent_branch == "main"

        branches = eng.list_branches()
        assert len(branches) > 0
        eng.reset()

    def test_aip_agent_prompt_tools_flow(self) -> None:
        """创建 AIP agent → 设置 prompt → 查看 prompt → 查看 tools。"""
        from aos_api.aip_agents_engine import get_engine

        eng = get_engine()
        # 先创建一个 agent
        agent = eng.create(
            name="integration-agent",
            description="Integration test agent",
            source="platform",
        )
        assert agent is not None

        # 设置 prompt
        eng.set_prompt(agent.id, "You are a helpful assistant.")
        prompt = eng.get_prompt(agent.id)
        assert prompt == "You are a helpful assistant."

        # 查看 tools
        tools = eng.list_tools(agent.id)
        assert isinstance(tools, list)

    def test_vs_events_full_crud(self) -> None:
        """VS Events 引擎：注册 → 列表 → 详情 → 更新 → 删除。"""
        from aos_api.vs_events import VsEvents, VsEventsEngine

        eng = VsEventsEngine()
        eng.reset()

        item = VsEvents(name="integration_event", description="test", enabled=True)
        eng.register(item)

        items = eng.list()
        assert len(items) == 1

        fetched = eng.get(item.id)
        assert fetched is not None
        assert fetched.name == "integration_event"

        updated = eng.update(item.id, {"name": "updated_event"})
        assert updated.name == "updated_event"

        assert eng.delete(item.id) is True
        assert eng.get(item.id) is None
        eng.reset()

    def test_ontology_automap_and_column_mapping(self) -> None:
        """创建 Type + Properties → automap → 设置 column mapping → 查询。"""
        from aos_api.ontology_engine import get_engine

        eng = get_engine()
        eng.reset()

        ot = eng.create_object_type(name="shipment")
        eng.add_property(ot.id, name="tracking_no", datatype="string")
        eng.add_property(ot.id, name="weight", datatype="double")

        mappings = eng.automap(ot.id, ["tracking_no", "weight", "unknown_col"])
        assert len(mappings) == 3

        mapped = [m for m in mappings if m.target_property == "tracking_no"]
        assert len(mapped) == 1

        skipped = [m for m in mappings if m.status == "skipped"]
        assert len(skipped) == 1
        eng.reset()
