#!/usr/bin/env python3
"""Idempotent seed of approved Agnes models into Phase-2 model_catalog for org-org/dev-project."""
from __future__ import annotations

import json

from aos_api.model_catalog import create_catalog, list_catalog
from aos_api.registered_models import list_registered, register_model
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
MODELS = [
    {
        "id": "mc-agnes-2-5-flash",
        "provider": "agnes",
        "model": "agnes-2.5-flash",
        "displayName": "Agnes 2.5 Flash（文本）",
        "capabilities": ["chat", "function-calling"],
        "contextWindow": 128000,
        "inputPrice": 0,
        "outputPrice": 0,
        "status": "ga",
        "description": "栖月汇正向租户批准文本模型；权威在 AIP-7 Provider/Route",
    },
    {
        "id": "mc-agnes-image-2-1-flash",
        "provider": "agnes",
        "model": "agnes-image-2.1-flash",
        "displayName": "Agnes Image 2.1 Flash",
        "capabilities": ["vision"],
        "contextWindow": 0,
        "inputPrice": 0,
        "outputPrice": 0,
        "status": "ga",
        "description": "栖月汇正向租户批准图像模型",
    },
    {
        "id": "mc-agnes-video-v2",
        "provider": "agnes",
        "model": "agnes-video-v2.0",
        "displayName": "Agnes Video v2.0",
        "capabilities": ["vision"],
        "contextWindow": 0,
        "inputPrice": 0,
        "outputPrice": 0,
        "status": "ga",
        "description": "栖月汇正向租户批准视频模型（Health 外呼可能间歇失败）",
    },
]


def main() -> int:
    for payload in MODELS:
        create_catalog(SCOPE, payload)
        regs = {r.get("modelId") for r in list_registered(SCOPE)}
        if payload["id"] not in regs:
            register_model(
                SCOPE,
                {
                    "modelId": payload["id"],
                    "alias": payload["displayName"],
                    "quota": {},
                    "status": "enabled",
                },
            )
    items = list_catalog(SCOPE)
    regs = list_registered(SCOPE)
    print(
        json.dumps(
            {
                "status": "GREEN",
                "catalog": len(items),
                "registered": len(regs),
                "ids": [i["id"] for i in items],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
