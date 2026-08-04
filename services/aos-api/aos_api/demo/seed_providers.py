"""Phase 2 seed · Providers + Health — 4 providers with latest health snapshot.

Providers: 深度求索 / Azure OpenAI / vLLM 本地 / Anthropic.
Each has a provider row + a latest provider_health row (p50 latency, availability).
"""

from __future__ import annotations

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.model_providers import ensure_schema
from aos_api.tenant_scope import TenantScope

log = get_logger("aos-api.demo.seed_providers")

_DEMO_SCOPE = TenantScope("dev-org", "dev-project")

_PROVIDERS = [
    {
        "id": "prov-deepseek",
        "name": "深度求索",
        "baseUrl": "https://api.deepseek.com/v1",
        "apiKey": "sk-deepseek-demo-1234567890abcdef",
        "status": "normal",
        "p50LatencyMs": 850,
        "availabilityPct": 99.95,
    },
    {
        "id": "prov-azure-openai",
        "name": "Azure OpenAI",
        "baseUrl": "https://aoa-demo.openai.azure.com",
        "apiKey": "azure-demo-key-0987654321fedcba",
        "status": "normal",
        "p50LatencyMs": 720,
        "availabilityPct": 99.98,
    },
    {
        "id": "prov-vllm-local",
        "name": "vLLM 本地",
        "baseUrl": "http://10.0.1.10:8000/v1",
        "apiKey": "vllm-local-no-auth",
        "status": "normal",
        "p50LatencyMs": 180,
        "availabilityPct": 99.99,
    },
    {
        "id": "prov-anthropic",
        "name": "Anthropic",
        "baseUrl": "https://api.anthropic.com/v1",
        "apiKey": "sk-ant-demo-aaaabbbbccccdddd",
        "status": "warming",
        "p50LatencyMs": 1240,
        "availabilityPct": 98.50,
    },
]


def _mask(raw: str) -> str:
    if len(raw) <= 8:
        return "***"
    return raw[:4] + "***" + raw[-4:]


def seed_providers(scope: TenantScope = _DEMO_SCOPE) -> int:
    """Idempotently seed 4 providers + latest health snapshot. Returns count."""
    ensure_schema()
    with connect(scope) as conn:
        # delete health first (FK-like)
        conn.execute(
            "DELETE FROM provider_health WHERE org_id=%s AND project_id=%s",
            scope.key,
        )
        conn.execute(
            "DELETE FROM model_provider WHERE org_id=%s AND project_id=%s",
            scope.key,
        )
        for p in _PROVIDERS:
            conn.execute(
                """
                INSERT INTO model_provider (
                    id, name, base_url, api_key_masked, status, org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (org_id,project_id,id) DO UPDATE SET
                    name=EXCLUDED.name, base_url=EXCLUDED.base_url,
                    api_key_masked=EXCLUDED.api_key_masked, status=EXCLUDED.status,
                    updated_at=NOW()
                """,
                (
                    p["id"],
                    p["name"],
                    p["baseUrl"],
                    _mask(p["apiKey"]),
                    p["status"],
                    *scope.key,
                ),
            )
            conn.execute(
                """
                INSERT INTO provider_health (
                    id, provider_id, p50_latency_ms, availability_pct, org_id, project_id
                ) VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (
                    f"ph-{p['id']}",
                    p["id"],
                    p["p50LatencyMs"],
                    p["availabilityPct"],
                    *scope.key,
                ),
            )
        conn.commit()
    log.info("seed_providers_done count=%s", len(_PROVIDERS))
    return len(_PROVIDERS)
