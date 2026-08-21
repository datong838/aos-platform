#!/usr/bin/env python3
"""IMG-3: one three-probe Health for agnes-image-qyh-dev (images/generations).

Metadata only. Never prints Secret, prompt, image URL/b64 or Provider headers.
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
ACTOR = "aip-r2-image-health-refresh"
APPROVAL_REF = "35-R1-C"
PROVIDER_ID = "agnes-image-qyh-dev"
NETWORK_ID = "network-qyh-image-dev"
PROVIDER_MODEL_ID = "agnes-image-2.1-flash"

_SAFE_PROBES = (
    "solid pale blue square abstract background",
    "simple geometric circle icon on white",
    "minimal gray gradient field no text",
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


def _head_revision(kind: str, asset_id: str) -> int:
    from aos_api.db import connect as db_connect

    with db_connect(SCOPE) as conn:
        if kind == "provider":
            row = conn.execute(
                "SELECT current_revision FROM aip_provider_instance_head "
                "WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s",
                (*SCOPE.key, asset_id),
            ).fetchone()
        elif kind == "network":
            row = conn.execute(
                "SELECT current_revision FROM aip_network_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_id=%s",
                (*SCOPE.key, asset_id),
            ).fetchone()
        else:
            raise ValueError(kind)
    if row is None:
        raise HealthRefreshBlocked(f"{kind}_authority_missing", 0)
    return int(row["current_revision"])


def build_plan(
    *, provider_revision: int | None = None, network_revision: int | None = None
) -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "provider": {
            "assetId": PROVIDER_ID,
            "revision": provider_revision,
        },
        "networkPolicy": {
            "assetId": NETWORK_ID,
            "revision": network_revision,
        },
        "providerModelId": PROVIDER_MODEL_ID,
        "probeCount": 3,
        "maxAttemptsPerProbe": 1,
        "endpoint": "/v1/images/generations",
        "outputPolicy": "metadata-only",
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
    provider_revision = _head_revision("provider", PROVIDER_ID)
    network_revision = _head_revision("network", NETWORK_ID)
    provider = store.get_provider(SCOPE, PROVIDER_ID, provider_revision)
    network = networks.get(SCOPE, NETWORK_ID, network_revision)
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
            f"health-agnes-image-qyh-r2-{observed_at:%Y%m%d%H%M%S%f}"
        ),
        provider=provider_ref,
        status="healthy",
        availability_pct=100,
        p50_latency_ms=latencies[1],
        observed_at=observed_at,
        expires_at=observed_at + timedelta(minutes=15),
    )
    store.record_health(
        SCOPE,
        ACTOR,
        f"r2-image-health-{observed_at:%Y%m%d%H%M%S%f}",
        observation,
    )
    return {
        **build_plan(
            provider_revision=provider_revision,
            network_revision=network_revision,
        ),
        "status": "PROVIDER_IMAGE_HEALTH_REFRESH_GREEN",
        "observationId": observation.observation_id,
        "p50LatencyMs": observation.p50_latency_ms,
        "probeCount": 3,
        "expiresAt": observation.expires_at,
        "secretPayloadReads": 0,
        "sensitiveBodiesPrinted": 0,
    }


def main() -> int:
    logging.getLogger().setLevel(logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = refresh() if args.apply else build_plan()
    except HealthRefreshBlocked as exc:
        result = {
            **build_plan(),
            "status": "blocked",
            "blockerCode": exc.code,
            "completedCalls": exc.completed_calls,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if result.get("status") in {
        "planned",
        "PROVIDER_IMAGE_HEALTH_REFRESH_GREEN",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
