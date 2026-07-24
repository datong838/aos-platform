"""W2-AM · Data Health Plus 引擎（#136 #137 #138）."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime

from pydantic import BaseModel

_MAX_DIAGNOSTICS_REPORTS = 200
_MAX_MONITORING_OPTIONS = 200
_MAX_NOTIFICATIONS = 200


def _utcnow() -> datetime:
    return datetime.utcnow()


class HealthDiagnosticsError(Exception):
    """健康诊断错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class HealthMonitoringOptionsError(Exception):
    """监测选项错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class HealthNotificationError(Exception):
    """平台内通知错误."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #136 Health Diagnostics ════════════════════

class FailedCheckDetail(BaseModel):
    check_id: str
    check_name: str
    check_kind: str
    severity: str
    dataset_rid: str
    failure_message: str
    last_run_at: datetime


class HealthDiagnosticsReport(BaseModel):
    report_id: str = ""
    group_id: str
    generated_at: datetime | None = None
    total_checks: int = 0
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    failed_checks: list[FailedCheckDetail] = []
    focus_summary: str = ""
    grouping_strategy: str = "by_severity"


_VALID_GROUPING_STRATEGIES = {"by_severity", "by_type", "by_dataset"}
_VALID_SEVERITIES = {"critical", "warning", "info"}
_CHECK_KINDS = ["schema", "freshness", "volume", "accuracy", "uniqueness", "completeness"]


def _generate_mock_failed_checks(group_id: str, count: int) -> list[FailedCheckDetail]:
    checks: list[FailedCheckDetail] = []
    for i in range(count):
        severity = list(_VALID_SEVERITIES)[i % len(_VALID_SEVERITIES)]
        kind = _CHECK_KINDS[i % len(_CHECK_KINDS)]
        checks.append(FailedCheckDetail(
            check_id=f"chk-{uuid.uuid4().hex[:8]}",
            check_name=f"{kind.capitalize()} Check {i + 1}",
            check_kind=kind,
            severity=severity,
            dataset_rid=f"ri.foundry.main.dataset.{uuid.uuid4().hex[:12]}",
            failure_message=f"Failure in {kind} check for group {group_id}",
            last_run_at=_utcnow(),
        ))
    return checks


def _generate_focus_summary(failed_checks: list[FailedCheckDetail]) -> str:
    if not failed_checks:
        return "All checks passed. No issues found."
    critical = [c for c in failed_checks if c.severity == "critical"]
    warning = [c for c in failed_checks if c.severity == "warning"]
    info = [c for c in failed_checks if c.severity == "info"]
    parts = []
    if critical:
        parts.append(f"{len(critical)} critical issue(s)")
    if warning:
        parts.append(f"{len(warning)} warning(s)")
    if info:
        parts.append(f"{len(info)} info issue(s)")
    summary = "Focus: " + ", ".join(parts) + ". "
    if critical:
        top = critical[0]
        summary += f"Top critical: {top.check_name} on {top.dataset_rid[-8:]}"
    elif warning:
        top = warning[0]
        summary += f"Top warning: {top.check_name} on {top.dataset_rid[-8:]}"
    return summary


class HealthDiagnosticsEngine:
    """健康诊断引擎（检查组诊断报告 + 失败检查 + 聚焦摘要）."""

    _instance: HealthDiagnosticsEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._reports: dict[str, HealthDiagnosticsReport] = {}
        self._group_checks: dict[str, list[dict]] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> HealthDiagnosticsEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _ensure_group_checks(self, group_id: str) -> list[dict]:
        if group_id not in self._group_checks:
            checks = []
            for i, kind in enumerate(_CHECK_KINDS):
                checks.append({
                    "check_id": f"chk-{uuid.uuid4().hex[:8]}",
                    "check_name": f"{kind.capitalize()} Check",
                    "check_kind": kind,
                    "severity": list(_VALID_SEVERITIES)[i % len(_VALID_SEVERITIES)],
                    "status": "active",
                    "last_run_at": _utcnow(),
                })
            self._group_checks[group_id] = checks
        return self._group_checks[group_id]

    def generate_diagnostics(self, group_id: str,
                             grouping_strategy: str = "by_severity") -> HealthDiagnosticsReport:
        if not group_id or not group_id.strip():
            raise HealthDiagnosticsError("MISSING_GROUP", "group_id is required")
        if grouping_strategy not in _VALID_GROUPING_STRATEGIES:
            raise HealthDiagnosticsError("INVALID_GROUPING",
                                         f"grouping_strategy must be one of {_VALID_GROUPING_STRATEGIES}")

        checks = self._ensure_group_checks(group_id)
        total = len(checks)
        failed_count = min(total // 3, 5)
        warning_count = min(total // 4, 3)
        passed_count = total - failed_count - warning_count

        failed_checks = _generate_mock_failed_checks(group_id, failed_count)
        focus_summary = _generate_focus_summary(failed_checks)

        now = _utcnow()
        rid = f"hdr-{uuid.uuid4().hex[:8]}"
        report = HealthDiagnosticsReport(
            report_id=rid,
            group_id=group_id,
            generated_at=now,
            total_checks=total,
            passed_count=passed_count,
            failed_count=failed_count,
            warning_count=warning_count,
            failed_checks=failed_checks,
            focus_summary=focus_summary,
            grouping_strategy=grouping_strategy,
        )

        with self._lock:
            if len(self._reports) >= _MAX_DIAGNOSTICS_REPORTS:
                oldest = min(self._reports.values(), key=lambda x: x.generated_at or datetime.min)
                del self._reports[oldest.report_id]
            self._reports[rid] = report

        return report

    def get_report(self, report_id: str) -> HealthDiagnosticsReport:
        with self._lock:
            r = self._reports.get(report_id)
        if r is None:
            raise HealthDiagnosticsError("NOT_FOUND", f"report {report_id} not found")
        return r

    def list_reports(self, group_id: str, limit: int = 20) -> list[HealthDiagnosticsReport]:
        with self._lock:
            results = [r for r in self._reports.values() if r.group_id == group_id]
        results = sorted(results, key=lambda r: r.generated_at or datetime.min, reverse=True)
        return results[:limit]

    def get_failed_checks(self, group_id: str,
                          severity_filter: str | None = None) -> list[FailedCheckDetail]:
        if not group_id or not group_id.strip():
            raise HealthDiagnosticsError("MISSING_GROUP", "group_id is required")
        if severity_filter and severity_filter not in _VALID_SEVERITIES:
            raise HealthDiagnosticsError("INVALID_SEVERITY",
                                         f"severity must be one of {_VALID_SEVERITIES}")

        reports = self.list_reports(group_id, limit=1)
        if not reports:
            report = self.generate_diagnostics(group_id)
        else:
            report = reports[0]

        failed = report.failed_checks
        if severity_filter:
            failed = [c for c in failed if c.severity == severity_filter]
        return failed

    def get_focus_summary(self, group_id: str) -> str:
        if not group_id or not group_id.strip():
            raise HealthDiagnosticsError("MISSING_GROUP", "group_id is required")

        reports = self.list_reports(group_id, limit=1)
        if not reports:
            report = self.generate_diagnostics(group_id)
        else:
            report = reports[0]
        return report.focus_summary

    def list_checks_by_group(self, group_id: str) -> list[dict]:
        if not group_id or not group_id.strip():
            raise HealthDiagnosticsError("MISSING_GROUP", "group_id is required")
        return self._ensure_group_checks(group_id)


_health_diagnostics_engine: HealthDiagnosticsEngine | None = None
_health_diagnostics_engine_lock = threading.Lock()


def get_health_diagnostics_engine() -> HealthDiagnosticsEngine:
    global _health_diagnostics_engine
    if _health_diagnostics_engine is None:
        with _health_diagnostics_engine_lock:
            if _health_diagnostics_engine is None:
                _health_diagnostics_engine = HealthDiagnosticsEngine.get_instance()
    return _health_diagnostics_engine


# ════════════════════ #137 Health Monitoring Options ════════════════════

class HealthMonitoringOptions(BaseModel):
    options_id: str = ""
    dataset_rid: str
    notification_mode: str = "all_failures"
    channels: list[str] = []
    reminder_interval_minutes: int = 60
    auto_resolve: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


_VALID_NOTIFICATION_MODES = {"none", "all_failures", "only_severe"}
_VALID_CHANNELS = {"email", "slack", "inapp"}


class HealthMonitoringOptionsEngine:
    """健康监测选项引擎（通知模式 + 渠道 + 提醒间隔 + 自动解决）."""

    _instance: HealthMonitoringOptionsEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._options: dict[str, HealthMonitoringOptions] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> HealthMonitoringOptionsEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, options: HealthMonitoringOptions) -> HealthMonitoringOptions:
        if not options.dataset_rid or not options.dataset_rid.strip():
            raise HealthMonitoringOptionsError("MISSING_DATASET", "dataset_rid is required")
        if options.notification_mode not in _VALID_NOTIFICATION_MODES:
            raise HealthMonitoringOptionsError("INVALID_NOTIFICATION_MODE",
                                               f"notification_mode must be one of {_VALID_NOTIFICATION_MODES}")
        for ch in options.channels:
            if ch not in _VALID_CHANNELS:
                raise HealthMonitoringOptionsError("INVALID_CHANNEL",
                                                   f"channel must be one of {_VALID_CHANNELS}")
        if options.reminder_interval_minutes <= 0:
            raise HealthMonitoringOptionsError("INVALID_INTERVAL",
                                               "reminder_interval_minutes must be positive")

        now = _utcnow()
        oid = f"hmo-{uuid.uuid4().hex[:8]}"
        o = options.model_copy(update={"options_id": oid, "created_at": now, "updated_at": now})
        with self._lock:
            if len(self._options) >= _MAX_MONITORING_OPTIONS:
                oldest = min(self._options.values(), key=lambda x: x.created_at or datetime.min)
                del self._options[oldest.options_id]
            self._options[oid] = o
        return o

    def get(self, options_id: str) -> HealthMonitoringOptions:
        with self._lock:
            o = self._options.get(options_id)
        if o is None:
            raise HealthMonitoringOptionsError("NOT_FOUND", f"options {options_id} not found")
        return o

    def get_by_dataset(self, dataset_rid: str) -> HealthMonitoringOptions:
        if not dataset_rid or not dataset_rid.strip():
            raise HealthMonitoringOptionsError("MISSING_DATASET", "dataset_rid is required")
        with self._lock:
            for o in self._options.values():
                if o.dataset_rid == dataset_rid:
                    return o
        raise HealthMonitoringOptionsError("NOT_FOUND",
                                           f"monitoring options for dataset {dataset_rid} not found")

    def list(self, dataset_rid: str | None = None) -> list[HealthMonitoringOptions]:
        with self._lock:
            results = list(self._options.values())
        if dataset_rid:
            results = [o for o in results if o.dataset_rid == dataset_rid]
        return sorted(results, key=lambda o: o.created_at or datetime.min, reverse=True)

    def update(self, options_id: str, updates: dict) -> HealthMonitoringOptions:
        with self._lock:
            o = self._options.get(options_id)
            if o is None:
                raise HealthMonitoringOptionsError("NOT_FOUND", f"options {options_id} not found")
            if "notification_mode" in updates and updates["notification_mode"] not in _VALID_NOTIFICATION_MODES:
                raise HealthMonitoringOptionsError("INVALID_NOTIFICATION_MODE",
                                                   f"notification_mode must be one of {_VALID_NOTIFICATION_MODES}")
            if "channels" in updates:
                for ch in updates["channels"]:
                    if ch not in _VALID_CHANNELS:
                        raise HealthMonitoringOptionsError("INVALID_CHANNEL",
                                                           f"channel must be one of {_VALID_CHANNELS}")
            if "reminder_interval_minutes" in updates and updates["reminder_interval_minutes"] <= 0:
                raise HealthMonitoringOptionsError("INVALID_INTERVAL",
                                                   "reminder_interval_minutes must be positive")
            data = o.model_dump()
            data.update(updates)
            updated = HealthMonitoringOptions(**{**data, "updated_at": _utcnow()})
            self._options[options_id] = updated
        return updated

    def delete(self, options_id: str) -> None:
        with self._lock:
            if options_id not in self._options:
                raise HealthMonitoringOptionsError("NOT_FOUND", f"options {options_id} not found")
            del self._options[options_id]

    def set_notification_mode(self, options_id: str, mode: str) -> HealthMonitoringOptions:
        if mode not in _VALID_NOTIFICATION_MODES:
            raise HealthMonitoringOptionsError("INVALID_NOTIFICATION_MODE",
                                               f"notification_mode must be one of {_VALID_NOTIFICATION_MODES}")
        return self.update(options_id, {"notification_mode": mode})

    def add_channel(self, options_id: str, channel: str) -> HealthMonitoringOptions:
        if channel not in _VALID_CHANNELS:
            raise HealthMonitoringOptionsError("INVALID_CHANNEL",
                                               f"channel must be one of {_VALID_CHANNELS}")
        with self._lock:
            o = self._options.get(options_id)
            if o is None:
                raise HealthMonitoringOptionsError("NOT_FOUND", f"options {options_id} not found")
            new_channels = list(o.channels)
            if channel not in new_channels:
                new_channels.append(channel)
            updated = o.model_copy(update={"channels": new_channels, "updated_at": _utcnow()})
            self._options[options_id] = updated
        return updated

    def remove_channel(self, options_id: str, channel: str) -> HealthMonitoringOptions:
        with self._lock:
            o = self._options.get(options_id)
            if o is None:
                raise HealthMonitoringOptionsError("NOT_FOUND", f"options {options_id} not found")
            if channel not in o.channels:
                raise HealthMonitoringOptionsError("CHANNEL_NOT_FOUND",
                                                   f"channel {channel} not found in options")
            new_channels = [c for c in o.channels if c != channel]
            updated = o.model_copy(update={"channels": new_channels, "updated_at": _utcnow()})
            self._options[options_id] = updated
        return updated


_health_monitoring_options_engine: HealthMonitoringOptionsEngine | None = None
_health_monitoring_options_engine_lock = threading.Lock()


def get_health_monitoring_options_engine() -> HealthMonitoringOptionsEngine:
    global _health_monitoring_options_engine
    if _health_monitoring_options_engine is None:
        with _health_monitoring_options_engine_lock:
            if _health_monitoring_options_engine is None:
                _health_monitoring_options_engine = HealthMonitoringOptionsEngine.get_instance()
    return _health_monitoring_options_engine


# ════════════════════ #138 Health Notification ════════════════════

class HealthNotification(BaseModel):
    notification_id: str = ""
    dataset_rid: str
    check_id: str
    check_name: str
    severity: str
    title: str
    message: str
    status: str = "unread"
    created_at: datetime | None = None
    read_at: datetime | None = None
    cleared_at: datetime | None = None
    user_id: str


_VALID_NOTIFICATION_STATUSES = {"unread", "read", "cleared"}
_VALID_NOTIFICATION_SEVERITIES = {"critical", "warning", "info"}


class HealthNotificationEngine:
    """平台内通知引擎（通知创建 + 读取 + 标记 + 清除 + 统计）."""

    _instance: HealthNotificationEngine | None = None
    _instance_lock = threading.Lock()

    def __init__(self) -> None:
        self._notifications: dict[str, HealthNotification] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> HealthNotificationEngine:
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def create(self, dataset_rid: str, check_id: str, check_name: str,
               severity: str, title: str, message: str, user_id: str) -> HealthNotification:
        if not user_id or not user_id.strip():
            raise HealthNotificationError("MISSING_USER", "user_id is required")
        if not dataset_rid or not dataset_rid.strip():
            raise HealthNotificationError("MISSING_DATASET", "dataset_rid is required")
        if severity not in _VALID_NOTIFICATION_SEVERITIES:
            raise HealthNotificationError("INVALID_SEVERITY",
                                           f"severity must be one of {_VALID_NOTIFICATION_SEVERITIES}")

        now = _utcnow()
        nid = f"hnt-{uuid.uuid4().hex[:8]}"
        notification = HealthNotification(
            notification_id=nid,
            dataset_rid=dataset_rid,
            check_id=check_id,
            check_name=check_name,
            severity=severity,
            title=title,
            message=message,
            status="unread",
            created_at=now,
            read_at=None,
            cleared_at=None,
            user_id=user_id,
        )

        with self._lock:
            if len(self._notifications) >= _MAX_NOTIFICATIONS:
                oldest = min(self._notifications.values(), key=lambda x: x.created_at or datetime.min)
                del self._notifications[oldest.notification_id]
            self._notifications[nid] = notification

        return notification

    def get(self, notification_id: str) -> HealthNotification:
        with self._lock:
            n = self._notifications.get(notification_id)
        if n is None:
            raise HealthNotificationError("NOT_FOUND", f"notification {notification_id} not found")
        return n

    def list(self, user_id: str, status: str | None = None,
             severity: str | None = None, limit: int = 50) -> list[HealthNotification]:
        if not user_id or not user_id.strip():
            raise HealthNotificationError("MISSING_USER", "user_id is required")
        if status and status not in _VALID_NOTIFICATION_STATUSES:
            raise HealthNotificationError("INVALID_STATUS",
                                          f"status must be one of {_VALID_NOTIFICATION_STATUSES}")
        if severity and severity not in _VALID_NOTIFICATION_SEVERITIES:
            raise HealthNotificationError("INVALID_SEVERITY",
                                          f"severity must be one of {_VALID_NOTIFICATION_SEVERITIES}")

        with self._lock:
            results = [n for n in self._notifications.values() if n.user_id == user_id]
        if status:
            results = [n for n in results if n.status == status]
        if severity:
            results = [n for n in results if n.severity == severity]
        results = sorted(results, key=lambda n: n.created_at or datetime.min, reverse=True)
        return results[:limit]

    def mark_read(self, notification_id: str) -> HealthNotification:
        with self._lock:
            n = self._notifications.get(notification_id)
            if n is None:
                raise HealthNotificationError("NOT_FOUND", f"notification {notification_id} not found")
            updated = n.model_copy(update={"status": "read", "read_at": _utcnow()})
            self._notifications[notification_id] = updated
        return updated

    def mark_all_read(self, user_id: str) -> int:
        if not user_id or not user_id.strip():
            raise HealthNotificationError("MISSING_USER", "user_id is required")
        count = 0
        now = _utcnow()
        with self._lock:
            for n in self._notifications.values():
                if n.user_id == user_id and n.status == "unread":
                    n.status = "read"
                    n.read_at = now
                    count += 1
        return count

    def clear(self, notification_id: str) -> HealthNotification:
        with self._lock:
            n = self._notifications.get(notification_id)
            if n is None:
                raise HealthNotificationError("NOT_FOUND", f"notification {notification_id} not found")
            updated = n.model_copy(update={"status": "cleared", "cleared_at": _utcnow()})
            self._notifications[notification_id] = updated
        return updated

    def clear_all(self, user_id: str) -> int:
        if not user_id or not user_id.strip():
            raise HealthNotificationError("MISSING_USER", "user_id is required")
        count = 0
        now = _utcnow()
        with self._lock:
            for n in self._notifications.values():
                if n.user_id == user_id and n.status != "cleared":
                    n.status = "cleared"
                    n.cleared_at = now
                    count += 1
        return count

    def get_unread_count(self, user_id: str, severity: str | None = None) -> dict:
        if not user_id or not user_id.strip():
            raise HealthNotificationError("MISSING_USER", "user_id is required")
        if severity and severity not in _VALID_NOTIFICATION_SEVERITIES:
            raise HealthNotificationError("INVALID_SEVERITY",
                                          f"severity must be one of {_VALID_NOTIFICATION_SEVERITIES}")

        with self._lock:
            unread = [n for n in self._notifications.values()
                      if n.user_id == user_id and n.status == "unread"]

        total = len(unread)
        if severity:
            count = len([n for n in unread if n.severity == severity])
            return {"total": total, "severity": severity, "count": count}

        by_severity: dict[str, int] = {}
        for n in unread:
            by_severity[n.severity] = by_severity.get(n.severity, 0) + 1
        return {"total": total, "by_severity": by_severity}

    def list_by_dataset(self, dataset_rid: str, limit: int = 20) -> list[HealthNotification]:
        if not dataset_rid or not dataset_rid.strip():
            raise HealthNotificationError("MISSING_DATASET", "dataset_rid is required")
        with self._lock:
            results = [n for n in self._notifications.values() if n.dataset_rid == dataset_rid]
        results = sorted(results, key=lambda n: n.created_at or datetime.min, reverse=True)
        return results[:limit]


_health_notification_engine: HealthNotificationEngine | None = None
_health_notification_engine_lock = threading.Lock()


def get_health_notification_engine() -> HealthNotificationEngine:
    global _health_notification_engine
    if _health_notification_engine is None:
        with _health_notification_engine_lock:
            if _health_notification_engine is None:
                _health_notification_engine = HealthNotificationEngine.get_instance()
    return _health_notification_engine
