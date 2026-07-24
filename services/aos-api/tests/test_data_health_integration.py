"""W2-AM · Data Health Integration 组测试（#139 / #140 / #141）.

覆盖 HealthIssuesIntegrationEngine / DatasetHealthTabEngine / LineageHealthColoringEngine 三引擎。
"""
from __future__ import annotations

import pytest

from aos_api.data_health_integration import (
    DatasetHealthTab,
    DatasetHealthTabEngine,
    DatasetHealthTabError,
    HealthIssue,
    HealthIssuesIntegrationEngine,
    HealthIssuesIntegrationError,
    LineageColoringConfig,
    LineageHealthColor,
    LineageHealthColoringEngine,
    LineageHealthColoringError,
    get_dataset_health_tab_engine,
    get_health_issues_integration_engine,
    get_lineage_health_coloring_engine,
)


# ════════════════════ HealthIssuesIntegrationEngine ════════════════════

class TestHealthIssuesIntegration:
    def setup_method(self) -> None:
        self.eng = HealthIssuesIntegrationEngine()
        self.eng._issues = {}

    def test_create_issue(self) -> None:
        issue = self.eng.create_issue(
            dataset_rid="ds-1",
            check_id="chk-1",
            check_name="Freshness Check",
            severity="warning",
            title="Test Issue",
            description="This is a test",
        )
        assert issue.issue_id.startswith("hsi-")
        assert issue.dataset_rid == "ds-1"
        assert issue.severity == "warning"
        assert issue.status == "open"
        assert issue.created_at is not None
        assert issue.created_by_check is False
        assert issue.linked_check_runs == []

    def test_get_issue(self) -> None:
        i1 = self.eng.create_issue(
            "ds-1", "chk-1", "Freshness Check", "warning", "T", "D"
        )
        fetched = self.eng.get_issue(i1.issue_id)
        assert fetched.issue_id == i1.issue_id
        assert fetched.dataset_rid == "ds-1"

    def test_list_issues(self) -> None:
        self.eng.create_issue("ds-1", "c1", "C1", "warning", "T1", "D1")
        self.eng.create_issue("ds-1", "c2", "C2", "critical", "T2", "D2")
        items = self.eng.list_issues()
        assert len(items) == 2

    def test_list_filter_dataset(self) -> None:
        self.eng.create_issue("ds-1", "c1", "C1", "warning", "T1", "D1")
        self.eng.create_issue("ds-2", "c2", "C2", "warning", "T2", "D2")
        self.eng.create_issue("ds-1", "c3", "C3", "warning", "T3", "D3")
        items = self.eng.list_issues(dataset_rid="ds-1")
        assert len(items) == 2
        for i in items:
            assert i.dataset_rid == "ds-1"

    def test_list_filter_status(self) -> None:
        i1 = self.eng.create_issue("ds-1", "c1", "C1", "warning", "T1", "D1")
        self.eng.create_issue("ds-1", "c2", "C2", "warning", "T2", "D2")
        self.eng.resolve_issue(i1.issue_id)
        open_items = self.eng.list_issues(status="open")
        resolved_items = self.eng.list_issues(status="resolved")
        assert len(open_items) == 1
        assert len(resolved_items) == 1
        assert resolved_items[0].status == "resolved"

    def test_list_filter_severity(self) -> None:
        self.eng.create_issue("ds-1", "c1", "C1", "critical", "T1", "D1")
        self.eng.create_issue("ds-1", "c2", "C2", "warning", "T2", "D2")
        self.eng.create_issue("ds-1", "c3", "C3", "info", "T3", "D3")
        critical = self.eng.list_issues(severity="critical")
        warning = self.eng.list_issues(severity="warning")
        assert len(critical) == 1
        assert len(warning) == 1
        assert critical[0].severity == "critical"
        assert warning[0].severity == "warning"

    def test_update_issue(self) -> None:
        issue = self.eng.create_issue("ds-1", "c1", "C1", "warning", "T", "D")
        updated = self.eng.update_issue(issue.issue_id, {
            "status": "in_progress",
            "severity": "critical",
        })
        assert updated.status == "in_progress"
        assert updated.severity == "critical"
        assert updated.updated_at is not None

    def test_resolve_issue(self) -> None:
        issue = self.eng.create_issue("ds-1", "c1", "C1", "warning", "T", "D")
        resolved = self.eng.resolve_issue(issue.issue_id)
        assert resolved.status == "resolved"
        assert resolved.resolved_at is not None
        assert resolved.updated_at is not None

    def test_close_issue(self) -> None:
        issue = self.eng.create_issue("ds-1", "c1", "C1", "warning", "T", "D")
        closed = self.eng.close_issue(issue.issue_id)
        assert closed.status == "closed"
        assert closed.updated_at is not None

    def test_auto_create_from_check(self) -> None:
        issue = self.eng.auto_create_from_check(
            dataset_rid="ds-1",
            check_id="chk-1",
            check_name="Freshness Check",
            severity="critical",
            failure_message="Data is stale",
        )
        assert issue.issue_id.startswith("hsi-")
        assert issue.created_by_check is True
        assert issue.status == "open"
        assert "[CRITICAL]" in issue.title
        assert "Freshness Check" in issue.title
        assert "ds-1" in issue.title
        assert issue.description == "Data is stale"

    def test_auto_resolve_from_check(self) -> None:
        self.eng.auto_create_from_check(
            "ds-1", "chk-1", "Freshness Check", "critical", "stale"
        )
        resolved = self.eng.auto_resolve_from_check("ds-1", "chk-1")
        assert resolved is not None
        assert resolved.status == "resolved"
        assert resolved.resolved_at is not None

    def test_auto_resolve_returns_none(self) -> None:
        # 无候选 issue 时返回 None
        result = self.eng.auto_resolve_from_check("ds-none", "chk-none")
        assert result is None

    def test_link_check_run(self) -> None:
        issue = self.eng.create_issue("ds-1", "c1", "C1", "warning", "T", "D")
        updated = self.eng.link_check_run(issue.issue_id, "run-001")
        assert "run-001" in updated.linked_check_runs
        # 幂等：再次关联同一 run 不重复
        updated2 = self.eng.link_check_run(issue.issue_id, "run-001")
        assert updated2.linked_check_runs.count("run-001") == 1
        # 关联第二个 run
        updated3 = self.eng.link_check_run(issue.issue_id, "run-002")
        assert "run-001" in updated3.linked_check_runs
        assert "run-002" in updated3.linked_check_runs

    def test_missing_dataset(self) -> None:
        with pytest.raises(HealthIssuesIntegrationError) as exc:
            self.eng.create_issue("", "chk-1", "C1", "warning", "T", "D")
        assert exc.value.code == "MISSING_DATASET"

    def test_missing_check(self) -> None:
        with pytest.raises(HealthIssuesIntegrationError) as exc:
            self.eng.create_issue("ds-1", "", "C1", "warning", "T", "D")
        assert exc.value.code == "MISSING_CHECK"

    def test_invalid_severity(self) -> None:
        with pytest.raises(HealthIssuesIntegrationError) as exc:
            self.eng.create_issue("ds-1", "c1", "C1", "bad-severity", "T", "D")
        assert exc.value.code == "INVALID_SEVERITY"

    def test_not_found(self) -> None:
        with pytest.raises(HealthIssuesIntegrationError) as exc:
            self.eng.get_issue("nonexistent-id")
        assert exc.value.code == "NOT_FOUND"

    def test_max_issues_eviction(self) -> None:
        from aos_api.data_health_integration import _MAX_HEALTH_ISSUES
        for i in range(_MAX_HEALTH_ISSUES + 5):
            self.eng.create_issue(
                dataset_rid=f"ds-{i}",
                check_id=f"c-{i}",
                check_name=f"C{i}",
                severity="warning",
                title=f"T{i}",
                description=f"D{i}",
            )
        assert len(self.eng._issues) == _MAX_HEALTH_ISSUES


# ════════════════════ DatasetHealthTabEngine ════════════════════

class TestDatasetHealthTab:
    def setup_method(self) -> None:
        self.eng = DatasetHealthTabEngine()
        self.eng._tabs = {}
        self.eng._dataset_index = {}

    def test_register(self) -> None:
        tab = self.eng.register("ds-1")
        assert tab.tab_id.startswith("dht-")
        assert tab.dataset_rid == "ds-1"
        assert tab.overall_status == "unknown"
        assert tab.created_at is not None
        assert tab.recommendations == []
        assert tab.trends == []

    def test_register_idempotent(self) -> None:
        t1 = self.eng.register("ds-1")
        t2 = self.eng.register("ds-1")
        assert t1.tab_id == t2.tab_id
        assert len(self.eng._tabs) == 1

    def test_get(self) -> None:
        tab = self.eng.register("ds-1")
        fetched = self.eng.get(tab.tab_id)
        assert fetched.tab_id == tab.tab_id
        assert fetched.dataset_rid == "ds-1"

    def test_get_by_dataset(self) -> None:
        self.eng.register("ds-1")
        self.eng.register("ds-2")
        tab = self.eng.get_by_dataset("ds-1")
        assert tab.dataset_rid == "ds-1"

    def test_list(self) -> None:
        self.eng.register("ds-1")
        self.eng.register("ds-2")
        assert len(self.eng.list()) == 2

    def test_list_filter_dataset(self) -> None:
        self.eng.register("ds-1")
        self.eng.register("ds-2")
        items = self.eng.list(dataset_rid="ds-1")
        assert len(items) == 1
        assert items[0].dataset_rid == "ds-1"

    def test_update_status(self) -> None:
        self.eng.register("ds-1")
        updated = self.eng.update_status(
            "ds-1", "warning", {"total": 5, "passed": 3, "failed": 1, "warning": 1}
        )
        assert updated.overall_status == "warning"
        assert updated.checks_summary["total"] == 5
        assert updated.checks_summary["failed"] == 1
        assert updated.last_check_at is not None
        assert updated.updated_at is not None

    def test_add_recommendation(self) -> None:
        self.eng.register("ds-1")
        updated = self.eng.add_recommendation("ds-1", "Fix stale data")
        assert "Fix stale data" in updated.recommendations

    def test_add_recommendation_idempotent(self) -> None:
        self.eng.register("ds-1")
        self.eng.add_recommendation("ds-1", "Rec A")
        updated = self.eng.add_recommendation("ds-1", "Rec A")
        assert updated.recommendations.count("Rec A") == 1

    def test_add_trend(self) -> None:
        self.eng.register("ds-1")
        updated = self.eng.add_trend("ds-1", "2026-07-23", "warning", 0.6)
        assert len(updated.trends) == 1
        assert updated.trends[0]["date"] == "2026-07-23"
        assert updated.trends[0]["status"] == "warning"
        assert updated.trends[0]["pass_rate"] == 0.6

    def test_get_overall_health(self) -> None:
        self.eng.register("ds-1")
        self.eng.update_status(
            "ds-1", "critical", {"total": 4, "passed": 1, "failed": 3, "warning": 0}
        )
        result = self.eng.get_overall_health("ds-1")
        assert result["overall_status"] == "critical"
        assert result["checks_summary"]["failed"] == 3

    def test_delete(self) -> None:
        tab = self.eng.register("ds-1")
        self.eng.delete(tab.tab_id)
        with pytest.raises(DatasetHealthTabError) as exc:
            self.eng.get(tab.tab_id)
        assert exc.value.code == "NOT_FOUND"
        # 删除后 _dataset_index 也应清理
        assert "ds-1" not in self.eng._dataset_index

    def test_missing_dataset(self) -> None:
        with pytest.raises(DatasetHealthTabError) as exc:
            self.eng.register("")
        assert exc.value.code == "MISSING_DATASET"

    def test_invalid_status(self) -> None:
        self.eng.register("ds-1")
        with pytest.raises(DatasetHealthTabError) as exc:
            self.eng.update_status("ds-1", "bad-status", {"total": 0})
        assert exc.value.code == "INVALID_STATUS"

    def test_not_found(self) -> None:
        with pytest.raises(DatasetHealthTabError) as exc:
            self.eng.get("nonexistent-id")
        assert exc.value.code == "NOT_FOUND"

    def test_max_tabs_eviction(self) -> None:
        from aos_api.data_health_integration import _MAX_DATASET_HEALTH_TABS
        for i in range(_MAX_DATASET_HEALTH_TABS + 5):
            self.eng.register(f"ds-{i}")
        assert len(self.eng._tabs) == _MAX_DATASET_HEALTH_TABS


# ════════════════════ LineageHealthColoringEngine ════════════════════

class TestLineageHealthColoring:
    def setup_method(self) -> None:
        self.eng = LineageHealthColoringEngine()
        self.eng._colors = {}
        self.eng._configs = {}

    def test_register_color(self) -> None:
        color = self.eng.register_color(
            dataset_rid="ds-1",
            health_status="healthy",
            color_code="green",
            display_name="Healthy",
            tooltip="All checks passed",
        )
        assert color.color_id.startswith("lhc-")
        assert color.dataset_rid == "ds-1"
        assert color.health_status == "healthy"
        assert color.color_code == "green"
        assert color.updated_at is not None

    def test_get_color(self) -> None:
        self.eng.register_color("ds-1", "healthy", "green", "Healthy", "ok")
        color = self.eng.get_color("ds-1")
        assert color.dataset_rid == "ds-1"
        assert color.color_code == "green"

    def test_list_colors(self) -> None:
        self.eng.register_color("ds-1", "healthy", "green", "H", "ok")
        self.eng.register_color("ds-2", "critical", "red", "C", "bad")
        items = self.eng.list_colors()
        assert len(items) == 2

    def test_list_filter_status(self) -> None:
        self.eng.register_color("ds-1", "healthy", "green", "H", "ok")
        self.eng.register_color("ds-2", "critical", "red", "C", "bad")
        self.eng.register_color("ds-3", "warning", "yellow", "W", "warn")
        healthy = self.eng.list_colors(status_filter="healthy")
        critical = self.eng.list_colors(status_filter="critical")
        assert len(healthy) == 1
        assert len(critical) == 1
        assert healthy[0].health_status == "healthy"
        assert critical[0].health_status == "critical"

    def test_update_color(self) -> None:
        self.eng.register_color("ds-1", "healthy", "green", "H", "ok")
        updated = self.eng.update_color("ds-1", {
            "health_status": "warning",
            "color_code": "yellow",
        })
        assert updated.health_status == "warning"
        assert updated.color_code == "yellow"
        assert updated.updated_at is not None

    def test_delete_color(self) -> None:
        self.eng.register_color("ds-1", "healthy", "green", "H", "ok")
        self.eng.delete_color("ds-1")
        with pytest.raises(LineageHealthColoringError) as exc:
            self.eng.get_color("ds-1")
        assert exc.value.code == "NOT_FOUND"

    def test_register_config(self) -> None:
        cfg = self.eng.register_config(LineageColoringConfig(name="Default Scheme"))
        assert cfg.config_id.startswith("lcc-")
        assert cfg.name == "Default Scheme"
        assert cfg.color_scheme == "traffic_light"
        assert cfg.created_at is not None
        # 默认 mapping 应填充
        assert cfg.status_color_mapping != {}

    def test_get_config(self) -> None:
        cfg = self.eng.register_config(LineageColoringConfig(name="C1"))
        fetched = self.eng.get_config(cfg.config_id)
        assert fetched.config_id == cfg.config_id
        assert fetched.name == "C1"

    def test_list_configs(self) -> None:
        self.eng.register_config(LineageColoringConfig(name="C1"))
        self.eng.register_config(LineageColoringConfig(name="C2"))
        items = self.eng.list_configs()
        assert len(items) == 2

    def test_apply_coloring(self) -> None:
        cfg = self.eng.register_config(LineageColoringConfig(name="Apply"))
        results = self.eng.apply_coloring(["ds-1", "ds-2"], cfg.config_id)
        assert len(results) == 2
        # 新 dataset 默认 unknown -> gray（默认 traffic_light mapping）
        for r in results:
            assert r.health_status == "unknown"
            assert r.color_code == "gray"
        # apply 后可通过 get_color 拿到
        assert self.eng.get_color("ds-1").color_code == "gray"

    def test_missing_dataset(self) -> None:
        with pytest.raises(LineageHealthColoringError) as exc:
            self.eng.register_color("", "healthy", "green", "H", "ok")
        assert exc.value.code == "MISSING_DATASET"

    def test_invalid_health_status(self) -> None:
        with pytest.raises(LineageHealthColoringError) as exc:
            self.eng.register_color("ds-1", "bad-status", "green", "H", "ok")
        assert exc.value.code == "INVALID_HEALTH_STATUS"

    def test_invalid_color_code(self) -> None:
        with pytest.raises(LineageHealthColoringError) as exc:
            self.eng.register_color("ds-1", "healthy", "purple", "H", "ok")
        assert exc.value.code == "INVALID_COLOR_CODE"

    def test_missing_name(self) -> None:
        with pytest.raises(LineageHealthColoringError) as exc:
            self.eng.register_config(LineageColoringConfig(name=""))
        assert exc.value.code == "MISSING_NAME"

    def test_invalid_color_scheme(self) -> None:
        with pytest.raises(LineageHealthColoringError) as exc:
            self.eng.register_config(
                LineageColoringConfig(name="C1", color_scheme="bad-scheme")
            )
        assert exc.value.code == "INVALID_COLOR_SCHEME"

    def test_not_found(self) -> None:
        with pytest.raises(LineageHealthColoringError) as exc:
            self.eng.get_color("nonexistent-ds")
        assert exc.value.code == "NOT_FOUND"

    def test_config_not_found(self) -> None:
        with pytest.raises(LineageHealthColoringError) as exc:
            self.eng.get_config("nonexistent-id")
        assert exc.value.code == "CONFIG_NOT_FOUND"

    def test_max_colors_eviction(self) -> None:
        from aos_api.data_health_integration import _MAX_LINEAGE_COLORS
        for i in range(_MAX_LINEAGE_COLORS + 5):
            self.eng.register_color(
                dataset_rid=f"ds-{i}",
                health_status="healthy",
                color_code="green",
                display_name=f"H{i}",
                tooltip="ok",
            )
        assert len(self.eng._colors) == _MAX_LINEAGE_COLORS


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_issues_singleton(self) -> None:
        a = get_health_issues_integration_engine()
        b = get_health_issues_integration_engine()
        assert a is b

    def test_dataset_tab_singleton(self) -> None:
        a = get_dataset_health_tab_engine()
        b = get_dataset_health_tab_engine()
        assert a is b

    def test_coloring_singleton(self) -> None:
        a = get_lineage_health_coloring_engine()
        b = get_lineage_health_coloring_engine()
        assert a is b
