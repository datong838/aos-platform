"""Immutable platform Module templates for the four core workbench apps."""
from __future__ import annotations

import copy
import json
from hashlib import sha256
from typing import Any

_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "templateId": "workshop.order-management",
        "version": "1.0.0",
        "moduleId": "mod-order-management",
        "name": "订单管理",
        "description": "订单、履约、退款与异常处理工作台",
        "module": {
            "objectType": "Order",
            "entryPath": "/workshop/orders",
            "widgets": ["stats", "filters", "table", "details"],
            "buddyBound": True,
            "category": "电商运营",
            "theme": "light",
        },
        "config": {
            "brand": {},
            "pages": ["orders", "order-detail", "fulfillment"],
            "fields": ["orderNo", "status", "amount", "customer", "createdAt"],
            "metrics": ["orderCount", "gmv", "refundRate"],
            "workflows": ["fulfillment", "refund"],
            "agents": ["data-advisor", "customer-service"],
            "permissions": {},
            "dataBindings": {},
        },
    },
    {
        "templateId": "workshop.risk-inbox",
        "version": "1.0.0",
        "moduleId": "mod-ops-inbox",
        "name": "风险告警管理",
        "description": "风险项、工单、处置与审批工作台",
        "module": {
            "objectType": "RiskItem",
            "entryPath": "/workshop/inbox",
            "widgets": ["filters", "table", "timeline", "actions"],
            "buddyBound": True,
            "category": "运营治理",
            "theme": "light",
        },
        "config": {
            "brand": {},
            "pages": ["risk-inbox", "risk-detail"],
            "fields": ["severity", "status", "owner", "deadline"],
            "metrics": ["openRiskCount", "overdueRate"],
            "workflows": ["triage", "escalation", "closure"],
            "agents": ["risk-analyst"],
            "permissions": {},
            "dataBindings": {},
        },
    },
    {
        "templateId": "workshop.cop-dashboard",
        "version": "1.0.0",
        "moduleId": "mod-cop-dashboard",
        "name": "态势大屏",
        "description": "核心经营指标、告警流与区域钻取",
        "module": {
            "objectType": "MetricSnapshot",
            "entryPath": "/workshop/cop",
            "widgets": ["kpi", "map", "trend", "alerts"],
            "buddyBound": False,
            "category": "态势感知",
            "theme": "dark",
        },
        "config": {
            "brand": {},
            "pages": ["command-center"],
            "fields": [],
            "metrics": ["gmv", "orders", "creators", "priceViolations"],
            "workflows": [],
            "agents": ["data-advisor"],
            "permissions": {},
            "dataBindings": {},
        },
    },
    {
        "templateId": "workshop.buddy-assist",
        "version": "1.0.0",
        "moduleId": "mod-buddy-assist",
        "name": "Buddy 智能助手",
        "description": "上下文问答、工具执行与协作建议",
        "module": {
            "objectType": "Conversation",
            "entryPath": "/workshop/buddy",
            "widgets": ["conversation", "context", "actions"],
            "buddyBound": True,
            "category": "智能协作",
            "theme": "light",
        },
        "config": {
            "brand": {},
            "pages": ["assistant"],
            "fields": [],
            "metrics": [],
            "workflows": ["handoff"],
            "agents": ["buddy"],
            "permissions": {},
            "dataBindings": {},
        },
    },
)

ALLOWED_OVERLAY_KEYS = frozenset(
    {
        "brand",
        "pages",
        "fields",
        "metrics",
        "workflows",
        "agents",
        "permissions",
        "dataBindings",
    }
)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{sha256(payload).hexdigest()}"


def list_module_templates() -> list[dict[str, Any]]:
    return [template_view(item) for item in _TEMPLATES]


def get_module_template(template_id: str) -> dict[str, Any] | None:
    for item in _TEMPLATES:
        if item["templateId"] == template_id:
            return copy.deepcopy(item)
    return None


def template_view(template: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(template)
    value["baseContentHash"] = canonical_hash(template)
    return value


def effective_config(template: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(patch) - ALLOWED_OVERLAY_KEYS)
    if unknown:
        raise ValueError(f"unsupported overlay keys: {', '.join(unknown)}")
    effective = copy.deepcopy(template["config"])
    effective.update(copy.deepcopy(patch))
    return effective
