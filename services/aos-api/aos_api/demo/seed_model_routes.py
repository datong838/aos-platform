"""Phase 2 seed · Model Routes — 4 routing rules.

Routes: default / code-gen / vision / fallback.
"""

from __future__ import annotations

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.model_routes import ensure_schema
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.demo.seed_model_routes")

_DEMO_SCOPE = TenantScope("dev-org", "dev-project")

_ROUTES = [
    {
        "id": "mr-default",
        "taskType": "default",
        "primaryModel": "rm-gpt-4o",
        "fallbackModel": "rm-glm-4-plus",
        "outboundPolicy": "deny_public",
        "priority": 100,
        "enabled": True,
    },
    {
        "id": "mr-code-gen",
        "taskType": "code_generation",
        "primaryModel": "rm-claude-3-5-sonnet",
        "fallbackModel": "rm-deepseek-v3",
        "outboundPolicy": "deny_public",
        "priority": 90,
        "enabled": True,
    },
    {
        "id": "mr-vision",
        "taskType": "vision",
        "primaryModel": "rm-gpt-4o",
        "fallbackModel": "rm-claude-3-5-sonnet",
        "outboundPolicy": "approved_allow",
        "priority": 80,
        "enabled": True,
    },
    {
        "id": "mr-fallback",
        "taskType": "fallback",
        "primaryModel": "rm-glm-4-plus",
        "fallbackModel": "",
        "outboundPolicy": "deny_public",
        "priority": 200,
        "enabled": True,
    },
]


def seed_model_routes(scope: TenantScope = _DEMO_SCOPE) -> int:
    """Idempotently seed 4 routing rules. Returns count."""
    ensure_schema()
    with connect(scope) as conn:
        conn.execute(
            "DELETE FROM model_route WHERE org_id=%s AND project_id=%s",
            scope.key,
        )
        for r in _ROUTES:
            conn.execute(
                """
                INSERT INTO model_route (
                    id, task_type, primary_model, fallback_model, outbound_policy,
                    priority, enabled, org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (org_id,project_id,id) DO UPDATE SET
                    task_type=EXCLUDED.task_type, primary_model=EXCLUDED.primary_model,
                    fallback_model=EXCLUDED.fallback_model,
                    outbound_policy=EXCLUDED.outbound_policy,
                    priority=EXCLUDED.priority, enabled=EXCLUDED.enabled, updated_at=NOW()
                """,
                (
                    r["id"],
                    r["taskType"],
                    r["primaryModel"],
                    r["fallbackModel"],
                    r["outboundPolicy"],
                    r["priority"],
                    r["enabled"],
                    *scope.key,
                ),
            )
        conn.commit()
    log.info("seed_model_routes_done count=%s", len(_ROUTES))
    return len(_ROUTES)
