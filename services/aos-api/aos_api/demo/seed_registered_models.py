"""Phase 2 seed · Registered Models — 4 org-registered models.

Registered: GPT-4o / Claude-3.5-Sonnet / DeepSeek-V3 / GLM-4-Plus.
Each with quota (rpm/tpm) and alias.
"""

from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.registered_models import ensure_schema
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.demo.seed_registered_models")

_DEMO_SCOPE = TenantScope("dev-org", "dev-project")

_REGISTERED = [
    {
        "id": "rm-gpt-4o",
        "modelId": "mc-gpt-4o",
        "alias": "gpt-4o-primary",
        "quota": {"rpm": 600, "tpm": 600000},
        "status": "enabled",
    },
    {
        "id": "rm-claude-3-5-sonnet",
        "modelId": "mc-claude-3-5-sonnet",
        "alias": "claude-sonnet",
        "quota": {"rpm": 300, "tpm": 300000},
        "status": "enabled",
    },
    {
        "id": "rm-deepseek-v3",
        "modelId": "mc-deepseek-v3",
        "alias": "deepseek-v3",
        "quota": {"rpm": 500, "tpm": 500000},
        "status": "enabled",
    },
    {
        "id": "rm-glm-4-plus",
        "modelId": "mc-glm-4-plus",
        "alias": "glm-4-plus",
        "quota": {"rpm": 200, "tpm": 200000},
        "status": "disabled",
    },
]


def seed_registered_models(scope: TenantScope = _DEMO_SCOPE) -> int:
    """Idempotently seed 4 registered models. Returns count."""
    ensure_schema()
    with connect(scope) as conn:
        conn.execute(
            "DELETE FROM registered_models WHERE org_id=%s AND project_id=%s",
            scope.key,
        )
        for r in _REGISTERED:
            conn.execute(
                """
                INSERT INTO registered_models (
                    id, model_id, alias, quota, status, org_id, project_id
                ) VALUES (%s,%s,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (org_id,project_id,id) DO UPDATE SET
                    model_id=EXCLUDED.model_id, alias=EXCLUDED.alias,
                    quota=EXCLUDED.quota, status=EXCLUDED.status, updated_at=NOW()
                """,
                (
                    r["id"],
                    r["modelId"],
                    r["alias"],
                    json.dumps(r["quota"]),
                    r["status"],
                    *scope.key,
                ),
            )
        conn.commit()
    log.info("seed_registered_models_done count=%s", len(_REGISTERED))
    return len(_REGISTERED)
