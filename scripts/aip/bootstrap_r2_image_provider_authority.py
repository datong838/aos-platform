#!/usr/bin/env python3
"""Bootstrap Agnes Image Provider authority (IMG-1/IMG-2).

Default is inspect. ``--apply`` publishes additive:
  Egress + Network + Provider ``agnes-image-qyh-dev``

Secret binding is plugin/provider exact:
  ``keychain://com.aos.llm/agnes-image/org-org/dev-project/agnes-image-qyh-dev#api-key``
Credential material may be cloned from the domestic text Keychain item by an
operator (never logged). Do not point the image Provider at the text secretRef.

Never starts AgentRun. Never Health-probes. Never prints Secret payload.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "aos-api"))

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_runtime_contracts import (
    ModelRuntimeLifecycle,
    ProviderEndpointProfile,
    ProviderInstanceRevision,
)
from aos_api.aip_model_runtime_store import AipModelRuntimeStore, canonical_hash
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_policy_store import AipNetworkPolicyStore
from aos_api.aip_provider_plugin_authority import (
    ProviderPluginAuthority,
    ProviderPluginAuthorityError,
)
from aos_api.aip_runtime_guard_policy_contracts import (
    EgressPolicyRevisionCreate,
    GuardPolicyLifecycle,
    RegionState,
)
from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
ACTOR = "aip-r2-img-provider-bootstrap"
APPROVAL_REF = "46-§8.75-IMG-2"
CN_HOST = "api.agnes-ai.cn"
CN_BASE_URL = "https://api.agnes-ai.cn/v1"
CN_REGION = "China (Domestic)"
PLUGIN_ID = "agnes-image"
PROVIDER_ID = "agnes-image-qyh-dev"
EGRESS_ID = "agnes-image-qyh-dev-egress"
NETWORK_ID = "network-qyh-image-dev"
TEXT_PROVIDER_ID = "agnes-text-qyh-dev"
TEXT_PROVIDER_REVISION = 7
IMAGE_SECRET_REF = (
    "keychain://com.aos.llm/agnes-image/org-org/dev-project/"
    "agnes-image-qyh-dev#api-key"
)
IMAGE_SECRET_VERSION = "v1"
# Must match AipModelRuntimeStore._META_FIELDS for provider hash.
META_FIELDS = {"tenant", "revision", "contentHash", "createdBy", "createdAt"}


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


def head_row(kind: str, asset_id: str) -> dict[str, Any] | None:
    with db_connect(SCOPE) as conn:
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
    if row is None:
        return None
    return {"revision": int(row["current_revision"]), "version": int(row["version"])}


def _provider_payload(
    *,
    plugin: Any,
    text_provider: Any,
    egress: Any,
    revision: int,
    actor: str,
    now: datetime,
) -> dict[str, Any]:
    return {
        "tenant": TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        "providerInstanceId": PROVIDER_ID,
        "revision": revision,
        "pluginRef": exact_ref("ProviderPluginRevision", plugin, "provider_plugin_id"),
        "endpointProfile": ProviderEndpointProfile(
            baseUrl=CN_BASE_URL,
            region=CN_REGION,
            timeoutMs=60_000,
            metadata={
                "protocol": "openai-compatible",
                "environment": "development",
                "modality": "image",
            },
        ),
        "secretRef": IMAGE_SECRET_REF,
        "secretVersion": IMAGE_SECRET_VERSION,
        "egressPolicyRef": exact_ref("EgressPolicyRevision", egress, "policy_id"),
        "dataClassificationPolicyRef": text_provider.data_classification_policy_ref,
        "lifecycle": ModelRuntimeLifecycle.ACTIVE,
        "createdBy": actor,
        "createdAt": now,
    }


def inspect() -> dict[str, Any]:
    try:
        plugin = ProviderPluginAuthority().get(SCOPE, PLUGIN_ID, 1)
    except ProviderPluginAuthorityError as exc:
        return {
            "status": "blocked",
            "blockerCode": exc.code,
            "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        }
    provider_head = head_row("provider", PROVIDER_ID)
    if provider_head is not None:
        provider = AipModelRuntimeStore().get_provider(
            SCOPE, PROVIDER_ID, provider_head["revision"]
        )
        secret_ok = provider.secret_ref == IMAGE_SECRET_REF
        return {
            "status": "already_present" if secret_ok else "secret_ref_needs_bump",
            "plugin": exact_ref(
                "ProviderPluginRevision", plugin, "provider_plugin_id"
            ).model_dump(mode="json", by_alias=True),
            "provider": exact_ref(
                "ProviderInstanceRevision", provider, "provider_instance_id"
            ).model_dump(mode="json", by_alias=True),
            "secretRefBound": secret_ok,
            "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        }
    return {
        "status": "ready",
        "plugin": {
            "assetId": plugin.provider_plugin_id,
            "revision": plugin.revision,
            "contentHash": plugin.content_hash,
            "modalities": list(plugin.modalities),
            "defaultModels": list(plugin.default_models),
        },
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
    }


def apply() -> dict[str, Any]:
    snapshot = inspect()
    if snapshot["status"] == "already_present":
        return {**snapshot, "status": "R2_IMG_PROVIDER_AUTHORITY_GREEN"}
    if snapshot["status"] not in {"ready", "secret_ref_needs_bump"}:
        raise RuntimeError(f"IMG provider bootstrap blocked: {snapshot.get('blockerCode')}")

    now = datetime.now(UTC)
    plugin = ProviderPluginAuthority().get(SCOPE, PLUGIN_ID, 1)
    text_provider = AipModelRuntimeStore().get_provider(
        SCOPE, TEXT_PROVIDER_ID, TEXT_PROVIDER_REVISION
    )
    guards = AipRuntimeGuardPolicyStore()
    networks = AipNetworkPolicyStore()
    runtime = AipModelRuntimeStore()

    effective_from = now - timedelta(minutes=1)
    effective_until = now + timedelta(days=3650)

    egress_head = head_row("egress", EGRESS_ID)
    if egress_head is None:
        egress = guards.publish_egress(
            SCOPE,
            ACTOR,
            f"{APPROVAL_REF}-egress-r1",
            EgressPolicyRevisionCreate(
                policyId=EGRESS_ID,
                revision=1,
                environment="development",
                effectiveFrom=effective_from,
                effectiveUntil=effective_until,
                owner="AOS/FDE",
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
            expected_version=0,
        )
    else:
        egress = guards.get_egress(SCOPE, EGRESS_ID, egress_head["revision"])

    network_head = head_row("network", NETWORK_ID)
    if network_head is None:
        network = networks.publish(
            SCOPE,
            ACTOR,
            f"{APPROVAL_REF}-network-r1",
            NetworkPolicyRevisionCreate(
                policyId=NETWORK_ID,
                revision=1,
                allowedSchemes=["https"],
                allowedHosts=[CN_HOST],
                allowedPorts=[443],
                tlsRequired=True,
                publicFallbackAllowed=False,
                egressPolicyRef=exact_ref("EgressPolicyRevision", egress, "policy_id"),
                effectiveFrom=effective_from,
                effectiveUntil=effective_until,
                owner="AOS/FDE",
                approvalRef=APPROVAL_REF,
                lifecycle=GuardPolicyLifecycle.ACTIVE,
            ),
            expected_version=0,
        )
    else:
        network = networks.get(SCOPE, NETWORK_ID, network_head["revision"])

    provider_head = head_row("provider", PROVIDER_ID)
    if provider_head is None:
        next_revision = 1
        expected_version = 0
        idem_key = f"{APPROVAL_REF}-provider-r1"
    else:
        next_revision = int(provider_head["revision"]) + 1
        expected_version = int(provider_head["version"])
        idem_key = f"{APPROVAL_REF}-provider-r{next_revision}-secret-bind"

    provider = runtime.publish_provider(
        SCOPE,
        ACTOR,
        idem_key,
        rehash_runtime(
            ProviderInstanceRevision,
            _provider_payload(
                plugin=plugin,
                text_provider=text_provider,
                egress=egress,
                revision=next_revision,
                actor=ACTOR,
                now=now,
            ),
        ),
        expected_version=expected_version,
    )
    return {
        "status": "R2_IMG_PROVIDER_AUTHORITY_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "plugin": exact_ref(
            "ProviderPluginRevision", plugin, "provider_plugin_id"
        ).model_dump(mode="json", by_alias=True),
        "egress": exact_ref("EgressPolicyRevision", egress, "policy_id").model_dump(
            mode="json", by_alias=True
        ),
        "network": exact_ref("NetworkPolicyRevision", network, "policy_id").model_dump(
            mode="json", by_alias=True
        ),
        "provider": exact_ref(
            "ProviderInstanceRevision", provider, "provider_instance_id"
        ).model_dump(mode="json", by_alias=True),
        "secretPayloadReads": 0,
        "healthProbes": 0,
        "providerBusinessCalls": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = apply() if args.apply else inspect()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0 if result.get("status") in {
        "ready",
        "already_present",
        "secret_ref_needs_bump",
        "R2_IMG_PROVIDER_AUTHORITY_GREEN",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
