#!/usr/bin/env python3
"""Publish S01/S02/S03/S05/S06 Skills from exact evaluated r1 sources.

Default mode is read-only. ``--apply`` creates only isolated Skill Eval packs,
release gates/events and immutable published Skill revisions. It does not call
a Provider, resolve Secret payloads, create Binding/AgentRun, contact a
    customer message, create a ticket, or execute a production Action. S04 is immutable pre-existing
authority and is snapshotted before and after.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "aos-api"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aos_api.aip_agent_registry_contracts import (  # noqa: E402
    PublishEvaluatedSkillRevisionRequest,
    TemplateLifecycle,
    VersionedAssetRef,
)
from aos_api.aip_contracts import ArtifactRef  # noqa: E402
from aos_api.aip_eval_contracts import (  # noqa: E402
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
from aos_api.aip_eval_pack_registry import (  # noqa: E402
    AipEvalPackRegistry,
    compute_eval_suite_hash,
)
from aos_api.aip_eval_runner import (  # noqa: E402
    AipEvalRunner,
    JudgeExecution,
    ResolvedArtifact,
    TargetExecution,
)
from aos_api.aip_logic_graph_store import LogicGraphStore  # noqa: E402
from aos_api.aip_model_runtime_store import AipModelRuntimeStore  # noqa: E402
from aos_api.aip_customer_service_logic import (  # noqa: E402
    CUSTOMER_SERVICE_LOGIC_IDS,
    evaluate_customer_service_contract,
    customer_service_definition,
)
from aos_api.aip_release_publication_models import (  # noqa: E402
    DeriveReleaseGateRequest,
    PublishReleaseRequest,
)
from aos_api.aip_release_publication_service import AipReleasePublicationService  # noqa: E402
from aos_api.aip_skill_publication_service import AipSkillPublicationService  # noqa: E402
from aos_api.aip_skill_registry import AipSkillRegistry  # noqa: E402
from aos_api.db import connect as db_connect  # noqa: E402
from aos_api.tenant_scope import TenantScope  # noqa: E402

from bootstrap_r09_customer_service_authority import (  # noqa: E402
    REQUIRED_ALEMBIC_HEAD,
    _isolated_registry,
    _require_schema_head,
    exact_model_alias,
)

SCOPE = TenantScope("org-org", "dev-project")
CANARY_SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "aip-r09-customer-service-skill-bootstrap"
APPROVAL_REF = "130-R09-CUSTOMER-SERVICE-AUTHORIZED"
ROUTE_ID = "route-qyh-text-dev"
MODEL_ID = "model-qyh-text-dev"
S04_SKILL_ID = "ecommerce.skill.S04"
S04_SKILL_REVISION = 2


def canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _skill_id(logic_id: str) -> str:
    return f"ecommerce.skill.{logic_id}"


def _suite_id(logic_id: str) -> str:
    return f"{_skill_id(logic_id)}.contract.v1"


def _dataset_id(logic_id: str) -> str:
    return f"{_skill_id(logic_id)}.contract-cases.v1"


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "schemaHead": REQUIRED_ALEMBIC_HEAD,
        "logicIds": list(CUSTOMER_SERVICE_LOGIC_IDS),
        "sourceSkills": [
            f"{_skill_id(item)}@r1" for item in CUSTOMER_SERVICE_LOGIC_IDS
        ],
        "preservedAuthority": [f"{S04_SKILL_ID}@r{S04_SKILL_REVISION}"],
        "steps": [
            "require exact evaluated Skill r1 and published Logic r1",
            "snapshot immutable S04 Skill r2",
            "run logic-specific isolated governance Eval per Skill",
            "derive exact release gate and immutable publication event",
            "publish a new immutable Skill revision with exact Route/Policy/Logic refs",
            "verify S04 unchanged and negative canary remains empty",
        ],
        "providerCalls": 0,
        "secretPayloadReads": 0,
        "forbiddenSideEffects": [
            "CapabilityBinding",
            "SkillBinding",
            "AgentRun",
            "Provider call",
            "customer-service external action",
            "production Action",
        ],
    }


def _expected_results(logic_id: str) -> dict[str, dict[str, Any]]:
    definition = customer_service_definition(logic_id)
    prefix = logic_id.lower()
    blocked: dict[str, str] = {
        "missing": f"{logic_id}_INPUT_STRUCTURE_INVALID",
        "fact-boundary": f"{logic_id}_FACT_EVIDENCE_REQUIRED",
        "unsafe-input": f"{logic_id}_UNSAFE_INPUT_DENIED",
        "unauthorized": f"{logic_id}_EXTERNAL_ACTION_DENIED",
    }
    if logic_id == "S01":
        blocked["high-risk-no-human"] = f"{logic_id}_HUMAN_HANDOFF_REQUIRED"
    if definition.requires_identity_order:
        blocked.update(
            {
                "identity-unverified": f"{logic_id}_IDENTITY_NOT_VERIFIED",
                "order-mismatch": f"{logic_id}_ORDER_OWNERSHIP_DENIED",
            }
        )
    if logic_id == "S02":
        blocked.update(
            {
                "field-overreach": f"{logic_id}_FIELD_ALLOWLIST_DENIED",
                "masking-missing": f"{logic_id}_MASKING_POLICY_REQUIRED",
            }
        )
    if definition.requires_logistics:
        blocked.update(
            {
                "logistics-stale": f"{logic_id}_LOGISTICS_STALE",
                "anomaly-invalid": f"{logic_id}_LOGISTICS_ENUM_INVALID",
            }
        )
    if definition.requires_complaint_handoff:
        blocked.update(
            {
                "handoff-missing": f"{logic_id}_HUMAN_HANDOFF_REQUIRED",
                "compensation-promised": f"{logic_id}_COMPENSATION_PROMISE_DENIED",
            }
        )
    if definition.requires_service_outcome:
        blocked.update(
            {
                "outcome-missing": f"{logic_id}_SERVICE_OUTCOME_REQUIRED",
                "case-unresolved": f"{logic_id}_CASE_NOT_RESOLVED",
                "raw-feedback": f"{logic_id}_RAW_FEEDBACK_DENIED",
                "survey-send": f"{logic_id}_SURVEY_SEND_DENIED",
                "low-score-no-human": f"{logic_id}_LOW_SCORE_HANDOFF_REQUIRED",
            }
        )
    values: dict[str, dict[str, Any]] = {
        f"{prefix}-positive": {
            "status": "succeeded",
            "output_contract": definition.output_contract,
            "usage_present": True,
            "production_written": False,
        }
    }
    values.update(
        {
            f"{prefix}-{suffix}": {"blocked": True, "code": code}
            for suffix, code in blocked.items()
        }
    )
    values[f"{prefix}-adapter-failure"] = {
        "status": "failed",
        "error_code": "LLM_ADAPTER_FAILED",
        "production_written": False,
    }
    return values


def _skill_eval(logic_id: str, source_skill: Any, graph: Any, model: Any):
    suite_id = _suite_id(logic_id)
    expected = _expected_results(logic_id)
    evaluated = evaluate_customer_service_contract(
        logic_id, graph, _isolated_registry(exact_model_alias(model))
    )
    actual = {item.case_id: item.actual for item in evaluated.report.results}
    if actual != expected:
        raise RuntimeError(f"isolated {logic_id} governance results drifted")

    artifacts: dict[tuple[str, str], Any] = {}
    cases: list[EvalCaseDefinition] = []
    kinds = {
        "positive": EvalCaseKind.POSITIVE,
        "missing": EvalCaseKind.NEGATIVE,
        "fact-boundary": EvalCaseKind.BOUNDARY,
        "unsafe-input": EvalCaseKind.PII,
        "unauthorized": EvalCaseKind.NEGATIVE,
        "high-risk-no-human": EvalCaseKind.BOUNDARY,
        "identity-unverified": EvalCaseKind.BOUNDARY,
        "order-mismatch": EvalCaseKind.BOUNDARY,
        "field-overreach": EvalCaseKind.PII,
        "masking-missing": EvalCaseKind.PII,
        "logistics-stale": EvalCaseKind.BOUNDARY,
        "anomaly-invalid": EvalCaseKind.BOUNDARY,
        "handoff-missing": EvalCaseKind.BOUNDARY,
        "compensation-promised": EvalCaseKind.NEGATIVE,
        "outcome-missing": EvalCaseKind.BOUNDARY,
        "case-unresolved": EvalCaseKind.BOUNDARY,
        "raw-feedback": EvalCaseKind.PII,
        "survey-send": EvalCaseKind.NEGATIVE,
        "low-score-no-human": EvalCaseKind.BOUNDARY,
        "adapter-failure": EvalCaseKind.TOOL_FAILURE,
    }
    for case_id, expected_value in expected.items():
        suffix = case_id.removeprefix(f"{logic_id.lower()}-")
        input_value = {"caseId": case_id}
        input_ref = ArtifactRef(
            artifact_id=f"{suite_id}.{case_id}.input",
            artifact_type="eval_input",
            revision="1",
            content_hash=canonical_hash(input_value),
        )
        expected_ref = ArtifactRef(
            artifact_id=f"{suite_id}.{case_id}.expected",
            artifact_type="eval_expected",
            revision="1",
            content_hash=canonical_hash(expected_value),
        )
        artifacts[(input_ref.artifact_id, "1")] = input_value
        artifacts[(expected_ref.artifact_id, "1")] = expected_value
        cases.append(
            EvalCaseDefinition(
                case_id=case_id,
                kind=kinds[suffix],
                input_artifact=input_ref,
                expected_artifact=expected_ref,
                timeout_ms=1_000,
            )
        )

    source_hash = canonical_hash({"suiteId": suite_id, "caseIds": list(expected)})
    dataset_id = _dataset_id(logic_id)
    dataset = DatasetRevisionRef(
        dataset_id=dataset_id,
        revision=1,
        content_hash=canonical_hash(
            {"datasetId": dataset_id, "sourceHash": source_hash}
        ),
        source_hash=source_hash,
        redaction_policy=AssetRevisionRef(
            asset_type=AssetType.POLICY,
            asset_id=f"{logic_id.lower()}-no-pii-governance-policy",
            revision="1",
            content_hash=canonical_hash(
                f"{logic_id.lower()}-no-pii-governance-policy-v1"
            ),
        ),
    )
    manifest = EvalDatasetManifest(
        source_kind=DatasetSourceKind.ARTIFACT_SNAPSHOT,
        source_id=f"{logic_id.lower()}-isolated-governance-cases",
        source_revision="1",
        source_hash=source_hash,
        fields_allowlist=["caseId"],
        redaction_receipt=ArtifactRef(
            artifact_id=f"{logic_id.lower()}-governance-redaction-receipt",
            artifact_type="receipt",
            revision="1",
            content_hash=canonical_hash(f"{logic_id.lower()}-no-pii-reviewed"),
        ),
        pii_state=DatasetPiiState.NONE,
        case_count=len(expected),
        captured_at=datetime(2026, 8, 21, 4, 0, tzinfo=UTC),
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
        judge_id=f"{logic_id.lower()}-exact-governance-judge",
        revision=1,
        content_hash=canonical_hash(
            f"{logic_id.lower()}-exact-governance-judge-v1"
        ),
    )
    suite = EvalSuiteRevision(
        suite_id=suite_id,
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
    run_key = f"{suite_id}-run-r1"
    with db_connect(SCOPE) as conn:
        existing = conn.execute(
            "SELECT run_id,status FROM aip_eval_run "
            "WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
            (*SCOPE.key, run_key),
        ).fetchone()
        report_row = (
            conn.execute(
                "SELECT report_id,revision FROM aip_eval_report_revision "
                "WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (*SCOPE.key, existing["run_id"]),
            ).fetchone()
            if existing and existing["status"] == "succeeded"
            else None
        )
    runner = AipEvalRunner()
    if report_row:
        report = runner.get_report(
            SCOPE, report_row["report_id"], report_row["revision"]
        )
    elif existing:
        raise RuntimeError(f"existing {logic_id} Skill Eval is not terminal GREEN")
    else:

        def resolve(ref: ArtifactRef) -> ResolvedArtifact:
            value = artifacts.get((ref.artifact_id, ref.revision or ""))
            if value is None:
                raise RuntimeError(f"{logic_id} Eval artifact is unavailable")
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
                detail_code=f"{logic_id.lower()}_exact_governance_match",
            ),
        )
    expected_total = len(expected)
    if (
        not report.gate_passed
        or report.passed != expected_total
        or report.total != expected_total
    ):
        raise RuntimeError(
            f"{logic_id} Skill Eval did not pass {expected_total}/{expected_total}"
        )
    return suite, report


def _release(logic_id: str, report: Any):
    suite_id = _suite_id(logic_id)
    service = AipReleasePublicationService()
    gate = service.derive_gate(
        SCOPE,
        actor=ACTOR,
        request=DeriveReleaseGateRequest(
            report_id=report.report_id,
            report_revision=report.revision,
            report_hash=report.content_hash,
            idempotency_key=f"{suite_id}-gate-r1",
        ),
    )
    publication = service.publish(
        SCOPE,
        actor=ACTOR,
        request=PublishReleaseRequest(
            release_gate_decision_id=gate.decision_id,
            reason_hash=canonical_hash(
                {"approvalRef": APPROVAL_REF, "scope": f"{logic_id}-only"}
            ),
            idempotency_key=f"{suite_id}-publication-r1",
        ),
    )
    return gate, publication


def _exact_ref(asset_type: str, item: Any, id_attr: str) -> VersionedAssetRef:
    return VersionedAssetRef(
        asset_type=asset_type,
        asset_id=str(getattr(item, id_attr)),
        revision=int(item.revision),
        content_hash=str(item.content_hash),
    )


def _publish_one(logic_id: str, route: Any, policy: Any, model: Any) -> dict[str, Any]:
    source = AipSkillRegistry().get_skill(_skill_id(logic_id), 1)
    if source.lifecycle is not TemplateLifecycle.EVALUATED:
        raise RuntimeError(f"{logic_id} source Skill r1 is not evaluated")
    graph = LogicGraphStore().get(
        SCOPE.org_id,
        SCOPE.project_id,
        customer_service_definition(logic_id).graph_id,
    )
    suite, report = _skill_eval(logic_id, source, graph, model)
    gate, publication = _release(logic_id, report)
    skill, receipt = AipSkillPublicationService().publish_evaluated_revision(
        SCOPE,
        PublishEvaluatedSkillRevisionRequest(
            source_skill=VersionedAssetRef(
                asset_type="SkillTemplate",
                asset_id=source.skill_id,
                revision=source.revision,
                content_hash=source.content_hash,
            ),
            publication_id=publication.publication_id,
            release_gate_decision_id=gate.decision_id,
            model_route_ref=_exact_ref("ModelRouteRevision", route, "route_id"),
            runtime_policy_ref=_exact_ref(
                "RuntimePolicyRevision", policy, "policy_id"
            ),
            logic_revision_ref=VersionedAssetRef(
                asset_type="LogicRevision",
                asset_id=graph.id,
                revision=graph.revision,
                content_hash=graph.graph_hash,
            ),
            idempotency_key=f"{suite.suite_id}-publish-skill-r2",
        ),
        actor=ACTOR,
        occurred_at=datetime.now(UTC),
    )
    return {
        "logicId": logic_id,
        "skillId": skill.skill_id,
        "revision": skill.revision,
        "contentHash": skill.content_hash,
        "logicRevisionRef": skill.logic_revision_ref.model_dump(
            mode="json", by_alias=True
        ),
        "eval": {
            "suiteId": suite.suite_id,
            "reportId": report.report_id,
            "passed": report.passed,
            "total": report.total,
        },
        "gateId": gate.decision_id,
        "publicationId": publication.publication_id,
        "receiptId": receipt.receipt_id,
    }


def _snapshot_s04() -> dict[str, Any]:
    skill = AipSkillRegistry().get_skill(S04_SKILL_ID, S04_SKILL_REVISION)
    return {
        "skillId": skill.skill_id,
        "revision": skill.revision,
        "contentHash": skill.content_hash,
        "lifecycle": skill.lifecycle.value,
        "logicRevisionRef": (
            skill.logic_revision_ref.model_dump(mode="json", by_alias=True)
            if skill.logic_revision_ref
            else None
        ),
    }


def _canary_counts() -> dict[str, int]:
    suite_ids = [_suite_id(item) for item in CUSTOMER_SERVICE_LOGIC_IDS]
    skill_ids = [_skill_id(item) for item in CUSTOMER_SERVICE_LOGIC_IDS]
    with db_connect(CANARY_SCOPE) as conn:
        return {
            "evalSuites": int(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM aip_eval_suite_revision "
                    "WHERE org_id=%s AND project_id=%s AND suite_id=ANY(%s)",
                    (*CANARY_SCOPE.key, suite_ids),
                ).fetchone()["count"]
            ),
            "releaseGates": int(
                conn.execute(
                    "SELECT COUNT(*) AS count FROM aip_release_gate_decision "
                    "WHERE org_id=%s AND project_id=%s "
                    "AND target_ref->>'assetId'=ANY(%s)",
                    (*CANARY_SCOPE.key, skill_ids),
                ).fetchone()["count"]
            ),
        }


def apply() -> dict[str, Any]:
    _require_schema_head()
    canary_before = _canary_counts()
    if any(canary_before.values()):
        raise RuntimeError("negative tenant already contains R09 Skill authority")
    s04_before = _snapshot_s04()
    runtime = AipModelRuntimeStore()
    route = runtime.get_route(SCOPE, ROUTE_ID)
    policy = runtime.get_policy(
        SCOPE, route.runtime_policy_ref.asset_id, route.runtime_policy_ref.revision
    )
    model = runtime.get_model(SCOPE, MODEL_ID)
    results = [
        _publish_one(logic_id, route, policy, model)
        for logic_id in CUSTOMER_SERVICE_LOGIC_IDS
    ]
    s04_after = _snapshot_s04()
    if s04_after != s04_before:
        raise RuntimeError("immutable S04 Skill authority changed during R09")
    canary_after = _canary_counts()
    if canary_after != canary_before:
        raise RuntimeError("R09 Skill authority leaked into negative tenant")
    return {
        "status": "R09_CUSTOMER_SERVICE_SKILL_PUBLICATION_GREEN",
        "scope": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
        "route": _exact_ref("ModelRouteRevision", route, "route_id").model_dump(
            mode="json", by_alias=True
        ),
        "policy": _exact_ref(
            "RuntimePolicyRevision", policy, "policy_id"
        ).model_dump(mode="json", by_alias=True),
        "skills": results,
        "preservedS04": s04_after,
        "negativeCanaryCounts": canary_after,
        "providerCalls": 0,
        "secretPayloadReads": 0,
        "bindingsCreated": 0,
        "agentRuns": 0,
        "externalCustomerActions": 0,
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
