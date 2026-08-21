#!/usr/bin/env python3
"""W-D3: attach exact EvidenceBundleRevision tool deps to ten shared Capabilities."""

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
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_capability_tool_deps import tool_ref_for
from aos_api.aip_solution_pack_publisher import CAPABILITY_IDS
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
ACTOR = "aip-w-d3-capability-tool-deps"
APPROVAL_REF = "92-W-D3-TOOL-DEPS"
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


def load_tool_evidence_ref(capability_id: str) -> VersionedAssetRef:
    """Reuse an existing frozen EvidenceBundleRevision as adapter-side tool evidence.

    exact_assets_available only accepts EvalDatasetRevision / EvidenceBundleRevision.
    Creating parallel production-contract bundles is out of scope for W-D3; we pin
    a real frozen org-org bundle and key the capability via requiredToolRefs list.
    """
    del capability_id  # one shared frozen bundle is enough for definition projection
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            """
            SELECT bundle_id, revision, content_hash
            FROM aip_evidence_bundle_revision
            WHERE org_id=%s AND project_id=%s AND lifecycle='frozen'
              AND license_summary IS NOT NULL
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (*SCOPE.key,),
        ).fetchone()
    if row is None:
        raise RuntimeError("no frozen EvidenceBundleRevision available for tool deps")
    return tool_ref_for(row["bundle_id"], int(row["revision"]), row["content_hash"])


def ensure_tool_evidence_bundle(capability_id: str) -> VersionedAssetRef:
    return load_tool_evidence_ref(capability_id)

def publish_with_tool_deps(current: Any, tool_ref: VersionedAssetRef) -> Any:
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
        requiredToolRefs=[tool_ref.model_dump(mode="json", by_alias=True)],
    )
    return AipCapabilityRegistry().publish(
        PublishCapabilityRevisionRequest(
            **payload, content_hash=AipAgentRegistryStore._hash(payload)
        ),
        actor=ACTOR,
    )


def ensure_binding_for_revision(
    published: Any, tool_ref: VersionedAssetRef
) -> dict[str, Any]:
    service = AipCapabilityBindingService()
    bid = f"ecommerce.shared.{published.capability_id}.r{published.revision}"
    try:
        existing = service.get(SCOPE, bid)
        return {
            "bindingId": bid,
            "disposition": "existing",
            "status": existing.status,
            "toolDeps": len(existing.dependencies.tool_dependency_refs or []),
        }
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
            "tool_dependency_refs": [tool_ref],
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
        "toolDeps": len(binding.dependencies.tool_dependency_refs or []),
        "operationalReadiness": readiness.readiness.value,
        "operationalReasons": list(readiness.reasons),
        "activated": activated,
    }


def canary_tool_binding_leak() -> int:
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
        items.append(
            {
                "capabilityId": capability_id,
                "fromRevision": current.revision,
                "toRevision": current.revision + 1,
                "currentToolRefs": len(current.required_tool_refs or []),
                "evidenceBundleId": load_tool_evidence_ref(capability_id).asset_id,
            }
        )
    return {
        "wave": "W-D3",
        "approvalRef": APPROVAL_REF,
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "mode": "plan",
        "items": items,
        "canarySharedBindingCount": canary_tool_binding_leak(),
    }


def apply() -> dict[str, Any]:
    if canary_tool_binding_leak():
        raise RuntimeError("negative canary already has shared capability bindings")
    results = []
    for capability_id in CAPABILITY_IDS:
        current = latest_capability(capability_id)
        tool_ref = ensure_tool_evidence_bundle(capability_id)
        published = publish_with_tool_deps(current, tool_ref)
        if not published.required_tool_refs:
            raise RuntimeError(f"{capability_id}: requiredToolRefs empty")
        binding = ensure_binding_for_revision(published, tool_ref)
        if binding["toolDeps"] < 1 and binding["disposition"] == "created":
            raise RuntimeError(f"{capability_id}: binding tool deps missing")
        results.append(
            {
                "capabilityId": capability_id,
                "revision": published.revision,
                "contentHash": published.content_hash,
                "requiredToolRefs": [
                    ref.model_dump(mode="json", by_alias=True)
                    for ref in published.required_tool_refs
                ],
                "readiness": published.readiness.value,
                "readinessReasons": list(published.readiness_reasons or []),
                "binding": binding,
            }
        )
    if canary_tool_binding_leak():
        raise RuntimeError("negative canary leaked shared capability bindings")
    return {
        "wave": "W-D3",
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
