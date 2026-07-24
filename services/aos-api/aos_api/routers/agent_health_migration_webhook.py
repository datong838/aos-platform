"""W2-BJ · Data Connection Agent 健康/迁移/市场/Webhook 路由（#6 #7 #8 #9）."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from aos_api.agent_health_migration_webhook import (
    AgentMigrationWebhookError,
    HealthAlert,
    HealthRule,
    MigrationPlan,
    MigrationStep,
    MarketplaceSource,
    SourceInstallation,
    WebhookDelivery,
    get_agent_health_monitor_engine,
    get_direct_connection_migration_engine,
    get_source_marketplace_engine,
    get_webhook_storage_engine,
)
from aos_api.auth import require_principal

router = APIRouter(
    prefix="/agent-health-migration-webhook",
    tags=["agent-health-migration-webhook"],
)


# ════════════════════ 错误映射 ════════════════════


def _map_err(err: AgentMigrationWebhookError) -> HTTPException:
    code = err.code
    if code == "NOT_FOUND":
        status = 404
    elif code.startswith("INVALID_"):
        status = 400
    else:
        status = 500
    payload = (
        err.error_payload()
        if hasattr(err, "error_payload")
        else {"code": err.code, "message": err.message}
    )
    return HTTPException(status_code=status, detail=payload)


# ════════════════════ 请求体模型 ════════════════════


class CreateRuleRequest(BaseModel):
    agent_id: str
    metric_name: str
    threshold_warning: float
    threshold_critical: float


class UpdateRuleRequest(BaseModel):
    threshold_warning: float | None = None
    threshold_critical: float | None = None
    enabled: bool | None = None


class EvaluateRequest(BaseModel):
    agent_id: str
    metric_name: str
    current_value: float


class CreatePlanRequest(BaseModel):
    source_connection_id: str
    target_connection_id: str
    rollback_window_days: int = 30


class PublishSourceRequest(BaseModel):
    name: str
    description: str
    source_type: str
    connection_config: dict[str, Any] | None = None
    provider: str = ""
    tags: list[str] | None = None


class InstallSourceRequest(BaseModel):
    installed_by: str
    connection_id: str


class RateSourceRequest(BaseModel):
    rating: float


class StoreDeliveryRequest(BaseModel):
    webhook_id: str
    event_type: str
    payload: dict[str, Any] | None = None
    response_status: int = 0
    response_body: str = ""
    full_response: bool = False
    storage_days: int | None = None


# ════════════════════ #6 Health Monitor ════════════════════


@router.post("/health/rules", response_model=HealthRule)
def create_health_rule(body: CreateRuleRequest, _=require_principal):
    try:
        return get_agent_health_monitor_engine().create_rule(
            agent_id=body.agent_id,
            metric_name=body.metric_name,
            threshold_warning=body.threshold_warning,
            threshold_critical=body.threshold_critical,
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get("/health/rules/{rule_id}", response_model=HealthRule)
def get_health_rule(rule_id: str, _=require_principal):
    try:
        return get_agent_health_monitor_engine().get_rule(rule_id)
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get("/health/rules", response_model=list[HealthRule])
def list_health_rules(
    agent_id: str | None = None,
    _=require_principal,
):
    return get_agent_health_monitor_engine().list_rules(agent_id=agent_id)


@router.put("/health/rules/{rule_id}", response_model=HealthRule)
def update_health_rule(
    rule_id: str, body: UpdateRuleRequest, _=require_principal
):
    try:
        return get_agent_health_monitor_engine().update_rule(
            rule_id,
            threshold_warning=body.threshold_warning,
            threshold_critical=body.threshold_critical,
            enabled=body.enabled,
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.delete("/health/rules/{rule_id}")
def delete_health_rule(rule_id: str, _=require_principal):
    return {
        "deleted": get_agent_health_monitor_engine().delete_rule(rule_id)
    }


@router.post("/health/evaluate", response_model=Optional[HealthAlert])
def evaluate_health(body: EvaluateRequest, _=require_principal):
    try:
        return get_agent_health_monitor_engine().evaluate(
            agent_id=body.agent_id,
            metric_name=body.metric_name,
            current_value=body.current_value,
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get("/health/alerts/{alert_id}", response_model=HealthAlert)
def get_health_alert(alert_id: str, _=require_principal):
    try:
        return get_agent_health_monitor_engine().get_alert(alert_id)
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get("/health/alerts", response_model=list[HealthAlert])
def list_health_alerts(
    agent_id: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    _=require_principal,
):
    return get_agent_health_monitor_engine().list_alerts(
        agent_id=agent_id, severity=severity, status=status
    )


@router.post("/health/alerts/{alert_id}/acknowledge", response_model=HealthAlert)
def acknowledge_health_alert(alert_id: str, _=require_principal):
    try:
        return get_agent_health_monitor_engine().acknowledge_alert(alert_id)
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.post("/health/alerts/{alert_id}/resolve", response_model=HealthAlert)
def resolve_health_alert(alert_id: str, _=require_principal):
    try:
        return get_agent_health_monitor_engine().resolve_alert(alert_id)
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.delete("/health/alerts/{alert_id}")
def delete_health_alert(alert_id: str, _=require_principal):
    return {
        "deleted": get_agent_health_monitor_engine().delete_alert(alert_id)
    }


# ════════════════════ #7 Migration ════════════════════


@router.post("/migration/plans", response_model=MigrationPlan)
def create_migration_plan(body: CreatePlanRequest, _=require_principal):
    try:
        return get_direct_connection_migration_engine().create_plan(
            source_connection_id=body.source_connection_id,
            target_connection_id=body.target_connection_id,
            rollback_window_days=body.rollback_window_days,
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get("/migration/plans/{plan_id}", response_model=MigrationPlan)
def get_migration_plan(plan_id: str, _=require_principal):
    try:
        return get_direct_connection_migration_engine().get_plan(plan_id)
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get("/migration/plans", response_model=list[MigrationPlan])
def list_migration_plans(
    status: str | None = None,
    _=require_principal,
):
    return get_direct_connection_migration_engine().list_plans(status=status)


@router.post("/migration/plans/{plan_id}/start", response_model=MigrationPlan)
def start_migration_plan(plan_id: str, _=require_principal):
    try:
        return get_direct_connection_migration_engine().start_plan(plan_id)
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.post(
    "/migration/plans/{plan_id}/steps/{step_num}/complete",
    response_model=MigrationPlan,
)
def complete_migration_step(
    plan_id: str, step_num: int, _=require_principal
):
    try:
        return get_direct_connection_migration_engine().complete_step(
            plan_id, step_num
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.post(
    "/migration/plans/{plan_id}/steps/{step_num}/skip",
    response_model=MigrationPlan,
)
def skip_migration_step(plan_id: str, step_num: int, _=require_principal):
    try:
        return get_direct_connection_migration_engine().skip_step(
            plan_id, step_num
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.post(
    "/migration/plans/{plan_id}/rollback", response_model=MigrationPlan
)
def rollback_migration_plan(plan_id: str, _=require_principal):
    try:
        return get_direct_connection_migration_engine().rollback(plan_id)
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.delete("/migration/plans/{plan_id}")
def delete_migration_plan(plan_id: str, _=require_principal):
    return {
        "deleted": get_direct_connection_migration_engine().delete_plan(
            plan_id
        )
    }


# ════════════════════ #8 Marketplace ════════════════════


@router.post("/marketplace/sources", response_model=MarketplaceSource)
def publish_marketplace_source(
    body: PublishSourceRequest, _=require_principal
):
    try:
        return get_source_marketplace_engine().publish_source(
            name=body.name,
            description=body.description,
            source_type=body.source_type,
            connection_config=body.connection_config,
            provider=body.provider,
            tags=body.tags,
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get(
    "/marketplace/sources/{source_id}", response_model=MarketplaceSource
)
def get_marketplace_source(source_id: str, _=require_principal):
    try:
        return get_source_marketplace_engine().get_source(source_id)
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get(
    "/marketplace/sources", response_model=list[MarketplaceSource]
)
def list_marketplace_sources(
    source_type: str | None = None,
    tag: str | None = None,
    published_only: bool = True,
    _=require_principal,
):
    return get_source_marketplace_engine().list_sources(
        source_type=source_type,
        tag=tag,
        published_only=published_only,
    )


@router.put(
    "/marketplace/sources/{source_id}", response_model=MarketplaceSource
)
def update_marketplace_source(
    source_id: str, updates: dict[str, Any], _=require_principal
):
    try:
        return get_source_marketplace_engine().update_source(
            source_id, updates
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.delete("/marketplace/sources/{source_id}")
def delete_marketplace_source(source_id: str, _=require_principal):
    return {
        "deleted": get_source_marketplace_engine().delete_source(source_id)
    }


@router.post(
    "/marketplace/sources/{source_id}/install",
    response_model=SourceInstallation,
)
def install_marketplace_source(
    source_id: str, body: InstallSourceRequest, _=require_principal
):
    try:
        return get_source_marketplace_engine().install_source(
            source_id=source_id,
            installed_by=body.installed_by,
            connection_id=body.connection_id,
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get(
    "/marketplace/installations/{installation_id}",
    response_model=SourceInstallation,
)
def get_marketplace_installation(
    installation_id: str, _=require_principal
):
    try:
        return get_source_marketplace_engine().get_installation(
            installation_id
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get(
    "/marketplace/installations", response_model=list[SourceInstallation]
)
def list_marketplace_installations(
    source_id: str | None = None,
    _=require_principal,
):
    return get_source_marketplace_engine().list_installations(
        source_id=source_id
    )


@router.post(
    "/marketplace/sources/{source_id}/rate",
    response_model=MarketplaceSource,
)
def rate_marketplace_source(
    source_id: str, body: RateSourceRequest, _=require_principal
):
    try:
        return get_source_marketplace_engine().rate_source(
            source_id, body.rating
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.delete("/marketplace/installations/{installation_id}")
def delete_marketplace_installation(
    installation_id: str, _=require_principal
):
    return {
        "deleted": get_source_marketplace_engine().delete_installation(
            installation_id
        )
    }


# ════════════════════ #9 Webhook Storage ════════════════════


@router.post(
    "/webhooks/deliveries", response_model=WebhookDelivery
)
def store_webhook_delivery(
    body: StoreDeliveryRequest, _=require_principal
):
    try:
        return get_webhook_storage_engine().store_delivery(
            webhook_id=body.webhook_id,
            event_type=body.event_type,
            payload=body.payload,
            response_status=body.response_status,
            response_body=body.response_body,
            full_response=body.full_response,
            storage_days=body.storage_days,
        )
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get(
    "/webhooks/deliveries/{delivery_id}", response_model=WebhookDelivery
)
def get_webhook_delivery(delivery_id: str, _=require_principal):
    try:
        return get_webhook_storage_engine().get_delivery(delivery_id)
    except AgentMigrationWebhookError as e:
        raise _map_err(e) from e


@router.get(
    "/webhooks/deliveries", response_model=list[WebhookDelivery]
)
def list_webhook_deliveries(
    webhook_id: str | None = None,
    event_type: str | None = None,
    include_expired: bool = False,
    _=require_principal,
):
    return get_webhook_storage_engine().list_deliveries(
        webhook_id=webhook_id,
        event_type=event_type,
        include_expired=include_expired,
    )


@router.post("/webhooks/cleanup-expired")
def cleanup_expired_webhooks(_=require_principal):
    removed = get_webhook_storage_engine().cleanup_expired()
    return {"removed": removed}


@router.get("/webhooks/stats")
def get_webhook_stats(
    webhook_id: str | None = None,
    _=require_principal,
):
    return get_webhook_storage_engine().get_delivery_stats(
        webhook_id=webhook_id
    )


@router.delete("/webhooks/deliveries/{delivery_id}")
def delete_webhook_delivery(delivery_id: str, _=require_principal):
    return {
        "deleted": get_webhook_storage_engine().delete_delivery(
            delivery_id
        )
    }
