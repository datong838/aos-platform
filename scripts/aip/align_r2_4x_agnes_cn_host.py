#!/usr/bin/env python3
"""Align Agnes Text authority to domestic api.agnes-ai.cn.

Default is inspect/dry-run. --apply publishes the next additive revisions:
  Egress + Network + Provider with baseUrl https://api.agnes-ai.cn/v1
Never starts AgentRun. Never probes Provider health.

Note: apihub.agnes-ai.cn was a mistaken host used in an earlier attempt and
remains only as a historical allowlisted hostname for old revisions.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "aos-api"))

from aos_api.aip_agent_registry_contracts import VersionedAssetRef  # noqa: E402
from aos_api.aip_model_runtime_contracts import ProviderInstanceRevision  # noqa: E402
from aos_api.aip_model_runtime_store import (  # noqa: E402
    AipModelRuntimeStore,
    canonical_hash,
)
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate  # noqa: E402
from aos_api.aip_network_policy_store import AipNetworkPolicyStore  # noqa: E402
from aos_api.aip_runtime_guard_policy_contracts import (  # noqa: E402
    EgressPolicyRevisionCreate,
    GuardPolicyLifecycle,
    RegionState,
)
from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore  # noqa: E402
from aos_api.db import connect as db_connect  # noqa: E402
from aos_api.tenant_scope import TenantScope  # noqa: E402

SCOPE = TenantScope("org-org", "dev-project")
ACTOR = "aip-r2-4x-agnes-cn-align"
APPROVAL_REF = "AIP-WKS-DEP-0B-R2-4X-AGNES-CN"
PROVIDER_ID = "agnes-text-qyh-dev"
EGRESS_ID = "agnes-text-qyh-dev-egress"
NETWORK_ID = "network-qyh-text-dev"
CN_HOST = "api.agnes-ai.cn"
CN_BASE_URL = f"https://{CN_HOST}/v1"
CN_REGION = "China (Domestic)"
META_FIELDS = {"tenant", "revision", "contentHash", "createdBy", "createdAt"}


def head_row(kind: str, asset_id: str) -> dict[str, Any]:
    with db_connect() as conn:
        if kind == "egress":
            row = conn.execute(
                "SELECT current_revision, version FROM aip_runtime_guard_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_kind=%s AND policy_id=%s",
                (*SCOPE.key, "egress", asset_id),
            ).fetchone()
        elif kind == "network":
            row = conn.execute(
                "SELECT current_revision, version FROM aip_network_policy_head "
                "WHERE org_id=%s AND project_id=%s AND policy_id=%s",
                (*SCOPE.key, asset_id),
            ).fetchone()
        elif kind == "provider":
            row = conn.execute(
                "SELECT current_revision, version FROM aip_provider_instance_head "
                "WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s",
                (*SCOPE.key, asset_id),
            ).fetchone()
        else:
            raise ValueError(kind)
    if not row:
        raise RuntimeError(f"missing head for {kind}:{asset_id}")
    return {"revision": int(row["current_revision"]), "version": int(row["version"])}


def exact_ref(asset_type: str, item: Any, id_attr: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=asset_type,
        asset_id=str(getattr(item, id_attr)),
        revision=int(item.revision),
        content_hash=str(item.content_hash),
    )


def rehash_runtime(model: type, payload: dict[str, Any]):
    provisional = model.model_validate({**payload, "contentHash": "0" * 64})
    dumped = provisional.model_dump(mode="json", by_alias=True)
    content = {name: value for name, value in dumped.items() if name not in META_FIELDS}
    return model.model_validate({**payload, "contentHash": canonical_hash(content)})


def inspect() -> dict[str, Any]:
    runtime = AipModelRuntimeStore()
    guards = AipRuntimeGuardPolicyStore()
    networks = AipNetworkPolicyStore()
    egress_head = head_row("egress", EGRESS_ID)
    network_head = head_row("network", NETWORK_ID)
    provider_head = head_row("provider", PROVIDER_ID)
    egress = guards.get_egress(SCOPE, EGRESS_ID, egress_head["revision"])
    network = networks.get(SCOPE, NETWORK_ID, network_head["revision"])
    provider = runtime.get_provider(SCOPE, PROVIDER_ID, provider_head["revision"])
    already = (
        list(egress.allowed_hosts) == [CN_HOST]
        and list(network.allowed_hosts) == [CN_HOST]
        and str(provider.endpoint_profile.base_url).rstrip("/") == CN_BASE_URL.rstrip("/")
    )
    return {
        "status": "already_aligned" if already else "ready",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "target": {
            "host": CN_HOST,
            "baseUrl": CN_BASE_URL,
            "region": CN_REGION,
            "egressRevision": egress_head["revision"] + (0 if already else 1),
            "networkRevision": network_head["revision"] + (0 if already else 1),
            "providerRevision": provider_head["revision"] + (0 if already else 1),
        },
        "egressHead": {
            **egress_head,
            "allowedHosts": list(egress.allowed_hosts),
            "region": egress.region,
        },
        "networkHead": {
            **network_head,
            "allowedHosts": list(network.allowed_hosts),
        },
        "providerHead": {
            **provider_head,
            "baseUrl": provider.endpoint_profile.base_url,
            "region": provider.endpoint_profile.region,
        },
        "providerBusinessCalls": 0,
        "healthProbes": 0,
    }


def apply() -> dict[str, Any]:
    snapshot = inspect()
    if snapshot["status"] == "already_aligned":
        return {**snapshot, "status": "R2_4X_AGNES_CN_HOST_ALIGN_GREEN"}
    if snapshot["status"] != "ready":
        raise RuntimeError("R2-4X align blocked")
    now = datetime.now(UTC)
    guards = AipRuntimeGuardPolicyStore()
    networks = AipNetworkPolicyStore()
    runtime = AipModelRuntimeStore()

    egress_cur = guards.get_egress(SCOPE, EGRESS_ID, snapshot["egressHead"]["revision"])
    next_egress = snapshot["egressHead"]["revision"] + 1
    egress = guards.publish_egress(
        SCOPE,
        ACTOR,
        f"r2-4x-egress-agnes-text-qyh-dev-api-cn-r{next_egress}",
        EgressPolicyRevisionCreate(
            policyId=EGRESS_ID,
            revision=next_egress,
            environment="development",
            effectiveFrom=egress_cur.effective_from,
            effectiveUntil=egress_cur.effective_until,
            owner=egress_cur.owner,
            approvalRef=APPROVAL_REF,
            lifecycle=GuardPolicyLifecycle.ACTIVE,
            allowedSchemes=["https"],
            allowedHosts=[CN_HOST],
            allowedPorts=[443],
            allowPublicFallback=False,
            unknownDestinationBehavior="block",
            regionState=RegionState.CONFIRMED,
            region=CN_REGION,
        ),
        expected_version=snapshot["egressHead"]["version"],
    )

    next_network = snapshot["networkHead"]["revision"] + 1
    network = networks.publish(
        SCOPE,
        ACTOR,
        f"r2-4x-network-qyh-text-dev-api-cn-r{next_network}",
        NetworkPolicyRevisionCreate(
            policyId=NETWORK_ID,
            revision=next_network,
            allowedSchemes=["https"],
            allowedHosts=[CN_HOST],
            allowedPorts=[443],
            tlsRequired=True,
            publicFallbackAllowed=False,
            egressPolicyRef=exact_ref("EgressPolicyRevision", egress, "policy_id"),
            effectiveFrom=egress.effective_from,
            effectiveUntil=egress.effective_until,
            owner=egress.owner,
            approvalRef=APPROVAL_REF,
            lifecycle=GuardPolicyLifecycle.ACTIVE,
        ),
        expected_version=snapshot["networkHead"]["version"],
    )

    provider_cur = runtime.get_provider(
        SCOPE, PROVIDER_ID, snapshot["providerHead"]["revision"]
    )
    next_provider = snapshot["providerHead"]["revision"] + 1
    provider_payload = provider_cur.model_dump(mode="json", by_alias=True)
    endpoint = dict(provider_payload["endpointProfile"])
    endpoint.update(baseUrl=CN_BASE_URL, region=CN_REGION)
    provider_payload.update(
        revision=next_provider,
        endpointProfile=endpoint,
        egressPolicyRef=exact_ref("EgressPolicyRevision", egress, "policy_id").model_dump(
            mode="json", by_alias=True
        ),
        createdBy=ACTOR,
        createdAt=now,
    )
    provider_payload.pop("contentHash", None)
    provider = runtime.publish_provider(
        SCOPE,
        ACTOR,
        f"r2-4x-provider-agnes-text-qyh-dev-api-cn-r{next_provider}",
        rehash_runtime(ProviderInstanceRevision, provider_payload),
        expected_version=snapshot["providerHead"]["version"],
    )

    return {
        "status": "R2_4X_AGNES_CN_HOST_ALIGN_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "egress": exact_ref("EgressPolicyRevision", egress, "policy_id").model_dump(
            mode="json", by_alias=True
        ),
        "network": exact_ref("NetworkPolicyRevision", network, "policy_id").model_dump(
            mode="json", by_alias=True
        ),
        "provider": exact_ref(
            "ProviderInstanceRevision", provider, "provider_instance_id"
        ).model_dump(mode="json", by_alias=True),
        "baseUrl": provider.endpoint_profile.base_url,
        "region": provider.endpoint_profile.region,
        "providerBusinessCalls": 0,
        "healthProbes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = apply() if args.apply else inspect()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    ok = result.get("status") in {
        "ready",
        "already_aligned",
        "R2_4X_AGNES_CN_HOST_ALIGN_GREEN",
    }
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
