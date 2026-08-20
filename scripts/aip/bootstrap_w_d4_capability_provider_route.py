#!/usr/bin/env python3
"""W-D4: strip definition-layer provider/route unknown for text Capabilities."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_agent_registry_contracts import (
    BindingHealth,
    CapabilityBindingRequest,
    CapabilityReadiness,
    CreateCapabilityBindingRequest,
    EvaluateOperationalBindingRequest,
    PublishCapabilityRevisionRequest,
    TemplateLifecycle,
    UpdateCapabilityBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound, AipAgentRegistryStore
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_capability_provider_route import (
    MEDIA_CAPABILITY_IDS,
    TEXT_CAPABILITY_IDS,
    definition_readiness,
    strip_provider_route_unknown,
)
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_solution_pack_publisher import CAPABILITY_IDS
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
ACTOR = "aip-w-d4-capability-provider-route"
APPROVAL_REF = "93-W-D4-PROVIDER-ROUTE"
TEMPLATE_BINDING_ID = "ecommerce.data_advisor.strategy.plan.r2"


def latest_capability(capability_id: str) -> Any:
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            """
            SELECT revision FROM aip_capability_revision
            WHERE capability_id=%s AND lifecycle='published'
            ORDER BY revision DESC LIMIT 1
            """,
            (capability_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"published capability missing: {capability_id}")
    return AipCapabilityRegistry().get(capability_id, int(row["revision"]))


def publish_stripped(current: Any, reasons: list[str]) -> Any:
    payload = current.model_dump(
        mode="json", by_alias=True, exclude={"content_hash", "created_by", "created_at"}
    )
    payload.update(
        revision=int(current.revision) + 1,
        lifecycle=TemplateLifecycle.PUBLISHED.value,
        parentRef=VersionedAssetRef(
            asset_type="CapabilityRevision",
            asset_id=current.capability_id,
            revision=current.revision,
            content_hash=current.content_hash,
        ).model_dump(mode="json", by_alias=True),
        readiness=definition_readiness(reasons).value,
        readinessReasons=reasons,
    )
    return AipCapabilityRegistry().publish(
        PublishCapabilityRevisionRequest(
            **payload, content_hash=AipAgentRegistryStore._hash(payload)
        ),
        actor=ACTOR,
    )


def ensure_binding_for_revision(published: Any) -> dict[str, Any]:
    service = AipCapabilityBindingService()
    bid = f"ecommerce.shared.{published.capability_id}.r{published.revision}"
    try:
        existing = service.get(SCOPE, bid)
        return {"bindingId": bid, "disposition": "existing", "status": existing.status}
    except AipAgentRegistryNotFound:
        pass
    template = service.get(SCOPE, TEMPLATE_BINDING_ID)
    cap_ref = VersionedAssetRef(
        asset_type="CapabilityRevision",
        asset_id=published.capability_id,
        revision=published.revision,
        content_hash=published.content_hash,
    )
    deps = template.dependencies.model_copy(
        update={
            "data_dependency_refs": list(published.required_data_refs or []),
            "tool_dependency_refs": list(published.required_tool_refs or []),
        }
    )
    now = datetime.now(UTC)
    binding, _ = service.create(
        SCOPE,
        CreateCapabilityBindingRequest(
            binding_id=bid,
            binding=CapabilityBindingRequest(
                capability=cap_ref,
                secret_ref=template.secret_ref,
                network_policy_revision=template.network_policy_revision,
                quota_policy_revision=template.quota_policy_revision,
                timeout_ms=template.timeout_ms,
                max_concurrency=1,
            ),
        ),
        idempotency_key=f"{APPROVAL_REF}:create:{bid}",
        actor=ACTOR,
        occurred_at=now,
    )
    binding, readiness, _ = service.evaluate(
        SCOPE,
        bid,
        EvaluateOperationalBindingRequest(
            expected_version=binding.version,
            dependencies=deps,
        ),
        idempotency_key=f"{APPROVAL_REF}:evaluate:{bid}",
        actor=ACTOR,
        evaluated_at=now,
    )
    activated = False
    if (
        binding.status == "provisioning"
        and readiness.readiness is CapabilityReadiness.AVAILABLE
    ):
        binding, _ = service.update(
            SCOPE,
            bid,
            UpdateCapabilityBindingRequest(
                expected_version=binding.version,
                from_status="provisioning",
                to_status="active",
                health=BindingHealth.HEALTHY,
                observed_at=now,
            ),
            idempotency_key=f"{APPROVAL_REF}:activate:{bid}",
            actor=ACTOR,
        )
        activated = True
    return {
        "bindingId": bid,
        "disposition": "created",
        "status": binding.status,
        "operationalReadiness": readiness.readiness.value,
        "operationalReasons": list(readiness.reasons),
        "activated": activated,
    }


def canary_shared_binding_leak() -> int:
    with db_connect(CANARY) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count FROM aip_capability_binding
            WHERE org_id=%s AND project_id=%s
              AND binding_id LIKE 'ecommerce.shared.%%'
            """,
            (*CANARY.key,),
        ).fetchone()
    return int(row["count"])


def build_plan() -> dict[str, Any]:
    items = []
    for capability_id in CAPABILITY_IDS:
        current = latest_capability(capability_id)
        reasons = list(current.readiness_reasons or [])
        if capability_id in TEXT_CAPABILITY_IDS:
            next_reasons = strip_provider_route_unknown(reasons)
            action = "strip_provider_route"
        else:
            next_reasons = reasons
            action = "keep_media_honest"
        items.append(
            {
                "capabilityId": capability_id,
                "class": "text" if capability_id in TEXT_CAPABILITY_IDS else "media",
                "action": action,
                "fromRevision": current.revision,
                "toRevision": current.revision + 1
                if next_reasons != reasons or capability_id in TEXT_CAPABILITY_IDS
                else current.revision,
                "currentReasons": reasons,
                "nextReasons": next_reasons,
            }
        )
    return {
        "wave": "W-D4",
        "approvalRef": APPROVAL_REF,
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "mode": "plan",
        "items": items,
        "canarySharedBindingCount": canary_shared_binding_leak(),
    }


def apply() -> dict[str, Any]:
    if canary_shared_binding_leak():
        raise RuntimeError("negative canary already has shared capability bindings")
    results = []
    for capability_id in CAPABILITY_IDS:
        current = latest_capability(capability_id)
        reasons = list(current.readiness_reasons or [])
        if capability_id in TEXT_CAPABILITY_IDS:
            next_reasons = strip_provider_route_unknown(reasons)
            if next_reasons == reasons and capability_id == "strategy.plan":
                results.append(
                    {
                        "capabilityId": capability_id,
                        "disposition": "already_clean",
                        "revision": current.revision,
                        "readiness": current.readiness.value,
                        "readinessReasons": reasons,
                    }
                )
                continue
            published = publish_stripped(current, next_reasons)
            for code in ("provider_unknown", "aip7_route_authority_unavailable"):
                if code in list(published.readiness_reasons or []):
                    raise RuntimeError(f"{capability_id}: {code} still present")
            binding = ensure_binding_for_revision(published)
            results.append(
                {
                    "capabilityId": capability_id,
                    "disposition": "published",
                    "class": "text",
                    "revision": published.revision,
                    "readiness": published.readiness.value,
                    "readinessReasons": list(published.readiness_reasons or []),
                    "binding": binding,
                }
            )
        else:
            results.append(
                {
                    "capabilityId": capability_id,
                    "disposition": "kept_media_honest",
                    "class": "media",
                    "revision": current.revision,
                    "readiness": current.readiness.value,
                    "readinessReasons": reasons,
                }
            )
            assert capability_id in MEDIA_CAPABILITY_IDS
    if canary_shared_binding_leak():
        raise RuntimeError("negative canary leaked shared capability bindings")
    return {
        "wave": "W-D4",
        "approvalRef": APPROVAL_REF,
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "mode": "apply",
        "items": results,
        "canarySharedBindingCount": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    payload = apply() if args.apply else build_plan()
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
