"""W-L14: return rework attempt must not be skipped by historical succeeded."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from aos_api.aip_contracts import PlanStep
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_production_contracts import (
    CreateReviewIssueRequest,
    ExactArtifactRef,
    ExactRevisionRef,
    ReturnReviewIssueRequest,
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
