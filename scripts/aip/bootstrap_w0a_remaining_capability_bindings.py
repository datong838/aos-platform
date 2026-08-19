#!/usr/bin/env python3
"""Create org CapabilityBindings for W0A ten-pack gaps (honest blocked OK).

Does not create AgentInstances or replay sealed pilots. Activation only when
evaluate returns AVAILABLE. Metadata-only; never resolves Secret payloads.
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
    OperationalBindingDependencies,
    UpdateCapabilityBindingRequest,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import AipAgentRegistryNotFound
from aos_api.aip_capability_binding_service import AipCapabilityBindingService
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_solution_pack_publisher import CAPABILITY_IDS
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
ACTOR = "aip-w0a-remaining-capability-bindings"
APPROVAL_REF = "58-W0A-CAP-BIND"
TEMPLATE_BINDING_ID = "ecommerce.data_advisor.strategy.plan.r2"


def compact_revision(ref: VersionedAssetRef) -> str:
    return f"{ref.asset_id}@{ref.revision}#{ref.content_hash}"


def latest_published(capability_id: str) -> tuple[int, str]:
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            """
            SELECT revision, content_hash FROM aip_capability_revision
            WHERE capability_id=%s AND lifecycle='published'
            ORDER BY revision DESC LIMIT 1
            """,
            (capability_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"published capability missing: {capability_id}")
    return int(row["revision"]), str(row["content_hash"])


def existing_capability_ids(service: AipCapabilityBindingService) -> set[str]:
    return {
        binding.capability.asset_id
        for binding in service.list_bindings(SCOPE, limit=200)
    }


def binding_id_for(capability_id: str, revision: int) -> str:
    return f"ecommerce.shared.{capability_id}.r{revision}"


def build_dependencies(
    *,
    template: Any,
    capability: Any,
) -> OperationalBindingDependencies:
    deps = template.dependencies
    return OperationalBindingDependencies(
        provider_ref=deps.provider_ref,
        model_route_ref=deps.model_route_ref,
        runtime_policy_ref=deps.runtime_policy_ref,
        eval_gate_ref=deps.eval_gate_ref,
        eval_contract_ref=deps.eval_contract_ref,
        license_evidence_refs=list(deps.license_evidence_refs),
        data_dependency_refs=list(getattr(capability, "required_data_refs", []) or []),
        tool_dependency_refs=list(getattr(capability, "required_tool_refs", []) or []),
        budget_policy_ref=deps.budget_policy_ref,
        allow_degraded=False,
    )


def ensure_one(
    *,
    service: AipCapabilityBindingService,
    capability_id: str,
    template: Any,
    now: datetime,
) -> dict[str, Any]:
    revision, content_hash = latest_published(capability_id)
    bid = binding_id_for(capability_id, revision)
    try:
        existing = service.get(SCOPE, bid)
        return {
            "capabilityId": capability_id,
            "bindingId": bid,
            "disposition": "existing",
            "status": existing.status,
            "readiness": getattr(
                existing.operational_readiness, "value", existing.operational_readiness
            ),
        }
    except AipAgentRegistryNotFound:
        pass

    capability = AipCapabilityRegistry().get(capability_id, revision)
    if capability.content_hash != content_hash:
        raise RuntimeError(f"capability hash drift: {capability_id}")
    cap_ref = VersionedAssetRef(
        asset_type="CapabilityRevision",
        asset_id=capability_id,
        revision=revision,
        content_hash=content_hash,
    )
    dependencies = build_dependencies(template=template, capability=capability)
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
            dependencies=dependencies,
        ),
        idempotency_key=f"{APPROVAL_REF}:evaluate:{bid}:{now:%Y%m%d%H%M%S}",
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
        "capabilityId": capability_id,
        "bindingId": bid,
        "disposition": "created",
        "status": binding.status,
        "readiness": readiness.readiness.value,
        "reasons": list(readiness.reasons),
        "activated": activated,
    }


def apply(*, now: datetime | None = None) -> dict[str, Any]:
    decision_at = now or datetime.now(UTC)
    service = AipCapabilityBindingService()
    template = service.get(SCOPE, TEMPLATE_BINDING_ID)
    present = existing_capability_ids(service)
    missing = [cid for cid in CAPABILITY_IDS if cid not in present]
    results = [
        ensure_one(
            service=service,
            capability_id=cid,
            template=template,
            now=decision_at,
        )
        for cid in missing
    ]
    after = existing_capability_ids(service)
    return {
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "approvalRef": APPROVAL_REF,
        "templateBindingId": TEMPLATE_BINDING_ID,
        "w0aCapabilityIds": list(CAPABILITY_IDS),
        "missingBefore": missing,
        "results": results,
        "w0aBoundAfter": sorted(cid for cid in CAPABILITY_IDS if cid in after),
        "w0aStillMissing": sorted(cid for cid in CAPABILITY_IDS if cid not in after),
        "secretPayloadReads": 0,
    }


def inspect() -> dict[str, Any]:
    service = AipCapabilityBindingService()
    present = existing_capability_ids(service)
    return {
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "w0aCapabilityIds": list(CAPABILITY_IDS),
        "bound": sorted(cid for cid in CAPABILITY_IDS if cid in present),
        "missing": sorted(cid for cid in CAPABILITY_IDS if cid not in present),
        "mode": "inspect",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = apply() if args.apply else inspect()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    if args.apply and result.get("w0aStillMissing"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
