"""W2-BJ · Agent 健康/迁移/市场/Webhook 存储引擎测试（#6 #7 #8 #9）.

覆盖：
- AgentHealthMonitorEngine（#6 Agent 健康监控）
- DirectConnectionMigrationEngine（#7 直连迁移向导）
- SourceMarketplaceEngine（#8 Source Marketplace）
- WebhookStorageEngine（#9 Webhook 投递存储）
"""
from __future__ import annotations

import time

import pytest

from aos_api.agent_health_migration_webhook import (
    AgentHealthMonitorEngine,
    AgentMigrationWebhookError,
    DirectConnectionMigrationEngine,
    HealthAlert,
    HealthRule,
    MarketplaceSource,
    MigrationPlan,
    MigrationStep,
    SourceInstallation,
    SourceMarketplaceEngine,
    WebhookDelivery,
    WebhookStorageEngine,
    get_agent_health_monitor_engine,
    get_direct_connection_migration_engine,
    get_source_marketplace_engine,
    get_webhook_storage_engine,
)


# ════════════════════ #6 AgentHealthMonitorEngine ════════════════════


class TestAgentHealthMonitorEngine:
    def setup_method(self) -> None:
        self.engine = AgentHealthMonitorEngine()

    # --- create_rule ---
    def test_create_rule(self) -> None:
        rule = self.engine.create_rule(
            agent_id="agent-1",
            metric_name="cpu",
            threshold_warning=50.0,
            threshold_critical=80.0,
        )
        assert rule.id.startswith("rule-")
        assert rule.agent_id == "agent-1"
        assert rule.metric_name == "cpu"
        assert rule.threshold_warning == 50.0
        assert rule.threshold_critical == 80.0
        assert rule.enabled is True
        assert rule.created_at > 0
        # 持久化
        assert self.engine.get_rule(rule.id).id == rule.id

    def test_create_rule_invalid_metric(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.create_rule(
                agent_id="agent-1",
                metric_name="network",
                threshold_warning=50.0,
                threshold_critical=80.0,
            )
        assert exc.value.code == "INVALID_METRIC_NAME"

    def test_create_rule_invalid_thresholds(self) -> None:
        # warning >= critical -> error
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.create_rule(
                agent_id="agent-1",
                metric_name="cpu",
                threshold_warning=80.0,
                threshold_critical=80.0,
            )
        assert exc.value.code == "INVALID_THRESHOLDS"

        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.create_rule(
                agent_id="agent-1",
                metric_name="cpu",
                threshold_warning=90.0,
                threshold_critical=80.0,
            )
        assert exc.value.code == "INVALID_THRESHOLDS"

    # --- get_rule ---
    def test_get_rule(self) -> None:
        rule = self.engine.create_rule(
            "agent-1", "cpu", 50.0, 80.0
        )
        got = self.engine.get_rule(rule.id)
        assert got.id == rule.id
        assert got.metric_name == "cpu"

    def test_get_rule_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.get_rule("rule-nope")
        assert exc.value.code == "NOT_FOUND"

    # --- list_rules ---
    def test_list_rules_filter_by_agent(self) -> None:
        self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        self.engine.create_rule("agent-1", "disk", 60.0, 90.0)
        self.engine.create_rule("agent-2", "cpu", 50.0, 80.0)
        all_rules = self.engine.list_rules()
        assert len(all_rules) == 3
        a1 = self.engine.list_rules(agent_id="agent-1")
        assert len(a1) == 2
        assert all(r.agent_id == "agent-1" for r in a1)
        a2 = self.engine.list_rules(agent_id="agent-2")
        assert len(a2) == 1
        assert a2[0].agent_id == "agent-2"

    # --- update_rule ---
    def test_update_rule(self) -> None:
        rule = self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        updated = self.engine.update_rule(
            rule.id,
            threshold_warning=60.0,
            threshold_critical=85.0,
            enabled=False,
        )
        assert updated.threshold_warning == 60.0
        assert updated.threshold_critical == 85.0
        assert updated.enabled is False
        # 持久化
        again = self.engine.get_rule(rule.id)
        assert again.threshold_warning == 60.0
        assert again.enabled is False

    def test_update_rule_invalid_thresholds(self) -> None:
        rule = self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.update_rule(
                rule.id, threshold_warning=90.0, threshold_critical=80.0
            )
        assert exc.value.code == "INVALID_THRESHOLDS"

    def test_update_rule_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.update_rule("rule-nope", enabled=False)
        assert exc.value.code == "NOT_FOUND"

    # --- delete_rule ---
    def test_delete_rule(self) -> None:
        rule = self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        assert self.engine.delete_rule(rule.id) is True
        with pytest.raises(AgentMigrationWebhookError):
            self.engine.get_rule(rule.id)
        # 二次删除返回 False
        assert self.engine.delete_rule(rule.id) is False

    # --- evaluate ---
    def test_evaluate_critical(self) -> None:
        rule = self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        alert = self.engine.evaluate("agent-1", "cpu", 90.0)
        assert alert is not None
        assert alert.rule_id == rule.id
        assert alert.severity == "critical"
        assert alert.threshold == 80.0
        assert alert.current_value == 90.0
        assert alert.status == "active"
        assert "critical" in alert.message

    def test_evaluate_critical_boundary(self) -> None:
        # value == threshold_critical => critical (>=)
        self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        alert = self.engine.evaluate("agent-1", "cpu", 80.0)
        assert alert is not None
        assert alert.severity == "critical"

    def test_evaluate_warning(self) -> None:
        self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        alert = self.engine.evaluate("agent-1", "cpu", 60.0)
        assert alert is not None
        assert alert.severity == "warning"
        assert alert.threshold == 50.0
        assert alert.current_value == 60.0

    def test_evaluate_warning_boundary(self) -> None:
        # value == threshold_warning => warning (>=)
        self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        alert = self.engine.evaluate("agent-1", "cpu", 50.0)
        assert alert is not None
        assert alert.severity == "warning"

    def test_evaluate_normal(self) -> None:
        self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        alert = self.engine.evaluate("agent-1", "cpu", 40.0)
        assert alert is None

    def test_evaluate_no_matching_rule(self) -> None:
        # 无规则或规则禁用 -> None
        assert self.engine.evaluate("agent-1", "cpu", 99.0) is None
        self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        self.engine.update_rule(
            self.engine.list_rules()[0].id, enabled=False
        )
        assert self.engine.evaluate("agent-1", "cpu", 99.0) is None

    # --- acknowledge / resolve ---
    def test_acknowledge_alert(self) -> None:
        self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        alert = self.engine.evaluate("agent-1", "cpu", 90.0)
        assert alert is not None
        ack = self.engine.acknowledge_alert(alert.id)
        assert ack.status == "acknowledged"
        assert ack.acknowledged_at > 0
        # 持久化
        assert self.engine.get_alert(alert.id).status == "acknowledged"

    def test_resolve_alert(self) -> None:
        self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        alert = self.engine.evaluate("agent-1", "cpu", 90.0)
        assert alert is not None
        resolved = self.engine.resolve_alert(alert.id)
        assert resolved.status == "resolved"
        assert resolved.resolved_at > 0
        assert self.engine.get_alert(alert.id).status == "resolved"

    def test_acknowledge_alert_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.acknowledge_alert("alert-nope")
        assert exc.value.code == "NOT_FOUND"

    def test_resolve_alert_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.resolve_alert("alert-nope")
        assert exc.value.code == "NOT_FOUND"

    # --- list_alerts ---
    def test_list_alerts_filters(self) -> None:
        self.engine.create_rule("agent-1", "cpu", 50.0, 80.0)
        self.engine.create_rule("agent-2", "disk", 50.0, 80.0)
        crit = self.engine.evaluate("agent-1", "cpu", 90.0)
        warn = self.engine.evaluate("agent-1", "cpu", 60.0)
        other = self.engine.evaluate("agent-2", "disk", 90.0)
        assert crit is not None and warn is not None and other is not None

        # 全部
        assert len(self.engine.list_alerts()) == 3
        # 按 agent
        assert len(self.engine.list_alerts(agent_id="agent-1")) == 2
        assert len(self.engine.list_alerts(agent_id="agent-2")) == 1
        # 按 severity
        assert len(self.engine.list_alerts(severity="critical")) == 2
        assert len(self.engine.list_alerts(severity="warning")) == 1
        # 按 status
        self.engine.acknowledge_alert(crit.id)
        assert len(self.engine.list_alerts(status="acknowledged")) == 1
        assert len(self.engine.list_alerts(status="active")) == 2
        # 组合
        assert (
            len(self.engine.list_alerts(agent_id="agent-1", severity="critical"))
            == 1
        )

    # --- FIFO eviction ---
    def test_fifo_eviction_alerts(self) -> None:
        max_alerts = AgentHealthMonitorEngine._MAX_ALERTS
        self.engine.create_rule("agent-1", "cpu", 1.0, 2.0)
        # 生成 > _MAX_ALERTS 条告警
        for i in range(max_alerts + 50):
            self.engine.evaluate("agent-1", "cpu", 100.0)
        alerts = self.engine.list_alerts()
        assert len(alerts) == max_alerts
        # 最旧的告警应被驱逐（created_at 最小者）
        assert min(a.created_at for a in alerts) >= max(
            a.created_at for a in alerts
        ) - (max_alerts + 50)


# ════════════════════ #7 DirectConnectionMigrationEngine ════════════════════


class TestDirectConnectionMigrationEngine:
    def setup_method(self) -> None:
        self.engine = DirectConnectionMigrationEngine()

    # --- create_plan ---
    def test_create_plan(self) -> None:
        plan = self.engine.create_plan(
            source_connection_id="conn-src",
            target_connection_id="conn-tgt",
        )
        assert plan.id.startswith("mig-")
        assert plan.source_connection_id == "conn-src"
        assert plan.target_connection_id == "conn-tgt"
        assert plan.status == "planning"
        assert plan.rollback_window_days == 30
        assert plan.created_at > 0
        assert plan.completed_at == 0
        # 5 个默认步骤，全部 pending
        assert len(plan.steps) == 5
        for i, step in enumerate(plan.steps):
            assert step.step_num == i + 1
            assert step.status == "pending"
            assert step.completed_at == 0
        # 步骤标题与 _DEFAULT_STEPS 一致
        assert plan.steps[0].title == "评估当前直连配置"

    def test_create_plan_custom_window(self) -> None:
        plan = self.engine.create_plan(
            "conn-src", "conn-tgt", rollback_window_days=7
        )
        assert plan.rollback_window_days == 7

    # --- get_plan ---
    def test_get_plan(self) -> None:
        plan = self.engine.create_plan("conn-src", "conn-tgt")
        got = self.engine.get_plan(plan.id)
        assert got.id == plan.id
        assert len(got.steps) == 5

    def test_get_plan_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.get_plan("mig-nope")
        assert exc.value.code == "NOT_FOUND"

    # --- list_plans ---
    def test_list_plans_filter_by_status(self) -> None:
        p1 = self.engine.create_plan("c1", "c2")
        p2 = self.engine.create_plan("c3", "c4")
        self.engine.start_plan(p1.id)
        assert len(self.engine.list_plans()) == 2
        assert len(self.engine.list_plans(status="planning")) == 1
        assert len(self.engine.list_plans(status="in_progress")) == 1
        assert self.engine.list_plans(status="planning")[0].id == p2.id

    # --- start_plan ---
    def test_start_plan(self) -> None:
        plan = self.engine.create_plan("c1", "c2")
        started = self.engine.start_plan(plan.id)
        assert started.status == "in_progress"
        assert started.steps[0].status == "in_progress"
        # 其余步骤仍为 pending
        for step in started.steps[1:]:
            assert step.status == "pending"
        # 持久化
        again = self.engine.get_plan(plan.id)
        assert again.status == "in_progress"
        assert again.steps[0].status == "in_progress"

    def test_start_plan_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.start_plan("mig-nope")
        assert exc.value.code == "NOT_FOUND"

    # --- complete_step ---
    def test_complete_step_advances_next(self) -> None:
        plan = self.engine.create_plan("c1", "c2")
        self.engine.start_plan(plan.id)
        updated = self.engine.complete_step(plan.id, 1)
        assert updated.steps[0].status == "completed"
        assert updated.steps[0].completed_at > 0
        assert updated.steps[1].status == "in_progress"
        # plan 仍在进行中
        assert updated.status == "in_progress"

    def test_complete_step_invalid_step(self) -> None:
        plan = self.engine.create_plan("c1", "c2")
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.complete_step(plan.id, 99)
        assert exc.value.code == "INVALID_STEP"

    def test_complete_step_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.complete_step("mig-nope", 1)
        assert exc.value.code == "NOT_FOUND"

    # --- complete_last_step ---
    def test_complete_last_step(self) -> None:
        plan = self.engine.create_plan("c1", "c2")
        self.engine.start_plan(plan.id)
        # 完成所有 5 步
        for step_num in range(1, 6):
            updated = self.engine.complete_step(plan.id, step_num)
        assert updated.status == "completed"
        assert updated.completed_at > 0
        # 全部步骤完成
        assert all(s.status == "completed" for s in updated.steps)

    # --- skip_step ---
    def test_skip_step_advances_next(self) -> None:
        plan = self.engine.create_plan("c1", "c2")
        self.engine.start_plan(plan.id)
        updated = self.engine.skip_step(plan.id, 1)
        assert updated.steps[0].status == "skipped"
        assert updated.steps[1].status == "in_progress"
        assert updated.status == "in_progress"

    def test_skip_last_step_completes_plan(self) -> None:
        plan = self.engine.create_plan("c1", "c2")
        self.engine.start_plan(plan.id)
        for step_num in range(1, 6):
            updated = self.engine.skip_step(plan.id, step_num)
        assert updated.status == "completed"
        assert updated.completed_at > 0
        assert all(s.status == "skipped" for s in updated.steps)

    def test_skip_step_invalid_step(self) -> None:
        plan = self.engine.create_plan("c1", "c2")
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.skip_step(plan.id, 99)
        assert exc.value.code == "INVALID_STEP"

    # --- rollback ---
    def test_rollback_within_window(self) -> None:
        plan = self.engine.create_plan("c1", "c2", rollback_window_days=30)
        rolled = self.engine.rollback(plan.id)
        assert rolled.status == "rolled_back"
        # 持久化
        assert self.engine.get_plan(plan.id).status == "rolled_back"

    def test_rollback_after_complete_within_window(self) -> None:
        plan = self.engine.create_plan("c1", "c2", rollback_window_days=30)
        self.engine.start_plan(plan.id)
        for step_num in range(1, 6):
            self.engine.complete_step(plan.id, step_num)
        # 已完成且在窗口内 -> 可回滚
        rolled = self.engine.rollback(plan.id)
        assert rolled.status == "rolled_back"

    def test_rollback_expired(self) -> None:
        plan = self.engine.create_plan("c1", "c2", rollback_window_days=30)
        # 直接操纵存储记录的 created_at 使其远早于窗口
        self.engine._plans[plan.id].created_at = time.time() - 86400 * 100
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.rollback(plan.id)
        assert exc.value.code == "INVALID_ROLLBACK"
        # 状态未变
        assert self.engine.get_plan(plan.id).status == "planning"

    def test_rollback_zero_window_expired(self) -> None:
        # rollback_window_days=0 且 created_at 稍早 -> 超窗
        plan = self.engine.create_plan("c1", "c2", rollback_window_days=0)
        self.engine._plans[plan.id].created_at = time.time() - 1
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.rollback(plan.id)
        assert exc.value.code == "INVALID_ROLLBACK"

    def test_rollback_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.rollback("mig-nope")
        assert exc.value.code == "NOT_FOUND"

    # --- delete_plan ---
    def test_delete_plan(self) -> None:
        plan = self.engine.create_plan("c1", "c2")
        assert self.engine.delete_plan(plan.id) is True
        with pytest.raises(AgentMigrationWebhookError):
            self.engine.get_plan(plan.id)
        # 二次删除返回 False
        assert self.engine.delete_plan(plan.id) is False


# ════════════════════ #8 SourceMarketplaceEngine ════════════════════


class TestSourceMarketplaceEngine:
    def setup_method(self) -> None:
        self.engine = SourceMarketplaceEngine()

    # --- publish_source ---
    def test_publish_source(self) -> None:
        src = self.engine.publish_source(
            name="pg-source",
            description="PostgreSQL source",
            source_type="database",
            connection_config={"host": "localhost"},
            provider="pg",
            tags=["relational", "sql"],
        )
        assert src.id.startswith("src-")
        assert src.name == "pg-source"
        assert src.source_type == "database"
        assert src.connection_config == {"host": "localhost"}
        assert src.provider == "pg"
        assert src.tags == ["relational", "sql"]
        assert src.published is True
        assert src.rating == 0.0
        assert src.install_count == 0
        assert src.version == "1.0"
        assert src.created_at > 0
        # 持久化
        assert self.engine.get_source(src.id).id == src.id

    def test_publish_source_defaults(self) -> None:
        src = self.engine.publish_source(
            name="api-src", description="api", source_type="api"
        )
        assert src.connection_config == {}
        assert src.tags == []
        assert src.provider == ""
        assert src.published is True

    def test_publish_source_invalid_type(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.publish_source(
                name="bad", description="d", source_type="graphql"
            )
        assert exc.value.code == "INVALID_SOURCE_TYPE"

    # --- get_source ---
    def test_get_source(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        got = self.engine.get_source(src.id)
        assert got.id == src.id
        assert got.name == "n"

    def test_get_source_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.get_source("src-nope")
        assert exc.value.code == "NOT_FOUND"

    # --- list_sources ---
    def test_list_sources_filters(self) -> None:
        s1 = self.engine.publish_source(
            "db1", "d", "database", tags=["relational"]
        )
        s2 = self.engine.publish_source(
            "api1", "d", "api", tags=["rest"]
        )
        s3 = self.engine.publish_source(
            "db2", "d", "database", tags=["relational", "cloud"]
        )
        # 默认仅 published
        assert len(self.engine.list_sources()) == 3
        # 按 source_type
        dbs = self.engine.list_sources(source_type="database")
        assert len(dbs) == 2
        assert all(s.source_type == "database" for s in dbs)
        # 按 tag
        rel = self.engine.list_sources(tag="relational")
        assert len(rel) == 2
        # 组合
        assert len(self.engine.list_sources(source_type="database", tag="cloud")) == 1
        # published_only=False 包含未发布项
        self.engine.update_source(s1.id, {"published": False})
        assert len(self.engine.list_sources()) == 2  # 默认 published_only=True
        assert len(self.engine.list_sources(published_only=False)) == 3

    # --- update_source ---
    def test_update_source(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        updated = self.engine.update_source(
            src.id,
            {
                "name": "new-name",
                "description": "new-desc",
                "version": "2.0",
                "tags": ["new"],
                "published": False,
            },
        )
        assert updated.name == "new-name"
        assert updated.description == "new-desc"
        assert updated.version == "2.0"
        assert updated.tags == ["new"]
        assert updated.published is False
        # 持久化
        assert self.engine.get_source(src.id).name == "new-name"

    def test_update_source_invalid_type(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.update_source(src.id, {"source_type": "graphql"})
        assert exc.value.code == "INVALID_SOURCE_TYPE"

    def test_update_source_ignores_disallowed_keys(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        # rating/install_count/id/created_at 不在 allowed 集合内 -> 忽略
        updated = self.engine.update_source(
            src.id,
            {"rating": 5.0, "install_count": 99, "name": "changed"},
        )
        assert updated.rating == 0.0
        assert updated.install_count == 0
        assert updated.name == "changed"

    def test_update_source_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.update_source("src-nope", {"name": "x"})
        assert exc.value.code == "NOT_FOUND"

    # --- delete_source ---
    def test_delete_source(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        assert self.engine.delete_source(src.id) is True
        with pytest.raises(AgentMigrationWebhookError):
            self.engine.get_source(src.id)
        assert self.engine.delete_source(src.id) is False

    # --- install_source ---
    def test_install_source_increments_count(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        inst1 = self.engine.install_source(
            src.id, installed_by="user-1", connection_id="conn-1"
        )
        assert inst1.id.startswith("inst-")
        assert inst1.source_id == src.id
        assert inst1.installed_by == "user-1"
        assert inst1.connection_id == "conn-1"
        assert inst1.installed_at > 0
        # install_count 增加
        assert self.engine.get_source(src.id).install_count == 1
        inst2 = self.engine.install_source(src.id, "user-2", "conn-2")
        assert self.engine.get_source(src.id).install_count == 2

    def test_install_source_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.install_source("src-nope", "u", "c")
        assert exc.value.code == "NOT_FOUND"

    # --- get_installation / list_installations ---
    def test_get_installation(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        inst = self.engine.install_source(src.id, "user-1", "conn-1")
        got = self.engine.get_installation(inst.id)
        assert got.id == inst.id
        assert got.source_id == src.id

    def test_get_installation_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.get_installation("inst-nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_installations_filter_by_source(self) -> None:
        s1 = self.engine.publish_source("n1", "d", "database")
        s2 = self.engine.publish_source("n2", "d", "api")
        self.engine.install_source(s1.id, "u1", "c1")
        self.engine.install_source(s1.id, "u2", "c2")
        self.engine.install_source(s2.id, "u3", "c3")
        assert len(self.engine.list_installations()) == 3
        assert len(self.engine.list_installations(source_id=s1.id)) == 2
        assert len(self.engine.list_installations(source_id=s2.id)) == 1
        assert all(
            i.source_id == s1.id
            for i in self.engine.list_installations(source_id=s1.id)
        )

    # --- rate_source ---
    def test_rate_source_first_then_average(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        # 首次：rating=0 -> 直接赋值
        r1 = self.engine.rate_source(src.id, 4.0)
        assert r1.rating == 4.0
        # 再次：rating>0 -> 取平均 (4+2)/2 = 3
        r2 = self.engine.rate_source(src.id, 2.0)
        assert r2.rating == pytest.approx(3.0)

    def test_rate_source_zero(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        r = self.engine.rate_source(src.id, 0.0)
        assert r.rating == 0.0

    def test_rate_source_invalid_too_high(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.rate_source(src.id, 5.5)
        assert exc.value.code == "INVALID_RATING"

    def test_rate_source_invalid_negative(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.rate_source(src.id, -0.1)
        assert exc.value.code == "INVALID_RATING"

    def test_rate_source_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.rate_source("src-nope", 3.0)
        assert exc.value.code == "NOT_FOUND"

    # --- delete_installation ---
    def test_delete_installation(self) -> None:
        src = self.engine.publish_source("n", "d", "database")
        inst = self.engine.install_source(src.id, "u", "c")
        assert self.engine.delete_installation(inst.id) is True
        with pytest.raises(AgentMigrationWebhookError):
            self.engine.get_installation(inst.id)
        assert self.engine.delete_installation(inst.id) is False


# ════════════════════ #9 WebhookStorageEngine ════════════════════


class TestWebhookStorageEngine:
    def setup_method(self) -> None:
        self.engine = WebhookStorageEngine()

    # --- store_delivery ---
    def test_store_delivery(self) -> None:
        before = time.time()
        delivery = self.engine.store_delivery(
            webhook_id="wh-1",
            event_type="connection.created",
            payload={"id": 123},
            response_status=200,
            response_body="ok",
            full_response=True,
        )
        after = time.time()
        assert delivery.id.startswith("wh-")
        assert delivery.webhook_id == "wh-1"
        assert delivery.event_type == "connection.created"
        assert delivery.payload == {"id": 123}
        assert delivery.response_status == 200
        assert delivery.response_body == "ok"
        assert delivery.full_response is True
        # delivered_at 与 storage_until 计算
        assert before <= delivery.delivered_at <= after
        expected_until = delivery.delivered_at + 180 * 86400
        assert delivery.storage_until == pytest.approx(expected_until)

    def test_store_delivery_custom_storage_days(self) -> None:
        delivery = self.engine.store_delivery(
            "wh-1", "evt", storage_days=10
        )
        assert delivery.storage_until == pytest.approx(
            delivery.delivered_at + 10 * 86400
        )

    def test_store_delivery_defaults(self) -> None:
        delivery = self.engine.store_delivery("wh-1", "evt")
        assert delivery.payload == {}
        assert delivery.response_status == 0
        assert delivery.response_body == ""
        assert delivery.full_response is False

    # --- get_delivery ---
    def test_get_delivery(self) -> None:
        d = self.engine.store_delivery("wh-1", "evt")
        got = self.engine.get_delivery(d.id)
        assert got.id == d.id
        assert got.webhook_id == "wh-1"

    def test_get_delivery_not_found(self) -> None:
        with pytest.raises(AgentMigrationWebhookError) as exc:
            self.engine.get_delivery("wh-nope")
        assert exc.value.code == "NOT_FOUND"

    # --- list_deliveries ---
    def test_list_deliveries_filters(self) -> None:
        self.engine.store_delivery("wh-1", "connection.created")
        self.engine.store_delivery("wh-1", "connection.updated")
        self.engine.store_delivery("wh-2", "connection.created")
        # 全部（默认 include_expired=False，但都未过期）
        assert len(self.engine.list_deliveries()) == 3
        # 按 webhook_id
        assert len(self.engine.list_deliveries(webhook_id="wh-1")) == 2
        assert len(self.engine.list_deliveries(webhook_id="wh-2")) == 1
        # 按 event_type
        assert (
            len(self.engine.list_deliveries(event_type="connection.created"))
            == 2
        )
        # 组合
        assert (
            len(
                self.engine.list_deliveries(
                    webhook_id="wh-1", event_type="connection.created"
                )
            )
            == 1
        )

    def test_list_deliveries_exclude_expired(self) -> None:
        d1 = self.engine.store_delivery("wh-1", "evt-1")
        d2 = self.engine.store_delivery("wh-1", "evt-2")
        # 直接将 d1 的 storage_until 改为过去
        self.engine._deliveries[d1.id].storage_until = time.time() - 1
        # 默认排除过期
        live = self.engine.list_deliveries()
        assert len(live) == 1
        assert live[0].id == d2.id
        # include_expired=True 包含过期
        all_deliveries = self.engine.list_deliveries(include_expired=True)
        assert len(all_deliveries) == 2
        ids = {d.id for d in all_deliveries}
        assert d1.id in ids and d2.id in ids

    # --- cleanup_expired ---
    def test_cleanup_expired(self) -> None:
        d1 = self.engine.store_delivery("wh-1", "evt-1")
        d2 = self.engine.store_delivery("wh-1", "evt-2")
        d3 = self.engine.store_delivery("wh-1", "evt-3")
        # d1, d2 过期
        self.engine._deliveries[d1.id].storage_until = time.time() - 1
        self.engine._deliveries[d2.id].storage_until = time.time() - 1
        count = self.engine.cleanup_expired()
        assert count == 2
        # 剩余仅 d3
        remaining = self.engine.list_deliveries(include_expired=True)
        assert len(remaining) == 1
        assert remaining[0].id == d3.id
        # 再次清理返回 0
        assert self.engine.cleanup_expired() == 0

    def test_cleanup_expired_boundary(self) -> None:
        # storage_until == now 视为过期 (<=)
        d = self.engine.store_delivery("wh-1", "evt")
        now = time.time()
        self.engine._deliveries[d.id].storage_until = now
        # cleanup 使用 _now_ts()，可能略大于 now，故必然 <=
        assert self.engine.cleanup_expired() == 1

    # --- get_delivery_stats ---
    def test_get_delivery_stats(self) -> None:
        self.engine.store_delivery(
            "wh-1", "evt-1", response_status=200
        )
        self.engine.store_delivery(
            "wh-1", "evt-2", response_status=201
        )
        self.engine.store_delivery(
            "wh-1", "evt-3", response_status=400
        )
        self.engine.store_delivery(
            "wh-1", "evt-4", response_status=404
        )
        self.engine.store_delivery(
            "wh-1", "evt-5", response_status=500
        )
        self.engine.store_delivery(
            "wh-1", "evt-6", response_status=0
        )
        stats = self.engine.get_delivery_stats()
        assert stats["total"] == 6
        assert stats["by_status"]["2xx"] == 2
        assert stats["by_status"]["4xx"] == 2
        assert stats["by_status"]["5xx"] == 1
        assert stats["by_status"]["other"] == 1
        assert stats["expired"] == 0

    def test_get_delivery_stats_with_expired_and_filter(self) -> None:
        d1 = self.engine.store_delivery("wh-1", "evt-1", response_status=200)
        self.engine.store_delivery("wh-2", "evt-2", response_status=200)
        self.engine.store_delivery("wh-1", "evt-3", response_status=500)
        # 让 d1 过期
        self.engine._deliveries[d1.id].storage_until = time.time() - 1
        # 全量统计
        all_stats = self.engine.get_delivery_stats()
        assert all_stats["total"] == 3
        assert all_stats["by_status"]["2xx"] == 2
        assert all_stats["by_status"]["5xx"] == 1
        assert all_stats["expired"] == 1
        # 按 webhook_id 过滤
        wh1_stats = self.engine.get_delivery_stats(webhook_id="wh-1")
        assert wh1_stats["total"] == 2
        assert wh1_stats["by_status"]["2xx"] == 1
        assert wh1_stats["by_status"]["5xx"] == 1
        assert wh1_stats["expired"] == 1

    # --- delete_delivery ---
    def test_delete_delivery(self) -> None:
        d = self.engine.store_delivery("wh-1", "evt")
        assert self.engine.delete_delivery(d.id) is True
        with pytest.raises(AgentMigrationWebhookError):
            self.engine.get_delivery(d.id)
        assert self.engine.delete_delivery(d.id) is False

    # --- FIFO eviction ---
    def test_fifo_eviction(self) -> None:
        max_deliveries = WebhookStorageEngine._MAX_DELIVERIES
        for _ in range(max_deliveries + 50):
            self.engine.store_delivery("wh-1", "evt")
        all_deliveries = self.engine.list_deliveries(include_expired=True)
        assert len(all_deliveries) == max_deliveries


# ════════════════════ 单例 getter ════════════════════


def test_singleton_getters_return_same_instance() -> None:
    assert get_agent_health_monitor_engine() is get_agent_health_monitor_engine()
    assert get_direct_connection_migration_engine() is get_direct_connection_migration_engine()
    assert get_source_marketplace_engine() is get_source_marketplace_engine()
    assert get_webhook_storage_engine() is get_webhook_storage_engine()
