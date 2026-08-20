#!/usr/bin/env python3
"""W-D2: attach exact EvalDatasetRevision data deps to ten shared Capabilities.

Reuses W-D1 datasets (ecommerce.shared.evalset.*). Publishes next Capability
revision with requiredDataRefs, then ensures a Binding for that revision with
matching dataDependencyRefs so the plugin page can show 数据依赖 ✓.
"""

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
from aos_api.aip_capability_data_deps import data_ref_for, dataset_id_for
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_solution_pack_publisher import CAPABILITY_IDS
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
ACTOR = "aip-w-d2-capability-data-deps"
APPROVAL_REF = "91-W-D2-DATA-DEPS"
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


def load_dataset_ref(capability_id: str) -> VersionedAssetRef:
    dataset_id = dataset_id_for(capability_id)
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            """
            SELECT dataset_id, revision, content_hash
            FROM aip_eval_dataset_revision
            WHERE org_id=%s AND project_id=%s AND dataset_id=%s
            ORDER BY revision DESC LIMIT 1
            """,
            (*SCOPE.key, dataset_id),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"W-D1 dataset missing for {capability_id}: {dataset_id}")
    return data_ref_for(row["dataset_id"], int(row["revision"]), row["content_hash"])


def publish_with_data_deps(current: Any, data_ref: VersionedAssetRef) -> Any:
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
        requiredDataRefs=[data_ref.model_dump(mode="json", by_alias=True)],
    )
    return AipCapabilityRegistry().publish(
        PublishCapabilityRevisionRequest(
            **payload, content_hash=AipAgentRegistryStore._hash(payload)
        ),
        actor=ACTOR,
    )


def ensure_binding_for_revision(published: Any, data_ref: VersionedAssetRef) -> dict[str, Any]:
    service = AipCapabilityBindingService()
    bid = f"ecommerce.shared.{published.capability_id}.r{published.revision}"
    try:
        existing = service.get(SCOPE, bid)
        return {
            "bindingId": bid,
            "disposition": "existing",
            "status": existing.status,
            "dataDeps": len(existing.dependencies.data_dependency_refs or []),
        }
    except AipAgentRegistryNotFound:
        pass
    try:
        template = service.get(SCOPE, TEMPLATE_BINDING_ID)
    except AipAgentRegistryNotFound as exc:
        raise RuntimeError("template binding missing for dependency clone") from exc
    cap_ref = VersionedAssetRef(
        asset_type="CapabilityRevision",
        asset_id=published.capability_id,
        revision=published.revision,
        content_hash=published.content_hash,
    )
    deps = template.dependencies.model_copy(
        update={
            "data_dependency_refs": [data_ref],
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
        "dataDeps": len(binding.dependencies.data_dependency_refs or []),
        "operationalReadiness": readiness.readiness.value,
        "operationalReasons": list(readiness.reasons),
        "activated": activated,
    }


def canary_dataset_count() -> int:
    with db_connect(CANARY) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count FROM aip_eval_dataset_revision
            WHERE org_id=%s AND project_id=%s
              AND dataset_id LIKE 'ecommerce.shared.evalset.%%'
            """,
            (*CANARY.key,),
        ).fetchone()
    return int(row["count"])


def build_plan() -> dict[str, Any]:
    items = []
    for capability_id in CAPABILITY_IDS:
        current = latest_capability(capability_id)
        data_ref = load_dataset_ref(capability_id)
        items.append(
            {
                "capabilityId": capability_id,
                "fromRevision": current.revision,
                "toRevision": current.revision + 1,
                "currentDataRefs": len(current.required_data_refs or []),
                "datasetId": data_ref.asset_id,
                "datasetRevision": data_ref.revision,
            }
        )
    return {
        "wave": "W-D2",
        "approvalRef": APPROVAL_REF,
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "mode": "plan",
        "items": items,
        "canaryDatasetCount": canary_dataset_count(),
    }


def apply() -> dict[str, Any]:
    if canary_dataset_count():
        raise RuntimeError("negative canary already has shared eval datasets")
    results = []
    for capability_id in CAPABILITY_IDS:
        current = latest_capability(capability_id)
        data_ref = load_dataset_ref(capability_id)
        published = publish_with_data_deps(current, data_ref)
        if not published.required_data_refs:
            raise RuntimeError(f"{capability_id}: requiredDataRefs empty after publish")
        binding = ensure_binding_for_revision(published, data_ref)
        if binding["dataDeps"] < 1 and binding["disposition"] == "created":
            raise RuntimeError(f"{capability_id}: binding data deps missing")
        results.append(
            {
                "capabilityId": capability_id,
                "revision": published.revision,
                "contentHash": published.content_hash,
                "requiredDataRefs": [
                    ref.model_dump(mode="json", by_alias=True)
                    for ref in published.required_data_refs
                ],
                "readiness": published.readiness.value,
                "readinessReasons": list(published.readiness_reasons or []),
                "binding": binding,
            }
        )
    return {
        "wave": "W-D2",
        "approvalRef": APPROVAL_REF,
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "mode": "apply",
        "items": results,
        "canaryDatasetCount": canary_dataset_count(),
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
