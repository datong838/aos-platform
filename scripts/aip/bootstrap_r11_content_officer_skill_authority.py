#!/usr/bin/env python3
"""Publish C01/C03-C08 Skills while preserving immutable C02 authority.

The implementation intentionally reuses the already sealed R10 isolated Skill
publication machinery, but replaces every domain-specific contract, identifier
and output with the R11 content-officer authority.  Default mode is read-only.
``--apply`` creates only Eval packs, release gates/events and immutable Skill
revisions.  It never calls a Provider, reads a Secret payload, creates a
Binding/AgentRun, generates media, publishes content or contacts a lead.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bootstrap_r10_campaign_planner_skill_authority as _base
from aos_api.aip_content_officer_logic import (
    CONTENT_OFFICER_LOGIC_IDS,
    content_officer_definition,
    evaluate_content_officer_contract,
)

ACTOR = "aip-r11-content-officer-skill-bootstrap"
APPROVAL_REF = "130-R11-CONTENT-OFFICER-AUTHORIZED"
C02_SKILL_ID = "ecommerce.skill.C02"
C02_SKILL_REVISION = 2


def _configure_base() -> None:
    """Bind generic sealed machinery to the exact R11 content contracts."""

    _base.CAMPAIGN_PLANNER_LOGIC_IDS = CONTENT_OFFICER_LOGIC_IDS
    _base.campaign_planner_definition = content_officer_definition
    _base.evaluate_campaign_planner_contract = evaluate_content_officer_contract
    _base.ACTOR = ACTOR
    _base.APPROVAL_REF = APPROVAL_REF
    _base.A02_SKILL_ID = C02_SKILL_ID
    _base.A02_SKILL_REVISION = C02_SKILL_REVISION
    _base._expected_results = _expected_results


def build_plan() -> dict[str, Any]:
    return {
        "status": "planned",
        "scope": {"orgId": _base.SCOPE.org_id, "projectId": _base.SCOPE.project_id},
        "schemaHead": _base.REQUIRED_ALEMBIC_HEAD,
        "logicIds": list(CONTENT_OFFICER_LOGIC_IDS),
        "sourceSkills": [
            f"ecommerce.skill.{item}@r1" for item in CONTENT_OFFICER_LOGIC_IDS
        ],
        "preservedAuthority": [f"{C02_SKILL_ID}@r{C02_SKILL_REVISION}"],
        "steps": [
            "require exact evaluated Skill r1 and published Logic r1",
            "snapshot immutable C02 Skill r2",
            "run logic-specific isolated governance Eval per Skill",
            "derive exact release gate and immutable publication event",
            "publish immutable Skill r2 with exact Route/Policy/Logic refs",
            "verify C02 unchanged and negative canary remains empty",
        ],
        "providerCalls": 0,
        "secretPayloadReads": 0,
        "forbiddenSideEffects": [
            "CapabilityBinding",
            "SkillBinding",
            "AgentRun",
            "Provider call",
            "media generation",
            "content publication",
            "platform contact",
            "memory promotion",
        ],
    }


def _expected_results(logic_id: str) -> dict[str, dict[str, Any]]:
    definition = content_officer_definition(logic_id)
    prefix = logic_id.lower()
    blocked: dict[str, str] = {
        "missing": f"{logic_id}_INPUT_STRUCTURE_INVALID",
        "fact-boundary": f"{logic_id}_FACT_EVIDENCE_REQUIRED",
        "unsafe-input": f"{logic_id}_UNSAFE_INPUT_DENIED",
        "unauthorized": f"{logic_id}_EXTERNAL_ACTION_DENIED",
    }
    blocked.update(
        {
            "C01": {"source-stale": "C01_SOURCE_STALE"},
            "C03": {
                "fact-pack-missing": "C03_CONTENT_REFERENCE_REQUIRED",
                "copyright-unclear": "C03_COPYRIGHT_NOT_CLEARED",
            },
            "C04": {
                "asset-unlicensed": "C04_ASSET_LICENSE_REQUIRED",
                "media-action": "C04_EXTERNAL_ACTION_DENIED",
            },
            "C05": {"platform-rule-stale": "C05_PLATFORM_RULE_STALE"},
            "C06": {
                "factuality-failed": "C06_HARD_GATE_FAILED",
                "compliance-failed": "C06_HARD_GATE_FAILED",
            },
            "C07": {
                "pii-not-minimized": "C07_PII_NOT_MINIMIZED",
                "auto-contact": "C07_EXTERNAL_ACTION_DENIED",
            },
            "C08": {
                "window-open": "C08_WINDOW_NOT_CLOSED",
                "cutoff-mismatch": "C08_CUTOFF_MISMATCH",
                "sample-insufficient": "C08_SAMPLE_INSUFFICIENT",
                "memory-promotion": "C08_MEMORY_PROMOTION_DENIED",
            },
        }[logic_id]
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
    """Persist exact R11 cases with explicit EvalCaseKind classification."""

    suite_id = _base._suite_id(logic_id)
    expected = _expected_results(logic_id)
    evaluated = evaluate_content_officer_contract(
        logic_id, graph, _base._isolated_registry(_base.exact_model_alias(model))
    )
    actual = {item.case_id: item.actual for item in evaluated.report.results}
    if actual != expected:
        raise RuntimeError(f"isolated {logic_id} governance results drifted")

    artifacts: dict[tuple[str, str], Any] = {}
    cases: list[Any] = []
    boundary = _base.EvalCaseKind.BOUNDARY
    negative = _base.EvalCaseKind.NEGATIVE
    kinds = {
        "positive": _base.EvalCaseKind.POSITIVE,
        "missing": negative,
        "fact-boundary": boundary,
        "unsafe-input": _base.EvalCaseKind.PII,
        "unauthorized": negative,
        "source-stale": boundary,
        "fact-pack-missing": boundary,
        "copyright-unclear": boundary,
        "asset-unlicensed": boundary,
        "media-action": negative,
        "platform-rule-stale": boundary,
        "factuality-failed": boundary,
        "compliance-failed": boundary,
        "pii-not-minimized": boundary,
        "auto-contact": negative,
        "window-open": boundary,
        "cutoff-mismatch": boundary,
        "sample-insufficient": boundary,
        "memory-promotion": negative,
        "adapter-failure": _base.EvalCaseKind.TOOL_FAILURE,
    }
    for case_id, expected_value in expected.items():
        suffix = case_id.removeprefix(f"{logic_id.lower()}-")
        input_value = {"caseId": case_id}
        input_ref = _base.ArtifactRef(
            artifact_id=f"{suite_id}.{case_id}.input",
            artifact_type="eval_input",
            revision="1",
            content_hash=_base.canonical_hash(input_value),
        )
        expected_ref = _base.ArtifactRef(
            artifact_id=f"{suite_id}.{case_id}.expected",
            artifact_type="eval_expected",
            revision="1",
            content_hash=_base.canonical_hash(expected_value),
        )
        artifacts[(input_ref.artifact_id, "1")] = input_value
        artifacts[(expected_ref.artifact_id, "1")] = expected_value
        cases.append(
            _base.EvalCaseDefinition(
                case_id=case_id,
                kind=kinds[suffix],
                input_artifact=input_ref,
                expected_artifact=expected_ref,
                timeout_ms=1_000,
            )
        )

    source_hash = _base.canonical_hash(
        {"suiteId": suite_id, "caseIds": list(expected)}
    )
    dataset_id = _base._dataset_id(logic_id)
    dataset = _base.DatasetRevisionRef(
        dataset_id=dataset_id,
        revision=1,
        content_hash=_base.canonical_hash(
            {"datasetId": dataset_id, "sourceHash": source_hash}
        ),
        source_hash=source_hash,
        redaction_policy=_base.AssetRevisionRef(
            asset_type=_base.AssetType.POLICY,
            asset_id=f"{logic_id.lower()}-no-pii-governance-policy",
            revision="1",
            content_hash=_base.canonical_hash(
                f"{logic_id.lower()}-no-pii-governance-policy-v1"
            ),
        ),
    )
    manifest = _base.EvalDatasetManifest(
        source_kind=_base.DatasetSourceKind.ARTIFACT_SNAPSHOT,
        source_id=f"{logic_id.lower()}-isolated-governance-cases",
        source_revision="1",
        source_hash=source_hash,
        fields_allowlist=["caseId"],
        redaction_receipt=_base.ArtifactRef(
            artifact_id=f"{logic_id.lower()}-governance-redaction-receipt",
            artifact_type="receipt",
            revision="1",
            content_hash=_base.canonical_hash(
                f"{logic_id.lower()}-no-pii-reviewed"
            ),
        ),
        pii_state=_base.DatasetPiiState.NONE,
        case_count=len(expected),
        captured_at=datetime(2026, 8, 21, 4, 0, tzinfo=UTC),
    )
    registry = _base.AipEvalPackRegistry()
    registry.register_dataset_revision(_base.SCOPE, dataset, manifest, actor=ACTOR)
    target = _base.AssetRevisionRef(
        asset_type=_base.AssetType.SKILL_TEMPLATE,
        asset_id=source_skill.skill_id,
        revision=str(source_skill.revision),
        content_hash=source_skill.content_hash,
    )
    judge = _base.JudgeRevisionRef(
        judge_id=f"{logic_id.lower()}-exact-governance-judge",
        revision=1,
        content_hash=_base.canonical_hash(
            f"{logic_id.lower()}-exact-governance-judge-v1"
        ),
    )
    suite = _base.EvalSuiteRevision(
        suite_id=suite_id,
        revision=1,
        content_hash="0" * 64,
        target=target,
        dataset=dataset,
        judge=judge,
        cases=cases,
        gate_threshold=1.0,
    )
    suite = suite.model_copy(
        update={"content_hash": _base.compute_eval_suite_hash(suite)}
    )
    suite = registry.register_suite_revision(_base.SCOPE, suite, actor=ACTOR)
    run_key = f"{suite_id}-run-r1"
    with _base.db_connect(_base.SCOPE) as conn:
        existing = conn.execute(
            "SELECT run_id,status FROM aip_eval_run "
            "WHERE org_id=%s AND project_id=%s AND idempotency_key=%s",
            (*_base.SCOPE.key, run_key),
        ).fetchone()
        report_row = (
            conn.execute(
                "SELECT report_id,revision FROM aip_eval_report_revision "
                "WHERE org_id=%s AND project_id=%s AND run_id=%s",
                (*_base.SCOPE.key, existing["run_id"]),
            ).fetchone()
            if existing and existing["status"] == "succeeded"
            else None
        )
    runner = _base.AipEvalRunner()
    if report_row:
        report = runner.get_report(
            _base.SCOPE, report_row["report_id"], report_row["revision"]
        )
    elif existing:
        raise RuntimeError(f"existing {logic_id} Skill Eval is not terminal GREEN")
    else:
        def resolve(ref: Any) -> Any:
            value = artifacts.get((ref.artifact_id, ref.revision or ""))
            if value is None:
                raise RuntimeError(f"{logic_id} Eval artifact is unavailable")
            return _base.ResolvedArtifact(reference=ref, value=value)

        report = runner.run(
            _base.SCOPE,
            suite_id=suite.suite_id,
            suite_revision=suite.revision,
            idempotency_key=run_key,
            actor=ACTOR,
            resolve_artifact=resolve,
            execute_target=lambda ref, value: _base.TargetExecution(
                target=ref, value=actual[value["caseId"]]
            ),
            execute_judge=lambda ref, observed, wanted: _base.JudgeExecution(
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


def apply() -> dict[str, Any]:
    _configure_base()
    _base._skill_eval = _skill_eval
    _base._require_schema_head()
    canary_before = _base._canary_counts()
    if any(canary_before.values()):
        raise RuntimeError("negative tenant already contains R11 Skill authority")
    c02_before = _base._snapshot_a02()
    runtime = _base.AipModelRuntimeStore()
    route = runtime.get_route(_base.SCOPE, _base.ROUTE_ID)
    policy = runtime.get_policy(
        _base.SCOPE,
        route.runtime_policy_ref.asset_id,
        route.runtime_policy_ref.revision,
    )
    model = runtime.get_model(_base.SCOPE, _base.MODEL_ID)
    results = [
        _base._publish_one(logic_id, route, policy, model)
        for logic_id in CONTENT_OFFICER_LOGIC_IDS
    ]
    c02_after = _base._snapshot_a02()
    if c02_after != c02_before:
        raise RuntimeError("immutable C02 Skill authority changed during R11")
    canary_after = _base._canary_counts()
    if canary_after != canary_before:
        raise RuntimeError("R11 Skill authority leaked into negative tenant")
    return {
        "status": "R11_CONTENT_OFFICER_SKILL_PUBLICATION_GREEN",
        "scope": {"orgId": _base.SCOPE.org_id, "projectId": _base.SCOPE.project_id},
        "route": _base._exact_ref("ModelRouteRevision", route, "route_id").model_dump(
            mode="json", by_alias=True
        ),
        "policy": _base._exact_ref(
            "RuntimePolicyRevision", policy, "policy_id"
        ).model_dump(mode="json", by_alias=True),
        "skills": results,
        "preservedC02": c02_after,
        "negativeCanaryCounts": canary_after,
        "providerCalls": 0,
        "secretPayloadReads": 0,
        "bindingsCreated": 0,
        "agentRuns": 0,
        "externalContentActions": 0,
        "mediaGenerations": 0,
        "memoryPromotions": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = apply() if args.apply else build_plan()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, default=str))
    return 0


_configure_base()


if __name__ == "__main__":
    raise SystemExit(main())
