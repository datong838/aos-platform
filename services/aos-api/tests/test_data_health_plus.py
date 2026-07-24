"""W2-AM · Data Health Plus 组测试（#136 / #137 / #138）.

覆盖 HealthDiagnosticsEngine / HealthMonitoringOptionsEngine / HealthNotificationEngine 三引擎。
"""
from __future__ import annotations

import pytest

from aos_api.data_health_plus import (
    FailedCheckDetail,
    HealthDiagnosticsEngine,
    HealthDiagnosticsError,
    HealthDiagnosticsReport,
    HealthMonitoringOptions,
    HealthMonitoringOptionsEngine,
    HealthMonitoringOptionsError,
    HealthNotification,
    HealthNotificationEngine,
    HealthNotificationError,
    get_health_diagnostics_engine,
    get_health_monitoring_options_engine,
    get_health_notification_engine,
)


# ════════════════════ HealthDiagnosticsEngine ════════════════════

class TestHealthDiagnostics:
    def setup_method(self) -> None:
        self.eng = HealthDiagnosticsEngine()
        self.eng._reports = {}
        self.eng._group_checks = {}

    def test_generate_report(self) -> None:
        report = self.eng.generate_diagnostics("group-1")
        assert report.report_id.startswith("hdr-")
        assert report.group_id == "group-1"
        assert report.total_checks > 0
        assert report.generated_at is not None

    def test_get_report(self) -> None:
        r1 = self.eng.generate_diagnostics("group-1")
        r2 = self.eng.get_report(r1.report_id)
        assert r2.report_id == r1.report_id
        assert r2.group_id == "group-1"

    def test_list_reports(self) -> None:
        self.eng.generate_diagnostics("group-1")
        self.eng.generate_diagnostics("group-1")
        reports = self.eng.list_reports("group-1")
        assert len(reports) == 2

    def test_list_reports_filter_group(self) -> None:
        self.eng.generate_diagnostics("group-a")
        self.eng.generate_diagnostics("group-b")
        self.eng.generate_diagnostics("group-a")
        reports = self.eng.list_reports("group-a")
        assert len(reports) == 2
        for r in reports:
            assert r.group_id == "group-a"

    def test_get_failed_checks(self) -> None:
        report = self.eng.generate_diagnostics("group-1")
        failed = self.eng.get_failed_checks("group-1")
        assert isinstance(failed, list)
        for f in failed:
            assert isinstance(f, FailedCheckDetail)

    def test_get_failed_checks_severity_filter(self) -> None:
        self.eng.generate_diagnostics("group-1")
        critical_failed = self.eng.get_failed_checks("group-1", severity_filter="critical")
        warning_failed = self.eng.get_failed_checks("group-1", severity_filter="warning")
        assert isinstance(critical_failed, list)
        assert isinstance(warning_failed, list)
        for f in critical_failed:
            assert f.severity == "critical"
        for f in warning_failed:
            assert f.severity == "warning"

    def test_get_focus_summary(self) -> None:
        self.eng.generate_diagnostics("group-1")
        summary = self.eng.get_focus_summary("group-1")
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_list_checks_by_group(self) -> None:
        checks = self.eng.list_checks_by_group("group-1")
        assert isinstance(checks, list)
        assert len(checks) > 0
        for c in checks:
            assert "check_id" in c
            assert "check_name" in c
            assert "check_kind" in c

    def test_missing_group(self) -> None:
        with pytest.raises(HealthDiagnosticsError) as exc:
            self.eng.generate_diagnostics("")
        assert exc.value.code == "MISSING_GROUP"

    def test_invalid_grouping(self) -> None:
        with pytest.raises(HealthDiagnosticsError) as exc:
            self.eng.generate_diagnostics("group-1", grouping_strategy="bad-strategy")
        assert exc.value.code == "INVALID_GROUPING"

    def test_not_found(self) -> None:
        with pytest.raises(HealthDiagnosticsError) as exc:
            self.eng.get_report("nonexistent-id")
        assert exc.value.code == "NOT_FOUND"

    def test_max_reports_eviction(self) -> None:
        from aos_api.data_health_plus import _MAX_DIAGNOSTICS_REPORTS
        for i in range(_MAX_DIAGNOSTICS_REPORTS + 5):
            self.eng.generate_diagnostics(f"group-{i}")
        assert len(self.eng._reports) == _MAX_DIAGNOSTICS_REPORTS

    def test_generate_report_with_grouping(self) -> None:
        report = self.eng.generate_diagnostics("group-1", grouping_strategy="by_type")
        assert report.grouping_strategy == "by_type"

    def test_failed_checks_auto_generate_report(self) -> None:
        failed = self.eng.get_failed_checks("new-group")
        assert isinstance(failed, list)

    def test_focus_summary_auto_generate_report(self) -> None:
        summary = self.eng.get_focus_summary("new-group")
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_invalid_severity_in_failed_checks(self) -> None:
        with pytest.raises(HealthDiagnosticsError) as exc:
            self.eng.get_failed_checks("group-1", severity_filter="bad-severity")
        assert exc.value.code == "INVALID_SEVERITY"


# ════════════════════ HealthMonitoringOptionsEngine ════════════════════

class TestHealthMonitoringOptions:
    def setup_method(self) -> None:
        self.eng = HealthMonitoringOptionsEngine()
        self.eng._options = {}

    def _mk(self, **kw: object) -> HealthMonitoringOptions:
        defaults: dict[str, object] = {
            "dataset_rid": "ri.foundry.main.dataset.test123",
            "notification_mode": "all_failures",
            "channels": ["email"],
            "reminder_interval_minutes": 60,
            "auto_resolve": False,
        }
        defaults.update(kw)
        return HealthMonitoringOptions(**defaults)

    def test_register(self) -> None:
        opt = self.eng.register(self._mk())
        assert opt.options_id.startswith("hmo-")
        assert opt.dataset_rid == "ri.foundry.main.dataset.test123"
        assert opt.created_at is not None

    def test_get(self) -> None:
        opt = self.eng.register(self._mk())
        fetched = self.eng.get(opt.options_id)
        assert fetched.options_id == opt.options_id
        assert fetched.dataset_rid == opt.dataset_rid

    def test_get_by_dataset(self) -> None:
        self.eng.register(self._mk(dataset_rid="ds-1"))
        self.eng.register(self._mk(dataset_rid="ds-2"))
        opt = self.eng.get_by_dataset("ds-1")
        assert opt.dataset_rid == "ds-1"

    def test_get_by_dataset_not_found(self) -> None:
        with pytest.raises(HealthMonitoringOptionsError) as exc:
            self.eng.get_by_dataset("nonexistent")
        assert exc.value.code == "NOT_FOUND"

    def test_list(self) -> None:
        self.eng.register(self._mk(dataset_rid="ds-1"))
        self.eng.register(self._mk(dataset_rid="ds-2"))
        assert len(self.eng.list()) == 2

    def test_list_filter_dataset(self) -> None:
        self.eng.register(self._mk(dataset_rid="ds-1"))
        self.eng.register(self._mk(dataset_rid="ds-2"))
        items = self.eng.list(dataset_rid="ds-1")
        assert len(items) == 1
        assert items[0].dataset_rid == "ds-1"

    def test_update(self) -> None:
        opt = self.eng.register(self._mk())
        updated = self.eng.update(opt.options_id, {
            "notification_mode": "only_severe",
            "reminder_interval_minutes": 30,
        })
        assert updated.notification_mode == "only_severe"
        assert updated.reminder_interval_minutes == 30

    def test_delete(self) -> None:
        opt = self.eng.register(self._mk())
        self.eng.delete(opt.options_id)
        with pytest.raises(HealthMonitoringOptionsError) as exc:
            self.eng.get(opt.options_id)
        assert exc.value.code == "NOT_FOUND"

    def test_set_mode(self) -> None:
        opt = self.eng.register(self._mk(notification_mode="all_failures"))
        updated = self.eng.set_notification_mode(opt.options_id, "only_severe")
        assert updated.notification_mode == "only_severe"

    def test_add_channel(self) -> None:
        opt = self.eng.register(self._mk(channels=["email"]))
        updated = self.eng.add_channel(opt.options_id, "slack")
        assert "slack" in updated.channels
        assert "email" in updated.channels

    def test_add_channel_idempotent(self) -> None:
        opt = self.eng.register(self._mk(channels=["email"]))
        updated = self.eng.add_channel(opt.options_id, "email")
        assert updated.channels.count("email") == 1

    def test_remove_channel(self) -> None:
        opt = self.eng.register(self._mk(channels=["email", "slack"]))
        updated = self.eng.remove_channel(opt.options_id, "email")
        assert "email" not in updated.channels
        assert "slack" in updated.channels

    def test_remove_channel_not_found(self) -> None:
        opt = self.eng.register(self._mk(channels=["email"]))
        with pytest.raises(HealthMonitoringOptionsError) as exc:
            self.eng.remove_channel(opt.options_id, "slack")
        assert exc.value.code == "CHANNEL_NOT_FOUND"

    def test_invalid_mode(self) -> None:
        with pytest.raises(HealthMonitoringOptionsError) as exc:
            self.eng.register(self._mk(notification_mode="bad-mode"))
        assert exc.value.code == "INVALID_NOTIFICATION_MODE"

    def test_invalid_channel(self) -> None:
        with pytest.raises(HealthMonitoringOptionsError) as exc:
            self.eng.register(self._mk(channels=["bad-channel"]))
        assert exc.value.code == "INVALID_CHANNEL"

    def test_invalid_interval(self) -> None:
        with pytest.raises(HealthMonitoringOptionsError) as exc:
            self.eng.register(self._mk(reminder_interval_minutes=0))
        assert exc.value.code == "INVALID_INTERVAL"

    def test_missing_dataset(self) -> None:
        with pytest.raises(HealthMonitoringOptionsError) as exc:
            self.eng.register(self._mk(dataset_rid=""))
        assert exc.value.code == "MISSING_DATASET"

    def test_not_found(self) -> None:
        with pytest.raises(HealthMonitoringOptionsError) as exc:
            self.eng.get("nonexistent-id")
        assert exc.value.code == "NOT_FOUND"

    def test_max_options_eviction(self) -> None:
        from aos_api.data_health_plus import _MAX_MONITORING_OPTIONS
        for i in range(_MAX_MONITORING_OPTIONS + 5):
            self.eng.register(HealthMonitoringOptions(
                dataset_rid=f"ds-{i}",
            ))
        assert len(self.eng._options) == _MAX_MONITORING_OPTIONS


# ════════════════════ HealthNotificationEngine ════════════════════

class TestHealthNotifications:
    def setup_method(self) -> None:
        self.eng = HealthNotificationEngine()
        self.eng._notifications = {}

    def test_create(self) -> None:
        n = self.eng.create(
            dataset_rid="ds-1",
            check_id="chk-1",
            check_name="Freshness Check",
            severity="warning",
            title="Test Notification",
            message="This is a test",
            user_id="user-1",
        )
        assert n.notification_id.startswith("hnt-")
        assert n.title == "Test Notification"
        assert n.status == "unread"
        assert n.created_at is not None

    def test_get(self) -> None:
        n = self.eng.create(
            dataset_rid="ds-1", check_id="chk-1", check_name="Test",
            severity="warning", title="T", message="M", user_id="user-1",
        )
        fetched = self.eng.get(n.notification_id)
        assert fetched.notification_id == n.notification_id
        assert fetched.user_id == "user-1"

    def test_list(self) -> None:
        self.eng.create("ds-1", "c1", "Check1", "warning", "T1", "M1", "user-1")
        self.eng.create("ds-1", "c2", "Check2", "critical", "T2", "M2", "user-1")
        items = self.eng.list("user-1")
        assert len(items) == 2

    def test_list_filter_status(self) -> None:
        n1 = self.eng.create("ds-1", "c1", "C1", "warning", "T1", "M1", "user-1")
        self.eng.create("ds-1", "c2", "C2", "warning", "T2", "M2", "user-1")
        self.eng.mark_read(n1.notification_id)
        unread = self.eng.list("user-1", status="unread")
        read = self.eng.list("user-1", status="read")
        assert len(unread) == 1
        assert len(read) == 1

    def test_list_filter_severity(self) -> None:
        self.eng.create("ds-1", "c1", "C1", "critical", "T1", "M1", "user-1")
        self.eng.create("ds-1", "c2", "C2", "warning", "T2", "M2", "user-1")
        self.eng.create("ds-1", "c3", "C3", "info", "T3", "M3", "user-1")
        critical = self.eng.list("user-1", severity="critical")
        warning = self.eng.list("user-1", severity="warning")
        assert len(critical) == 1
        assert len(warning) == 1
        assert critical[0].severity == "critical"
        assert warning[0].severity == "warning"

    def test_mark_read(self) -> None:
        n = self.eng.create("ds-1", "c1", "C1", "warning", "T", "M", "user-1")
        updated = self.eng.mark_read(n.notification_id)
        assert updated.status == "read"
        assert updated.read_at is not None

    def test_mark_all_read(self) -> None:
        self.eng.create("ds-1", "c1", "C1", "warning", "T1", "M1", "user-1")
        self.eng.create("ds-1", "c2", "C2", "warning", "T2", "M2", "user-1")
        self.eng.create("ds-1", "c3", "C3", "warning", "T3", "M3", "user-2")
        count = self.eng.mark_all_read("user-1")
        assert count == 2
        remaining = self.eng.list("user-1", status="unread")
        assert len(remaining) == 0

    def test_clear(self) -> None:
        n = self.eng.create("ds-1", "c1", "C1", "warning", "T", "M", "user-1")
        cleared = self.eng.clear(n.notification_id)
        assert cleared.status == "cleared"
        assert cleared.cleared_at is not None

    def test_clear_all(self) -> None:
        self.eng.create("ds-1", "c1", "C1", "warning", "T1", "M1", "user-1")
        self.eng.create("ds-1", "c2", "C2", "warning", "T2", "M2", "user-1")
        self.eng.create("ds-1", "c3", "C3", "warning", "T3", "M3", "user-2")
        count = self.eng.clear_all("user-1")
        assert count == 2
        remaining = self.eng.list("user-1")
        for r in remaining:
            assert r.status == "cleared"

    def test_unread_count(self) -> None:
        self.eng.create("ds-1", "c1", "C1", "critical", "T1", "M1", "user-1")
        self.eng.create("ds-1", "c2", "C2", "warning", "T2", "M2", "user-1")
        self.eng.create("ds-1", "c3", "C3", "warning", "T3", "M3", "user-1")
        self.eng.create("ds-1", "c4", "C4", "warning", "T4", "M4", "user-2")
        result = self.eng.get_unread_count("user-1")
        assert result["total"] == 3
        assert "by_severity" in result

    def test_list_by_dataset(self) -> None:
        self.eng.create("ds-1", "c1", "C1", "warning", "T1", "M1", "user-1")
        self.eng.create("ds-2", "c2", "C2", "warning", "T2", "M2", "user-1")
        items = self.eng.list_by_dataset("ds-1")
        assert len(items) == 1
        assert items[0].dataset_rid == "ds-1"

    def test_missing_user(self) -> None:
        with pytest.raises(HealthNotificationError) as exc:
            self.eng.create("ds-1", "c1", "C1", "warning", "T", "M", "")
        assert exc.value.code == "MISSING_USER"

    def test_invalid_severity(self) -> None:
        with pytest.raises(HealthNotificationError) as exc:
            self.eng.create("ds-1", "c1", "C1", "bad-severity", "T", "M", "user-1")
        assert exc.value.code == "INVALID_SEVERITY"

    def test_not_found(self) -> None:
        with pytest.raises(HealthNotificationError) as exc:
            self.eng.get("nonexistent-id")
        assert exc.value.code == "NOT_FOUND"

    def test_max_notifications_eviction(self) -> None:
        from aos_api.data_health_plus import _MAX_NOTIFICATIONS
        for i in range(_MAX_NOTIFICATIONS + 5):
            self.eng.create(
                dataset_rid=f"ds-{i}",
                check_id=f"c-{i}",
                check_name=f"Check {i}",
                severity="warning",
                title=f"Title {i}",
                message=f"Message {i}",
                user_id="user-1",
            )
        assert len(self.eng._notifications) == _MAX_NOTIFICATIONS

    def test_unread_count_with_severity(self) -> None:
        self.eng.create("ds-1", "c1", "C1", "critical", "T1", "M1", "user-1")
        self.eng.create("ds-1", "c2", "C2", "warning", "T2", "M2", "user-1")
        self.eng.create("ds-1", "c3", "C3", "warning", "T3", "M3", "user-1")
        result = self.eng.get_unread_count("user-1", severity="warning")
        assert result["total"] == 3
        assert result["severity"] == "warning"
        assert result["count"] == 2

    def test_invalid_status_in_list(self) -> None:
        with pytest.raises(HealthNotificationError) as exc:
            self.eng.list("user-1", status="bad-status")
        assert exc.value.code == "INVALID_STATUS"

    def test_list_with_limit(self) -> None:
        for i in range(10):
            self.eng.create("ds-1", f"c-{i}", f"C{i}", "warning", f"T{i}", f"M{i}", "user-1")
        items = self.eng.list("user-1", limit=5)
        assert len(items) == 5


# ════════════════════ 单例 ════════════════════

class TestSingletons:
    def test_diagnostics_singleton(self) -> None:
        a = get_health_diagnostics_engine()
        b = get_health_diagnostics_engine()
        assert a is b

    def test_monitoring_options_singleton(self) -> None:
        a = get_health_monitoring_options_engine()
        b = get_health_monitoring_options_engine()
        assert a is b

    def test_notifications_singleton(self) -> None:
        a = get_health_notification_engine()
        b = get_health_notification_engine()
        assert a is b
