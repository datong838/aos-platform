#!/usr/bin/env python3
"""Restricted R1 runtime authority bootstrap for org-org/dev-project.

Dry-run is the default.  The apply path publishes only the approved R1
prerequisites and promotes the already validated Provider revision; it never
creates a Binding or AgentRun and never prints a secret payload.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_agent_registry_store import AipAgentRegistryTransitionBlocked
from aos_api.aip_contracts import ArtifactRef, TenantContext
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_store import AipBudgetAuthorityStore
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
from aos_api.aip_eval_runner import (
    AipEvalRunner,
    JudgeExecution,
    ResolvedArtifact,
    TargetExecution,
)
from aos_api.aip_model_governance_policy_contracts import (
    BudgetPolicyRevisionCreate,
    QuotaPolicyRevisionCreate,
)
from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
from aos_api.aip_model_runtime_contracts import (
    ModelModality,
    ModelPriceSnapshotRevision,
    ModelRouteCandidate,
    ModelRouteRevision,
    ModelRuntimeLifecycle,
    ProviderHealthObservation,
    ProviderInstanceRevision,
    RegisteredModelRevision,
    RouteStrategy,
    RuntimePolicyRevision,
)
from aos_api.aip_model_capacity_authority import (
    AipModelCapacityAuthorityStore,
    CapacityPoolRevisionCreate,
)
from aos_api.aip_model_capacity_reservation import AipModelCapacityReservationGate
from aos_api.aip_model_runtime_resolver import AipModelRuntimeResolver
from aos_api.aip_model_runtime_store import (
    AipModelRuntimeStore,
    ModelRuntimeNotFound,
    canonical_hash,
    evaluation_candidate_ref,
)
from aos_api.aip_network_policy_contracts import NetworkPolicyRevisionCreate
from aos_api.aip_network_policy_store import AipNetworkPolicyStore
from aos_api.aip_r1_bootstrap_probe import (
    AipR1BootstrapProbe,
    R1BootstrapProbeRequest,
)
from aos_api.aip_release_publication_models import DeriveReleaseGateRequest
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r1-runtime-bootstrap"
APPROVAL_REF = "35-R1-C"
WINDOW_START = datetime(2026, 8, 17, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
WINDOW_END = datetime(2026, 10, 15, 23, 59, 59, tzinfo=ZoneInfo("Asia/Shanghai"))
META_FIELDS = {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
GOLDSET_SIZE = 20
LIVE_MODEL_CASE_IDS = {"basic-01", "secret-01", "modality-01"}
PLACEHOLDER_GATE = VersionedAssetRef(
    assetType="EvalGateDecision",
    assetId="pending-r1-eval-gate",
    revision=1,
    contentHash="0" * 64,
)


def exact_ref(kind: str, item: Any) -> VersionedAssetRef:
    id_field = {
        "BudgetRevision": "budget_id",
        "QuotaPolicyRevision": "policy_id",
        "BudgetPolicyRevision": "policy_id",
        "NetworkPolicyRevision": "policy_id",
        "ProviderInstanceRevision": "provider_instance_id",
        "RuntimePolicyRevision": "policy_id",
        "ModelPriceSnapshotRevision": "price_snapshot_id",
        "RegisteredModelRevision": "registered_model_id",
        "ModelRouteRevision": "route_id",
    }[kind]
    return VersionedAssetRef(
        assetType=kind,
        assetId=getattr(item, id_field),
        revision=item.revision,
        contentHash=item.content_hash,
    )


def rehash_runtime(model: type, payload: dict[str, Any]):
    provisional = model.model_validate({**payload, "contentHash": "0" * 64})
    dumped = provisional.model_dump(mode="json", by_alias=True)
    content = {name: value for name, value in dumped.items() if name not in META_FIELDS}
    return model.model_validate({**payload, "contentHash": canonical_hash(content)})


def build_plan() -> dict[str, Any]:
    return {
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "approvalRef": APPROVAL_REF,
        "mode": "restricted-development",
        "steps": [
            "BudgetRevision",
            "QuotaPolicyRevision",
            "BudgetPolicyRevision",
            "ModelPriceSnapshotRevision",
            "NetworkPolicyRevision",
            "RuntimePolicyRevision",
            "ProviderInstanceRevision@3(active,timeout=60000)",
            "EvalDataset+20CaseModelAndRouteRuns",
            "RegisteredModelRevision+ModelRouteRevision",
            "ProviderHealthObservation+CapacityPoolRevision",
            "OperationalVerification",
        ],
        "forbiddenSideEffects": ["CapabilityBinding", "SkillBinding", "AgentRun"],
    }


def apply_prerequisites() -> dict[str, Any]:
    created_at = WINDOW_START.astimezone(UTC)
    runtime_store = AipModelRuntimeStore()
    governance_store = AipModelGovernancePolicyStore()
    provider_v1 = runtime_store.get_provider(SCOPE, "agnes-text-qyh-dev", 1)

    budget = AipBudgetAuthorityStore().publish(
        SCOPE,
        ACTOR,
        "r1-08-budget-qyh-text-dev-v1",
        BudgetRevisionCreate(
            budgetId="budget-qyh-text-dev",
            revision=1,
            dailyLimitMinor=500,
            monthlyLimitMinor=5000,
            alertThresholdPct=80,
            hardStop=True,
            unknownUsageBehavior="block",
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner="杜大同",
            overBudgetApprover="杜大同",
            lifecycle="active",
        ),
    )
    quota = governance_store.publish_quota(
        SCOPE,
        ACTOR,
        "r1-07-quota-qyh-text-dev-v1",
        QuotaPolicyRevisionCreate(
            policyId="quota-qyh-text-dev",
            revision=1,
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner="杜大同",
            approvalRef=APPROVAL_REF,
            lifecycle="active",
            maxConcurrency=2,
            maxInputTokens=8000,
            maxOutputTokens=2000,
            hourlyRequestLimit=50,
            dailyRequestLimit=200,
            reservationLeaseSeconds=60,
            overflowBehavior="reject",
            allowPublicProviderFallback=False,
            allowAutoScale=False,
        ),
    )
    budget_policy = governance_store.publish_budget(
        SCOPE,
        ACTOR,
        "r1-08-budget-policy-qyh-text-dev-v1",
        BudgetPolicyRevisionCreate(
            policyId="budget-policy-qyh-text-dev",
            revision=1,
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner="杜大同",
            approvalRef=APPROVAL_REF,
            lifecycle="active",
            budgetRevisionRef=exact_ref("BudgetRevision", budget),
            hardStop=True,
            unknownUsageBehavior="block",
            unknownPriceBehavior="block",
            allowZeroPrice=True,
            zeroPriceApprovalRef=APPROVAL_REF,
        ),
    )
    price = rehash_runtime(
        ModelPriceSnapshotRevision,
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "priceSnapshotId": "price-qyh-text-dev",
            "revision": 1,
            "currency": "CNY",
            "inputTokenPrice": 0,
            "outputTokenPrice": 0,
            "cachedTokenPrice": 0,
            "tokenUnit": 1000,
            "effectiveFrom": WINDOW_START,
            "effectiveUntil": WINDOW_END,
            "lifecycle": "active",
            "createdBy": ACTOR,
            "createdAt": created_at,
        },
    )
    price = runtime_store.publish_price_snapshot(
        SCOPE, ACTOR, "r1-08-price-qyh-text-dev-v1", price
    )
    network = AipNetworkPolicyStore().publish(
        SCOPE,
        ACTOR,
        "r1-04-network-qyh-text-dev-v1",
        NetworkPolicyRevisionCreate(
            policyId="network-qyh-text-dev",
            revision=1,
            allowedSchemes=["https"],
            allowedHosts=["apihub.agnes-ai.com"],
            allowedPorts=[443],
            tlsRequired=True,
            publicFallbackAllowed=False,
            egressPolicyRef=provider_v1.egress_policy_ref,
            effectiveFrom=WINDOW_START,
            effectiveUntil=WINDOW_END,
            owner="杜大同",
            approvalRef=APPROVAL_REF,
            lifecycle="active",
        ),
    )
    policy = rehash_runtime(
        RuntimePolicyRevision,
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "policyId": "policy-qyh-text-dev",
            "revision": 1,
            "networkPolicyRef": exact_ref("NetworkPolicyRevision", network),
            "egressPolicyRef": provider_v1.egress_policy_ref,
            "dataClassificationPolicyRef": provider_v1.data_classification_policy_ref,
            "quotaPolicyRef": exact_ref("QuotaPolicyRevision", quota),
            "budgetPolicyRef": exact_ref("BudgetPolicyRevision", budget_policy),
            "deadlineMs": 60000,
            "maxAttempts": 1,
            "allowedFallbackReasons": [],
            "unknownUsageBehavior": "block",
            "unknownPriceBehavior": "block",
            "killSwitchEnabled": False,
            "lifecycle": "active",
            "createdBy": ACTOR,
            "createdAt": created_at,
        },
    )
    policy = runtime_store.publish_policy(
        SCOPE, ACTOR, "r1-04-policy-qyh-text-dev-v1", policy
    )
    provider_payload = provider_v1.model_dump(mode="json", by_alias=True)
    provider_payload.update(
        revision=2,
        lifecycle=ModelRuntimeLifecycle.ACTIVE.value,
        createdBy=ACTOR,
        createdAt=created_at,
    )
    provider_payload.pop("contentHash", None)
    provider_v2 = rehash_runtime(ProviderInstanceRevision, provider_payload)
    provider_v2 = runtime_store.publish_provider(
        SCOPE,
        ACTOR,
        "r1-02-provider-agnes-text-qyh-dev-v2-active",
        provider_v2,
        expected_version=1,
    )
    assets = [budget, quota, budget_policy, price, network, policy, provider_v2]
    return {
        "status": "prerequisites-published",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "assets": [
            {
                "type": type(item).__name__,
                "id": next(
                    getattr(item, field)
                    for field in (
                        "budget_id",
                        "policy_id",
                        "price_snapshot_id",
                        "provider_instance_id",
                    )
                    if hasattr(item, field)
                ),
                "revision": item.revision,
                "contentHash": item.content_hash,
            }
            for item in assets
        ],
        "forbiddenSideEffects": ["CapabilityBinding", "SkillBinding", "AgentRun"],
    }


def _load_goldset(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or len(payload) != GOLDSET_SIZE:
        raise ValueError(f"approved GoldSet must contain exactly {GOLDSET_SIZE} cases")
    required = {
        "caseId",
        "kind",
        "prompt",
        "expectedBehavior",
        "routeTaskType",
        "routeInputModality",
        "routeCapability",
        "routeExpected",
    }
    ids: set[str] = set()
    for case in payload:
        if not isinstance(case, dict) or set(case) != required:
            raise ValueError("GoldSet case schema drifted")
        if not all(isinstance(case[name], str) and case[name].strip() for name in required):
            raise ValueError("GoldSet values must be non-blank strings")
        if case["caseId"] in ids:
            raise ValueError("GoldSet case ids must be unique")
        EvalCaseKind(case["kind"])
        if case["expectedBehavior"] not in {"non_empty", "refusal"}:
            raise ValueError("GoldSet expectedBehavior must be non_empty or refusal")
        if case["routeExpected"] not in {"SELECT", "BLOCK"}:
            raise ValueError("GoldSet routeExpected must be SELECT or BLOCK")
        ids.add(case["caseId"])
    return payload


def _artifact(artifact_id: str, artifact_type: str, value: Any) -> ArtifactRef:
    return ArtifactRef(
        artifactId=artifact_id,
        artifactType=artifact_type,
        revision="1",
        contentHash=canonical_hash(value),
    )


def _asset_target(ref: VersionedAssetRef) -> AssetRevisionRef:
    asset_type = {
        "RegisteredModelRevision": AssetType.REGISTERED_MODEL,
        "ModelRouteRevision": AssetType.MODEL_ROUTE,
    }[ref.asset_type]
    return AssetRevisionRef(
        assetType=asset_type,
        assetId=ref.asset_id,
        revision=str(ref.revision),
        contentHash=ref.content_hash,
    )


def _gate_ref(gate) -> VersionedAssetRef:
    return VersionedAssetRef(
        assetType="EvalGateDecision",
        assetId=gate.decision_id,
        revision=1,
        contentHash=gate.decision_hash,
    )


def _find_passed_gate(target: AssetRevisionRef):
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            """SELECT * FROM aip_release_gate_decision
            WHERE org_id=%s AND project_id=%s AND target_ref=%s::jsonb
              AND status='passed' AND invalidated_by IS NULL AND expires_at>NOW()
            ORDER BY decided_at DESC LIMIT 1""",
            (*SCOPE.key, json.dumps(target.model_dump(mode="json", by_alias=True), sort_keys=True)),
        ).fetchone()
    if not row:
        return None
    ref = VersionedAssetRef(
        assetType="EvalGateDecision",
        assetId=row["decision_id"],
        revision=1,
        contentHash=row["decision_hash"],
    )
    return ref


def _eval_attempt(target: AssetRevisionRef) -> int:
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS count FROM aip_eval_run
            WHERE org_id=%s AND project_id=%s AND target_ref=%s::jsonb""",
            (*SCOPE.key, json.dumps(target.model_dump(mode="json", by_alias=True), sort_keys=True)),
        ).fetchone()
    return int(row["count"]) + 1


def _register_goldset(cases: list[dict[str, Any]]) -> DatasetRevisionRef:
    source_index = [
        {
            "caseId": case["caseId"],
            "promptHash": canonical_hash(case["prompt"]),
            "expectedBehavior": case["expectedBehavior"],
        }
        for case in cases
    ]
    source_hash = canonical_hash(source_index)
    dataset = DatasetRevisionRef(
        datasetId=f"goldset-qyh-text-dev-{source_hash[:12]}",
        revision=1,
        contentHash=canonical_hash({"sourceHash": source_hash, "caseCount": len(cases)}),
        sourceHash=source_hash,
        redactionPolicy=AssetRevisionRef(
            assetType=AssetType.POLICY,
            assetId="redaction-approved-development-sample",
            revision="1",
            contentHash=canonical_hash("redaction-approved-development-sample@1"),
        ),
    )
    manifest = EvalDatasetManifest(
        sourceKind=DatasetSourceKind.ARTIFACT_SNAPSHOT,
        sourceId="approved-r1-development-goldset",
        sourceRevision="1",
        sourceHash=source_hash,
        fieldsAllowlist=[
            "caseId",
            "kind",
            "promptHash",
            "expectedBehavior",
            "routeTaskType",
            "routeInputModality",
            "routeCapability",
            "routeExpected",
        ],
        redactionReceipt=_artifact(
            "r1-goldset-redaction-receipt",
            "redaction_receipt",
            {"pii": "none", "caseCount": len(cases), "approvalRef": APPROVAL_REF},
        ),
        piiState=DatasetPiiState.NONE,
        caseCount=len(cases),
        capturedAt=WINDOW_START.astimezone(UTC),
    )
    return AipEvalPackRegistry().register_dataset_revision(
        SCOPE, dataset, manifest, actor=ACTOR
    )


def _suite(
    *,
    target: AssetRevisionRef,
    dataset: DatasetRevisionRef,
    cases: list[dict[str, Any]],
    mode: str,
) -> EvalSuiteRevision:
    definitions = []
    for case in cases:
        expected = (
            {
                "status": "PASS",
                "evidence": (
                    "live_provider_probe"
                    if case["caseId"] in LIVE_MODEL_CASE_IDS
                    else "policy_contract"
                ),
            }
            if mode == "model"
            else case["routeExpected"]
        )
        definitions.append(
            EvalCaseDefinition(
                caseId=case["caseId"],
                kind=EvalCaseKind(case["kind"]),
                inputArtifact=_artifact(
                    f"r1-{mode}-input-{case['caseId']}", "eval_input", case
                ),
                expectedArtifact=_artifact(
                    f"r1-{mode}-expected-{case['caseId']}", "eval_expected", expected
                ),
                timeoutMs=60_000,
            )
        )
    suite = EvalSuiteRevision(
        suiteId=(
            f"r1-{mode}-goldset-qyh-text-dev-{dataset.content_hash[:12]}-"
            f"{target.content_hash[:12]}-v2"
        ),
        revision=1,
        contentHash="0" * 64,
        target=target,
        dataset=dataset,
        judge=JudgeRevisionRef(
            judgeId="r1-restricted-exact-judge",
            revision=1,
            contentHash=canonical_hash("r1-restricted-exact-judge@1"),
        ),
        cases=definitions,
        gateThreshold=1.0,
    )
    return suite.model_copy(update={"content_hash": compute_eval_suite_hash(suite)})


def _derive_gate(
    *,
    target_ref: VersionedAssetRef,
    cases: list[dict[str, Any]],
    dataset: DatasetRevisionRef,
    mode: str,
    provider_ref: VersionedAssetRef,
    network_ref: VersionedAssetRef,
    route_candidate: ModelRouteRevision | None = None,
    probe_results: list[Any] | None = None,
) -> VersionedAssetRef:
    target = _asset_target(target_ref)
    existing = _find_passed_gate(target)
    if existing:
        return existing

    suite = _suite(target=target, dataset=dataset, cases=cases, mode=mode)
    AipEvalPackRegistry().register_suite_revision(SCOPE, suite, actor=ACTOR)
    values: dict[str, Any] = {}
    for case, definition in zip(cases, suite.cases, strict=True):
        values[definition.input_artifact.artifact_id] = case
        values[definition.expected_artifact.artifact_id] = (
            {
                "status": "PASS",
                "evidence": (
                    "live_provider_probe"
                    if case["caseId"] in LIVE_MODEL_CASE_IDS
                    else "policy_contract"
                ),
            }
            if mode == "model"
            else case["routeExpected"]
        )

    def resolve(ref: ArtifactRef) -> ResolvedArtifact:
        value = values[ref.artifact_id]
        return ResolvedArtifact(reference=ref, value=value)

    probe = AipR1BootstrapProbe()

    def execute(target_ref_: AssetRevisionRef, value: dict[str, Any]) -> TargetExecution:
        if mode == "model":
            evidence = "policy_contract"
            if value["caseId"] in LIVE_MODEL_CASE_IDS:
                result = probe.run(
                    SCOPE,
                    R1BootstrapProbeRequest(
                        provider=provider_ref,
                        networkPolicy=network_ref,
                        providerModelId="agnes-2.0-flash",
                        dataClassification="approved_development_sample",
                        prompt=value["prompt"],
                        expectedResponseBehavior=value["expectedBehavior"],
                        approvalRef=APPROVAL_REF,
                    ),
                )
                if result.response_contract_passed is not True:
                    raise RuntimeError("model eval response contract did not pass")
                if probe_results is not None:
                    probe_results.append(result)
                evidence = "live_provider_probe"
            actual = {"status": "PASS", "evidence": evidence}
        else:
            if route_candidate is None:
                raise RuntimeError("route candidate is required")
            selectable = (
                value["routeTaskType"] in route_candidate.task_types
                and value["routeInputModality"]
                == route_candidate.required_input_modality.value
                and value["routeCapability"] in route_candidate.required_capabilities
            )
            actual = "SELECT" if selectable else "BLOCK"
        return TargetExecution(target=target_ref_, value=actual)

    def judge(ref, actual, expected) -> JudgeExecution:
        return JudgeExecution(
            judge=ref,
            passed=actual == expected,
            detail_code="exact_contract_match" if actual == expected else "contract_mismatch",
        )

    report = AipEvalRunner().run(
        SCOPE,
        suite_id=suite.suite_id,
        suite_revision=suite.revision,
        idempotency_key=(
            f"r1-{mode}-goldset-run-{target_ref.content_hash[:16]}-"
            f"attempt-{_eval_attempt(target)}"
        ),
        actor=ACTOR,
        resolve_artifact=resolve,
        execute_target=execute,
        execute_judge=judge,
    )
    gate = AipReleasePublicationService().derive_gate(
        SCOPE,
        actor=ACTOR,
        request=DeriveReleaseGateRequest(
            reportId=report.report_id,
            reportRevision=report.revision,
            reportHash=report.content_hash,
            idempotencyKey=f"r1-{mode}-gate-{target_ref.content_hash[:16]}",
        ),
    )
    return _gate_ref(gate)


def _refresh_health(
    cases: list[dict[str, Any]],
    provider_ref: VersionedAssetRef,
    network_ref: VersionedAssetRef,
    existing_results: list[Any] | None = None,
) -> ProviderHealthObservation:
    results = list(existing_results or [])
    probe = AipR1BootstrapProbe()
    for case in cases[: max(0, 3 - len(results))]:
        results.append(
            probe.run(
                SCOPE,
                R1BootstrapProbeRequest(
                    provider=provider_ref,
                    networkPolicy=network_ref,
                    providerModelId="agnes-2.0-flash",
                    dataClassification="approved_development_sample",
                    prompt=case["prompt"],
                    expectedResponseBehavior=case["expectedBehavior"],
                    approvalRef=APPROVAL_REF,
                ),
            )
        )
    observed_at = max(result.observed_at for result in results)
    latencies = sorted(result.latency_ms for result in results)
    observation = ProviderHealthObservation(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        observationId=f"health-agnes-text-qyh-dev-r1-{observed_at:%Y%m%d%H%M%S}",
        provider=provider_ref,
        status="healthy",
        availabilityPct=100,
        p50LatencyMs=latencies[len(latencies) // 2],
        observedAt=observed_at,
        expiresAt=observed_at + timedelta(minutes=15),
    )
    return AipModelRuntimeStore().record_health(
        SCOPE,
        ACTOR,
        f"r1-health-{observed_at:%Y%m%d%H%M%S}",
        observation,
    )


def _latest_fresh_health(
    provider_ref: VersionedAssetRef,
) -> ProviderHealthObservation | None:
    with db_connect(SCOPE) as conn:
        row = conn.execute(
            """SELECT * FROM aip_provider_health_observation
            WHERE org_id=%s AND project_id=%s
              AND provider_ref->>'assetId'=%s
              AND provider_ref->>'contentHash'=%s
              AND status='healthy' AND expires_at>NOW()
            ORDER BY observed_at DESC LIMIT 1""",
            (*SCOPE.key, provider_ref.asset_id, provider_ref.content_hash),
        ).fetchone()
    if not row:
        return None
    return ProviderHealthObservation(
        tenant=TenantContext(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        observationId=row["observation_id"],
        provider=row["provider_ref"],
        status=row["status"],
        availabilityPct=row["availability_pct"],
        p50LatencyMs=row["p50_latency_ms"],
        observedAt=row["observed_at"],
        expiresAt=row["expires_at"],
    )


def apply_runtime(goldset_path: Path) -> dict[str, Any]:
    cases = _load_goldset(goldset_path)
    store = AipModelRuntimeStore()
    try:
        provider = store.get_provider(SCOPE, "agnes-text-qyh-dev", 3)
    except ModelRuntimeNotFound:
        provider_v2 = store.get_provider(SCOPE, "agnes-text-qyh-dev", 2)
        provider_payload = provider_v2.model_dump(mode="json", by_alias=True)
        endpoint = dict(provider_payload["endpointProfile"])
        endpoint["timeoutMs"] = 60_000
        provider_payload.update(
            revision=3,
            endpointProfile=endpoint,
            createdBy=ACTOR,
            createdAt=datetime.now(UTC),
        )
        provider_payload.pop("contentHash", None)
        provider = store.publish_provider(
            SCOPE,
            ACTOR,
            "r1-02-provider-agnes-text-qyh-dev-v3-timeout-aligned",
            rehash_runtime(ProviderInstanceRevision, provider_payload),
            expected_version=2,
        )
    policy = store.get_policy(SCOPE, "policy-qyh-text-dev", 1)
    price = store.get_price_snapshot(SCOPE, "price-qyh-text-dev", 1)
    governance = AipModelGovernancePolicyStore()
    quota = governance.get_quota(SCOPE, "quota-qyh-text-dev", 1)
    budget_policy = governance.get_budget(SCOPE, "budget-policy-qyh-text-dev", 1)
    network = AipNetworkPolicyStore().get(SCOPE, "network-qyh-text-dev", 1)
    provider_ref = exact_ref("ProviderInstanceRevision", provider)
    network_ref = exact_ref("NetworkPolicyRevision", network)
    dataset = _register_goldset(cases)
    probe_results: list[Any] = []
    created_at = WINDOW_START.astimezone(UTC)

    model_payload = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "registeredModelId": "model-qyh-text-dev",
        "revision": 1,
        "provider": provider_ref,
        "providerModelId": "agnes-2.0-flash",
        "inputModalities": [ModelModality.TEXT],
        "outputModalities": [ModelModality.TEXT],
        "capabilities": ["llm", "chat", "structured_output"],
        "contextWindow": 32_768,
        "quotaPolicyRef": exact_ref("QuotaPolicyRevision", quota),
        "budgetPolicyRef": exact_ref("BudgetPolicyRevision", budget_policy),
        "priceSnapshotRef": exact_ref("ModelPriceSnapshotRevision", price),
        "evalGateRef": PLACEHOLDER_GATE,
        "lifecycle": ModelRuntimeLifecycle.ACTIVE,
        "createdBy": ACTOR,
        "createdAt": created_at,
    }
    model_candidate = rehash_runtime(RegisteredModelRevision, model_payload)
    model_gate = _derive_gate(
        target_ref=evaluation_candidate_ref(model_candidate),
        cases=cases,
        dataset=dataset,
        mode="model",
        provider_ref=provider_ref,
        network_ref=network_ref,
        probe_results=probe_results,
    )
    model = rehash_runtime(
        RegisteredModelRevision, {**model_payload, "evalGateRef": model_gate}
    )
    model = store.publish_model(
        SCOPE, ACTOR, "r1-model-qyh-text-dev-v1", model
    )

    route_payload = {
        "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "routeId": "route-qyh-text-dev",
        "revision": 1,
        "taskTypes": ["copy.generate", "chat.answer", "analysis.summarize"],
        "requiredInputModality": ModelModality.TEXT,
        "requiredOutputModality": ModelModality.TEXT,
        "requiredCapabilities": ["llm", "chat"],
        "candidates": [
            ModelRouteCandidate(model=exact_ref("RegisteredModelRevision", model))
        ],
        "strategy": RouteStrategy.FAILOVER,
        "runtimePolicyRef": exact_ref("RuntimePolicyRevision", policy),
        "evalGateRef": PLACEHOLDER_GATE,
        "lifecycle": ModelRuntimeLifecycle.ACTIVE,
        "createdBy": ACTOR,
        "createdAt": created_at,
    }
    route_candidate = rehash_runtime(ModelRouteRevision, route_payload)
    route_gate = _derive_gate(
        target_ref=evaluation_candidate_ref(route_candidate),
        cases=cases,
        dataset=dataset,
        mode="route",
        provider_ref=provider_ref,
        network_ref=network_ref,
        route_candidate=route_candidate,
    )
    route = rehash_runtime(
        ModelRouteRevision, {**route_payload, "evalGateRef": route_gate}
    )
    route = store.publish_route(
        SCOPE, ACTOR, "r1-route-qyh-text-dev-v1", route
    )
    capacity = AipModelCapacityAuthorityStore().publish(
        SCOPE,
        ACTOR,
        "r1-capacity-qyh-text-dev-v1",
        CapacityPoolRevisionCreate(
            poolId="capacity-qyh-text-dev",
            revision=1,
            routeRef=exact_ref("ModelRouteRevision", route),
            modelRef=exact_ref("RegisteredModelRevision", model),
            providerRef=provider_ref,
            maxConcurrency=2,
            maxTokenUnits=10_000,
            tokenUnitPerReservation=2_000,
            leaseSeconds=60,
            lifecycle="active",
        ),
    )
    health = _latest_fresh_health(provider_ref) or _refresh_health(
        cases, provider_ref, network_ref, existing_results=probe_results
    )
    resolution = AipModelRuntimeResolver(store=store).resolve(
        SCOPE, route.route_id, now=datetime.now(UTC)
    )
    if resolution.readiness.value != "ready":
        raise RuntimeError(f"runtime resolver blocked: {resolution.blocker_codes}")
    return {
        "status": "runtime-ready",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "assets": {
            "model": exact_ref("RegisteredModelRevision", model).model_dump(mode="json", by_alias=True),
            "route": exact_ref("ModelRouteRevision", route).model_dump(mode="json", by_alias=True),
            "capacity": {
                "assetId": capacity.pool_id,
                "revision": capacity.revision,
                "contentHash": capacity.content_hash,
            },
            "health": {"observationId": health.observation_id, "expiresAt": health.expires_at},
        },
        "goldSetCases": len(cases),
        "readiness": resolution.readiness.value,
        "forbiddenSideEffects": ["CapabilityBinding", "SkillBinding", "AgentRun"],
    }


def verify_runtime() -> dict[str, Any]:
    """Verify the live R1 chain without creating a Binding or AgentRun."""
    store = AipModelRuntimeStore()
    resolver = AipModelRuntimeResolver(store=store)
    now = datetime.now(UTC)
    resolution = resolver.resolve(SCOPE, "route-qyh-text-dev", now=now)
    if resolution.readiness.value != "ready":
        raise RuntimeError(f"runtime resolver blocked: {resolution.blocker_codes}")

    with db_connect(SCOPE) as conn:
        before = {
            table: int(
                conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            )
            for table in ("aip_capability_binding", "aip_skill_binding", "aip_agent_run")
        }
        active = conn.execute(
            """SELECT COUNT(*) AS count FROM aip_model_capacity_reservation
               WHERE pool_id=%s AND status IN ('reserved','consumed') AND expires_at>NOW()""",
            ("capacity-qyh-text-dev",),
        ).fetchone()
        if int(active["count"]) != 0:
            raise RuntimeError("capacity verification requires an idle exact pool")
        health = conn.execute(
            """SELECT observation_id,expires_at FROM aip_provider_health_observation
               WHERE provider_ref->>'assetId'=%s AND status='healthy'
               ORDER BY observed_at DESC LIMIT 1""",
            (resolution.selected_provider.asset_id,),
        ).fetchone()
        gates = conn.execute(
            """SELECT decision_id,expires_at,status FROM aip_release_gate_decision
               WHERE decision_id IN (%s,%s) ORDER BY decision_id""",
            (
                store.get_model(SCOPE, "model-qyh-text-dev", 1).eval_gate_ref.asset_id,
                store.get_route(SCOPE, "route-qyh-text-dev", 1).eval_gate_ref.asset_id,
            ),
        ).fetchall()
        eval_runs = conn.execute(
            """SELECT status,COUNT(*) AS count FROM aip_eval_run
               WHERE target_ref->>'assetId' IN (%s,%s)
               GROUP BY status ORDER BY status""",
            ("model-qyh-text-dev", "route-qyh-text-dev"),
        ).fetchall()
    if health is None or len(gates) != 2 or any(row["status"] != "passed" for row in gates):
        raise RuntimeError("health or exact Eval gate evidence is incomplete")

    gate = AipModelCapacityReservationGate()
    run_prefix = f"r1-capacity-verification-{now:%Y%m%d%H%M%S%f}"
    reservations: list[str] = []
    capacity_blocker = None
    try:
        for index in (1, 2):
            reservations.append(gate.reserve(SCOPE, resolution, f"{run_prefix}-{index}"))
        try:
            gate.reserve(SCOPE, resolution, f"{run_prefix}-3")
        except AipAgentRegistryTransitionBlocked as exc:
            capacity_blocker = str(exc)
        if capacity_blocker != "capacity_concurrency_exhausted":
            raise RuntimeError("third capacity reservation did not fail closed")
        drifted = resolution.model_copy(
            update={
                "selected_model": resolution.selected_model.model_copy(
                    update={"content_hash": "0" * 64}
                )
            }
        )
        try:
            gate.reserve(SCOPE, drifted, f"{run_prefix}-drift")
        except AipAgentRegistryTransitionBlocked as exc:
            drift_blocker = str(exc)
        else:
            raise RuntimeError("drifted exact model unexpectedly reserved capacity")
    finally:
        for reservation_id in reservations:
            gate.release(SCOPE, reservation_id)

    canary_blocker = None
    try:
        resolver.resolve(CANARY_SCOPE, "route-qyh-text-dev", now=now)
    except ModelRuntimeNotFound as exc:
        canary_blocker = str(exc)
    if not canary_blocker:
        raise RuntimeError("negative tenant canary unexpectedly resolved the real route")

    health_expired = resolver.resolve(
        SCOPE, "route-qyh-text-dev", now=health["expires_at"] + timedelta(seconds=1)
    )
    gate_expired = resolver.resolve(
        SCOPE,
        "route-qyh-text-dev",
        now=max(row["expires_at"] for row in gates) + timedelta(seconds=1),
    )
    price = store.get_price_snapshot(SCOPE, "price-qyh-text-dev", 1)
    price_expired = resolver.resolve(
        SCOPE, "route-qyh-text-dev", now=price.effective_until + timedelta(seconds=1)
    )

    with db_connect(SCOPE) as conn:
        after = {
            table: int(
                conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            )
            for table in ("aip_capability_binding", "aip_skill_binding", "aip_agent_run")
        }
        reservation_rows = conn.execute(
            """SELECT status,COUNT(*) AS count FROM aip_model_capacity_reservation
               WHERE agent_run_id LIKE %s GROUP BY status ORDER BY status""",
            (f"{run_prefix}%",),
        ).fetchall()
    with db_connect(CANARY_SCOPE) as conn:
        canary_counts = {
            table: int(
                conn.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()["count"]
            )
            for table in (
                "aip_registered_model_head",
                "aip_model_route_head",
                "aip_model_capacity_pool_head",
            )
        }
    if before != after:
        raise RuntimeError("forbidden R2 side-effect counts changed")
    if any(canary_counts.values()):
        raise RuntimeError("negative tenant canary can see runtime authority")

    return {
        "status": "runtime-operational-verification-passed",
        "verifiedAt": now,
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "readiness": resolution.readiness.value,
        "exactRefs": {
            "route": resolution.route.model_dump(mode="json", by_alias=True),
            "model": resolution.selected_model.model_dump(mode="json", by_alias=True),
            "provider": resolution.selected_provider.model_dump(mode="json", by_alias=True),
            "price": resolution.selected_price_snapshot.model_dump(mode="json", by_alias=True),
        },
        "evalRuns": {row["status"]: int(row["count"]) for row in eval_runs},
        "evalGates": [
            {"decisionId": row["decision_id"], "status": row["status"], "expiresAt": row["expires_at"]}
            for row in gates
        ],
        "capacity": {
            "reserved": len(reservations),
            "thirdReservationBlocker": capacity_blocker,
            "driftBlocker": drift_blocker,
            "terminalRows": {row["status"]: int(row["count"]) for row in reservation_rows},
        },
        "failClosed": {
            "canary": canary_blocker,
            "healthExpiry": health_expired.blocker_codes,
            "gateExpiry": gate_expired.blocker_codes,
            "priceExpiry": price_expired.blocker_codes,
        },
        "negativeCanaryCounts": canary_counts,
        "forbiddenSideEffectsBefore": before,
        "forbiddenSideEffectsAfter": after,
    }


def main() -> int:
    # Third-party DEBUG traces may include transient response cookies.  This
    # restricted bootstrap emits only its sanitized terminal JSON contract.
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply-prerequisites", action="store_true")
    parser.add_argument("--apply-runtime", action="store_true")
    parser.add_argument("--verify-runtime", action="store_true")
    parser.add_argument("--goldset-file", type=Path)
    args = parser.parse_args()
    if sum((args.apply_prerequisites, args.apply_runtime, args.verify_runtime)) > 1:
        parser.error("choose only one apply or verify mode")
    if args.verify_runtime:
        result = verify_runtime()
    elif args.apply_runtime:
        if args.goldset_file is None:
            parser.error("--apply-runtime requires --goldset-file")
        result = apply_runtime(args.goldset_file)
    elif args.apply_prerequisites:
        result = apply_prerequisites()
    else:
        result = build_plan()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
