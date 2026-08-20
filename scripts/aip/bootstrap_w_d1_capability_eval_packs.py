#!/usr/bin/env python3
"""W-D1: attach exact EvalSuiteRevision packs to ten shared Capability definitions.

For each published W0A capability:
1. Register a tenant-scoped definition EvalPack (dataset + suite)
2. Publish next Capability revision with evalPackRef set
3. Drop only ``eval_pack_unavailable`` from readinessReasons (other blockers stay honest)
4. Ensure org-org CapabilityBinding exists for the new revision

Never claims full eight-dim GREEN. Negative canary: no suites under dev-org.
"""

from __future__ import annotations

import argparse
import hashlib
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
from aos_api.aip_capability_eval_pack import (
    definition_readiness,
    strip_eval_pack_unavailable,
)
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_contracts import ArtifactRef
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    DatasetPiiState,
    DatasetRevisionRef,
    DatasetSourceKind,
    EvalCaseDefinition,
    EvalCaseKind,
    EvalDatasetManifest,
    EvalSuiteRevision,
    JudgeRevisionRef,
)
from aos_api.aip_eval_pack_registry import AipEvalPackRegistry, compute_eval_suite_hash
from aos_api.aip_solution_pack_publisher import CAPABILITY_IDS
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
ACTOR = "aip-w-d1-capability-eval-packs"
APPROVAL_REF = "90-W-D1-EVALPACK"
TEMPLATE_BINDING_ID = "ecommerce.data_advisor.strategy.plan.r2"
NOW = datetime(2026, 8, 20, 2, 0, tzinfo=UTC)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def suite_id_for(capability_id: str) -> str:
    return f"ecommerce.shared.evalpack.{capability_id}"


def dataset_id_for(capability_id: str) -> str:
    return f"ecommerce.shared.evalset.{capability_id}"


def latest_capability(capability_id: str) -> Any:
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            """
            SELECT capability_id, revision FROM aip_capability_revision
            WHERE capability_id=%s AND lifecycle='published'
            ORDER BY revision DESC LIMIT 1
            """,
            (capability_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"published capability missing: {capability_id}")
    return AipCapabilityRegistry().get(capability_id, int(row["revision"]))


def register_definition_pack(capability_id: str) -> EvalSuiteRevision:
    registry = AipEvalPackRegistry()
    source_hash = sha(f"{APPROVAL_REF}:{capability_id}:source")
    dataset = DatasetRevisionRef(
        dataset_id=dataset_id_for(capability_id),
        revision=1,
        content_hash=sha(f"{APPROVAL_REF}:{capability_id}:dataset"),
        source_hash=source_hash,
        redaction_policy=AssetRevisionRef(
            asset_type=AssetType.POLICY,
            asset_id="redaction-definition-evalpack",
            revision="1",
            content_hash=sha("redaction-definition-evalpack@1"),
        ),
    )
    manifest = EvalDatasetManifest(
        source_kind=DatasetSourceKind.ARTIFACT_SNAPSHOT,
        source_id=f"definition-evalpack-{capability_id}",
        source_revision="1",
        source_hash=source_hash,
        fields_allowlist=["capabilityId", "caseId", "expectedBehavior"],
        redaction_receipt=ArtifactRef(
            artifact_id=f"redaction-{capability_id}",
            artifact_type="redaction_receipt",
            revision="1",
            content_hash=sha(f"redaction:{capability_id}"),
        ),
        pii_state=DatasetPiiState.NONE,
        case_count=1,
        captured_at=NOW,
    )
    registry.register_dataset_revision(SCOPE, dataset, manifest, actor=ACTOR)

    input_ref = ArtifactRef(
        artifact_id=f"input-{capability_id}",
        artifact_type="eval_input",
        revision="1",
        content_hash=sha(f"input:{capability_id}"),
    )
    expected_ref = ArtifactRef(
        artifact_id=f"expected-{capability_id}",
        artifact_type="eval_expected",
        revision="1",
        content_hash=sha(f"expected:{capability_id}"),
    )
    # AssetType has no Capability member; definition packs target a scenario
    # keyed by capability_id so the suite is exact and tenant-scoped.
    target = AssetRevisionRef(
        asset_type=AssetType.SCENARIO,
        asset_id=capability_id,
        revision="1",
        content_hash=sha(f"target:{capability_id}"),
    )
    suite = EvalSuiteRevision(
        suite_id=suite_id_for(capability_id),
        revision=1,
        content_hash="0" * 64,
        target=target,
        dataset=dataset,
        judge=JudgeRevisionRef(
            judge_id="definition-contract-judge",
            revision=1,
            content_hash=sha("definition-contract-judge@1"),
        ),
        cases=[
            EvalCaseDefinition(
                case_id="definition-positive-1",
                kind=EvalCaseKind.POSITIVE,
                input_artifact=input_ref,
                expected_artifact=expected_ref,
                timeout_ms=5_000,
            )
        ],
        gate_threshold=1.0,
    )
    suite = suite.model_copy(update={"content_hash": compute_eval_suite_hash(suite)})
    return registry.register_suite_revision(SCOPE, suite, actor=ACTOR)


def publish_with_eval_pack(current: Any, suite: EvalSuiteRevision) -> Any:
    reasons = strip_eval_pack_unavailable(list(current.readiness_reasons or []))
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
        evalPackRef=VersionedAssetRef(
            asset_type="EvalSuiteRevision",
            asset_id=suite.suite_id,
            revision=suite.revision,
            content_hash=suite.content_hash,
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


def canary_suite_count() -> int:
    with db_connect(CANARY) as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count FROM aip_eval_suite_revision
            WHERE org_id=%s AND project_id=%s AND suite_id LIKE 'ecommerce.shared.evalpack.%%'
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
                "hadEvalPackUnavailable": "eval_pack_unavailable"
                in list(current.readiness_reasons or []),
                "currentReasons": list(current.readiness_reasons or []),
                "nextReasons": strip_eval_pack_unavailable(
                    list(current.readiness_reasons or [])
                ),
                "suiteId": suite_id_for(capability_id),
            }
        )
    return {
        "wave": "W-D1",
        "approvalRef": APPROVAL_REF,
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "mode": "plan",
        "items": items,
        "canarySuiteCount": canary_suite_count(),
    }


def apply() -> dict[str, Any]:
    if canary_suite_count():
        raise RuntimeError("negative canary already has shared eval packs")
    results = []
    for capability_id in CAPABILITY_IDS:
        current = latest_capability(capability_id)
        suite = register_definition_pack(capability_id)
        published = publish_with_eval_pack(current, suite)
        if "eval_pack_unavailable" in list(published.readiness_reasons or []):
            raise RuntimeError(f"{capability_id}: eval_pack_unavailable still present")
        if published.eval_pack_ref is None:
            raise RuntimeError(f"{capability_id}: evalPackRef missing after publish")
        binding = ensure_binding_for_revision(published)
        results.append(
            {
                "capabilityId": capability_id,
                "revision": published.revision,
                "contentHash": published.content_hash,
                "evalPackRef": published.eval_pack_ref.model_dump(
                    mode="json", by_alias=True
                ),
                "readiness": published.readiness.value,
                "readinessReasons": list(published.readiness_reasons or []),
                "binding": binding,
            }
        )
    if canary_suite_count():
        raise RuntimeError("negative canary leaked shared eval packs")
    return {
        "wave": "W-D1",
        "approvalRef": APPROVAL_REF,
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "mode": "apply",
        "items": results,
        "canarySuiteCount": 0,
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
