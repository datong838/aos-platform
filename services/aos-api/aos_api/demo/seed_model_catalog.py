"""Phase 2 seed · Model Catalog — 12 discoverable models.

Idempotent: delete by org_id then insert.
"""

from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.model_catalog import ensure_schema
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.demo.seed_model_catalog")

_DEMO_SCOPE = TenantScope("dev-org", "dev-project")

# 12 models: GPT-4o/GPT-4o-mini/Claude-3.5-Sonnet/Claude-3-Haiku/
# DeepSeek-V3/DeepSeek-R1/Llama-3.1-70B/Llama-3.1-8B/Qwen-2.5-72B/
# GLM-4-Plus/GLM-4-Flash/paLM-2
_CATALOG = [
    {
        "id": "mc-gpt-4o",
        "provider": "azure-openai",
        "model": "gpt-4o",
        "displayName": "GPT-4o",
        "capabilities": ["text", "vision", "function_calling"],
        "contextWindow": 128000,
        "inputPrice": 0.005,
        "outputPrice": 0.015,
        "status": "ga",
        "description": "OpenAI flagship multimodal model",
    },
    {
        "id": "mc-gpt-4o-mini",
        "provider": "azure-openai",
        "model": "gpt-4o-mini",
        "displayName": "GPT-4o mini",
        "capabilities": ["text", "function_calling"],
        "contextWindow": 128000,
        "inputPrice": 0.00015,
        "outputPrice": 0.0006,
        "status": "ga",
        "description": "Lightweight GPT-4o variant",
    },
    {
        "id": "mc-claude-3-5-sonnet",
        "provider": "anthropic",
        "model": "claude-3-5-sonnet",
        "displayName": "Claude 3.5 Sonnet",
        "capabilities": ["text", "vision", "code", "function_calling"],
        "contextWindow": 200000,
        "inputPrice": 0.003,
        "outputPrice": 0.015,
        "status": "ga",
        "description": "Anthropic balanced flagship",
    },
    {
        "id": "mc-claude-3-haiku",
        "provider": "anthropic",
        "model": "claude-3-haiku",
        "displayName": "Claude 3 Haiku",
        "capabilities": ["text"],
        "contextWindow": 200000,
        "inputPrice": 0.00025,
        "outputPrice": 0.00125,
        "status": "ga",
        "description": "Fast Anthropic model",
    },
    {
        "id": "mc-deepseek-v3",
        "provider": "deepseek",
        "model": "deepseek-v3",
        "displayName": "DeepSeek-V3",
        "capabilities": ["text", "code", "function_calling"],
        "contextWindow": 64000,
        "inputPrice": 0.00027,
        "outputPrice": 0.0011,
        "status": "ga",
        "description": "DeepSeek V3 MoE",
    },
    {
        "id": "mc-deepseek-r1",
        "provider": "deepseek",
        "model": "deepseek-r1",
        "displayName": "DeepSeek-R1",
        "capabilities": ["text", "code"],
        "contextWindow": 64000,
        "inputPrice": 0.00055,
        "outputPrice": 0.0022,
        "status": "preview",
        "description": "Reasoning-tuned DeepSeek",
    },
    {
        "id": "mc-llama-3-1-70b",
        "provider": "vllm-local",
        "model": "llama-3.1-70b",
        "displayName": "Llama 3.1 70B",
        "capabilities": ["text", "code"],
        "contextWindow": 128000,
        "inputPrice": 0.0009,
        "outputPrice": 0.0009,
        "status": "ga",
        "description": "Self-hosted Llama 3.1",
    },
    {
        "id": "mc-llama-3-1-8b",
        "provider": "vllm-local",
        "model": "llama-3.1-8b",
        "displayName": "Llama 3.1 8B",
        "capabilities": ["text"],
        "contextWindow": 128000,
        "inputPrice": 0.0001,
        "outputPrice": 0.0001,
        "status": "ga",
        "description": "Self-hosted Llama 3.1 small",
    },
    {
        "id": "mc-qwen-2-5-72b",
        "provider": "vllm-local",
        "model": "qwen-2.5-72b",
        "displayName": "Qwen 2.5 72B",
        "capabilities": ["text", "code"],
        "contextWindow": 32000,
        "inputPrice": 0.0008,
        "outputPrice": 0.0008,
        "status": "preview",
        "description": "Self-hosted Qwen 2.5",
    },
    {
        "id": "mc-glm-4-plus",
        "provider": "zhipu",
        "model": "glm-4-plus",
        "displayName": "GLM-4-Plus",
        "capabilities": ["text", "code", "function_calling"],
        "contextWindow": 128000,
        "inputPrice": 0.0028,
        "outputPrice": 0.0028,
        "status": "ga",
        "description": "智谱 GLM-4 Plus",
    },
    {
        "id": "mc-glm-4-flash",
        "provider": "zhipu",
        "model": "glm-4-flash",
        "displayName": "GLM-4-Flash",
        "capabilities": ["text"],
        "contextWindow": 128000,
        "inputPrice": 0.0001,
        "outputPrice": 0.0001,
        "status": "ga",
        "description": "智谱 GLM-4 Flash 免费",
    },
    {
        "id": "mc-palm-2",
        "provider": "google",
        "model": "palm-2",
        "displayName": "PaLM 2",
        "capabilities": ["text"],
        "contextWindow": 8000,
        "inputPrice": 0.001,
        "outputPrice": 0.002,
        "status": "deprecated",
        "description": "Legacy Google PaLM 2",
    },
]


def seed_model_catalog(scope: TenantScope = _DEMO_SCOPE) -> int:
    """Idempotently seed 12 model catalog entries. Returns count."""
    ensure_schema()
    with connect(scope) as conn:
        conn.execute(
            "DELETE FROM model_catalog WHERE org_id=%s AND project_id=%s",
            scope.key,
        )
        for c in _CATALOG:
            conn.execute(
                """
                INSERT INTO model_catalog (
                    id, provider, model, display_name, capabilities,
                    context_window, input_price, output_price, status, description,
                    org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (org_id,project_id,id) DO UPDATE SET
                    provider=EXCLUDED.provider, model=EXCLUDED.model,
                    display_name=EXCLUDED.display_name, capabilities=EXCLUDED.capabilities,
                    context_window=EXCLUDED.context_window, input_price=EXCLUDED.input_price,
                    output_price=EXCLUDED.output_price, status=EXCLUDED.status,
                    description=EXCLUDED.description, updated_at=NOW()
                """,
                (
                    c["id"],
                    c["provider"],
                    c["model"],
                    c["displayName"],
                    json.dumps(c["capabilities"]),
                    c["contextWindow"],
                    c["inputPrice"],
                    c["outputPrice"],
                    c["status"],
                    c["description"],
                    *scope.key,
                ),
            )
        conn.commit()
    log.info("seed_model_catalog_done count=%s", len(_CATALOG))
    return len(_CATALOG)
