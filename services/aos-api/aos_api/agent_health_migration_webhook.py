"""W2-BJ · Data Connection Agent 健康/迁移/市场/Webhook 存储（#6 #7 #8 #9）.

- AgentHealthMonitorEngine：#6 Agent 健康监控
- DirectConnectionMigrationEngine：#7 直连迁移向导
- SourceMarketplaceEngine：#8 Source Marketplace
- WebhookStorageEngine：#9 Webhook 投递存储
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ════════════════════ 辅助 ════════════════════


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


# ════════════════════ 错误 ════════════════════


class AgentMigrationWebhookError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def error_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


# ════════════════════ #6 Agent Health Monitor ════════════════════

_VALID_METRICS = {"cpu", "queue", "disk", "memory"}
_VALID_SEVERITIES = {"warning", "critical"}
_VALID_ALERT_STATUSES = {"active", "acknowledged", "resolved"}


class HealthRule(BaseModel):
    id: str
    agent_id: str
    metric_name: str  # cpu/queue/disk/memory
    threshold_warning: float
    threshold_critical: float
    enabled: bool = True
    created_at: float = Field(default_factory=_now_ts)


class HealthAlert(BaseModel):
    id: str = Field(default_factory=lambda: _uid("alert"))
    rule_id: str
    agent_id: str
    metric_name: str
    current_value: float
    threshold: float
    severity: str  # warning/critical
    status: str  # active/acknowledged/resolved
    message: str
    created_at: float = Field(default_factory=_now_ts)
    acknowledged_at: float = 0
    resolved_at: float = 0


class AgentHealthMonitorEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: dict[str, HealthRule] = {}
        self._alerts: dict[str, HealthAlert] = {}

    _MAX_RULES = 200
    _MAX_ALERTS = 200

    def create_rule(
        self,
        agent_id: str,
        metric_name: str,
        threshold_warning: float,
        threshold_critical: float,
    ) -> HealthRule:
        if metric_name not in _VALID_METRICS:
            raise AgentMigrationWebhookError(
                "INVALID_METRIC_NAME",
                f"metric_name must be one of {_VALID_METRICS}",
            )
        if threshold_warning >= threshold_critical:
            raise AgentMigrationWebhookError(
                "INVALID_THRESHOLDS",
                "threshold_warning must be < threshold_critical",
            )
        with self._lock:
            rule = HealthRule(
                id=_uid("rule"),
                agent_id=agent_id,
                metric_name=metric_name,
                threshold_warning=threshold_warning,
                threshold_critical=threshold_critical,
            )
            self._rules[rule.id] = rule
            if len(self._rules) > self._MAX_RULES:
                oldest = min(self._rules.values(), key=lambda r: r.created_at)
                self._rules.pop(oldest.id, None)
            return rule.model_copy(deep=True)

    def get_rule(self, rule_id: str) -> HealthRule:
        with self._lock:
            r = self._rules.get(rule_id)
            if not r:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"rule {rule_id} not found"
                )
            return r.model_copy(deep=True)

    def list_rules(self, agent_id: str | None = None) -> list[HealthRule]:
        with self._lock:
            result = list(self._rules.values())
            if agent_id:
                result = [r for r in result if r.agent_id == agent_id]
            return [r.model_copy(deep=True) for r in result]

    def update_rule(
        self,
        rule_id: str,
        threshold_warning: float | None = None,
        threshold_critical: float | None = None,
        enabled: bool | None = None,
    ) -> HealthRule:
        with self._lock:
            r = self._rules.get(rule_id)
            if not r:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"rule {rule_id} not found"
                )
            new_warning = (
                threshold_warning
                if threshold_warning is not None
                else r.threshold_warning
            )
            new_critical = (
                threshold_critical
                if threshold_critical is not None
                else r.threshold_critical
            )
            if new_warning >= new_critical:
                raise AgentMigrationWebhookError(
                    "INVALID_THRESHOLDS",
                    "threshold_warning must be < threshold_critical",
                )
            r.threshold_warning = new_warning
            r.threshold_critical = new_critical
            if enabled is not None:
                r.enabled = enabled
            return r.model_copy(deep=True)

    def delete_rule(self, rule_id: str) -> bool:
        with self._lock:
            if rule_id in self._rules:
                del self._rules[rule_id]
                return True
            return False

    def evaluate(
        self,
        agent_id: str,
        metric_name: str,
        current_value: float,
    ) -> HealthAlert | None:
        with self._lock:
            rule = next(
                (
                    r
                    for r in self._rules.values()
                    if r.agent_id == agent_id
                    and r.metric_name == metric_name
                    and r.enabled
                ),
                None,
            )
            if not rule:
                return None
            if current_value >= rule.threshold_critical:
                severity = "critical"
                threshold = rule.threshold_critical
            elif current_value >= rule.threshold_warning:
                severity = "warning"
                threshold = rule.threshold_warning
            else:
                return None
            alert = HealthAlert(
                rule_id=rule.id,
                agent_id=agent_id,
                metric_name=metric_name,
                current_value=current_value,
                threshold=threshold,
                severity=severity,
                status="active",
                message=(
                    f"{metric_name}={current_value} exceeded "
                    f"{severity} threshold {threshold}"
                ),
            )
            self._alerts[alert.id] = alert
            if len(self._alerts) > self._MAX_ALERTS:
                oldest = min(self._alerts.values(), key=lambda a: a.created_at)
                self._alerts.pop(oldest.id, None)
            return alert.model_copy(deep=True)

    def get_alert(self, alert_id: str) -> HealthAlert:
        with self._lock:
            a = self._alerts.get(alert_id)
            if not a:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"alert {alert_id} not found"
                )
            return a.model_copy(deep=True)

    def list_alerts(
        self,
        agent_id: str | None = None,
        severity: str | None = None,
        status: str | None = None,
    ) -> list[HealthAlert]:
        with self._lock:
            result = list(self._alerts.values())
            if agent_id:
                result = [a for a in result if a.agent_id == agent_id]
            if severity:
                result = [a for a in result if a.severity == severity]
            if status:
                result = [a for a in result if a.status == status]
            return [a.model_copy(deep=True) for a in result]

    def acknowledge_alert(self, alert_id: str) -> HealthAlert:
        with self._lock:
            a = self._alerts.get(alert_id)
            if not a:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"alert {alert_id} not found"
                )
            a.status = "acknowledged"
            a.acknowledged_at = _now_ts()
            return a.model_copy(deep=True)

    def resolve_alert(self, alert_id: str) -> HealthAlert:
        with self._lock:
            a = self._alerts.get(alert_id)
            if not a:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"alert {alert_id} not found"
                )
            a.status = "resolved"
            a.resolved_at = _now_ts()
            return a.model_copy(deep=True)

    def delete_alert(self, alert_id: str) -> bool:
        with self._lock:
            if alert_id in self._alerts:
                del self._alerts[alert_id]
                return True
            return False


# ════════════════════ #7 Direct Connection Migration ════════════════════

_VALID_PLAN_STATUSES = {"planning", "in_progress", "completed", "rolled_back"}
_VALID_STEP_STATUSES = {"pending", "in_progress", "completed", "skipped"}


class MigrationStep(BaseModel):
    step_num: int
    title: str
    description: str
    status: str  # pending/in_progress/completed/skipped
    completed_at: float = 0


class MigrationPlan(BaseModel):
    id: str = Field(default_factory=lambda: _uid("mig"))
    source_connection_id: str
    target_connection_id: str
    steps: list[MigrationStep] = Field(default_factory=list)
    rollback_window_days: int = 30
    status: str  # planning/in_progress/completed/rolled_back
    created_at: float = Field(default_factory=_now_ts)
    completed_at: float = 0


class DirectConnectionMigrationEngine:
    _DEFAULT_STEPS = [
        ("assess", "评估当前直连配置", "分析现有连接参数与依赖"),
        ("prepare", "准备目标连接", "配置新连接参数并验证连通性"),
        ("migrate", "执行数据迁移", "迁移元数据与历史记录"),
        ("validate", "验证迁移结果", "检查数据完整性与功能一致性"),
        ("cutover", "切换流量", "将流量从旧连接切换到新连接"),
    ]

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._plans: dict[str, MigrationPlan] = {}

    _MAX_PLANS = 200

    def create_plan(
        self,
        source_connection_id: str,
        target_connection_id: str,
        rollback_window_days: int = 30,
    ) -> MigrationPlan:
        with self._lock:
            plan = MigrationPlan(
                source_connection_id=source_connection_id,
                target_connection_id=target_connection_id,
                rollback_window_days=rollback_window_days,
                status="planning",
                steps=[
                    MigrationStep(
                        step_num=i + 1,
                        title=t[1],
                        description=t[2],
                        status="pending",
                    )
                    for i, t in enumerate(self._DEFAULT_STEPS)
                ],
            )
            self._plans[plan.id] = plan
            if len(self._plans) > self._MAX_PLANS:
                oldest = min(self._plans.values(), key=lambda p: p.created_at)
                self._plans.pop(oldest.id, None)
            return plan.model_copy(deep=True)

    def get_plan(self, plan_id: str) -> MigrationPlan:
        with self._lock:
            p = self._plans.get(plan_id)
            if not p:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"plan {plan_id} not found"
                )
            return p.model_copy(deep=True)

    def list_plans(self, status: str | None = None) -> list[MigrationPlan]:
        with self._lock:
            result = list(self._plans.values())
            if status:
                result = [p for p in result if p.status == status]
            return [p.model_copy(deep=True) for p in result]

    def start_plan(self, plan_id: str) -> MigrationPlan:
        with self._lock:
            p = self._plans.get(plan_id)
            if not p:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"plan {plan_id} not found"
                )
            p.status = "in_progress"
            if p.steps:
                p.steps[0].status = "in_progress"
            return p.model_copy(deep=True)

    def complete_step(self, plan_id: str, step_num: int) -> MigrationPlan:
        with self._lock:
            p = self._plans.get(plan_id)
            if not p:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"plan {plan_id} not found"
                )
            step = next(
                (s for s in p.steps if s.step_num == step_num), None
            )
            if not step:
                raise AgentMigrationWebhookError(
                    "INVALID_STEP", f"step {step_num} not found in plan {plan_id}"
                )
            step.status = "completed"
            step.completed_at = _now_ts()
            next_step = next(
                (s for s in p.steps if s.step_num == step_num + 1), None
            )
            if next_step:
                next_step.status = "in_progress"
            else:
                p.status = "completed"
                p.completed_at = _now_ts()
            return p.model_copy(deep=True)

    def skip_step(self, plan_id: str, step_num: int) -> MigrationPlan:
        with self._lock:
            p = self._plans.get(plan_id)
            if not p:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"plan {plan_id} not found"
                )
            step = next(
                (s for s in p.steps if s.step_num == step_num), None
            )
            if not step:
                raise AgentMigrationWebhookError(
                    "INVALID_STEP", f"step {step_num} not found in plan {plan_id}"
                )
            step.status = "skipped"
            next_step = next(
                (s for s in p.steps if s.step_num == step_num + 1), None
            )
            if next_step:
                next_step.status = "in_progress"
            else:
                p.status = "completed"
                p.completed_at = _now_ts()
            return p.model_copy(deep=True)

    def rollback(self, plan_id: str) -> MigrationPlan:
        with self._lock:
            p = self._plans.get(plan_id)
            if not p:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"plan {plan_id} not found"
                )
            baseline = p.completed_at if p.completed_at > 0 else p.created_at
            if _now_ts() - baseline > p.rollback_window_days * 86400:
                raise AgentMigrationWebhookError(
                    "INVALID_ROLLBACK",
                    f"rollback window of {p.rollback_window_days} days has expired",
                )
            p.status = "rolled_back"
            return p.model_copy(deep=True)

    def delete_plan(self, plan_id: str) -> bool:
        with self._lock:
            if plan_id in self._plans:
                del self._plans[plan_id]
                return True
            return False


# ════════════════════ #8 Source Marketplace ════════════════════

_VALID_SOURCE_TYPES = {"database", "api", "file", "stream"}


class MarketplaceSource(BaseModel):
    id: str = Field(default_factory=lambda: _uid("src"))
    name: str
    description: str
    source_type: str  # database/api/file/stream
    connection_config: dict[str, Any] = {}
    provider: str
    version: str = "1.0"
    tags: list[str] = []
    published: bool = False
    rating: float = 0.0
    install_count: int = 0
    created_at: float = Field(default_factory=_now_ts)


class SourceInstallation(BaseModel):
    id: str = Field(default_factory=lambda: _uid("inst"))
    source_id: str
    installed_by: str
    connection_id: str
    installed_at: float = Field(default_factory=_now_ts)


class SourceMarketplaceEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sources: dict[str, MarketplaceSource] = {}
        self._installations: dict[str, SourceInstallation] = {}

    _MAX_SOURCES = 200
    _MAX_INSTALLATIONS = 200

    def publish_source(
        self,
        name: str,
        description: str,
        source_type: str,
        connection_config: dict | None = None,
        provider: str = "",
        tags: list[str] | None = None,
    ) -> MarketplaceSource:
        if source_type not in _VALID_SOURCE_TYPES:
            raise AgentMigrationWebhookError(
                "INVALID_SOURCE_TYPE",
                f"source_type must be one of {_VALID_SOURCE_TYPES}",
            )
        with self._lock:
            src = MarketplaceSource(
                name=name,
                description=description,
                source_type=source_type,
                connection_config=connection_config or {},
                provider=provider,
                tags=tags or [],
                published=True,
            )
            self._sources[src.id] = src
            if len(self._sources) > self._MAX_SOURCES:
                oldest = min(
                    self._sources.values(), key=lambda s: s.created_at
                )
                self._sources.pop(oldest.id, None)
            return src.model_copy(deep=True)

    def get_source(self, source_id: str) -> MarketplaceSource:
        with self._lock:
            s = self._sources.get(source_id)
            if not s:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"source {source_id} not found"
                )
            return s.model_copy(deep=True)

    def list_sources(
        self,
        source_type: str | None = None,
        tag: str | None = None,
        published_only: bool = True,
    ) -> list[MarketplaceSource]:
        with self._lock:
            result = list(self._sources.values())
            if published_only:
                result = [s for s in result if s.published]
            if source_type:
                result = [s for s in result if s.source_type == source_type]
            if tag:
                result = [s for s in result if tag in s.tags]
            return [s.model_copy(deep=True) for s in result]

    def update_source(
        self, source_id: str, updates: dict[str, Any]
    ) -> MarketplaceSource:
        with self._lock:
            s = self._sources.get(source_id)
            if not s:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"source {source_id} not found"
                )
            data = s.model_dump()
            allowed = {
                "name",
                "description",
                "source_type",
                "connection_config",
                "provider",
                "version",
                "tags",
                "published",
            }
            data.update({k: v for k, v in updates.items() if k in allowed})
            if data["source_type"] not in _VALID_SOURCE_TYPES:
                raise AgentMigrationWebhookError(
                    "INVALID_SOURCE_TYPE",
                    f"source_type must be one of {_VALID_SOURCE_TYPES}",
                )
            updated = MarketplaceSource(**data)
            self._sources[source_id] = updated
            return updated.model_copy(deep=True)

    def delete_source(self, source_id: str) -> bool:
        with self._lock:
            if source_id in self._sources:
                del self._sources[source_id]
                return True
            return False

    def install_source(
        self,
        source_id: str,
        installed_by: str,
        connection_id: str,
    ) -> SourceInstallation:
        with self._lock:
            s = self._sources.get(source_id)
            if not s:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"source {source_id} not found"
                )
            s.install_count += 1
            inst = SourceInstallation(
                source_id=source_id,
                installed_by=installed_by,
                connection_id=connection_id,
            )
            self._installations[inst.id] = inst
            if len(self._installations) > self._MAX_INSTALLATIONS:
                oldest = min(
                    self._installations.values(),
                    key=lambda i: i.installed_at,
                )
                self._installations.pop(oldest.id, None)
            return inst.model_copy(deep=True)

    def get_installation(self, installation_id: str) -> SourceInstallation:
        with self._lock:
            inst = self._installations.get(installation_id)
            if not inst:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND",
                    f"installation {installation_id} not found",
                )
            return inst.model_copy(deep=True)

    def list_installations(
        self, source_id: str | None = None
    ) -> list[SourceInstallation]:
        with self._lock:
            result = list(self._installations.values())
            if source_id:
                result = [i for i in result if i.source_id == source_id]
            return [i.model_copy(deep=True) for i in result]

    def rate_source(self, source_id: str, rating: float) -> MarketplaceSource:
        if not (0 <= rating <= 5):
            raise AgentMigrationWebhookError(
                "INVALID_RATING", "rating must be between 0 and 5"
            )
        with self._lock:
            s = self._sources.get(source_id)
            if not s:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"source {source_id} not found"
                )
            if s.rating > 0:
                s.rating = (s.rating + rating) / 2
            else:
                s.rating = rating
            return s.model_copy(deep=True)

    def delete_installation(self, installation_id: str) -> bool:
        with self._lock:
            if installation_id in self._installations:
                del self._installations[installation_id]
                return True
            return False


# ════════════════════ #9 Webhook Storage ════════════════════


class WebhookDelivery(BaseModel):
    id: str = Field(default_factory=lambda: _uid("wh"))
    webhook_id: str
    event_type: str
    payload: dict[str, Any] = {}
    response_status: int = 0
    response_body: str = ""
    delivered_at: float = 0
    storage_until: float = 0
    created_at: float = Field(default_factory=_now_ts)
    full_response: bool = False


class WebhookStorageEngine:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._deliveries: dict[str, WebhookDelivery] = {}

    _MAX_DELIVERIES = 200
    _DEFAULT_STORAGE_DAYS = 180  # 6 months

    def store_delivery(
        self,
        webhook_id: str,
        event_type: str,
        payload: dict | None = None,
        response_status: int = 0,
        response_body: str = "",
        full_response: bool = False,
        storage_days: int | None = None,
    ) -> WebhookDelivery:
        with self._lock:
            now = _now_ts()
            days = (
                storage_days
                if storage_days is not None
                else self._DEFAULT_STORAGE_DAYS
            )
            delivery = WebhookDelivery(
                webhook_id=webhook_id,
                event_type=event_type,
                payload=payload or {},
                response_status=response_status,
                response_body=response_body,
                delivered_at=now,
                storage_until=now + days * 86400,
                full_response=full_response,
            )
            self._deliveries[delivery.id] = delivery
            if len(self._deliveries) > self._MAX_DELIVERIES:
                oldest = min(
                    self._deliveries.values(),
                    key=lambda d: d.created_at,
                )
                self._deliveries.pop(oldest.id, None)
            return delivery.model_copy(deep=True)

    def get_delivery(self, delivery_id: str) -> WebhookDelivery:
        with self._lock:
            d = self._deliveries.get(delivery_id)
            if not d:
                raise AgentMigrationWebhookError(
                    "NOT_FOUND", f"delivery {delivery_id} not found"
                )
            return d.model_copy(deep=True)

    def list_deliveries(
        self,
        webhook_id: str | None = None,
        event_type: str | None = None,
        include_expired: bool = False,
    ) -> list[WebhookDelivery]:
        with self._lock:
            now = _now_ts()
            result = list(self._deliveries.values())
            if webhook_id:
                result = [d for d in result if d.webhook_id == webhook_id]
            if event_type:
                result = [d for d in result if d.event_type == event_type]
            if not include_expired:
                result = [d for d in result if d.storage_until > now]
            return [d.model_copy(deep=True) for d in result]

    def cleanup_expired(self) -> int:
        with self._lock:
            now = _now_ts()
            expired_ids = [
                did
                for did, d in self._deliveries.items()
                if d.storage_until <= now
            ]
            for did in expired_ids:
                del self._deliveries[did]
            return len(expired_ids)

    def get_delivery_stats(
        self, webhook_id: str | None = None
    ) -> dict[str, Any]:
        with self._lock:
            now = _now_ts()
            deliveries = list(self._deliveries.values())
            if webhook_id:
                deliveries = [
                    d for d in deliveries if d.webhook_id == webhook_id
                ]
            by_status: dict[str, int] = {
                "2xx": 0,
                "4xx": 0,
                "5xx": 0,
                "other": 0,
            }
            expired = 0
            for d in deliveries:
                code = d.response_status
                if 200 <= code < 300:
                    by_status["2xx"] += 1
                elif 400 <= code < 500:
                    by_status["4xx"] += 1
                elif 500 <= code < 600:
                    by_status["5xx"] += 1
                else:
                    by_status["other"] += 1
                if d.storage_until <= now:
                    expired += 1
            return {
                "total": len(deliveries),
                "by_status": by_status,
                "expired": expired,
            }

    def delete_delivery(self, delivery_id: str) -> bool:
        with self._lock:
            if delivery_id in self._deliveries:
                del self._deliveries[delivery_id]
                return True
            return False


# ════════════════════ 单例 getter ════════════════════

_lock = threading.Lock()
_health_engine: AgentHealthMonitorEngine | None = None
_migration_engine: DirectConnectionMigrationEngine | None = None
_marketplace_engine: SourceMarketplaceEngine | None = None
_webhook_storage_engine: WebhookStorageEngine | None = None


def get_agent_health_monitor_engine() -> AgentHealthMonitorEngine:
    global _health_engine
    if _health_engine is None:
        with _lock:
            if _health_engine is None:
                _health_engine = AgentHealthMonitorEngine()
    return _health_engine


def get_direct_connection_migration_engine() -> DirectConnectionMigrationEngine:
    global _migration_engine
    if _migration_engine is None:
        with _lock:
            if _migration_engine is None:
                _migration_engine = DirectConnectionMigrationEngine()
    return _migration_engine


def get_source_marketplace_engine() -> SourceMarketplaceEngine:
    global _marketplace_engine
    if _marketplace_engine is None:
        with _lock:
            if _marketplace_engine is None:
                _marketplace_engine = SourceMarketplaceEngine()
    return _marketplace_engine


def get_webhook_storage_engine() -> WebhookStorageEngine:
    global _webhook_storage_engine
    if _webhook_storage_engine is None:
        with _lock:
            if _webhook_storage_engine is None:
                _webhook_storage_engine = WebhookStorageEngine()
    return _webhook_storage_engine
