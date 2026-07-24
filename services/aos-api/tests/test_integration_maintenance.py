"""W2-AR · Integration Maintenance 组测试（#161 / #162 / #163）.

覆盖 DataIntegrationFrameworkEngine / PipelineMaintenanceEngine / OntologyInterfaceExtensionEngine 三引擎。
"""
from __future__ import annotations

import pytest

from aos_api.integration_maintenance import (
    DataExpectation,
    DataIntegrationError,
    DataIntegrationFrameworkEngine,
    IntegrationFramework,
    InterfaceExtensionError,
    InterfaceLinkType,
    InterfaceMarketplaceListing,
    OntologyInterfaceExtensionEngine,
    PipelineHealthCheck,
    PipelineMaintenanceEngine,
    PipelineMaintenanceError,
    StabilitySuggestion,
    get_data_integration_framework_engine,
    get_ontology_interface_extension_engine,
    get_pipeline_maintenance_engine,
)


# ════════════════════ DataIntegrationFrameworkEngine ════════════════════

class TestDataIntegrationFramework:
    def setup_method(self) -> None:
        self.eng = DataIntegrationFrameworkEngine()
        self.eng._frameworks = {}

    def test_register(self) -> None:
        fw = self.eng.register(IntegrationFramework(name="fw1"))
        assert fw.framework_id.startswith("fw-")
        assert fw.name == "fw1"
        assert fw.status == "active"
        assert fw.created_at is not None

    def test_get(self) -> None:
        fw = self.eng.register(IntegrationFramework(name="fw1"))
        fetched = self.eng.get(fw.framework_id)
        assert fetched.framework_id == fw.framework_id
        assert fetched.name == "fw1"

    def test_list(self) -> None:
        self.eng.register(IntegrationFramework(name="fw1"))
        self.eng.register(IntegrationFramework(name="fw2"))
        assert len(self.eng.list()) == 2

    def test_list_filter_status(self) -> None:
        fw1 = self.eng.register(IntegrationFramework(name="fw1"))
        self.eng.register(IntegrationFramework(name="fw2"))
        active = self.eng.list(status="active")
        assert len(active) == 2
        for f in active:
            assert f.status == "active"
        # 更新一个为非 active 后过滤
        self.eng.update(fw1.framework_id, {"status": "inactive"})
        only_active = self.eng.list(status="active")
        assert len(only_active) == 1
        assert only_active[0].status == "active"

    def test_update(self) -> None:
        fw = self.eng.register(IntegrationFramework(name="fw1"))
        updated = self.eng.update(fw.framework_id, {"description": "new desc"})
        assert updated.description == "new desc"
        assert updated.updated_at is not None

    def test_delete(self) -> None:
        fw = self.eng.register(IntegrationFramework(name="fw1"))
        self.eng.delete(fw.framework_id)
        with pytest.raises(DataIntegrationError) as exc:
            self.eng.get(fw.framework_id)
        assert exc.value.code == "NOT_FOUND"

    def test_link_connection(self) -> None:
        fw = self.eng.register(IntegrationFramework(name="fw1"))
        linked = self.eng.link_connection(fw.framework_id, "conn-1")
        assert linked.connection_id == "conn-1"
        assert linked.connection_id != ""

    def test_link_transform(self) -> None:
        fw = self.eng.register(IntegrationFramework(name="fw1"))
        linked = self.eng.link_transform(fw.framework_id, "tf-1")
        assert linked.transform_id == "tf-1"
        assert linked.transform_id != ""

    def test_get_summary_empty(self) -> None:
        fw = self.eng.register(IntegrationFramework(name="fw1"))
        summary = self.eng.get_summary(fw.framework_id)
        assert summary["has_connection"] is False
        assert summary["has_transform"] is False
        assert summary["has_management"] is False
        assert summary["completeness"] == "empty"

    def test_get_summary_partial(self) -> None:
        fw = self.eng.register(IntegrationFramework(name="fw1"))
        self.eng.link_connection(fw.framework_id, "conn-1")
        summary = self.eng.get_summary(fw.framework_id)
        assert summary["has_connection"] is True
        assert summary["has_transform"] is False
        assert summary["completeness"] == "partial"

    def test_get_summary_full(self) -> None:
        fw = self.eng.register(
            IntegrationFramework(name="fw1", management_config={"key": "val"})
        )
        self.eng.link_connection(fw.framework_id, "conn-1")
        self.eng.link_transform(fw.framework_id, "tf-1")
        summary = self.eng.get_summary(fw.framework_id)
        assert summary["has_connection"] is True
        assert summary["has_transform"] is True
        assert summary["has_management"] is True
        assert summary["completeness"] == "full"

    def test_missing_name(self) -> None:
        with pytest.raises(DataIntegrationError) as exc:
            self.eng.register(IntegrationFramework(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_not_found_get(self) -> None:
        with pytest.raises(DataIntegrationError) as exc:
            self.eng.get("nonexist")
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_update(self) -> None:
        with pytest.raises(DataIntegrationError) as exc:
            self.eng.update("nonexist", {})
        assert exc.value.code == "NOT_FOUND"

    def test_not_found_link_connection(self) -> None:
        with pytest.raises(DataIntegrationError) as exc:
            self.eng.link_connection("nonexist", "c1")
        assert exc.value.code == "NOT_FOUND"

    def test_max_frameworks_eviction(self) -> None:
        from aos_api.integration_maintenance import _MAX_INTEGRATION_FRAMEWORKS
        for i in range(_MAX_INTEGRATION_FRAMEWORKS + 5):
            self.eng.register(IntegrationFramework(name=f"fw{i}"))
        assert len(self.eng._frameworks) == _MAX_INTEGRATION_FRAMEWORKS


# ════════════════════ PipelineMaintenanceEngine ════════════════════

class TestPipelineMaintenance:
    def setup_method(self) -> None:
        self.eng = PipelineMaintenanceEngine()
        self.eng._checks = {}
        self.eng._expectations = {}
        self.eng._suggestions = {}

    # ── 健康检查 ──

    def test_register_check(self) -> None:
        chk = self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="freshness")
        )
        assert chk.check_id.startswith("phc-")
        assert chk.pipeline_id == "p1"
        assert chk.check_type == "freshness"
        assert chk.status == "pass"
        assert chk.severity == "info"
        assert chk.created_at is not None

    def test_get_check(self) -> None:
        chk = self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="freshness")
        )
        fetched = self.eng.get_check(chk.check_id)
        assert fetched.check_id == chk.check_id
        assert fetched.pipeline_id == "p1"

    def test_list_checks(self) -> None:
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c1")
        )
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c2")
        )
        assert len(self.eng.list_checks()) == 2

    def test_list_checks_filter_pipeline(self) -> None:
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c1")
        )
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p2", check_type="c2")
        )
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c3")
        )
        items = self.eng.list_checks(pipeline_id="p1")
        assert len(items) == 2
        for c in items:
            assert c.pipeline_id == "p1"

    def test_list_checks_filter_status(self) -> None:
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c1", status="pass")
        )
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c2", status="fail")
        )
        passing = self.eng.list_checks(status="pass")
        failing = self.eng.list_checks(status="fail")
        assert len(passing) == 1
        assert len(failing) == 1
        assert passing[0].status == "pass"
        assert failing[0].status == "fail"

    def test_update_check(self) -> None:
        chk = self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c1")
        )
        updated = self.eng.update_check(chk.check_id, {"message": "new msg"})
        assert updated.message == "new msg"
        assert updated.check_id == chk.check_id

    def test_delete_check(self) -> None:
        chk = self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c1")
        )
        self.eng.delete_check(chk.check_id)
        with pytest.raises(PipelineMaintenanceError) as exc:
            self.eng.get_check(chk.check_id)
        assert exc.value.code == "NOT_FOUND"

    def test_list_failing_checks(self) -> None:
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c1", status="pass")
        )
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c2", status="fail")
        )
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c3", status="warning")
        )
        failing = self.eng.list_failing_checks()
        assert len(failing) == 2
        for c in failing:
            assert c.status in ("fail", "warning")

    def test_invalid_check_status(self) -> None:
        with pytest.raises(PipelineMaintenanceError) as exc:
            self.eng.register_check(
                PipelineHealthCheck(pipeline_id="p1", check_type="c1", status="bad")
            )
        assert exc.value.code == "INVALID_STATUS"

    def test_invalid_severity(self) -> None:
        with pytest.raises(PipelineMaintenanceError) as exc:
            self.eng.register_check(
                PipelineHealthCheck(
                    pipeline_id="p1", check_type="c1", severity="bad"
                )
            )
        assert exc.value.code == "INVALID_SEVERITY"

    # ── 数据期望 ──

    def test_register_expectation(self) -> None:
        exp = self.eng.register_expectation(DataExpectation(pipeline_id="p1"))
        assert exp.expectation_id.startswith("de-")
        assert exp.pipeline_id == "p1"
        assert exp.data_expiry_threshold_hours == 24
        assert exp.created_at is not None

    def test_list_expectations(self) -> None:
        self.eng.register_expectation(DataExpectation(pipeline_id="p1"))
        self.eng.register_expectation(DataExpectation(pipeline_id="p2"))
        self.eng.register_expectation(DataExpectation(pipeline_id="p1"))
        items = self.eng.list_expectations(pipeline_id="p1")
        assert len(items) == 2
        for e in items:
            assert e.pipeline_id == "p1"

    def test_update_expectation(self) -> None:
        exp = self.eng.register_expectation(DataExpectation(pipeline_id="p1"))
        updated = self.eng.update_expectation(
            exp.expectation_id, {"build_frequency": "daily"}
        )
        assert updated.build_frequency == "daily"
        assert updated.updated_at is not None

    def test_delete_expectation(self) -> None:
        exp = self.eng.register_expectation(DataExpectation(pipeline_id="p1"))
        self.eng.delete_expectation(exp.expectation_id)
        with pytest.raises(PipelineMaintenanceError) as exc:
            self.eng.get_expectation(exp.expectation_id)
        assert exc.value.code == "NOT_FOUND"

    def test_missing_pipeline_expectation(self) -> None:
        with pytest.raises(PipelineMaintenanceError) as exc:
            self.eng.register_expectation(DataExpectation(pipeline_id=""))
        assert exc.value.code == "MISSING_PIPELINE"

    # ── 稳定性建议 ──

    def test_register_suggestion(self) -> None:
        sug = self.eng.register_suggestion(
            StabilitySuggestion(pipeline_id="p1", suggestion_type="perf")
        )
        assert sug.suggestion_id.startswith("ss-")
        assert sug.pipeline_id == "p1"
        assert sug.suggestion_type == "perf"
        assert sug.priority == "medium"
        assert sug.created_at is not None

    def test_list_suggestions(self) -> None:
        self.eng.register_suggestion(
            StabilitySuggestion(pipeline_id="p1", suggestion_type="t1", priority="high")
        )
        self.eng.register_suggestion(
            StabilitySuggestion(pipeline_id="p2", suggestion_type="t2", priority="low")
        )
        self.eng.register_suggestion(
            StabilitySuggestion(pipeline_id="p1", suggestion_type="t3", priority="high")
        )
        # 按 pipeline_id 过滤
        p1_items = self.eng.list_suggestions(pipeline_id="p1")
        assert len(p1_items) == 2
        for s in p1_items:
            assert s.pipeline_id == "p1"
        # 按 priority 过滤
        high_items = self.eng.list_suggestions(priority="high")
        assert len(high_items) == 2
        for s in high_items:
            assert s.priority == "high"

    def test_delete_suggestion(self) -> None:
        sug = self.eng.register_suggestion(
            StabilitySuggestion(pipeline_id="p1", suggestion_type="perf")
        )
        self.eng.delete_suggestion(sug.suggestion_id)
        with pytest.raises(PipelineMaintenanceError) as exc:
            self.eng.get_suggestion(sug.suggestion_id)
        assert exc.value.code == "NOT_FOUND"

    def test_invalid_priority(self) -> None:
        with pytest.raises(PipelineMaintenanceError) as exc:
            self.eng.register_suggestion(
                StabilitySuggestion(
                    pipeline_id="p1", suggestion_type="perf", priority="bad"
                )
            )
        assert exc.value.code == "INVALID_PRIORITY"

    def test_missing_suggestion_type(self) -> None:
        with pytest.raises(PipelineMaintenanceError) as exc:
            self.eng.register_suggestion(
                StabilitySuggestion(pipeline_id="p1", suggestion_type="")
            )
        assert exc.value.code == "MISSING_SUGGESTION_TYPE"

    def test_missing_pipeline_suggestion(self) -> None:
        with pytest.raises(PipelineMaintenanceError) as exc:
            self.eng.register_suggestion(
                StabilitySuggestion(pipeline_id="", suggestion_type="perf")
            )
        assert exc.value.code == "MISSING_PIPELINE"

    # ── 综合 ──

    def test_monitor_pipeline_healthy(self) -> None:
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c1", status="pass")
        )
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c2", status="pass")
        )
        result = self.eng.monitor_pipeline("p1")
        assert result["total_checks"] == 2
        assert result["failing_checks"] == 0
        assert result["health_status"] == "healthy"

    def test_monitor_pipeline_degraded(self) -> None:
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c1", status="pass")
        )
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c2", status="warning")
        )
        result = self.eng.monitor_pipeline("p1")
        assert result["failing_checks"] == 1
        assert result["health_status"] == "degraded"

    def test_monitor_pipeline_critical(self) -> None:
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c1", status="fail")
        )
        self.eng.register_check(
            PipelineHealthCheck(pipeline_id="p1", check_type="c2", status="warning")
        )
        result = self.eng.monitor_pipeline("p1")
        assert result["failing_checks"] == 2
        assert result["health_status"] == "critical"

    def test_monitor_pipeline_empty(self) -> None:
        result = self.eng.monitor_pipeline("p1")
        assert result["total_checks"] == 0
        assert result["failing_checks"] == 0
        assert result["has_expectation"] is False
        assert result["suggestions_count"] == 0
        assert result["health_status"] == "healthy"

    # ── 边界 ──

    def test_max_checks_eviction(self) -> None:
        from aos_api.integration_maintenance import _MAX_PIPELINE_HEALTH_CHECKS
        for i in range(_MAX_PIPELINE_HEALTH_CHECKS + 5):
            self.eng.register_check(
                PipelineHealthCheck(pipeline_id=f"p{i}", check_type=f"c{i}")
            )
        assert len(self.eng._checks) == _MAX_PIPELINE_HEALTH_CHECKS


# ════════════════════ OntologyInterfaceExtensionEngine ════════════════════

class TestOntologyInterfaceExtension:
    def setup_method(self) -> None:
        self.eng = OntologyInterfaceExtensionEngine()
        self.eng._link_types = {}
        self.eng._listings = {}

    # ── 接口链接类型 ──

    def test_register_link_type(self) -> None:
        lt = self.eng.register_link_type(
            InterfaceLinkType(
                name="lt1", source_interface_id="i1", target_interface_id="i2"
            )
        )
        assert lt.link_type_id.startswith("ilt-")
        assert lt.name == "lt1"
        assert lt.source_interface_id == "i1"
        assert lt.target_interface_id == "i2"
        assert lt.cardinality == "many_to_many"
        assert lt.created_at is not None

    def test_get_link_type(self) -> None:
        lt = self.eng.register_link_type(
            InterfaceLinkType(
                name="lt1", source_interface_id="i1", target_interface_id="i2"
            )
        )
        fetched = self.eng.get_link_type(lt.link_type_id)
        assert fetched.link_type_id == lt.link_type_id
        assert fetched.name == "lt1"

    def test_list_link_types(self) -> None:
        self.eng.register_link_type(
            InterfaceLinkType(
                name="lt1", source_interface_id="i1", target_interface_id="i2"
            )
        )
        self.eng.register_link_type(
            InterfaceLinkType(
                name="lt2", source_interface_id="i1", target_interface_id="i3"
            )
        )
        self.eng.register_link_type(
            InterfaceLinkType(
                name="lt3", source_interface_id="i9", target_interface_id="i2"
            )
        )
        items = self.eng.list_link_types(source_interface_id="i1")
        assert len(items) == 2
        for lt in items:
            assert lt.source_interface_id == "i1"

    def test_update_link_type(self) -> None:
        lt = self.eng.register_link_type(
            InterfaceLinkType(
                name="lt1", source_interface_id="i1", target_interface_id="i2"
            )
        )
        updated = self.eng.update_link_type(lt.link_type_id, {"description": "new"})
        assert updated.description == "new"
        assert updated.updated_at is not None

    def test_delete_link_type(self) -> None:
        lt = self.eng.register_link_type(
            InterfaceLinkType(
                name="lt1", source_interface_id="i1", target_interface_id="i2"
            )
        )
        self.eng.delete_link_type(lt.link_type_id)
        with pytest.raises(InterfaceExtensionError) as exc:
            self.eng.get_link_type(lt.link_type_id)
        assert exc.value.code == "NOT_FOUND"

    def test_missing_name(self) -> None:
        with pytest.raises(InterfaceExtensionError) as exc:
            self.eng.register_link_type(
                InterfaceLinkType(
                    name="", source_interface_id="i1", target_interface_id="i2"
                )
            )
        assert exc.value.code == "MISSING_NAME"

    def test_missing_source_interface(self) -> None:
        with pytest.raises(InterfaceExtensionError) as exc:
            self.eng.register_link_type(
                InterfaceLinkType(
                    name="lt1", source_interface_id="", target_interface_id="i2"
                )
            )
        assert exc.value.code == "MISSING_SOURCE_INTERFACE"

    def test_invalid_cardinality(self) -> None:
        with pytest.raises(InterfaceExtensionError) as exc:
            self.eng.register_link_type(
                InterfaceLinkType(
                    name="lt1",
                    source_interface_id="i1",
                    target_interface_id="i2",
                    cardinality="bad",
                )
            )
        assert exc.value.code == "INVALID_CARDINALITY"

    def test_not_found_get_link_type(self) -> None:
        with pytest.raises(InterfaceExtensionError) as exc:
            self.eng.get_link_type("nonexist")
        assert exc.value.code == "NOT_FOUND"

    # ── Marketplace ──

    def test_register_listing(self) -> None:
        listing = self.eng.register_listing(
            InterfaceMarketplaceListing(interface_id="i1", title="My Listing")
        )
        assert listing.listing_id.startswith("iml-")
        assert listing.interface_id == "i1"
        assert listing.title == "My Listing"
        assert listing.status == "draft"
        assert listing.version == "1.0.0"
        assert listing.created_at is not None

    def test_get_listing(self) -> None:
        listing = self.eng.register_listing(
            InterfaceMarketplaceListing(interface_id="i1", title="My Listing")
        )
        fetched = self.eng.get_listing(listing.listing_id)
        assert fetched.listing_id == listing.listing_id
        assert fetched.title == "My Listing"

    def test_list_listings(self) -> None:
        self.eng.register_listing(
            InterfaceMarketplaceListing(interface_id="i1", title="L1", status="draft")
        )
        self.eng.register_listing(
            InterfaceMarketplaceListing(
                interface_id="i2", title="L2", status="published"
            )
        )
        self.eng.register_listing(
            InterfaceMarketplaceListing(interface_id="i3", title="L3", status="draft")
        )
        drafts = self.eng.list_listings(status="draft")
        published = self.eng.list_listings(status="published")
        assert len(drafts) == 2
        assert len(published) == 1
        for l in drafts:
            assert l.status == "draft"

    def test_publish_to_marketplace(self) -> None:
        listing = self.eng.register_listing(
            InterfaceMarketplaceListing(interface_id="i1", title="L1")
        )
        published = self.eng.publish_to_marketplace(listing.listing_id)
        assert published.status == "published"
        assert published.published_at is not None

    def test_import_from_marketplace(self) -> None:
        imported = self.eng.import_from_marketplace(
            interface_id="i1", title="Imported L"
        )
        assert imported.listing_id.startswith("iml-")
        assert imported.interface_id == "i1"
        assert imported.title == "Imported L"
        assert imported.status == "imported"

    def test_update_listing(self) -> None:
        listing = self.eng.register_listing(
            InterfaceMarketplaceListing(interface_id="i1", title="L1")
        )
        updated = self.eng.update_listing(
            listing.listing_id, {"description": "new desc"}
        )
        assert updated.description == "new desc"
        assert updated.updated_at is not None

    def test_delete_listing(self) -> None:
        listing = self.eng.register_listing(
            InterfaceMarketplaceListing(interface_id="i1", title="L1")
        )
        self.eng.delete_listing(listing.listing_id)
        with pytest.raises(InterfaceExtensionError) as exc:
            self.eng.get_listing(listing.listing_id)
        assert exc.value.code == "NOT_FOUND"

    def test_missing_interface(self) -> None:
        with pytest.raises(InterfaceExtensionError) as exc:
            self.eng.register_listing(
                InterfaceMarketplaceListing(interface_id="", title="L1")
            )
        assert exc.value.code == "MISSING_INTERFACE"

    def test_missing_title(self) -> None:
        with pytest.raises(InterfaceExtensionError) as exc:
            self.eng.register_listing(
                InterfaceMarketplaceListing(interface_id="i1", title="")
            )
        assert exc.value.code == "MISSING_TITLE"

    def test_invalid_listing_status(self) -> None:
        with pytest.raises(InterfaceExtensionError) as exc:
            self.eng.register_listing(
                InterfaceMarketplaceListing(
                    interface_id="i1", title="L1", status="bad"
                )
            )
        assert exc.value.code == "INVALID_STATUS"

    # ── 边界 ──

    def test_max_link_types_eviction(self) -> None:
        from aos_api.integration_maintenance import _MAX_INTERFACE_LINK_TYPES
        for i in range(_MAX_INTERFACE_LINK_TYPES + 5):
            self.eng.register_link_type(
                InterfaceLinkType(
                    name=f"lt{i}",
                    source_interface_id=f"src{i}",
                    target_interface_id=f"tgt{i}",
                )
            )
        assert len(self.eng._link_types) == _MAX_INTERFACE_LINK_TYPES

    def test_max_listings_eviction(self) -> None:
        from aos_api.integration_maintenance import _MAX_MARKETPLACE_LISTINGS
        for i in range(_MAX_MARKETPLACE_LISTINGS + 5):
            self.eng.register_listing(
                InterfaceMarketplaceListing(
                    interface_id=f"i{i}", title=f"L{i}"
                )
            )
        assert len(self.eng._listings) == _MAX_MARKETPLACE_LISTINGS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_data_integration_singleton(self) -> None:
        a = get_data_integration_framework_engine()
        b = get_data_integration_framework_engine()
        assert a is b

    def test_pipeline_maintenance_singleton(self) -> None:
        a = get_pipeline_maintenance_engine()
        b = get_pipeline_maintenance_engine()
        assert a is b

    def test_interface_extension_singleton(self) -> None:
        a = get_ontology_interface_extension_engine()
        b = get_ontology_interface_extension_engine()
        assert a is b
