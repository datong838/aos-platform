"""W2-AB · Data Health 检查组（#133 / #134 / #135）.

- #133 HealthCheckTypeEngine：freshness/freshness_duration/volume/schema/content 5 种检查类型
- #134 HealthScheduleEngine：auto（数据集更新触发）+ manual（cron 定时）双模式
- #135 HealthCheckGroupEngine：检查分组 + 通知 + 监控概览

详见 docs/palantier/20_tech/220tech_w2-ab-data-health.md。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ════════════════════ 常量 ════════════════════

_VALID_CHECK_KINDS = {"freshness", "freshness_duration", "volume", "schema", "content"}
_VALID_SEVERITIES = {"error", "warning", "info"}
_VALID_RESULT_STATUSES = {"passed", "failed", "errored", "skipped"}
_VALID_SCHEDULE_MODES = {"auto", "manual"}

_MAX_CHECKS = 200
_MAX_RESULTS = 200
_MAX_SCHEDULES = 200
_MAX_GROUPS = 200


# ════════════════════ 数据模型 ════════════════════

class HealthCheckType(BaseModel):
    """检查类型定义。"""
    id: str = Field(default_factory=lambda: "hc-" + uuid.uuid4().hex[:10])
    name: str
    check_kind: str
    target_dataset_rid: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    severity: str = "warning"
    enabled: bool = True
    created_at: float = Field(default_factory=lambda: time.time())


class HealthCheckResult(BaseModel):
    """检查执行结果。"""
    id: str = Field(default_factory=lambda: "hr-" + uuid.uuid4().hex[:10])
    check_id: str
    check_kind: str = ""
    status: str = "passed"          # passed / failed / errored / skipped
    message: str = ""
    measured_value: Any | None = None
    threshold: Any | None = None
    executed_at: float = Field(default_factory=lambda: time.time())


class HealthSchedule(BaseModel):
    """检查计划。"""
    id: str = Field(default_factory=lambda: "hs-" + uuid.uuid4().hex[:10])
    check_id: str
    mode: str                       # auto / manual
    cron_expression: str = ""
    trigger_dataset_rid: str = ""
    enabled: bool = True
    last_run_at: float = 0.0
    next_run_at: float = 0.0
    run_count: int = 0
    created_at: float = Field(default_factory=lambda: time.time())


class HealthCheckGroup(BaseModel):
    """检查分组。"""
    id: str = Field(default_factory=lambda: "hg-" + uuid.uuid4().hex[:10])
    name: str
    description: str = ""
    check_ids: list[str] = Field(default_factory=list)
    notification_config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: float = Field(default_factory=lambda: time.time())


class GroupMonitorSummary(BaseModel):
    """分组监控概览。"""
    group_id: str
    total_checks: int = 0
    enabled_checks: int = 0
    last_results: dict[str, str] = Field(default_factory=dict)
    pass_rate: float = 0.0


# ════════════════════ 错误 ════════════════════

class DataHealthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════ #133 HealthCheckTypeEngine ════════════════════

class HealthCheckTypeEngine:
    def __init__(self) -> None:
        self._checks: dict[str, HealthCheckType] = {}
        self._results: list[HealthCheckResult] = []
        self._lock = threading.Lock()

    # ---- CRUD ----
    def register(self, check: HealthCheckType) -> HealthCheckType:
        if not check.name:
            raise DataHealthError("MISSING_NAME", "检查名称不能为空")
        if check.check_kind not in _VALID_CHECK_KINDS:
            raise DataHealthError("INVALID_CHECK_KIND", f"未知检查类型：{check.check_kind}")
        if check.severity not in _VALID_SEVERITIES:
            raise DataHealthError("INVALID_SEVERITY", f"未知严重级：{check.severity}")
        if not check.target_dataset_rid:
            raise DataHealthError("MISSING_DATASET", "target_dataset_rid 不能为空")
        with self._lock:
            if len(self._checks) >= _MAX_CHECKS:
                oldest_id = next(iter(self._checks))
                self._checks.pop(oldest_id, None)
            self._checks[check.id] = check
        return check

    def get(self, check_id: str) -> HealthCheckType:
        c = self._checks.get(check_id)
        if c is None:
            raise DataHealthError("NOT_FOUND", f"检查 {check_id} 不存在")
        return c

    def list(
        self, check_kind: str | None = None, enabled_only: bool = False,
    ) -> list[HealthCheckType]:
        items = list(self._checks.values())
        if check_kind:
            items = [c for c in items if c.check_kind == check_kind]
        if enabled_only:
            items = [c for c in items if c.enabled]
        return items

    def update(self, check_id: str, updates: dict[str, Any]) -> HealthCheckType:
        c = self.get(check_id)
        if "check_kind" in updates and updates["check_kind"] not in _VALID_CHECK_KINDS:
            raise DataHealthError("INVALID_CHECK_KIND", f"未知检查类型：{updates['check_kind']}")
        if "severity" in updates and updates["severity"] not in _VALID_SEVERITIES:
            raise DataHealthError("INVALID_SEVERITY", f"未知严重级：{updates['severity']}")
        for k, v in updates.items():
            if hasattr(c, k) and k != "id":
                setattr(c, k, v)
        return c

    def delete(self, check_id: str) -> bool:
        return self._checks.pop(check_id, None) is not None

    # ---- run ----
    def run(self, check_id: str, measured_value: Any | None = None) -> HealthCheckResult:
        c = self.get(check_id)
        now = time.time()
        if not c.enabled:
            r = HealthCheckResult(
                check_id=c.id, check_kind=c.check_kind,
                status="skipped", message="检查已禁用",
                measured_value=measured_value, executed_at=now,
            )
            self._append_result(r)
            return r

        cfg = c.configuration or {}
        threshold = cfg.get("threshold")
        status = "passed"
        message = ""

        try:
            if c.check_kind == "freshness":
                # measured_value = 数据最后更新时间戳（秒）；threshold = 最大延迟秒
                if measured_value is None:
                    status = "errored"
                    message = "缺少 measured_value"
                else:
                    max_delay = float(threshold or 3600)
                    age = now - float(measured_value)
                    if age <= max_delay:
                        status = "passed"
                        message = f"数据新鲜度正常（延迟 {age:.0f}s <= {max_delay:.0f}s）"
                    else:
                        status = "failed"
                        message = f"数据过期（延迟 {age:.0f}s > {max_delay:.0f}s）"

            elif c.check_kind == "freshness_duration":
                # 同 freshness 但 threshold 单位为小时
                if measured_value is None:
                    status = "errored"
                    message = "缺少 measured_value"
                else:
                    max_hours = float(threshold or 24)
                    max_delay = max_hours * 3600
                    age = now - float(measured_value)
                    if age <= max_delay:
                        status = "passed"
                        message = f"数据新鲜度正常（延迟 {age / 3600:.2f}h <= {max_hours:.2f}h）"
                    else:
                        status = "failed"
                        message = f"数据过期（延迟 {age / 3600:.2f}h > {max_hours:.2f}h）"

            elif c.check_kind == "volume":
                # measured_value = 行数；threshold = 最小行数
                if measured_value is None:
                    status = "errored"
                    message = "缺少 measured_value"
                else:
                    min_rows = int(threshold or 0)
                    rows = int(measured_value)
                    if rows >= min_rows:
                        status = "passed"
                        message = f"行数充足（{rows} >= {min_rows}）"
                    else:
                        status = "failed"
                        message = f"行数不足（{rows} < {min_rows}）"

            elif c.check_kind == "schema":
                # measured_value = 列名列表；configuration["expected_columns"] = 期望列名列表
                if measured_value is None:
                    status = "errored"
                    message = "缺少 measured_value"
                else:
                    expected = set(cfg.get("expected_columns", []))
                    actual = set(measured_value) if isinstance(measured_value, (list, tuple)) else set()
                    if expected == actual:
                        status = "passed"
                        message = "Schema 匹配"
                    else:
                        status = "failed"
                        missing = expected - actual
                        extra = actual - expected
                        parts: list[str] = []
                        if missing:
                            parts.append(f"缺失列 {missing}")
                        if extra:
                            parts.append(f"多余列 {extra}")
                        message = "Schema 不匹配：" + "；".join(parts)

            elif c.check_kind == "content":
                # measured_value = dict；configuration["rules"] = [{field, op, value}]
                if measured_value is None or not isinstance(measured_value, dict):
                    status = "errored"
                    message = "measured_value 必须为 dict"
                else:
                    rules = cfg.get("rules", [])
                    failed_rules: list[str] = []
                    for rule in rules:
                        field = rule.get("field", "")
                        op = rule.get("op", "")
                        expected_val = rule.get("value")
                        actual_val = measured_value.get(field)
                        if not _eval_content_rule(actual_val, op, expected_val):
                            failed_rules.append(f"{field} {op} {expected_val}（实际 {actual_val}）")
                    if not failed_rules:
                        status = "passed"
                        message = "内容规则全部通过"
                    else:
                        status = "failed"
                        message = "内容规则失败：" + "；".join(failed_rules)
        except Exception as exc:  # noqa: BLE001
            status = "errored"
            message = f"检查执行异常：{exc}"

        r = HealthCheckResult(
            check_id=c.id, check_kind=c.check_kind,
            status=status, message=message,
            measured_value=measured_value, threshold=threshold,
            executed_at=now,
        )
        self._append_result(r)
        return r

    def list_results(
        self, check_id: str | None = None, status: str | None = None, limit: int = 50,
    ) -> list[HealthCheckResult]:
        items = list(self._results)
        if check_id:
            items = [r for r in items if r.check_id == check_id]
        if status:
            items = [r for r in items if r.status == status]
        items = list(reversed(items))  # 最新在前
        if limit > 0:
            items = items[:limit]
        return items

    def _append_result(self, r: HealthCheckResult) -> None:
        with self._lock:
            if len(self._results) >= _MAX_RESULTS:
                self._results.pop(0)
            self._results.append(r)


def _eval_content_rule(actual: Any, op: str, expected: Any) -> bool:
    """评估 content 规则。"""
    try:
        if op == "eq":
            return actual == expected
        if op == "ne":
            return actual != expected
        if op == "gt":
            return float(actual) > float(expected)
        if op == "lt":
            return float(actual) < float(expected)
        if op == "ge":
            return float(actual) >= float(expected)
        if op == "le":
            return float(actual) <= float(expected)
        if op == "in":
            return actual in (expected or [])
        if op == "contains":
            return expected in (actual or "")
        return False
    except (TypeError, ValueError):
        return False


# ════════════════════ #134 HealthScheduleEngine ════════════════════

class HealthScheduleEngine:
    def __init__(self) -> None:
        self._schedules: dict[str, HealthSchedule] = {}
        self._lock = threading.Lock()

    def register(self, schedule: HealthSchedule) -> HealthSchedule:
        if not schedule.check_id:
            raise DataHealthError("MISSING_CHECK", "check_id 不能为空")
        if schedule.mode not in _VALID_SCHEDULE_MODES:
            raise DataHealthError("INVALID_MODE", f"未知模式：{schedule.mode}")
        if schedule.mode == "auto" and not schedule.trigger_dataset_rid:
            raise DataHealthError("MISSING_TRIGGER_DATASET", "auto 模式需要 trigger_dataset_rid")
        if schedule.mode == "manual" and not schedule.cron_expression:
            raise DataHealthError("MISSING_CRON", "manual 模式需要 cron_expression")
        with self._lock:
            if len(self._schedules) >= _MAX_SCHEDULES:
                oldest_id = next(iter(self._schedules))
                self._schedules.pop(oldest_id, None)
            # 计算初始 next_run_at
            if schedule.mode == "manual":
                schedule.next_run_at = time.time() + _parse_cron_seconds(schedule.cron_expression)
            self._schedules[schedule.id] = schedule
        return schedule

    def get(self, schedule_id: str) -> HealthSchedule:
        s = self._schedules.get(schedule_id)
        if s is None:
            raise DataHealthError("NOT_FOUND", f"计划 {schedule_id} 不存在")
        return s

    def list(
        self, check_id: str | None = None, mode: str | None = None,
        enabled_only: bool = False,
    ) -> list[HealthSchedule]:
        items = list(self._schedules.values())
        if check_id:
            items = [s for s in items if s.check_id == check_id]
        if mode:
            items = [s for s in items if s.mode == mode]
        if enabled_only:
            items = [s for s in items if s.enabled]
        return items

    def update(self, schedule_id: str, updates: dict[str, Any]) -> HealthSchedule:
        s = self.get(schedule_id)
        if "mode" in updates and updates["mode"] not in _VALID_SCHEDULE_MODES:
            raise DataHealthError("INVALID_MODE", f"未知模式：{updates['mode']}")
        for k, v in updates.items():
            if hasattr(s, k) and k != "id":
                setattr(s, k, v)
        # 如果改了 cron，重算 next_run_at
        if "cron_expression" in updates and s.mode == "manual":
            s.next_run_at = time.time() + _parse_cron_seconds(s.cron_expression)
        return s

    def delete(self, schedule_id: str) -> bool:
        return self._schedules.pop(schedule_id, None) is not None

    def trigger(self, schedule_id: str) -> dict[str, Any]:
        s = self.get(schedule_id)
        if not s.enabled:
            return {
                "schedule_id": schedule_id, "triggered": False,
                "reason": "计划已禁用",
            }
        now = time.time()
        s.last_run_at = now
        s.run_count += 1
        if s.mode == "manual":
            s.next_run_at = now + _parse_cron_seconds(s.cron_expression)
        # auto 模式 next_run_at 不变（事件驱动）
        return {
            "schedule_id": schedule_id, "triggered": True,
            "last_run_at": now, "next_run_at": s.next_run_at,
            "run_count": s.run_count,
        }

    def compute_next_run(self, schedule_id: str) -> float:
        s = self.get(schedule_id)
        if s.mode == "manual":
            return s.next_run_at
        # auto 模式：事件驱动，next_run_at 为 0 表示随时可触发
        return 0.0


def _parse_cron_seconds(cron_expr: str) -> float:
    """简化 cron 解析：将 cron 表达式解析为秒级间隔。

    支持格式：
    - "*/N * * * * *" → N 秒
    - "N * * * * *" → N 分钟
    - "* N * * * *" → N 小时
    - 纯数字 → 该数字秒
    """
    if not cron_expr:
        return 3600.0  # 默认 1 小时
    expr = cron_expr.strip()
    # 纯数字
    try:
        return float(expr)
    except ValueError:
        pass
    parts = expr.split()
    if not parts:
        return 3600.0
    # */N 格式（第一段）
    first = parts[0]
    if first.startswith("*/"):
        try:
            n = float(first[2:])
            # 如果只有一段，按秒
            if len(parts) == 1:
                return n
            # 5 段标准 cron：*/N 在分钟位 → N*60
            if len(parts) >= 2:
                return n * 60
        except ValueError:
            pass
    # 标准五段 cron：minute hour day month weekday
    if len(parts) >= 5:
        try:
            minute = int(parts[0])
            hour = int(parts[1])
            # 简化：按 (hour*60 + minute) * 60 估算间隔
            if hour > 0 or minute > 0:
                return (hour * 3600 + minute * 60) or 3600
        except ValueError:
            pass
    return 3600.0


# ════════════════════ #135 HealthCheckGroupEngine ════════════════════

class HealthCheckGroupEngine:
    def __init__(self) -> None:
        self._groups: dict[str, HealthCheckGroup] = {}
        self._notifications: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def register(self, group: HealthCheckGroup) -> HealthCheckGroup:
        if not group.name:
            raise DataHealthError("MISSING_NAME", "分组名称不能为空")
        with self._lock:
            for existing in self._groups.values():
                if existing.name == group.name and existing.id != group.id:
                    raise DataHealthError("NAME_DUPLICATE", f"分组名 '{group.name}' 已存在")
            if len(self._groups) >= _MAX_GROUPS:
                oldest_id = next(iter(self._groups))
                self._groups.pop(oldest_id, None)
            self._groups[group.id] = group
        return group

    def get(self, group_id: str) -> HealthCheckGroup:
        g = self._groups.get(group_id)
        if g is None:
            raise DataHealthError("NOT_FOUND", f"分组 {group_id} 不存在")
        return g

    def list(self, enabled_only: bool = False) -> list[HealthCheckGroup]:
        items = list(self._groups.values())
        if enabled_only:
            items = [g for g in items if g.enabled]
        return items

    def update(self, group_id: str, updates: dict[str, Any]) -> HealthCheckGroup:
        g = self.get(group_id)
        if "name" in updates and updates["name"] != g.name:
            for existing in self._groups.values():
                if existing.name == updates["name"] and existing.id != g.id:
                    raise DataHealthError("NAME_DUPLICATE", f"分组名 '{updates['name']}' 已存在")
        for k, v in updates.items():
            if hasattr(g, k) and k != "id":
                setattr(g, k, v)
        return g

    def delete(self, group_id: str) -> bool:
        return self._groups.pop(group_id, None) is not None

    def attach_check(self, group_id: str, check_id: str) -> HealthCheckGroup:
        g = self.get(group_id)
        if check_id not in g.check_ids:
            g.check_ids.append(check_id)
        return g

    def detach_check(self, group_id: str, check_id: str) -> HealthCheckGroup:
        g = self.get(group_id)
        if check_id in g.check_ids:
            g.check_ids.remove(check_id)
        return g

    def monitor(self, group_id: str) -> GroupMonitorSummary:
        """汇总分组监控概览。"""
        g = self.get(group_id)
        total = len(g.check_ids)
        # 获取每个 check 的最近一次 result status
        check_engine = get_health_check_type_engine()
        last_results: dict[str, str] = {}
        enabled_count = 0
        pass_count = 0
        for cid in g.check_ids:
            try:
                c = check_engine.get(cid)
                if c.enabled:
                    enabled_count += 1
                results = check_engine.list_results(check_id=cid, limit=1)
                if results:
                    status = results[0].status
                    last_results[cid] = status
                    if status == "passed":
                        pass_count += 1
                else:
                    last_results[cid] = "unknown"
            except DataHealthError:
                last_results[cid] = "missing"
        evaluated = sum(1 for s in last_results.values() if s in ("passed", "failed"))
        pass_rate = (pass_count / evaluated) if evaluated > 0 else 0.0
        return GroupMonitorSummary(
            group_id=group_id, total_checks=total,
            enabled_checks=enabled_count,
            last_results=last_results, pass_rate=pass_rate,
        )

    def send_notification(
        self, group_id: str, event: dict[str, Any],
    ) -> dict[str, Any]:
        g = self.get(group_id)
        cfg = g.notification_config or {}
        channels = cfg.get("channels", ["log"])
        severity_filter = cfg.get("severity_filter", ["error", "warning"])
        event_severity = event.get("severity", "warning")
        dispatched: list[str] = []
        if event_severity in severity_filter:
            for ch in channels:
                dispatched.append(ch)
        record = {
            "group_id": group_id,
            "event": event,
            "dispatched_channels": dispatched,
            "timestamp": time.time(),
        }
        with self._lock:
            if len(self._notifications) >= 200:
                self._notifications.pop(0)
            self._notifications.append(record)
        return record


# ════════════════════ 单例 ════════════════════

_health_check_type_engine: HealthCheckTypeEngine | None = None
_health_schedule_engine: HealthScheduleEngine | None = None
_health_check_group_engine: HealthCheckGroupEngine | None = None
_singleton_lock = threading.Lock()


def get_health_check_type_engine() -> HealthCheckTypeEngine:
    global _health_check_type_engine
    if _health_check_type_engine is None:
        with _singleton_lock:
            if _health_check_type_engine is None:
                _health_check_type_engine = HealthCheckTypeEngine()
    return _health_check_type_engine


def get_health_schedule_engine() -> HealthScheduleEngine:
    global _health_schedule_engine
    if _health_schedule_engine is None:
        with _singleton_lock:
            if _health_schedule_engine is None:
                _health_schedule_engine = HealthScheduleEngine()
    return _health_schedule_engine


def get_health_check_group_engine() -> HealthCheckGroupEngine:
    global _health_check_group_engine
    if _health_check_group_engine is None:
        with _singleton_lock:
            if _health_check_group_engine is None:
                _health_check_group_engine = HealthCheckGroupEngine()
    return _health_check_group_engine
