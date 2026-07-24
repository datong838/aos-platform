"""W2-BL · Linter Foundry Rules 引擎单元测试。

覆盖四个引擎：LinterRuleEngine、LinterScanScheduleEngine、FoundryRulesEngine、FoundryTimeSeriesEngine。
"""
from __future__ import annotations

import pytest
import time
from aos_api.linter_foundry_rules import (
    LinterRuleEngine, LinterRule, LintFinding, LintFixProposal,
    LinterScanScheduleEngine, ScanSchedule, ScanRun,
    FoundryRulesEngine, FoundryRule, FoundryRuleExecution,
    FoundryTimeSeriesEngine, TimeSeriesSync, TimeSeriesDataPoint,
    LinterFoundryError,
    get_linter_rule_engine,
    get_linter_scan_schedule_engine,
    get_foundry_rules_engine,
    get_foundry_time_series_engine,
)


# --------------------------------------------------------------------------- #
# LinterRuleEngine 测试
# --------------------------------------------------------------------------- #
class TestLinterRuleEngine:
    def setup_method(self) -> None:
        self.engine = LinterRuleEngine()

    def test_register_rule(self) -> None:
        rule = self.engine.register_rule(
            code="LINT001",
            title="No plaintext password",
            description="Password should not be stored in plaintext",
            severity="error",
            category="security",
            pattern="password",
            suggestion="Use environment variables",
            auto_fix=False,
        )
        assert rule.id.startswith("lint-")
        assert rule.code == "LINT001"
        assert rule.title == "No plaintext password"
        assert rule.severity == "error"
        assert rule.category == "security"
        assert rule.pattern == "password"
        assert rule.suggestion == "Use environment variables"
        assert rule.enabled is True
        assert rule.created_at > 0

    def test_register_rule_invalid_severity(self) -> None:
        with pytest.raises(LinterFoundryError) as exc_info:
            self.engine.register_rule(
                code="LINT002",
                title="bad severity",
                description="desc",
                severity="fatal",
                category="security",
            )
        assert exc_info.value.code == "INVALID_SEVERITY"

    def test_register_rule_invalid_category(self) -> None:
        with pytest.raises(LinterFoundryError) as exc_info:
            self.engine.register_rule(
                code="LINT003",
                title="bad category",
                description="desc",
                severity="warning",
                category="unknown",
            )
        assert exc_info.value.code == "INVALID_CATEGORY"

    def test_get_rule(self) -> None:
        rule = self.engine.register_rule(
            code="LINT004",
            title="get test",
            description="desc",
            severity="info",
            category="style",
        )
        retrieved = self.engine.get_rule(rule.id)
        assert retrieved.id == rule.id
        assert retrieved.code == "LINT004"

    def test_get_rule_not_found(self) -> None:
        with pytest.raises(LinterFoundryError) as exc_info:
            self.engine.get_rule("lint-nonexistent")
        assert exc_info.value.code == "NOT_FOUND"

    def test_list_rules(self) -> None:
        self.engine.register_rule(
            code="R1", title="t1", description="d",
            severity="error", category="security",
        )
        self.engine.register_rule(
            code="R2", title="t2", description="d",
            severity="warning", category="style",
        )
        self.engine.register_rule(
            code="R3", title="t3", description="d",
            severity="info", category="security",
        )
        # 全部
        assert len(self.engine.list_rules()) == 3
        # 按 category 过滤
        security_rules = self.engine.list_rules(category="security")
        assert len(security_rules) == 2
        assert all(r.category == "security" for r in security_rules)
        # 按 severity 过滤
        warning_rules = self.engine.list_rules(severity="warning")
        assert len(warning_rules) == 1
        assert warning_rules[0].severity == "warning"
        # enabled_only 过滤
        self.engine.update_rule(security_rules[0].id, {"enabled": False})
        enabled = self.engine.list_rules(enabled_only=True)
        assert len(enabled) == 2

    def test_update_rule(self) -> None:
        rule = self.engine.register_rule(
            code="U1", title="orig", description="d",
            severity="info", category="style",
        )
        updated = self.engine.update_rule(rule.id, {
            "title": "updated title",
            "severity": "critical",
            "enabled": False,
        })
        assert updated.title == "updated title"
        assert updated.severity == "critical"
        assert updated.enabled is False
        # 验证持久化
        assert self.engine.get_rule(rule.id).title == "updated title"

    def test_delete_rule(self) -> None:
        rule = self.engine.register_rule(
            code="D1", title="del", description="d",
            severity="info", category="style",
        )
        assert self.engine.delete_rule(rule.id) is True
        with pytest.raises(LinterFoundryError):
            self.engine.get_rule(rule.id)
        # 再次删除返回 False
        assert self.engine.delete_rule(rule.id) is False

    def test_detect(self) -> None:
        self.engine.register_rule(
            code="DET1", title="detect password", description="found password",
            severity="error", category="security",
            pattern="password", suggestion="remove it",
        )
        findings = self.engine.detect(
            resource_type="config",
            resource_id="cfg-1",
            resource_data={"password": "secret123", "name": "app"},
        )
        assert len(findings) == 1
        f = findings[0]
        assert f.rule_code == "DET1"
        assert f.resource_type == "config"
        assert f.resource_id == "cfg-1"
        assert f.severity == "error"
        assert f.message == "found password"
        assert f.suggestion == "remove it"
        assert f.status == "open"

    def test_detect_no_match(self) -> None:
        self.engine.register_rule(
            code="DET2", title="no match", description="desc",
            severity="warning", category="style",
            pattern="nonexistent_key",
        )
        findings = self.engine.detect(
            resource_type="config",
            resource_id="cfg-2",
            resource_data={"foo": "bar", "baz": "qux"},
        )
        assert findings == []

    def test_get_finding_and_list_findings(self) -> None:
        self.engine.register_rule(
            code="F1", title="t", description="d",
            severity="critical", category="security",
            pattern="secret",
        )
        self.engine.detect("service", "svc-1", {"secret": "abc"})
        self.engine.register_rule(
            code="F2", title="t", description="d",
            severity="warning", category="style",
            pattern="flag",
        )
        self.engine.detect("job", "job-1", {"flag": True})

        all_findings = self.engine.list_findings()
        assert len(all_findings) == 2

        # 按 resource_type 过滤
        svc_findings = self.engine.list_findings(resource_type="service")
        assert len(svc_findings) == 1
        assert svc_findings[0].resource_type == "service"

        # 按 severity 过滤
        critical = self.engine.list_findings(severity="critical")
        assert len(critical) == 1
        assert critical[0].severity == "critical"

        # 按 status 过滤
        open_findings = self.engine.list_findings(status="open")
        assert len(open_findings) == 2

        # get_finding
        f_id = all_findings[0].id
        assert self.engine.get_finding(f_id).id == f_id

    def test_fix_finding(self) -> None:
        self.engine.register_rule(
            code="FX1", title="t", description="d",
            severity="error", category="security",
            pattern="pwd", auto_fix=True,
        )
        findings = self.engine.detect("config", "c-1", {"pwd": "123"})
        finding = findings[0]

        fix = self.engine.fix_finding(
            finding.id, proposed_value="***", description="mask value"
        )
        assert fix.finding_id == finding.id
        assert fix.proposed_value == "***"
        assert fix.description == "mask value"
        assert fix.applied is False
        # finding 状态变为 fixed
        assert self.engine.get_finding(finding.id).status == "fixed"

    def test_ignore_finding(self) -> None:
        self.engine.register_rule(
            code="IG1", title="t", description="d",
            severity="warning", category="style",
            pattern="todo",
        )
        findings = self.engine.detect("code", "f-1", {"todo": "fixme"})
        finding = findings[0]

        ignored = self.engine.ignore_finding(finding.id)
        assert ignored.status == "ignored"
        assert self.engine.get_finding(finding.id).status == "ignored"

    def test_apply_fix(self) -> None:
        self.engine.register_rule(
            code="AF1", title="t", description="d",
            severity="error", category="security",
            pattern="key",
        )
        findings = self.engine.detect("config", "c-2", {"key": "value"})
        finding = findings[0]
        fix = self.engine.fix_finding(finding.id, proposed_value="new")

        applied = self.engine.apply_fix(fix.id)
        assert applied.applied is True
        # 持久化验证
        assert self.engine.get_fix_proposal(fix.id).applied is True

    def test_fifo_eviction_findings(self) -> None:
        self.engine.register_rule(
            code="EV1", title="t", description="d",
            severity="info", category="style",
            pattern="pat",
        )
        # 产生超过 _MAX_FINDINGS 的 findings
        for i in range(self.engine._MAX_FINDINGS + 5):
            self.engine.detect("config", f"r-{i}", {"pat": i})
        assert len(self.engine.list_findings()) == self.engine._MAX_FINDINGS


# --------------------------------------------------------------------------- #
# LinterScanScheduleEngine 测试
# --------------------------------------------------------------------------- #
class TestLinterScanScheduleEngine:
    def setup_method(self) -> None:
        self.engine = LinterScanScheduleEngine()

    def test_create_schedule(self) -> None:
        before = time.time()
        schedule = self.engine.create_schedule(
            name="nightly-scan",
            cron_expression="0 2 * * *",
            resource_scope="all",
            rule_scope="all",
        )
        after = time.time()
        assert schedule.id.startswith("scan-")
        assert schedule.name == "nightly-scan"
        assert schedule.cron_expression == "0 2 * * *"
        assert schedule.resource_scope == "all"
        assert schedule.rule_scope == "all"
        assert schedule.enabled is True
        assert schedule.last_run_at == 0
        # next_run_at = now + 3600
        assert before + 3600 <= schedule.next_run_at <= after + 3600

    def test_create_schedule_invalid_resource_scope(self) -> None:
        with pytest.raises(LinterFoundryError) as exc_info:
            self.engine.create_schedule(
                name="bad", cron_expression="0 * * * *",
                resource_scope="invalid_scope",
            )
        assert exc_info.value.code == "INVALID_RESOURCE_SCOPE"

    def test_create_schedule_invalid_rule_scope(self) -> None:
        with pytest.raises(LinterFoundryError) as exc_info:
            self.engine.create_schedule(
                name="bad", cron_expression="0 * * * *",
                resource_scope="all",
                rule_scope="invalid_rule_scope",
            )
        assert exc_info.value.code == "INVALID_RULE_SCOPE"

    def test_get_schedule_and_list_schedules(self) -> None:
        s1 = self.engine.create_schedule(name="s1", cron_expression="0 * * * *")
        s2 = self.engine.create_schedule(name="s2", cron_expression="0 * * * *")

        # get_schedule
        retrieved = self.engine.get_schedule(s1.id)
        assert retrieved.id == s1.id
        assert retrieved.name == "s1"

        # list_schedules
        assert len(self.engine.list_schedules()) == 2
        # 禁用 s1 后 enabled_only
        self.engine.update_schedule(s1.id, {"enabled": False})
        enabled = self.engine.list_schedules(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].id == s2.id

    def test_update_schedule_and_delete_schedule(self) -> None:
        schedule = self.engine.create_schedule(name="orig", cron_expression="0 * * * *")
        updated = self.engine.update_schedule(schedule.id, {
            "name": "updated",
            "cron_expression": "0 0 * * *",
            "enabled": False,
        })
        assert updated.name == "updated"
        assert updated.cron_expression == "0 0 * * *"
        assert updated.enabled is False
        assert self.engine.get_schedule(schedule.id).name == "updated"

        # delete
        assert self.engine.delete_schedule(schedule.id) is True
        with pytest.raises(LinterFoundryError):
            self.engine.get_schedule(schedule.id)
        assert self.engine.delete_schedule(schedule.id) is False

    def test_run_scan(self) -> None:
        schedule = self.engine.create_schedule(name="scan1", cron_expression="0 * * * *")
        assert schedule.last_run_at == 0

        before = time.time()
        run = self.engine.run_scan(schedule.id)
        after = time.time()

        assert run.id.startswith("run-")
        assert run.schedule_id == schedule.id
        assert run.status == "completed"
        assert run.resources_scanned > 0
        assert run.findings_count >= 0
        assert run.completed_at > 0

        # schedule.last_run_at 已更新
        updated_schedule = self.engine.get_schedule(schedule.id)
        assert before <= updated_schedule.last_run_at <= after
        assert updated_schedule.next_run_at >= updated_schedule.last_run_at + 3600

    def test_list_runs(self) -> None:
        s1 = self.engine.create_schedule(name="s1", cron_expression="0 * * * *")
        s2 = self.engine.create_schedule(name="s2", cron_expression="0 * * * *")
        r1 = self.engine.run_scan(s1.id)
        r2 = self.engine.run_scan(s1.id)
        r3 = self.engine.run_scan(s2.id)

        # 全部
        all_runs = self.engine.list_runs()
        assert len(all_runs) == 3
        # 按 schedule_id 过滤
        s1_runs = self.engine.list_runs(schedule_id=s1.id)
        assert len(s1_runs) == 2
        assert all(r.schedule_id == s1.id for r in s1_runs)
        # 按 status 过滤（全部 completed）
        completed = self.engine.list_runs(status="completed")
        assert len(completed) == 3

    def test_fifo_eviction_runs(self) -> None:
        schedule = self.engine.create_schedule(name="fifo", cron_expression="0 * * * *")
        for _ in range(self.engine._MAX_RUNS + 5):
            self.engine.run_scan(schedule.id)
        assert len(self.engine.list_runs()) == self.engine._MAX_RUNS


# --------------------------------------------------------------------------- #
# FoundryRulesEngine 测试
# --------------------------------------------------------------------------- #
class TestFoundryRulesEngine:
    def setup_method(self) -> None:
        self.engine = FoundryRulesEngine()

    def test_create_rule(self) -> None:
        rule = self.engine.create_rule(
            name="auto-notify",
            description="Notify on threshold breach",
            trigger_type="condition",
            conditions=[{"field": "cpu", "op": ">", "value": 90}],
            actions=["notify", "call_function"],
            workflow_id="wf-1",
        )
        assert rule.id.startswith("fr-")
        assert rule.name == "auto-notify"
        assert rule.trigger_type == "condition"
        assert len(rule.conditions) == 1
        assert rule.conditions[0]["field"] == "cpu"
        assert rule.actions == ["notify", "call_function"]
        assert rule.workflow_id == "wf-1"
        assert rule.enabled is True

    def test_create_rule_invalid_trigger_type(self) -> None:
        with pytest.raises(LinterFoundryError) as exc_info:
            self.engine.create_rule(
                name="bad", description="d",
                trigger_type="invalid_trigger",
            )
        assert exc_info.value.code == "INVALID_TRIGGER_TYPE"

    def test_create_rule_invalid_action(self) -> None:
        with pytest.raises(LinterFoundryError) as exc_info:
            self.engine.create_rule(
                name="bad", description="d",
                trigger_type="event",
                actions=["notify", "delete_everything"],
            )
        assert exc_info.value.code == "INVALID_ACTION"

    def test_get_rule_and_list_rules(self) -> None:
        r1 = self.engine.create_rule(
            name="r1", description="d", trigger_type="condition",
            actions=["notify"],
        )
        r2 = self.engine.create_rule(
            name="r2", description="d", trigger_type="schedule",
            actions=["create_object"],
        )
        r3 = self.engine.create_rule(
            name="r3", description="d", trigger_type="condition",
            actions=["update_object"],
        )

        # get_rule
        assert self.engine.get_rule(r1.id).id == r1.id

        # list_rules 全部
        assert len(self.engine.list_rules()) == 3
        # 按 trigger_type 过滤
        condition_rules = self.engine.list_rules(trigger_type="condition")
        assert len(condition_rules) == 2
        assert all(r.trigger_type == "condition" for r in condition_rules)
        # enabled_only
        self.engine.update_rule(r1.id, {"enabled": False})
        enabled = self.engine.list_rules(enabled_only=True)
        assert len(enabled) == 2

    def test_update_rule_and_delete_rule(self) -> None:
        rule = self.engine.create_rule(
            name="orig", description="d", trigger_type="event",
            actions=["notify"],
        )
        updated = self.engine.update_rule(rule.id, {
            "name": "updated",
            "enabled": False,
            "actions": ["notify", "create_object"],
        })
        assert updated.name == "updated"
        assert updated.enabled is False
        assert updated.actions == ["notify", "create_object"]
        assert self.engine.get_rule(rule.id).name == "updated"

        # delete
        assert self.engine.delete_rule(rule.id) is True
        with pytest.raises(LinterFoundryError):
            self.engine.get_rule(rule.id)
        assert self.engine.delete_rule(rule.id) is False

    def test_execute_rule(self) -> None:
        rule = self.engine.create_rule(
            name="exec", description="d", trigger_type="condition",
            actions=["notify", "call_function"],
        )
        execution = self.engine.execute_rule(rule.id, input_data={"x": 1})
        assert execution.id.startswith("fre-")
        assert execution.rule_id == rule.id
        assert execution.input_data == {"x": 1}
        assert execution.actions_taken == ["notify", "call_function"]
        assert execution.status == "success"
        assert execution.completed_at > 0

    def test_execute_rule_disabled(self) -> None:
        rule = self.engine.create_rule(
            name="disabled", description="d", trigger_type="event",
            actions=["notify"],
        )
        self.engine.update_rule(rule.id, {"enabled": False})
        execution = self.engine.execute_rule(rule.id)
        assert execution.status == "skipped"
        assert execution.actions_taken == []
        assert execution.error_message == "rule is disabled"

    def test_list_executions_and_delete_execution(self) -> None:
        r1 = self.engine.create_rule(
            name="r1", description="d", trigger_type="condition",
            actions=["notify"],
        )
        r2 = self.engine.create_rule(
            name="r2", description="d", trigger_type="event",
            actions=["create_object"],
        )
        e1 = self.engine.execute_rule(r1.id)
        e2 = self.engine.execute_rule(r1.id)
        e3 = self.engine.execute_rule(r2.id)

        # 全部
        assert len(self.engine.list_executions()) == 3
        # 按 rule_id 过滤
        r1_execs = self.engine.list_executions(rule_id=r1.id)
        assert len(r1_execs) == 2
        assert all(e.rule_id == r1.id for e in r1_execs)
        # 按 status 过滤
        success = self.engine.list_executions(status="success")
        assert len(success) == 3

        # delete_execution
        assert self.engine.delete_execution(e1.id) is True
        assert len(self.engine.list_executions()) == 2
        assert self.engine.delete_execution(e1.id) is False


# --------------------------------------------------------------------------- #
# FoundryTimeSeriesEngine 测试
# --------------------------------------------------------------------------- #
class TestFoundryTimeSeriesEngine:
    def setup_method(self) -> None:
        self.engine = FoundryTimeSeriesEngine()

    def test_register_sync(self) -> None:
        sync = self.engine.register_sync(
            rule_id="fr-1",
            dataset_id="ds-1",
            sync_interval_seconds=600,
        )
        assert sync.id.startswith("ts-")
        assert sync.rule_id == "fr-1"
        assert sync.dataset_id == "ds-1"
        assert sync.sync_interval_seconds == 600
        assert sync.last_sync_at == 0
        assert sync.last_value == 0.0
        assert sync.trend == "stable"
        assert sync.status == "active"
        assert sync.created_at > 0

    def test_get_sync_and_list_syncs(self) -> None:
        s1 = self.engine.register_sync(rule_id="r1", dataset_id="d1")
        s2 = self.engine.register_sync(rule_id="r1", dataset_id="d2")
        s3 = self.engine.register_sync(rule_id="r2", dataset_id="d3")

        # get_sync
        assert self.engine.get_sync(s1.id).id == s1.id

        # list_syncs 全部
        assert len(self.engine.list_syncs()) == 3
        # 按 rule_id 过滤
        r1_syncs = self.engine.list_syncs(rule_id="r1")
        assert len(r1_syncs) == 2
        assert all(s.rule_id == "r1" for s in r1_syncs)
        # 按 status 过滤
        self.engine.pause_sync(s1.id)
        active = self.engine.list_syncs(status="active")
        assert len(active) == 2
        paused = self.engine.list_syncs(status="paused")
        assert len(paused) == 1

    def test_update_sync(self) -> None:
        sync = self.engine.register_sync(rule_id="r1", dataset_id="d1")
        updated = self.engine.update_sync(sync.id, {
            "sync_interval_seconds": 120,
            "status": "error",
        })
        assert updated.sync_interval_seconds == 120
        assert updated.status == "error"
        assert self.engine.get_sync(sync.id).sync_interval_seconds == 120

    def test_update_sync_invalid_trend(self) -> None:
        sync = self.engine.register_sync(rule_id="r1", dataset_id="d1")
        with pytest.raises(LinterFoundryError) as exc_info:
            self.engine.update_sync(sync.id, {"trend": "sideways"})
        assert exc_info.value.code == "INVALID_TREND"

    def test_pause_sync_and_resume_sync(self) -> None:
        sync = self.engine.register_sync(rule_id="r1", dataset_id="d1")
        assert sync.status == "active"

        paused = self.engine.pause_sync(sync.id)
        assert paused.status == "paused"
        assert self.engine.get_sync(sync.id).status == "paused"

        resumed = self.engine.resume_sync(sync.id)
        assert resumed.status == "active"
        assert self.engine.get_sync(sync.id).status == "active"

    def test_record_datapoint(self) -> None:
        sync = self.engine.register_sync(rule_id="r1", dataset_id="d1")
        assert sync.last_value == 0.0
        assert sync.last_sync_at == 0

        before = time.time()
        dp = self.engine.record_datapoint(sync.id, value=42.5, metadata={"src": "api"})
        after = time.time()

        assert dp.id.startswith("dp-")
        assert dp.sync_id == sync.id
        assert dp.value == 42.5
        assert dp.metadata == {"src": "api"}
        assert before <= dp.timestamp <= after

        # sync 的 last_value 和 last_sync_at 已更新
        updated = self.engine.get_sync(sync.id)
        assert updated.last_value == 42.5
        assert updated.last_sync_at > 0
        # 第一个点 trend 为 stable
        assert updated.trend == "stable"

    def test_record_datapoint_trend(self) -> None:
        sync = self.engine.register_sync(rule_id="r1", dataset_id="d1")
        # 第一个点
        self.engine.record_datapoint(sync.id, value=10.0)
        assert self.engine.get_sync(sync.id).trend == "stable"

        # 上升
        self.engine.record_datapoint(sync.id, value=20.0)
        assert self.engine.get_sync(sync.id).trend == "up"

        # 下降
        self.engine.record_datapoint(sync.id, value=5.0)
        assert self.engine.get_sync(sync.id).trend == "down"

        # 相等
        self.engine.record_datapoint(sync.id, value=5.0)
        assert self.engine.get_sync(sync.id).trend == "stable"

    def test_get_datapoint_and_list_datapoints(self) -> None:
        sync = self.engine.register_sync(rule_id="r1", dataset_id="d1")
        dp1 = self.engine.record_datapoint(sync.id, value=1.0)
        time.sleep(0.01)
        dp2 = self.engine.record_datapoint(sync.id, value=2.0)
        time.sleep(0.01)
        dp3 = self.engine.record_datapoint(sync.id, value=3.0)

        # get_datapoint
        assert self.engine.get_datapoint(dp2.id).id == dp2.id

        # list_datapoints 默认按 timestamp 降序
        all_dps = self.engine.list_datapoints()
        assert len(all_dps) == 3
        assert all_dps[0].timestamp >= all_dps[1].timestamp >= all_dps[2].timestamp
        # 最新值在前
        assert all_dps[0].value == 3.0

        # 按 sync_id 过滤 + limit
        sync_dps = self.engine.list_datapoints(sync_id=sync.id, limit=2)
        assert len(sync_dps) == 2
        assert all(dp.sync_id == sync.id for dp in sync_dps)
        # limit 截断
        assert sync_dps[0].value == 3.0
        assert sync_dps[1].value == 2.0

    def test_delete_sync_and_delete_datapoint(self) -> None:
        sync = self.engine.register_sync(rule_id="r1", dataset_id="d1")
        dp = self.engine.record_datapoint(sync.id, value=1.0)

        # delete_datapoint
        assert self.engine.delete_datapoint(dp.id) is True
        with pytest.raises(LinterFoundryError):
            self.engine.get_datapoint(dp.id)
        assert self.engine.delete_datapoint(dp.id) is False

        # delete_sync
        assert self.engine.delete_sync(sync.id) is True
        with pytest.raises(LinterFoundryError):
            self.engine.get_sync(sync.id)
        assert self.engine.delete_sync(sync.id) is False

    def test_fifo_eviction_datapoints(self) -> None:
        sync = self.engine.register_sync(rule_id="r1", dataset_id="d1")
        for i in range(self.engine._MAX_DATAPOINTS + 5):
            self.engine.record_datapoint(sync.id, value=float(i))
        assert len(self.engine.list_datapoints(limit=10000)) == self.engine._MAX_DATAPOINTS


# --------------------------------------------------------------------------- #
# 单例 getter 测试
# --------------------------------------------------------------------------- #
def test_singleton_getters():
    assert get_linter_rule_engine() is get_linter_rule_engine()
    assert get_linter_scan_schedule_engine() is get_linter_scan_schedule_engine()
    assert get_foundry_rules_engine() is get_foundry_rules_engine()
    assert get_foundry_time_series_engine() is get_foundry_time_series_engine()
