"""W-L14: return rework attempt must not be skipped by historical succeeded."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from aos_api.aip_contracts import PlanStep
from aos_api.aip_production_contract_store import (
    AipProductionContractStore,
    ProductionContractDependencyBlocked,
)
from aos_api.aip_production_contracts import (
    CreateReviewIssueRequest,
    ExactArtifactRef,
    ExactRevisionRef,
    ReturnReviewIssueRequest,
    ResolveReviewIssueRequest,
    RegisterReviewRuleRevisionRequest,
    ReviewSeverity,
)
from aos_api.aip_task_models import (
    CreatePlanRevisionRequest,
    CreateTaskRequest,
    CreateTaskRunRequest,
)
from aos_api.aip_task_store import AipTaskStore, AipTaskTransitionBlocked
from aos_api.db import connect
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("dev-org", "dev-project")
ACTOR = "test:w-l14"
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def _key(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def _exact(kind: str, identifier: str, digest: str = HASH_A) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind,
        resource_id=identifier,
        revision=1,
        content_hash=digest,
    )


def _seed_review_authorities() -> dict[str, str]:
    suffix = uuid.uuid4().hex[:12]
    artifact_id = f"artifact-l14-{suffix}"
    evidence_id = f"evidence-l14-{suffix}"
    eval_run_id = f"eval-run-l14-{suffix}"
    report_id = f"eval-report-l14-{suffix}"
    now = datetime.now(timezone.utc)
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_review_rule_revision
            (org_id,project_id,rule_id,revision,spec,content_hash,created_by)
            VALUES(%s,%s,'rule-l14',1,'{"check":"legacy-l14"}'::jsonb,%s,%s)
            ON CONFLICT DO NOTHING""",
            (*SCOPE.key, HASH_A, ACTOR),
        )
        conn.execute(
            """INSERT INTO aip_artifact
            (org_id,project_id,artifact_id,artifact_type,content_hash,created_by)
            VALUES(%s,%s,%s,'content',%s,%s)""",
            (*SCOPE.key, artifact_id, HASH_A, ACTOR),
        )
        conn.execute(
            """INSERT INTO aip_evidence
            (org_id,project_id,evidence_id,evidence_type,subject_ref,source_type,
             source_ref,observed_at,freshness_at,content_hash,created_by)
            VALUES(%s,%s,%s,'review','{}','database','w-l14',%s,%s,%s,%s)""",
            (*SCOPE.key, evidence_id, now, now, HASH_C, ACTOR),
        )
        conn.execute(
            """INSERT INTO aip_eval_run
            (org_id,project_id,run_id,suite_id,suite_revision,suite_hash,target_ref,
             dataset_ref,judge_ref,status,idempotency_key,created_by,started_at,finished_at)
            VALUES(%s,%s,%s,'suite-l14',1,%s,'{}','{}','{}','succeeded',%s,%s,%s,%s)""",
            (*SCOPE.key, eval_run_id, HASH_A, eval_run_id, ACTOR, now, now),
        )
        conn.execute(
            """INSERT INTO aip_eval_report_revision
            (org_id,project_id,report_id,revision,content_hash,run_id,suite_ref,
             target_ref,dataset_ref,judge_ref,results,passed,failed,total,pass_rate,
             gate_passed,created_at)
            VALUES(%s,%s,%s,1,%s,%s,'{}','{}','{}','{}','[{"case":"l14"}]',
             1,0,1,1.0,true,%s)""",
            (*SCOPE.key, report_id, HASH_B, eval_run_id, now),
        )
        conn.commit()
    return {
        "artifact": artifact_id,
        "evidence": evidence_id,
        "report": report_id,
    }


def test_return_after_succeeded_keeps_latest_attempt_claimable() -> None:
    authority = _seed_review_authorities()
    task_store = AipTaskStore()
    task = task_store.create_task(
        SCOPE,
        ACTOR,
        _key("task"),
        CreateTaskRequest(title="返工不被跳过"),
    )
    plan = task_store.create_plan(
        SCOPE,
        ACTOR,
        task.id,
        _key("plan"),
        CreatePlanRevisionRequest(
            expected_task_version=task.version,
            steps=[PlanStep(step_key="draft", title="生成草稿")],
        ),
    )
    task_store.approve_plan(
        SCOPE, ACTOR, task.id, plan.revision, task.version + 1, plan.content_hash
    )
    run = task_store.create_run(
        SCOPE,
        ACTOR,
        task.id,
        _key("run"),
        CreateTaskRunRequest(
            plan_revision_id=plan.id, expected_task_version=task.version + 2
        ),
    )
    task_store.start_run(
        SCOPE,
        run.id,
        expected_run_version=run.version,
        expected_task_version=task.version + 2,
        actor=ACTOR,
        idempotency_key=_key("start"),
    )
    old_step_run_id = f"step-run-{uuid.uuid4().hex[:20]}"
    with connect(SCOPE) as conn:
        conn.execute(
            """INSERT INTO aip_step_run
            (org_id,project_id,step_run_id,run_id,step_key,attempt,status,input_refs)
            VALUES(%s,%s,%s,%s,'draft',1,'succeeded','[{"legacy":true}]'::jsonb)""",
            (*SCOPE.key, old_step_run_id, run.id),
        )
        conn.commit()

    # Historical succeeded alone would previously allow complete_run — still true
    # until return inserts a newer queued attempt.
    store = AipProductionContractStore()
    issue = store.create_review_issue(
        SCOPE,
        ACTOR,
        _key("issue"),
        CreateReviewIssueRequest(
            rule_ref=_exact("EvalRuleRevision", "rule-l14"),
            severity=ReviewSeverity.ERROR,
            artifact_ref=ExactArtifactRef(
                artifact_id=authority["artifact"], content_hash=HASH_A
            ),
            eval_report_ref=_exact(
                "EvalReportRevision", authority["report"], HASH_B
            ),
            location={"path": "title"},
            evidence_refs=[_exact("Evidence", authority["evidence"], HASH_C)],
            suggested_fix="按评审返工",
            return_stage="draft",
        ),
    )
    decision = store.return_review_issue(
        SCOPE,
        ACTOR,
        issue.issue_id,
        _key("return"),
        ReturnReviewIssueRequest(
            expected_version=issue.version,
            run_id=run.id,
            target_stage="draft",
            reason="返工必须执行 attempt N+1",
            attempt_idempotency_key=_key("attempt"),
        ),
    )
    assert decision.attempt == 2
    assert decision.impact_readiness == "exact"
    assert [(item.step_key, item.action.value) for item in decision.impact_decisions] == [
        ("draft", "invalidate")
    ]

    with connect(SCOPE) as conn:
        rows = conn.execute(
            """SELECT attempt,status,input_refs FROM aip_step_run
            WHERE org_id=%s AND project_id=%s AND run_id=%s AND step_key='draft'
            ORDER BY attempt""",
            (*SCOPE.key, run.id),
        ).fetchall()
    assert [(row["attempt"], row["status"]) for row in rows] == [
        (1, "succeeded"),
        (2, "queued"),
    ]
    refs = rows[1]["input_refs"]
    types = {item.get("resourceType") for item in refs}
    assert {"ReviewIssue", "ReturnDecision", "Artifact"} <= types
    assert any(
        item.get("resourceId") == decision.decision_id for item in refs
    )

    with pytest.raises(AipTaskTransitionBlocked, match="all plan steps must succeed"):
        task_store.complete_run(SCOPE, run.id)

    lease = task_store.claim_step(
        SCOPE, run.id, "draft", "worker-l14", lease_seconds=30
    )
    assert lease.attempt == 2
    assert lease.step_run_id == decision.step_run_id

    listed = store.list_return_decisions(SCOPE, issue_id=issue.issue_id)
    assert listed.count == 1
    assert listed.items[0].decision_id == decision.decision_id
    got = store.get_return_decision(SCOPE, decision.decision_id)
    assert got.decision_hash == decision.decision_hash

    with connect(SCOPE) as conn:
        event = conn.execute(
            """SELECT payload,payload_hash FROM aip_review_issue_event
            WHERE org_id=%s AND project_id=%s AND issue_id=%s AND sequence=2""",
            (*SCOPE.key, issue.issue_id),
        ).fetchone()
    assert event["payload"]["decisionHash"] == decision.decision_hash


def test_return_impact_uses_explicit_transitive_dag_and_rejects_ambiguous_plan() -> None:
    impact = AipProductionContractStore._review_return_impact(
        [
            {"stepKey": "research"},
            {"stepKey": "draft"},
            {"stepKey": "review"},
            {"stepKey": "publish"},
        ],
        [
            {"fromStepKey": "research", "toStepKey": "draft"},
            {"fromStepKey": "draft", "toStepKey": "review"},
            {"fromStepKey": "review", "toStepKey": "publish"},
        ],
        "draft",
    )
    assert [(item.step_key, item.action.value) for item in impact] == [
        ("research", "reuse"),
        ("draft", "invalidate"),
        ("review", "invalidate"),
        ("publish", "invalidate"),
    ]

    with pytest.raises(ProductionContractDependencyBlocked, match="RETURN_PLAN_DAG_MISSING"):
        AipProductionContractStore._review_return_impact(
            [{"stepKey": "draft"}, {"stepKey": "review"}], [], "draft"
        )
    with pytest.raises(ProductionContractDependencyBlocked, match="RETURN_PLAN_DAG_CYCLE"):
        AipProductionContractStore._review_return_impact(
            [{"stepKey": "draft"}, {"stepKey": "review"}],
            [
                {"fromStepKey": "draft", "toStepKey": "review"},
                {"fromStepKey": "review", "toStepKey": "draft"},
            ],
            "draft",
        )


def test_review_rule_and_resolution_refs_fail_closed() -> None:
    authority = _seed_review_authorities()
    store = AipProductionContractStore()
    with pytest.raises(ProductionContractDependencyBlocked, match="REVIEW_RULE_DRIFTED"):
        store.create_review_issue(
            SCOPE, ACTOR, _key("drifted-rule"),
            CreateReviewIssueRequest(
                rule_ref=_exact("EvalRuleRevision", "rule-l14", HASH_B),
                severity=ReviewSeverity.ERROR,
                artifact_ref=ExactArtifactRef(
                    artifact_id=authority["artifact"], content_hash=HASH_A
                ),
                eval_report_ref=_exact("EvalReportRevision", authority["report"], HASH_B),
                location={"path": "title"},
                evidence_refs=[_exact("Evidence", authority["evidence"], HASH_C)],
                suggested_fix="rule hash 漂移必须阻断",
                return_stage="draft",
            ),
        )
    issue = store.create_review_issue(
        SCOPE, ACTOR, _key("valid-rule"),
        CreateReviewIssueRequest(
            rule_ref=_exact("EvalRuleRevision", "rule-l14", HASH_A),
            severity=ReviewSeverity.ERROR,
            artifact_ref=ExactArtifactRef(
                artifact_id=authority["artifact"], content_hash=HASH_A
            ),
            eval_report_ref=_exact("EvalReportRevision", authority["report"], HASH_B),
            location={"path": "title"},
            evidence_refs=[_exact("Evidence", authority["evidence"], HASH_C)],
            suggested_fix="校验 resolution refs",
            return_stage="draft",
        ),
    )
    with pytest.raises(ProductionContractDependencyBlocked, match="EVIDENCE_MISSING"):
        store.resolve_review_issue(
            SCOPE, ACTOR, issue.issue_id, _key("resolve-missing"),
            ResolveReviewIssueRequest(
                expectedVersion=issue.version,
                reason="不存在的 evidence 不得解决问题",
                resolutionRefs=[_exact("Evidence", "missing-evidence", HASH_C)],
            ),
        )


def test_review_rule_revision_is_exact_append_only_authority() -> None:
    store = AipProductionContractStore()
    suffix = uuid.uuid4().hex[:12]
    rule = store.register_review_rule_revision(
        SCOPE, ACTOR, _key("rule-register"),
        RegisterReviewRuleRevisionRequest(
            ruleId=f"rule-w4-04-{suffix}",
            revision=1,
            spec={"check": "evidence-required", "severity": "error"},
        ),
    )
    assert rule.content_hash == store.get_review_rule_revision(
        SCOPE, rule.rule_id, 1
    ).content_hash
    assert any(
        item.rule_id == rule.rule_id
        for item in store.list_review_rule_revisions(SCOPE).items
    )
