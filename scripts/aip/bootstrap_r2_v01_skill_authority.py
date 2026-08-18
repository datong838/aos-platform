#!/usr/bin/env python3
"""Publish the exact V01 Skill/Capability control chain for the R2 pilot.

Dry-run is the default. ``--apply`` persists only governance metadata and
isolated contract evidence. It never resolves a Secret, calls a Provider,
creates a Binding, activates an AgentInstance, or creates an AgentRun.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_agent_registry_contracts import (
    CapabilityReadiness,
    PublishCapabilityRevisionRequest,
    PublishEvaluatedSkillRevisionRequest,
    PublishSkillTemplateRequest,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_agent_registry_store import (
    AipAgentRegistryNotFound,
    AipAgentRegistryStore,
)
from aos_api.aip_capability_registry import AipCapabilityRegistry
from aos_api.aip_contracts import ArtifactRef, PlanStep, ResourceRef
from aos_api.aip_v01_pilot import V01_GRAPH_ID, evaluate_i01_contract
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
from aos_api.aip_logic_graph_store import LogicGraphStore
from aos_api.aip_logic_runtime_adapters import (
    LLMAdapterResult,
    LogicAdapterError,
    RuntimeAdapterRegistry,
)
from aos_api.aip_logic_dry_run_models import LogicTokenUsage
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    canonical_hash as production_contract_hash,
)
from aos_api.aip_production_contracts import (
    Coverage,
    CreateBriefRequest,
    CreateEvalContractRequest,
    CreateEvidenceBundleRequest,
    ExactRevisionRef,
    Freshness,
)
from aos_api.aip_release_publication_models import (
    DeriveReleaseGateRequest,
    PublishReleaseRequest,
)
from aos_api.aip_release_publication_service import AipReleasePublicationService
from aos_api.aip_skill_publication_service import AipSkillPublicationService
from aos_api.aip_skill_registry import AipSkillRegistry
from aos_api.aip_task_models import CreatePlanRevisionRequest, CreateTaskRequest, CreateTaskRunRequest
from aos_api.aip_task_store import AipTaskStore
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r2-v01-skill-bootstrap"
APPROVAL_REF = "46-R2-V01-VIDEO-DRAFT"
SKILL_ID = "ecommerce.skill.V01"
CAPABILITY_ID = "video.generate"
ROUTE_ID = "route-qyh-video-dev"
POLICY_ID = "policy-qyh-video-dev"
MODEL_ID = "model-qyh-video-dev"
SUITE_ID = "ecommerce.skill.V01.contract.v1"
DATASET_ID = "ecommerce.skill.V01.contract-cases.v1"
TASK_KEY = "r2-v01-governance-task-v1"
REQUIRED_ALEMBIC_HEAD = "aip10_006"
SCHEMA_HASH = "c3e4f9503222fed59eb150f6ac89b3fb49991123f15699fb36c9702ab35048b7"
POLICY_HASH = "2ff91b4c0b34906fcc18b40a467cb786835d6168a6301f8abc9647476417cd4f"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


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
        "approvalRef": APPROVAL_REF,
        "steps": [
            "create canonical governance Task/Plan/TaskRun Evidence",
            "freeze TaskBrief and EvidenceBundle",
            "run six-case isolated skill-specific Eval",
            "derive exact Skill release gate and publication event",
            "freeze V01 EvalContract",
            "ensure video.generate r1 and V01 Skill r1 exist",
            "publish immutable V01 Skill r2 and video.generate r2",
            "verify exact readback and negative tenant canary",
        ],
        "forbiddenSideEffects": [
            "Secret payload read",
            "Provider call",
            "ProviderHealth refresh",
            "CapabilityBinding",
            "SkillBinding",
            "AgentInstance activation",
            "AgentRun",
        ],
    }


def _require_schema_head() -> None:
    with db_connect(SCOPE) as conn:
        row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
    current = str(row["version_num"]) if row else ""
    if current != REQUIRED_ALEMBIC_HEAD:
        raise RuntimeError(f"schema head must be {REQUIRED_ALEMBIC_HEAD}; current={current or 'missing'}")


def _isolated_registry(model_alias: str) -> RuntimeAdapterRegistry:
    registry = RuntimeAdapterRegistry(max_concurrency=1)

    def invoke(prompt, context):
        context.checkpoint()
        if "__simulate_adapter_error__" in prompt:
            raise LogicAdapterError("LLM_ADAPTER_FAILED", "isolated V01 adapter failure")
        return LLMAdapterResult(
            output="isolated V01 contract draft; not Provider quality evidence",
            usage=LogicTokenUsage(
                model=model_alias,
                input_tokens=16,
                output_tokens=8,
                total_tokens=24,
            ),
        )

    registry.register_llm(
        model_alias,
        invoke,
        adapter_name="v01-isolated-skill-contract-eval",
        read_only=True,
        dry_run_safe=True,
    )
    return registry


def _model_alias(model: Any) -> str:
    return f"RegisteredModelRevision:{model.registered_model_id}@{model.revision}#{model.content_hash}"


def _governance_evidence() -> tuple[ExactRevisionRef, ExactRevisionRef]:
    tasks = AipTaskStore()
    task = tasks.create_task(
        SCOPE,
        ACTOR,
        TASK_KEY,
        CreateTaskRequest(
            type="aip.governance",
            title="R2 V01 Skill 发布治理审批",
            description="记录 46 号清单批准范围与隔离评测事实，不包含外部 Provider 调用。",
            goal={"approvalRef": APPROVAL_REF, "skillId": SKILL_ID},
        ),
    )
    with db_connect(SCOPE) as conn:
        plan_row = conn.execute(
            "SELECT * FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND task_id=%s ORDER BY revision DESC LIMIT 1",
            (*SCOPE.key, task.id),
        ).fetchone()
    if plan_row is None:
        plan = tasks.create_plan(
            SCOPE,
            ACTOR,
            task.id,
            f"{TASK_KEY}-plan",
            CreatePlanRevisionRequest(
                expected_task_version=task.version,
                steps=[PlanStep(step_key="approve-i01", title="核验并记录 V01 受限发布范围")],
                risk={"providerCalls": 0, "externalActions": False},
            ),
        )
    else:
        plan = tasks._plan(plan_row)
    task = tasks.get_task(SCOPE, task.id)
    if plan.approval_status == "draft":
        plan = tasks.approve_plan(
            SCOPE,
            ACTOR,
            task.id,
            plan.revision,
            task.version,
            plan.content_hash,
        )
    task = tasks.get_task(SCOPE, task.id)
    with db_connect(SCOPE) as conn:
        run_row = conn.execute(
            "SELECT * FROM aip_task_run WHERE org_id=%s AND project_id=%s AND task_id=%s ORDER BY created_at DESC LIMIT 1",
            (*SCOPE.key, task.id),
        ).fetchone()
    run = (
        tasks._run(run_row)
        if run_row is not None
        else tasks.create_run(
            SCOPE,
            ACTOR,
            task.id,
            f"{TASK_KEY}-run",
            CreateTaskRunRequest(
                plan_revision_id=plan.id,
                expected_task_version=task.version,
                logic_graph_id=V01_GRAPH_ID,
                logic_revision=1,
            ),
        )
    )
    task = tasks.get_task(SCOPE, task.id)
    if run.status.value == "queued":
        control = tasks.start_run(
            SCOPE,
            run.id,
            expected_run_version=run.version,
            expected_task_version=task.version,
            actor=ACTOR,
            idempotency_key=f"{TASK_KEY}-start",
        )
        run, task = control.run, control.task
    if run.status.value == "running":
        with db_connect(SCOPE) as conn:
            step = conn.execute(
                "SELECT * FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_key='approve-i01' ORDER BY attempt DESC LIMIT 1",
                (*SCOPE.key, run.id),
            ).fetchone()
        if step is None or step["status"] != "succeeded":
            lease = tasks.claim_step(SCOPE, run.id, "approve-i01", ACTOR, lease_seconds=300)
            for phase, payload in (
                ("think", {"approvalRef": APPROVAL_REF, "decision": "restricted_v01_only"}),
                ("act", {"providerCalls": 0, "externalActions": False, "tenant": SCOPE.org_id}),
                ("verify", {"logicId": V01_GRAPH_ID, "skillId": SKILL_ID, "scopeExact": True}),
                ("observe", {"outcome": "approved", "licenseBasis": "internal use; restricted text only"}),
            ):
                tasks.record_step_phase(SCOPE, lease.step_run_id, ACTOR, ACTOR, phase, payload)
            tasks.complete_step(SCOPE, lease.step_run_id, ACTOR, ACTOR)
        tasks.complete_run(SCOPE, run.id)
    with db_connect(SCOPE) as conn:
        evidence = conn.execute(
            """SELECT e.* FROM aip_evidence e
               JOIN aip_task_run r ON r.org_id=e.org_id AND r.project_id=e.project_id AND r.run_id=e.run_id
               WHERE e.org_id=%s AND e.project_id=%s AND r.task_id=%s AND e.evidence_type='taor.observe'
               ORDER BY e.created_at DESC LIMIT 1""",
            (*SCOPE.key, task.id),
        ).fetchone()
    if evidence is None:
        raise RuntimeError("canonical governance Evidence is missing")
    contracts = AipProductionContractStore()
    brief = contracts.create_brief(
        SCOPE,
        ACTOR,
        f"{TASK_KEY}-brief",
        CreateBriefRequest(
            task_id=task.id,
            brief_type="aip.skill-publication.approval",
            schema_ref=ResourceRef(
                resource_type="Schema",
                resource_id="AipRestrictedSkillPublicationApproval.v1",
                revision="1",
                authority="aip-contract",
            ),
            spec={"approvalRef": APPROVAL_REF, "skillId": SKILL_ID, "providerCalls": 0},
        ),
    )
    brief = contracts.get_brief(SCOPE, brief.brief_id)
    if brief.lifecycle.value == "draft":
        brief = contracts.freeze_brief(
            SCOPE, ACTOR, brief.brief_id, brief.version, f"{TASK_KEY}-brief-freeze"
        )
    evidence_ref = ExactRevisionRef(
        resource_type="Evidence",
        resource_id=evidence["evidence_id"],
        revision=1,
        content_hash=evidence["content_hash"],
    )
    bundle = contracts.create_evidence_bundle(
        SCOPE,
        ACTOR,
        f"{TASK_KEY}-bundle",
        CreateEvidenceBundleRequest(
            brief_ref=ExactRevisionRef(
                resource_type="TaskBriefRevision",
                resource_id=brief.brief_id,
                revision=brief.revision,
                content_hash=brief.content_hash,
            ),
            subject_refs=[
                ResourceRef(resource_type="SkillTemplate", resource_id=SKILL_ID, revision="1", authority="aip-registry")
            ],
            cutoff_at=evidence["created_at"],
            item_refs=[evidence_ref],
            coverage=Coverage.COMPLETE,
            freshness=Freshness.FRESH,
            marking=["internal", "no-secret", "no-pii"],
            license_summary={
                "basis": "internal use approval",
                "approvedCapabilities": ["text", "video", "llm"],
                "forbiddenCapabilities": ["audio", "image", "tool_execution"],
                "restrictedTextCopied": False,
            },
        ),
    )
    return (
        evidence_ref,
        ExactRevisionRef(
            resource_type="EvidenceBundleRevision",
            resource_id=bundle.bundle_id,
            revision=bundle.revision,
            content_hash=bundle.content_hash,
        ),
    )


def _skill_eval(source_skill: Any, graph: Any, model: Any):
    evaluated = evaluate_i01_contract(graph, _isolated_registry(_model_alias(model)))
    actual = {item.case_id: item.actual for item in evaluated.report.results}
    expected = {
        "v01-positive": {
            "status": "succeeded",
            "output_contract": "VideoDraft.DRAFT",
            "usage_present": True,
            "production_written": False,
        },
        "v01-structure": {"blocked": True, "code": "V01_INPUT_STRUCTURE_INVALID"},
        "v01-fact-boundary": {"blocked": True, "code": "V01_FACT_EVIDENCE_REQUIRED"},
        "v01-external-action": {"blocked": True, "code": "V01_EXTERNAL_ACTION_DENIED"},
        "v01-sensitive": {"blocked": True, "code": "V01_SENSITIVE_INPUT_DENIED"},
        "v01-adapter-failure": {
            "status": "failed",
            "error_code": "LLM_ADAPTER_FAILED",
            "production_written": False,
        },
    }
    if actual != expected:
        raise RuntimeError("isolated V01 contract results drifted before Skill Eval")
    artifacts: dict[tuple[str, str], Any] = {}
    cases: list[EvalCaseDefinition] = []
    kinds = {
        "v01-positive": EvalCaseKind.POSITIVE,
        "v01-structure": EvalCaseKind.NEGATIVE,
        "v01-fact-boundary": EvalCaseKind.BOUNDARY,
        "v01-external-action": EvalCaseKind.NEGATIVE,
        "v01-sensitive": EvalCaseKind.PII,
        "v01-adapter-failure": EvalCaseKind.TOOL_FAILURE,
    }
    for case_id in expected:
        input_value = {"caseId": case_id}
        expected_value = expected[case_id]
        input_ref = ArtifactRef(
            artifact_id=f"{SUITE_ID}.{case_id}.input",
            artifact_type="eval_input",
            revision="1",
            content_hash=canonical_hash(input_value),
        )
        expected_ref = ArtifactRef(
            artifact_id=f"{SUITE_ID}.{case_id}.expected",
            artifact_type="eval_expected",
            revision="1",
            content_hash=canonical_hash(expected_value),
        )
        artifacts[(input_ref.artifact_id, "1")] = input_value
        artifacts[(expected_ref.artifact_id, "1")] = expected_value
        cases.append(
            EvalCaseDefinition(
                case_id=case_id,
                kind=kinds[case_id],
                input_artifact=input_ref,
                expected_artifact=expected_ref,
                timeout_ms=1_000,
            )
        )
    source_hash = canonical_hash({"suiteId": SUITE_ID, "caseIds": list(expected)})
    dataset = DatasetRevisionRef(
        dataset_id=DATASET_ID,
        revision=1,
        content_hash=canonical_hash({"datasetId": DATASET_ID, "sourceHash": source_hash}),
        source_hash=source_hash,
        redaction_policy=AssetRevisionRef(
            asset_type=AssetType.POLICY,
            asset_id="v01-no-pii-contract-policy",
            revision="1",
            content_hash=canonical_hash("v01-no-pii-contract-policy-v1"),
        ),
    )
    manifest = EvalDatasetManifest(
        source_kind=DatasetSourceKind.ARTIFACT_SNAPSHOT,
        source_id="v01-isolated-contract-cases",
        source_revision="1",
        source_hash=source_hash,
        fields_allowlist=["caseId"],
        redaction_receipt=ArtifactRef(
            artifact_id="v01-contract-redaction-receipt",
            artifact_type="receipt",
            revision="1",
            content_hash=canonical_hash("v01-no-pii-reviewed"),
        ),
        pii_state=DatasetPiiState.NONE,
        case_count=6,
        captured_at=datetime(2026, 8, 17, 12, 0, tzinfo=UTC),
    )
    registry = AipEvalPackRegistry()
    registry.register_dataset_revision(SCOPE, dataset, manifest, actor=ACTOR)
    target = AssetRevisionRef(
        asset_type=AssetType.SKILL_TEMPLATE,
        asset_id=source_skill.skill_id,
        revision=str(source_skill.revision),
        content_hash=source_skill.content_hash,
    )
    judge = JudgeRevisionRef(
        judge_id="v01-exact-contract-judge",
        revision=1,
        content_hash=canonical_hash("v01-exact-contract-judge-v1"),
    )
    suite = EvalSuiteRevision(
        suite_id=SUITE_ID,
        revision=1,
        content_hash="0" * 64,
        target=target,
        dataset=dataset,
        judge=judge,
        cases=cases,
        gate_threshold=1.0,
    )
    suite = suite.model_copy(update={"content_hash": compute_eval_suite_hash(suite)})
    suite = registry.register_suite_revision(SCOPE, suite, actor=ACTOR)
    run_key = f"{SUITE_ID}-run-r1"
    with db_connect(SCOPE) as conn:
        existing = conn.execute(
            "SELECT run_id,status FROM aip_eval_run WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
            (*SCOPE.key, run_key),
        ).fetchone()
        report_row = (
            conn.execute(
                "SELECT report_id,revision FROM aip_eval_report_revision WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (*SCOPE.key, existing["run_id"]),
            ).fetchone()
            if existing and existing["status"] == "succeeded"
            else None
        )
    runner = AipEvalRunner()
    if report_row:
        report = runner.get_report(SCOPE, report_row["report_id"], report_row["revision"])
    elif existing:
        raise RuntimeError("existing V01 Skill Eval is not terminal GREEN")
    else:
        def resolve(ref: ArtifactRef) -> ResolvedArtifact:
            value = artifacts.get((ref.artifact_id, ref.revision or ""))
            if value is None:
                raise RuntimeError("V01 Eval artifact is unavailable")
            return ResolvedArtifact(reference=ref, value=value)

        report = runner.run(
            SCOPE,
            suite_id=suite.suite_id,
            suite_revision=suite.revision,
            idempotency_key=run_key,
            actor=ACTOR,
            resolve_artifact=resolve,
            execute_target=lambda ref, value: TargetExecution(
                target=ref, value=actual[value["caseId"]]
            ),
            execute_judge=lambda ref, observed, wanted: JudgeExecution(
                judge=ref,
                passed=observed == wanted,
                detail_code="i01_exact_contract_match",
            ),
        )
    if not report.gate_passed or report.passed != 6 or report.total != 6:
        raise RuntimeError("V01 Skill Eval did not pass 6/6")
    return suite, report


def _publication_exact_refs(suite: Any, report: Any):
    release = AipReleasePublicationService()
    gate = release.derive_gate(
        SCOPE,
        actor=ACTOR,
        request=DeriveReleaseGateRequest(
            report_id=report.report_id,
            report_revision=report.revision,
            report_hash=report.content_hash,
            idempotency_key=f"{SUITE_ID}-gate-r1",
        ),
    )
    publication = release.publish(
        SCOPE,
        actor=ACTOR,
        request=PublishReleaseRequest(
            release_gate_decision_id=gate.decision_id,
            reason_hash=canonical_hash({"approvalRef": APPROVAL_REF, "scope": "V01-only"}),
            idempotency_key=f"{SUITE_ID}-publication-r1",
        ),
    )
    with db_connect(SCOPE) as conn:
        event_row = conn.execute(
            "SELECT * FROM aip_publication_event WHERE org_id=%s AND project_id=%s AND event_id=%s",
            (*SCOPE.key, publication.event_id),
        ).fetchone()
    if event_row is None:
        raise RuntimeError("V01 publication event exact row is missing")
    event_hash = production_contract_hash(
        AipProductionContractStore._publication_snapshot(event_row)
    )
    return gate, publication, event_hash


def _freeze_eval_contract(suite: Any, gate: Any, publication: Any, event_hash: str):
    store = AipProductionContractStore()
    contract = store.create_eval_contract(
        SCOPE,
        ACTOR,
        f"{SUITE_ID}-eval-contract",
        CreateEvalContractRequest(
            suite_ref=ExactRevisionRef(
                resource_type="EvalSuiteRevision",
                resource_id=suite.suite_id,
                revision=suite.revision,
                content_hash=suite.content_hash,
            ),
            publication_ref=ExactRevisionRef(
                resource_type="PublicationEvent",
                resource_id=publication.event_id,
                revision=1,
                content_hash=event_hash,
            ),
            release_gate_ref=ExactRevisionRef(
                resource_type="ReleaseGateDecision",
                resource_id=gate.decision_id,
                revision=1,
                content_hash=gate.decision_hash,
            ),
            artifact_schema_ref=ResourceRef(
                resource_type="Schema",
                resource_id="VideoDraft.DRAFT",
                revision="1",
                authority="aip-contract",
            ),
            severity_thresholds={"critical": 1.0, "required": 1.0},
            gate_policy={"requiredPassRate": 1.0, "requiredCases": 6},
            return_mapping={"pass": "publish", "fail": "block"},
            override_policy={"allowed": False},
        ),
    )
    contract = store.get_eval_contract(SCOPE, contract.contract_id)
    if contract.lifecycle.value == "draft":
        contract = store.freeze_eval_contract(
            SCOPE,
            ACTOR,
            contract.contract_id,
            contract.version,
            f"{SUITE_ID}-eval-contract-freeze",
        )
    return contract


def _policy_ref(asset_type: str, asset_id: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=asset_type,
        asset_id=asset_id,
        revision=1,
        content_hash=POLICY_HASH,
    )


def _schema_ref(asset_id: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type="SchemaRevision",
        asset_id=asset_id,
        revision=1,
        content_hash=SCHEMA_HASH,
    )


def _ensure_capability_r1() -> Any:
    registry = AipCapabilityRegistry()
    try:
        return registry.get(CAPABILITY_ID, 1)
    except AipAgentRegistryNotFound:
        pass
    payload = {
        "capabilityId": CAPABILITY_ID,
        "revision": 1,
        "displayName": "视频生成",
        "lifecycle": TemplateLifecycle.PUBLISHED.value,
        "parentRef": None,
        "aliases": ["visual.video.generate", "content.video.generate"],
        "inputSchemaRef": _schema_ref("VideoGenerationRequest").model_dump(
            mode="json", by_alias=True
        ),
        "outputSchemaRef": _schema_ref("VideoDraftRef").model_dump(
            mode="json", by_alias=True
        ),
        "riskLevel": "medium",
        "requiredDataRefs": [],
        "requiredToolRefs": [],
        "requiredCapabilityRefs": [],
        "evalPackRef": None,
        "memoryPolicyRef": _policy_ref("MemoryPolicy", "ecommerce.memory.default").model_dump(
            mode="json", by_alias=True
        ),
        "handoffPolicyRef": _policy_ref("HandoffPolicy", "ecommerce.handoff.default").model_dump(
            mode="json", by_alias=True
        ),
        "effectReviewSchemaRef": _schema_ref("EffectReviewRef").model_dump(
            mode="json", by_alias=True
        ),
        "licensePolicyRef": _policy_ref("LicensePolicy", "ecommerce.license.default").model_dump(
            mode="json", by_alias=True
        ),
        "readinessPolicyRef": _policy_ref(
            "ReadinessPolicy", "ecommerce.readiness.default"
        ).model_dump(mode="json", by_alias=True),
        "readiness": CapabilityReadiness.AVAILABLE.value,
        "readinessReasons": [],
        "sourceRef": {
            "resourceType": "ApprovalRef",
            "resourceId": APPROVAL_REF,
            "revision": "1",
            "authority": "aip-r2-i01",
        },
        "sourceLicense": "internal",
    }
    return registry.publish(
        PublishCapabilityRevisionRequest(
            **payload, content_hash=AipAgentRegistryStore._hash(payload)
        ),
        actor=ACTOR,
    )


def _ensure_skill_r1() -> Any:
    registry = AipSkillRegistry()
    try:
        return registry.get_skill(SKILL_ID, 1)
    except AipAgentRegistryNotFound:
        pass
    template = AipSkillRegistry().get_skill("ecommerce.skill.C02", 1)
    payload = {
        "skillId": SKILL_ID,
        "revision": 1,
        "canonicalLogicId": V01_GRAPH_ID,
        "lifecycle": TemplateLifecycle.EVALUATED.value,
        "inputSchema": template.input_schema,
        "outputSchema": template.output_schema,
        "toolAllowlist": [],
        "requiredCapabilities": [CAPABILITY_ID],
        "riskLevel": "medium",
        "evalPackRef": None,
        "memoryPolicyRef": template.memory_policy_ref.model_dump(
            mode="json", by_alias=True
        ),
        "handoffPolicyRef": template.handoff_policy_ref.model_dump(
            mode="json", by_alias=True
        ),
        "sourceRef": {
            "resourceType": "ApprovalRef",
            "resourceId": APPROVAL_REF,
            "revision": "1",
            "authority": "aip-r2-i01",
        },
        "sourceLicense": "internal",
        "parentRef": None,
        "publicationTenant": None,
        "releaseGateRef": None,
        "publicationRef": None,
        "modelRouteRef": None,
        "runtimePolicyRef": None,
        "logicRevisionRef": None,
    }
    return registry.publish_skill(
        PublishSkillTemplateRequest(
            **payload, content_hash=AipAgentRegistryStore._hash(payload)
        ),
        actor=ACTOR,
    )


def _publish_skill_and_capability(
    source_skill: Any,
    graph: Any,
    suite: Any,
    gate: Any,
    publication: Any,
    route: Any,
    policy: Any,
):
    route_ref = exact_ref("ModelRouteRevision", route, "route_id")
    policy_ref = exact_ref("RuntimePolicyRevision", policy, "policy_id")
    logic_ref = VersionedAssetRef(
        asset_type="LogicRevision",
        asset_id=graph.id,
        revision=graph.revision,
        content_hash=graph.graph_hash,
    )
    skill, receipt = AipSkillPublicationService().publish_evaluated_revision(
        SCOPE,
        PublishEvaluatedSkillRevisionRequest(
            source_skill=VersionedAssetRef(
                asset_type="SkillTemplate",
                asset_id=source_skill.skill_id,
                revision=source_skill.revision,
                content_hash=source_skill.content_hash,
            ),
            publication_id=publication.publication_id,
            release_gate_decision_id=gate.decision_id,
            model_route_ref=route_ref,
            runtime_policy_ref=policy_ref,
            logic_revision_ref=logic_ref,
            idempotency_key=f"{SUITE_ID}-publish-skill-r2",
        ),
        actor=ACTOR,
        occurred_at=datetime.now(UTC),
    )
    capability_registry = AipCapabilityRegistry()
    current = capability_registry.get(CAPABILITY_ID, 1)
    payload = current.model_dump(
        mode="json", by_alias=True, exclude={"content_hash", "created_by", "created_at"}
    )
    payload.update(
        revision=2,
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
        readiness=CapabilityReadiness.AVAILABLE.value,
        readinessReasons=[],
    )
    capability = capability_registry.publish(
        PublishCapabilityRevisionRequest(
            **payload, content_hash=AipAgentRegistryStore._hash(payload)
        ),
        actor=ACTOR,
    )
    return skill, receipt, capability


def _negative_canary_counts() -> dict[str, int]:
    subject_ref = json.dumps(
        [
            {
                "resourceType": "SkillTemplate",
                "resourceId": SKILL_ID,
                "revision": "1",
                "authority": "aip-registry",
            }
        ],
        ensure_ascii=False,
        sort_keys=True,
    )
    with db_connect(CANARY_SCOPE) as conn:
        return {
            "skillEvalSuite": int(conn.execute(
                "SELECT COUNT(*) AS count FROM aip_eval_suite_revision WHERE org_id=%s AND project_id=%s AND suite_id=%s",
                (*CANARY_SCOPE.key, SUITE_ID),
            ).fetchone()["count"]),
            "evidenceBundle": int(conn.execute(
                """SELECT COUNT(*) AS count FROM aip_evidence_bundle_revision
                   WHERE org_id=%s AND project_id=%s AND subject_refs @> %s::jsonb""",
                (*CANARY_SCOPE.key, subject_ref),
            ).fetchone()["count"]),
            "evalContract": int(conn.execute(
                """SELECT COUNT(*) AS count FROM aip_eval_contract_revision
                   WHERE org_id=%s AND project_id=%s
                     AND suite_ref->>'resourceId'=%s""",
                (*CANARY_SCOPE.key, SUITE_ID),
            ).fetchone()["count"]),
        }


def apply() -> dict[str, Any]:
    _require_schema_head()
    before_canary = _negative_canary_counts()
    if any(before_canary.values()):
        raise RuntimeError("negative tenant canary already contains R2 authority")
    _ensure_capability_r1()
    source_skill = _ensure_skill_r1()
    graph = LogicGraphStore().get(SCOPE.org_id, SCOPE.project_id, V01_GRAPH_ID)
    model_store = AipModelRuntimeStore()
    model = model_store.get_model(SCOPE, MODEL_ID, 1)
    route = model_store.get_route(SCOPE, ROUTE_ID, 1)
    policy = model_store.get_policy(SCOPE, POLICY_ID, 1)
    _, bundle_ref = _governance_evidence()
    suite, report = _skill_eval(source_skill, graph, model)
    gate, publication, event_hash = _publication_exact_refs(suite, report)
    eval_contract = _freeze_eval_contract(suite, gate, publication, event_hash)
    skill, receipt, capability = _publish_skill_and_capability(
        source_skill, graph, suite, gate, publication, route, policy
    )
    after_canary = _negative_canary_counts()
    if after_canary != before_canary:
        raise RuntimeError("R2 authority leaked into the negative tenant canary")
    return {
        "status": "V01_SKILL_CAPABILITY_PUBLICATION_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "skill": {"assetId": skill.skill_id, "revision": skill.revision, "contentHash": skill.content_hash},
        "capability": {"assetId": capability.capability_id, "revision": capability.revision, "contentHash": capability.content_hash},
        "logic": {"assetId": graph.id, "revision": graph.revision, "contentHash": graph.graph_hash},
        "eval": {"suiteId": suite.suite_id, "reportId": report.report_id, "passed": report.passed, "total": report.total},
        "gate": {"assetId": gate.decision_id, "revision": 1, "contentHash": gate.decision_hash},
        "publicationId": publication.publication_id,
        "evalContract": {"assetId": eval_contract.contract_id, "revision": eval_contract.revision, "contentHash": eval_contract.content_hash},
        "licenseEvidence": bundle_ref.model_dump(mode="json", by_alias=True),
        "receiptId": receipt.receipt_id,
        "negativeCanaryCounts": after_canary,
        "providerCalls": 0,
        "forbiddenSideEffects": ["CapabilityBinding", "SkillBinding", "AgentInstance activation", "AgentRun"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = apply() if args.apply else build_plan()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
