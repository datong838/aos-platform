#!/usr/bin/env python3
"""Run the approved three single-attempt R2 Provider health probes.

Only metadata is emitted. Prompt, answer, Secret payload and response headers
never leave the restricted probe implementation.
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_contracts import ProviderHealthObservation
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_network_policy_store import AipNetworkPolicyStore
from aos_api.aip_r1_bootstrap_probe import (
    AipR1BootstrapProbe,
    R1BootstrapProbeBlocked,
    R1BootstrapProbeRequest,
)
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
ACTOR = "aip-r2-health-refresh"
APPROVAL_REF = "35-R1-C"
PROVIDER_ID = "agnes-text-qyh-dev"
PROVIDER_REVISION = 7
NETWORK_ID = "network-qyh-text-dev"
NETWORK_REVISION = 3
PROVIDER_MODEL_ID = "agnes-2.5-flash"

_SAFE_PROBES = (
    "请仅回复一个简短的服务可用状态词。",
    "请用一句不含个人信息的中文说明当前服务可用。",
    "请仅回复：健康检查通过。",
)


class HealthRefreshBlocked(RuntimeError):
    def __init__(self, code: str, completed_calls: int) -> None:
        super().__init__(code)
        self.code = code
        self.completed_calls = completed_calls


def exact_ref(asset_type: str, item: Any, id_attr: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=asset_type,
        asset_id=str(getattr(item, id_attr)),
        revision=int(item.revision),
        content_hash=str(item.content_hash),
    )


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "provider": {"assetId": PROVIDER_ID, "revision": PROVIDER_REVISION},
        "networkPolicy": {"assetId": NETWORK_ID, "revision": NETWORK_REVISION},
        "providerModelId": PROVIDER_MODEL_ID,
        "probeCount": 3,
        "maxAttemptsPerProbe": 1,
        "outputPolicy": "metadata-only",
        "forbiddenOutputs": [
            "Secret payload",
            "prompt text",
            "answer text",
            "Provider headers",
            "customer data",
        ],
    }


def refresh(
    *,
    probe: Any | None = None,
    runtime_store: Any | None = None,
    network_store: Any | None = None,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    store = runtime_store or AipModelRuntimeStore()
    networks = network_store or AipNetworkPolicyStore()
    restricted_probe = probe or AipR1BootstrapProbe()
    now = clock or (lambda: datetime.now(UTC))
    provider = store.get_provider(SCOPE, PROVIDER_ID, PROVIDER_REVISION)
    network = networks.get(SCOPE, NETWORK_ID, NETWORK_REVISION)
    provider_ref = exact_ref(
        "ProviderInstanceRevision", provider, "provider_instance_id"
    )
    network_ref = exact_ref("NetworkPolicyRevision", network, "policy_id")
    results = []
    for prompt in _SAFE_PROBES:
        try:
            results.append(
                restricted_probe.run(
                    SCOPE,
                    R1BootstrapProbeRequest(
                        provider=provider_ref,
                        network_policy=network_ref,
                        provider_model_id=PROVIDER_MODEL_ID,
                        data_classification="approved_development_sample",
                        prompt=prompt,
                        expected_response_behavior="non_empty",
                        approval_ref=APPROVAL_REF,
                    ),
                )
            )
        except R1BootstrapProbeBlocked as exc:
            raise HealthRefreshBlocked(exc.code, len(results)) from None
    if len(results) != 3:
        raise HealthRefreshBlocked("health_probe_count_incomplete", len(results))
    observed_at = max(result.observed_at for result in results)
    latencies = sorted(result.latency_ms for result in results)
    observation = ProviderHealthObservation(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        observation_id=(
            f"health-agnes-text-qyh-r2-{observed_at:%Y%m%d%H%M%S%f}"
        ),
        provider=provider_ref,
        status="healthy",
        availability_pct=100,
        p50_latency_ms=latencies[1],
        observed_at=observed_at,
        expires_at=observed_at + timedelta(minutes=15),
    )
    persisted = store.record_health(
        SCOPE,
        ACTOR,
        f"r2-health-{observed_at:%Y%m%d%H%M%S%f}",
        observation,
    )
    return {
        "status": "PROVIDER_HEALTH_REFRESH_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "observationId": persisted.observation_id,
        "observedAt": persisted.observed_at,
        "expiresAt": persisted.expires_at,
        "probeCount": len(results),
        "providerCalls": len(results),
        "p50LatencyMs": persisted.p50_latency_ms,
        "totalTokens": sum(result.total_tokens for result in results),
        "secretPayloadReadsReported": 0,
        "promptOrAnswerBodiesReported": 0,
    }


def main() -> int:
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        result = build_plan()
        exit_code = 0
    else:
        try:
            result = refresh()
            exit_code = 0
        except HealthRefreshBlocked as exc:
            result = {
                **build_plan(),
                "status": "blocked",
                "blockerCode": exc.code,
                "providerCallsCompleted": exc.completed_calls,
                "healthObservationWritten": False,
            }
            exit_code = 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
