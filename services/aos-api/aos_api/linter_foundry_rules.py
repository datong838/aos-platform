"""W2-BL · Linter Foundry Rules 引擎（#14 #15 #16/#28 #17）.

- #14 Linter 规则引擎
- #15 Linter 扫描调度
- #16/#28 Foundry Rules 规则引擎
- #17 Foundry Rules 时间序列
"""
from __future__ import annotations

import random
import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class LinterFoundryError(Exception):
    """Linter / Foundry 引擎统一错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def error_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


# ════════════════════ #14 Linter 规则引擎 ════════════════════

class LinterRule(BaseModel):
    id: str = Field(default_factory=lambda: _uid("lint"))
    code: str
    title: str
    description: str
    severity: str  # info / warning / error / critical
    category: str  # naming / security / performance / style / architecture
    pattern: str = ""
    suggestion: str = ""
    auto_fix: bool = False
    enabled: bool = True
    created_at: float = Field(default_factory=_now_ts)


class LintFinding(BaseModel):
    id: str = Field(default_factory=lambda: _uid("finding"))
    rule_id: str
    rule_code: str
    resource_type: str
    resource_id: str
    severity: str
    message: str
    suggestion: str
    auto_fix_available: bool = False
    status: str = "open"  # open / fixed / ignored
    created_at: float = Field(default_factory=_now_ts)


class LintFixProposal(BaseModel):
    id: str = Field(default_factory=lambda: _uid("fix"))
    finding_id: str
    rule_id: str
    resource_type: str
    resource_id: str
    current_value: str = ""
    proposed_value: str
    description: str = ""
    applied: bool = False
    created_at: float = Field(default_factory=_now_ts)


class LinterRuleEngine:
    """#14 Linter 规则引擎。"""

    _MAX_RULES = 200
    _MAX_FINDINGS = 200
    _MAX_FIXES = 200
    _VALID_SEVERITIES = {"info", "warning", "error", "critical"}
    _VALID_CATEGORIES = {"naming", "security", "performance", "style", "architecture"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: dict[str, LinterRule] = {}
        self._findings: dict[str, LintFinding] = {}
        self._fixes: dict[str, LintFixProposal] = {}

    def register_rule(
        self,
        code: str,
        title: str,
        description: str,
        severity: str,
        category: str,
        pattern: str = "",
        suggestion: str = "",
        auto_fix: bool = False,
    ) -> LinterRule:
        if severity not in self._VALID_SEVERITIES:
            raise LinterFoundryError(
                "INVALID_SEVERITY",
                f"severity must be one of {sorted(self._VALID_SEVERITIES)}",
            )
        if category not in self._VALID_CATEGORIES:
            raise LinterFoundryError(
                "INVALID_CATEGORY",
                f"category must be one of {sorted(self._VALID_CATEGORIES)}",
            )
        rule = LinterRule(
            code=code,
            title=title,
            description=description,
            severity=severity,
            category=category,
            pattern=pattern,
            suggestion=suggestion,
            auto_fix=auto_fix,
        )
        with self._lock:
            if len(self._rules) >= self._MAX_RULES:
                oldest_id = min(
                    self._rules, key=lambda rid: self._rules[rid].created_at
                )
                del self._rules[oldest_id]
            self._rules[rule.id] = rule
        return rule

    def get_rule(self, rule_id: str) -> LinterRule:
        with self._lock:
            rule = self._rules.get(rule_id)
        if rule is None:
            raise LinterFoundryError("NOT_FOUND", f"rule {rule_id} not found")
        return rule

    def list_rules(
        self,
        category: str | None = None,
        severity: str | None = None,
        enabled_only: bool = False,
    ) -> list[LinterRule]:
        with self._lock:
            items = list(self._rules.values())
        if category is not None:
            items = [r for r in items if r.category == category]
        if severity is not None:
            items = [r for r in items if r.severity == severity]
        if enabled_only:
            items = [r for r in items if r.enabled]
        return sorted(items, key=lambda r: r.created_at)

    def update_rule(self, rule_id: str, updates: dict[str, Any]) -> LinterRule:
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule is None:
                raise LinterFoundryError("NOT_FOUND", f"rule {rule_id} not found")
            if "severity" in updates and updates["severity"] not in self._VALID_SEVERITIES:
                raise LinterFoundryError(
                    "INVALID_SEVERITY",
                    f"severity must be one of {sorted(self._VALID_SEVERITIES)}",
                )
            if "category" in updates and updates["category"] not in self._VALID_CATEGORIES:
                raise LinterFoundryError(
                    "INVALID_CATEGORY",
                    f"category must be one of {sorted(self._VALID_CATEGORIES)}",
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(rule).model_fields
            }
            updated = rule.model_copy(update=applicable)
            self._rules[rule_id] = updated
        return updated

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            return self._rules.pop(rule_id, None) is not None

    def detect(
        self,
        resource_type: str,
        resource_id: str,
        resource_data: dict[str, Any],
    ) -> list[LintFinding]:
        data_str = str(resource_data)
        with self._lock:
            rules_snapshot = [r for r in self._rules.values() if r.enabled]
        findings: list[LintFinding] = []
        for rule in rules_snapshot:
            matched = False
            if rule.pattern:
                if rule.pattern in resource_data or rule.pattern in data_str:
                    matched = True
            if not matched:
                continue
            findings.append(
                LintFinding(
                    rule_id=rule.id,
                    rule_code=rule.code,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    severity=rule.severity,
                    message=rule.description,
                    suggestion=rule.suggestion,
                    auto_fix_available=rule.auto_fix,
                    status="open",
                )
            )
        with self._lock:
            for finding in findings:
                if len(self._findings) >= self._MAX_FINDINGS:
                    oldest_id = min(
                        self._findings,
                        key=lambda fid: self._findings[fid].created_at,
                    )
                    del self._findings[oldest_id]
                self._findings[finding.id] = finding
        return findings

    def get_finding(self, finding_id: str) -> LintFinding:
        with self._lock:
            finding = self._findings.get(finding_id)
        if finding is None:
            raise LinterFoundryError("NOT_FOUND", f"finding {finding_id} not found")
        return finding

    def list_findings(
        self,
        resource_type: str | None = None,
        severity: str | None = None,
        status: str | None = None,
    ) -> list[LintFinding]:
        with self._lock:
            items = list(self._findings.values())
        if resource_type is not None:
            items = [f for f in items if f.resource_type == resource_type]
        if severity is not None:
            items = [f for f in items if f.severity == severity]
        if status is not None:
            items = [f for f in items if f.status == status]
        return sorted(items, key=lambda f: f.created_at)

    def fix_finding(
        self,
        finding_id: str,
        proposed_value: str,
        description: str = "",
    ) -> LintFixProposal:
        with self._lock:
            finding = self._findings.get(finding_id)
            if finding is None:
                raise LinterFoundryError(
                    "NOT_FOUND", f"finding {finding_id} not found"
                )
            fix = LintFixProposal(
                finding_id=finding_id,
                rule_id=finding.rule_id,
                resource_type=finding.resource_type,
                resource_id=finding.resource_id,
                current_value="",
                proposed_value=proposed_value,
                description=description,
            )
            if len(self._fixes) >= self._MAX_FIXES:
                oldest_id = min(
                    self._fixes, key=lambda fxid: self._fixes[fxid].created_at
                )
                del self._fixes[oldest_id]
            self._fixes[fix.id] = fix
            self._findings[finding_id] = finding.model_copy(update={"status": "fixed"})
        return fix

    def ignore_finding(self, finding_id: str) -> LintFinding:
        with self._lock:
            finding = self._findings.get(finding_id)
            if finding is None:
                raise LinterFoundryError(
                    "NOT_FOUND", f"finding {finding_id} not found"
                )
            updated = finding.model_copy(update={"status": "ignored"})
            self._findings[finding_id] = updated
        return updated

    def get_fix_proposal(self, fix_id: str) -> LintFixProposal:
        with self._lock:
            fix = self._fixes.get(fix_id)
        if fix is None:
            raise LinterFoundryError("NOT_FOUND", f"fix {fix_id} not found")
        return fix

    def apply_fix(self, fix_id: str) -> LintFixProposal:
        with self._lock:
            fix = self._fixes.get(fix_id)
            if fix is None:
                raise LinterFoundryError("NOT_FOUND", f"fix {fix_id} not found")
            updated = fix.model_copy(update={"applied": True})
            self._fixes[fix_id] = updated
        return updated

    def delete_finding(self, finding_id: str) -> bool:
        with self._lock:
            return self._findings.pop(finding_id, None) is not None


# ════════════════════ #15 Linter 扫描调度 ════════════════════

class ScanSchedule(BaseModel):
    id: str = Field(default_factory=lambda: _uid("scan"))
    name: str
    cron_expression: str
    resource_scope: str = "all"  # all / specific_type / specific_id
    resource_filter: dict[str, Any] = Field(default_factory=dict)
    rule_scope: str = "all"  # all / specific_category / specific_severity
    rule_filter: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    last_run_at: float = 0
    next_run_at: float = 0
    created_at: float = Field(default_factory=_now_ts)


class ScanRun(BaseModel):
    id: str = Field(default_factory=lambda: _uid("run"))
    schedule_id: str
    started_at: float = Field(default_factory=_now_ts)
    completed_at: float = 0
    status: str = "running"  # running / completed / failed
    resources_scanned: int = 0
    findings_count: int = 0
    error_message: str = ""


class LinterScanScheduleEngine:
    """#15 Linter 扫描调度引擎。"""

    _MAX_SCHEDULES = 200
    _MAX_RUNS = 200
    _VALID_RESOURCE_SCOPES = {"all", "specific_type", "specific_id"}
    _VALID_RULE_SCOPES = {"all", "specific_category", "specific_severity"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._schedules: dict[str, ScanSchedule] = {}
        self._runs: dict[str, ScanRun] = {}

    def create_schedule(
        self,
        name: str,
        cron_expression: str,
        resource_scope: str = "all",
        resource_filter: dict[str, Any] | None = None,
        rule_scope: str = "all",
        rule_filter: dict[str, Any] | None = None,
    ) -> ScanSchedule:
        if resource_scope not in self._VALID_RESOURCE_SCOPES:
            raise LinterFoundryError(
                "INVALID_RESOURCE_SCOPE",
                f"resource_scope must be one of {sorted(self._VALID_RESOURCE_SCOPES)}",
            )
        if rule_scope not in self._VALID_RULE_SCOPES:
            raise LinterFoundryError(
                "INVALID_RULE_SCOPE",
                f"rule_scope must be one of {sorted(self._VALID_RULE_SCOPES)}",
            )
        now = _now_ts()
        schedule = ScanSchedule(
            name=name,
            cron_expression=cron_expression,
            resource_scope=resource_scope,
            resource_filter=resource_filter or {},
            rule_scope=rule_scope,
            rule_filter=rule_filter or {},
            next_run_at=now + 3600,
        )
        with self._lock:
            if len(self._schedules) >= self._MAX_SCHEDULES:
                oldest_id = min(
                    self._schedules,
                    key=lambda sid: self._schedules[sid].created_at,
                )
                del self._schedules[oldest_id]
            self._schedules[schedule.id] = schedule
        return schedule

    def get_schedule(self, schedule_id: str) -> ScanSchedule:
        with self._lock:
            schedule = self._schedules.get(schedule_id)
        if schedule is None:
            raise LinterFoundryError(
                "NOT_FOUND", f"schedule {schedule_id} not found"
            )
        return schedule

    def list_schedules(self, enabled_only: bool = False) -> list[ScanSchedule]:
        with self._lock:
            items = list(self._schedules.values())
        if enabled_only:
            items = [s for s in items if s.enabled]
        return sorted(items, key=lambda s: s.created_at)

    def update_schedule(
        self, schedule_id: str, updates: dict[str, Any]
    ) -> ScanSchedule:
        with self._lock:
            schedule = self._schedules.get(schedule_id)
            if schedule is None:
                raise LinterFoundryError(
                    "NOT_FOUND", f"schedule {schedule_id} not found"
                )
            if "resource_scope" in updates and updates["resource_scope"] not in self._VALID_RESOURCE_SCOPES:
                raise LinterFoundryError(
                    "INVALID_RESOURCE_SCOPE",
                    f"resource_scope must be one of {sorted(self._VALID_RESOURCE_SCOPES)}",
                )
            if "rule_scope" in updates and updates["rule_scope"] not in self._VALID_RULE_SCOPES:
                raise LinterFoundryError(
                    "INVALID_RULE_SCOPE",
                    f"rule_scope must be one of {sorted(self._VALID_RULE_SCOPES)}",
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(schedule).model_fields
            }
            updated = schedule.model_copy(update=applicable)
            self._schedules[schedule_id] = updated
        return updated

    def delete_schedule(self, schedule_id: str) -> bool:
        with self._lock:
            return self._schedules.pop(schedule_id, None) is not None

    def run_scan(self, schedule_id: str) -> ScanRun:
        with self._lock:
            schedule = self._schedules.get(schedule_id)
            if schedule is None:
                raise LinterFoundryError(
                    "NOT_FOUND", f"schedule {schedule_id} not found"
                )
            now = _now_ts()
            run = ScanRun(
                schedule_id=schedule_id,
                started_at=now,
                completed_at=now,
                status="completed",
                resources_scanned=random.randint(1, 50),
                findings_count=random.randint(0, 10),
            )
            if len(self._runs) >= self._MAX_RUNS:
                oldest_id = min(
                    self._runs, key=lambda rid: self._runs[rid].started_at
                )
                del self._runs[oldest_id]
            self._runs[run.id] = run
            self._schedules[schedule_id] = schedule.model_copy(
                update={"last_run_at": now, "next_run_at": now + 3600}
            )
        return run

    def get_run(self, run_id: str) -> ScanRun:
        with self._lock:
            run = self._runs.get(run_id)
        if run is None:
            raise LinterFoundryError("NOT_FOUND", f"run {run_id} not found")
        return run

    def list_runs(
        self,
        schedule_id: str | None = None,
        status: str | None = None,
    ) -> list[ScanRun]:
        with self._lock:
            items = list(self._runs.values())
        if schedule_id is not None:
            items = [r for r in items if r.schedule_id == schedule_id]
        if status is not None:
            items = [r for r in items if r.status == status]
        return sorted(items, key=lambda r: r.started_at)

    def delete_run(self, run_id: str) -> bool:
        with self._lock:
            return self._runs.pop(run_id, None) is not None


# ════════════════════ #16/#28 Foundry Rules 规则引擎 ════════════════════

class FoundryRule(BaseModel):
    id: str = Field(default_factory=lambda: _uid("fr"))
    name: str
    description: str
    trigger_type: str  # condition / schedule / event
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[str] = []  # notify / create_object / update_object / call_function
    workflow_id: str = ""
    enabled: bool = True
    created_at: float = Field(default_factory=_now_ts)


class FoundryRuleExecution(BaseModel):
    id: str = Field(default_factory=lambda: _uid("fre"))
    rule_id: str
    triggered_at: float = Field(default_factory=_now_ts)
    input_data: dict[str, Any] = Field(default_factory=dict)
    actions_taken: list[str] = []
    status: str = "success"  # success / failed / skipped
    error_message: str = ""
    completed_at: float = 0


class FoundryRulesEngine:
    """#16/#28 Foundry Rules 规则引擎。"""

    _MAX_RULES = 200
    _MAX_EXECUTIONS = 200
    _VALID_TRIGGER_TYPES = {"condition", "schedule", "event"}
    _VALID_ACTIONS = {"notify", "create_object", "update_object", "call_function"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: dict[str, FoundryRule] = {}
        self._executions: dict[str, FoundryRuleExecution] = {}

    def create_rule(
        self,
        name: str,
        description: str,
        trigger_type: str,
        conditions: list[dict[str, Any]] | None = None,
        actions: list[str] | None = None,
        workflow_id: str = "",
    ) -> FoundryRule:
        if trigger_type not in self._VALID_TRIGGER_TYPES:
            raise LinterFoundryError(
                "INVALID_TRIGGER_TYPE",
                f"trigger_type must be one of {sorted(self._VALID_TRIGGER_TYPES)}",
            )
        rule_actions = actions or []
        for action in rule_actions:
            if action not in self._VALID_ACTIONS:
                raise LinterFoundryError(
                    "INVALID_ACTION",
                    f"action must be one of {sorted(self._VALID_ACTIONS)}",
                )
        rule = FoundryRule(
            name=name,
            description=description,
            trigger_type=trigger_type,
            conditions=conditions or [],
            actions=rule_actions,
            workflow_id=workflow_id,
        )
        with self._lock:
            if len(self._rules) >= self._MAX_RULES:
                oldest_id = min(
                    self._rules, key=lambda rid: self._rules[rid].created_at
                )
                del self._rules[oldest_id]
            self._rules[rule.id] = rule
        return rule

    def get_rule(self, rule_id: str) -> FoundryRule:
        with self._lock:
            rule = self._rules.get(rule_id)
        if rule is None:
            raise LinterFoundryError("NOT_FOUND", f"rule {rule_id} not found")
        return rule

    def list_rules(
        self,
        trigger_type: str | None = None,
        enabled_only: bool = False,
    ) -> list[FoundryRule]:
        with self._lock:
            items = list(self._rules.values())
        if trigger_type is not None:
            items = [r for r in items if r.trigger_type == trigger_type]
        if enabled_only:
            items = [r for r in items if r.enabled]
        return sorted(items, key=lambda r: r.created_at)

    def update_rule(self, rule_id: str, updates: dict[str, Any]) -> FoundryRule:
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule is None:
                raise LinterFoundryError("NOT_FOUND", f"rule {rule_id} not found")
            if "trigger_type" in updates and updates["trigger_type"] not in self._VALID_TRIGGER_TYPES:
                raise LinterFoundryError(
                    "INVALID_TRIGGER_TYPE",
                    f"trigger_type must be one of {sorted(self._VALID_TRIGGER_TYPES)}",
                )
            if "actions" in updates:
                for action in updates["actions"]:
                    if action not in self._VALID_ACTIONS:
                        raise LinterFoundryError(
                            "INVALID_ACTION",
                            f"action must be one of {sorted(self._VALID_ACTIONS)}",
                        )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(rule).model_fields
            }
            updated = rule.model_copy(update=applicable)
            self._rules[rule_id] = updated
        return updated

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            return self._rules.pop(rule_id, None) is not None

    def execute_rule(
        self, rule_id: str, input_data: dict[str, Any] | None = None
    ) -> FoundryRuleExecution:
        with self._lock:
            rule = self._rules.get(rule_id)
            if rule is None:
                raise LinterFoundryError("NOT_FOUND", f"rule {rule_id} not found")
            if not rule.enabled:
                execution = FoundryRuleExecution(
                    rule_id=rule_id,
                    input_data=input_data or {},
                    actions_taken=[],
                    status="skipped",
                    error_message="rule is disabled",
                    completed_at=_now_ts(),
                )
            else:
                execution = FoundryRuleExecution(
                    rule_id=rule_id,
                    input_data=input_data or {},
                    actions_taken=list(rule.actions),
                    status="success",
                    completed_at=_now_ts(),
                )
            if len(self._executions) >= self._MAX_EXECUTIONS:
                oldest_id = min(
                    self._executions,
                    key=lambda eid: self._executions[eid].triggered_at,
                )
                del self._executions[oldest_id]
            self._executions[execution.id] = execution
        return execution

    def get_execution(self, execution_id: str) -> FoundryRuleExecution:
        with self._lock:
            execution = self._executions.get(execution_id)
        if execution is None:
            raise LinterFoundryError(
                "NOT_FOUND", f"execution {execution_id} not found"
            )
        return execution

    def list_executions(
        self,
        rule_id: str | None = None,
        status: str | None = None,
    ) -> list[FoundryRuleExecution]:
        with self._lock:
            items = list(self._executions.values())
        if rule_id is not None:
            items = [e for e in items if e.rule_id == rule_id]
        if status is not None:
            items = [e for e in items if e.status == status]
        return sorted(items, key=lambda e: e.triggered_at)

    def delete_execution(self, execution_id: str) -> bool:
        with self._lock:
            return self._executions.pop(execution_id, None) is not None


# ════════════════════ #17 Foundry Rules 时间序列 ════════════════════

class TimeSeriesSync(BaseModel):
    id: str = Field(default_factory=lambda: _uid("ts"))
    rule_id: str
    dataset_id: str
    sync_interval_seconds: int = 300
    last_sync_at: float = 0
    last_value: float = 0.0
    trend: str = "stable"  # up / down / stable
    status: str = "active"  # active / paused / error
    created_at: float = Field(default_factory=_now_ts)


class TimeSeriesDataPoint(BaseModel):
    id: str = Field(default_factory=lambda: _uid("dp"))
    sync_id: str
    timestamp: float = Field(default_factory=_now_ts)
    value: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class FoundryTimeSeriesEngine:
    """#17 Foundry Rules 时间序列引擎。"""

    _MAX_SYNCS = 200
    _MAX_DATAPOINTS = 200
    _VALID_TRENDS = {"up", "down", "stable"}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._syncs: dict[str, TimeSeriesSync] = {}
        self._datapoints: dict[str, TimeSeriesDataPoint] = {}

    def register_sync(
        self,
        rule_id: str,
        dataset_id: str,
        sync_interval_seconds: int = 300,
    ) -> TimeSeriesSync:
        sync = TimeSeriesSync(
            rule_id=rule_id,
            dataset_id=dataset_id,
            sync_interval_seconds=sync_interval_seconds,
        )
        with self._lock:
            if len(self._syncs) >= self._MAX_SYNCS:
                oldest_id = min(
                    self._syncs, key=lambda sid: self._syncs[sid].created_at
                )
                del self._syncs[oldest_id]
            self._syncs[sync.id] = sync
        return sync

    def get_sync(self, sync_id: str) -> TimeSeriesSync:
        with self._lock:
            sync = self._syncs.get(sync_id)
        if sync is None:
            raise LinterFoundryError("NOT_FOUND", f"sync {sync_id} not found")
        return sync

    def list_syncs(
        self,
        rule_id: str | None = None,
        status: str | None = None,
    ) -> list[TimeSeriesSync]:
        with self._lock:
            items = list(self._syncs.values())
        if rule_id is not None:
            items = [s for s in items if s.rule_id == rule_id]
        if status is not None:
            items = [s for s in items if s.status == status]
        return sorted(items, key=lambda s: s.created_at)

    def update_sync(self, sync_id: str, updates: dict[str, Any]) -> TimeSeriesSync:
        with self._lock:
            sync = self._syncs.get(sync_id)
            if sync is None:
                raise LinterFoundryError("NOT_FOUND", f"sync {sync_id} not found")
            if "trend" in updates and updates["trend"] not in self._VALID_TRENDS:
                raise LinterFoundryError(
                    "INVALID_TREND",
                    f"trend must be one of {sorted(self._VALID_TRENDS)}",
                )
            applicable = {
                k: v
                for k, v in updates.items()
                if k != "id" and k in type(sync).model_fields
            }
            updated = sync.model_copy(update=applicable)
            self._syncs[sync_id] = updated
        return updated

    def pause_sync(self, sync_id: str) -> TimeSeriesSync:
        with self._lock:
            sync = self._syncs.get(sync_id)
            if sync is None:
                raise LinterFoundryError("NOT_FOUND", f"sync {sync_id} not found")
            updated = sync.model_copy(update={"status": "paused"})
            self._syncs[sync_id] = updated
        return updated

    def resume_sync(self, sync_id: str) -> TimeSeriesSync:
        with self._lock:
            sync = self._syncs.get(sync_id)
            if sync is None:
                raise LinterFoundryError("NOT_FOUND", f"sync {sync_id} not found")
            updated = sync.model_copy(update={"status": "active"})
            self._syncs[sync_id] = updated
        return updated

    def record_datapoint(
        self,
        sync_id: str,
        value: float,
        metadata: dict[str, Any] | None = None,
    ) -> TimeSeriesDataPoint:
        with self._lock:
            sync = self._syncs.get(sync_id)
            if sync is None:
                raise LinterFoundryError("NOT_FOUND", f"sync {sync_id} not found")
            now = _now_ts()
            datapoint = TimeSeriesDataPoint(
                sync_id=sync_id,
                timestamp=now,
                value=value,
                metadata=metadata or {},
            )
            if len(self._datapoints) >= self._MAX_DATAPOINTS:
                oldest_id = min(
                    self._datapoints,
                    key=lambda did: self._datapoints[did].timestamp,
                )
                del self._datapoints[oldest_id]
            self._datapoints[datapoint.id] = datapoint
            # 重新计算 trend：与上一个 datapoint 比较
            prev_points = [
                dp
                for dp in self._datapoints.values()
                if dp.sync_id == sync_id and dp.id != datapoint.id
            ]
            if prev_points:
                prev = max(prev_points, key=lambda dp: dp.timestamp)
                if value > prev.value:
                    trend = "up"
                elif value < prev.value:
                    trend = "down"
                else:
                    trend = "stable"
            else:
                trend = "stable"
            self._syncs[sync_id] = sync.model_copy(
                update={
                    "last_sync_at": now,
                    "last_value": value,
                    "trend": trend,
                }
            )
        return datapoint

    def get_datapoint(self, datapoint_id: str) -> TimeSeriesDataPoint:
        with self._lock:
            datapoint = self._datapoints.get(datapoint_id)
        if datapoint is None:
            raise LinterFoundryError(
                "NOT_FOUND", f"datapoint {datapoint_id} not found"
            )
        return datapoint

    def list_datapoints(
        self,
        sync_id: str | None = None,
        limit: int = 100,
    ) -> list[TimeSeriesDataPoint]:
        with self._lock:
            items = list(self._datapoints.values())
        if sync_id is not None:
            items = [dp for dp in items if dp.sync_id == sync_id]
        items = sorted(items, key=lambda dp: dp.timestamp, reverse=True)
        return items[:limit]

    def delete_sync(self, sync_id: str) -> bool:
        with self._lock:
            return self._syncs.pop(sync_id, None) is not None

    def delete_datapoint(self, datapoint_id: str) -> bool:
        with self._lock:
            return self._datapoints.pop(datapoint_id, None) is not None


# ────────────────────────────────────────────────────────────────
# 单例 getter（双重检查锁）
# ────────────────────────────────────────────────────────────────

_lock = threading.Lock()
_linter_engine: LinterRuleEngine | None = None
_scan_engine: LinterScanScheduleEngine | None = None
_foundry_engine: FoundryRulesEngine | None = None
_ts_engine: FoundryTimeSeriesEngine | None = None


def get_linter_rule_engine() -> LinterRuleEngine:
    global _linter_engine
    if _linter_engine is None:
        with _lock:
            if _linter_engine is None:
                _linter_engine = LinterRuleEngine()
    return _linter_engine


def get_linter_scan_schedule_engine() -> LinterScanScheduleEngine:
    global _scan_engine
    if _scan_engine is None:
        with _lock:
            if _scan_engine is None:
                _scan_engine = LinterScanScheduleEngine()
    return _scan_engine


def get_foundry_rules_engine() -> FoundryRulesEngine:
    global _foundry_engine
    if _foundry_engine is None:
        with _lock:
            if _foundry_engine is None:
                _foundry_engine = FoundryRulesEngine()
    return _foundry_engine


def get_foundry_time_series_engine() -> FoundryTimeSeriesEngine:
    global _ts_engine
    if _ts_engine is None:
        with _lock:
            if _ts_engine is None:
                _ts_engine = FoundryTimeSeriesEngine()
    return _ts_engine
