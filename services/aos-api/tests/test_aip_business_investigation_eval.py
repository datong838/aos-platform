"""BI-W5-06 canonical stage Eval/Review coordination tests."""

from datetime import UTC, datetime

import pytest

from aos_api.aip_business_investigation_eval import (
    BusinessInvestigationEvalBlocked,
    BusinessInvestigationEvalCoordinator,
    BusinessInvestigationStageEvalRequest,
)
from aos_api.aip_business_investigation_runtime import (
    BusinessInvestigationRuntimeBinding,
    CanonicalCheckpointRef,
    CanonicalRuntimeRef,
)
from aos_api.aip_contracts import TaskRunStatus, TenantContext
from aos_api.aip_eval_contracts import (
    AssetRevisionRef,
    AssetType,
    DatasetRevisionRef,
    EvalContractRevisionRef,
    EvalGatePolicyRef,
    EvalReportRevision,
    EvalStageAttemptRef,
    EvalSubjectArtifactRef,
    JudgeRevisionRef,
)
from aos_api.aip_production_contracts import (
    CreateReviewIssueRequest,
    ExactArtifactRef,
    ExactRevisionRef,
    ReturnReviewIssueRequest,
    ReviewIssue,
    ReviewIssueStatus,
    ReviewSeverity,
)
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 26, 12, tzinfo=UTC)


def exact(kind: str, identity: str, fill: str) -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind, resource_id=identity, revision=1, content_hash=fill * 64
    )


def runtime(*, checkpoint=True):
    return BusinessInvestigationRuntimeBinding(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        case_ref=exact("BusinessInvestigationCaseRevision", "case-1", "1"),
        business_investigation_run_ref=exact(
            "BusinessInvestigationRun", "investigation-run-1", "2"
        ),
        compilation_hash="3" * 64,
        task_ref=CanonicalRuntimeRef(resource_type="Task", resource_id="task-1", version=1),
        plan_ref=exact("PlanRevision", "plan-1", "4"),
        task_run_ref=CanonicalRuntimeRef(
            resource_type="TaskRun", resource_id="task-run-1", version=1
        ),
        checkpoint_ref=(
            CanonicalCheckpointRef(
                resource_id="checkpoint-1", sequence=1, state_hash="5" * 64
            )
            if checkpoint
            else None
        ),
        task_run_status=TaskRunStatus.PAUSED,
        plan_step_count=3,
        binding_hash="6" * 64,
        start_authorized=False,
    )


def request():
    return BusinessInvestigationStageEvalRequest(
        stage="portrait",
        idempotency_key="eval-1",
        eval_contract_ref=EvalContractRevisionRef(
            resource_id="contract-1", revision=1, content_hash="a" * 64
        ),
        subject_artifact_ref=EvalSubjectArtifactRef(
            resource_id="artifact-1", content_hash="b" * 64
        ),
        stage_attempt_ref=EvalStageAttemptRef(
            run_id="task-run-1",
            step_key="portrait",
            step_run_id="step-run-1",
            attempt=1,
            input_hash="c" * 64,
        ),
        gate_policy_ref=EvalGatePolicyRef(
            resource_id="policy-1", revision=1, content_hash="d" * 64
        ),
        evidence_cutoff_at=NOW,
    )


def report(req, *, passed=1, failed=0, gate_passed=True):
    policy = AssetRevisionRef(
        asset_type=AssetType.POLICY,
        asset_id="redaction-1",
        revision="1",
        content_hash="e" * 64,
    )
    return EvalReportRevision(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        report_id="report-1",
        revision=1,
        content_hash="f" * 64,
        run_id="eval-run-1",
        suite_ref=AssetRevisionRef(
            asset_type=AssetType.EVAL_SUITE,
            asset_id="suite-1",
            revision="1",
            content_hash="1" * 64,
        ),
        eval_contract_ref=req.eval_contract_ref,
        subject_artifact_ref=req.subject_artifact_ref,
        stage_attempt_ref=req.stage_attempt_ref,
        gate_policy_ref=req.gate_policy_ref,
        evidence_cutoff_at=req.evidence_cutoff_at,
        target=AssetRevisionRef(
            asset_type=AssetType.LOGIC_GRAPH,
            asset_id="target-1",
            revision="1",
            content_hash="2" * 64,
        ),
        dataset=DatasetRevisionRef(
            dataset_id="dataset-1",
            revision=1,
            content_hash="3" * 64,
            source_hash="4" * 64,
            redaction_policy=policy,
        ),
        judge=JudgeRevisionRef(judge_id="judge-1", revision=1, content_hash="5" * 64),
        results=[
            {
                "caseId": f"case-{index}",
                "passed": index < passed,
                "actualHash": "6" * 64,
                "detailCode": "PASS" if index < passed else "FAIL",
                "durationMs": 1,
            }
            for index in range(passed + failed)
        ],
        passed=passed,
        failed=failed,
        total=passed + failed,
        pass_rate=round(passed / (passed + failed), 6),
        gate_passed=gate_passed,
        created_at=NOW,
    )


class Runner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run_by_contract(self, scope, **kwargs):
        self.calls.append((scope, kwargs))
        return self.result


class Reviews:
    def __init__(self):
        self.calls = []

    def create_review_issue(self, *args):
        self.calls.append(("create", args))
        return "issue"

    def return_review_issue(self, *args):
        self.calls.append(("return", args))
        return "decision"


def test_passed_eval_never_auto_promotes_and_uses_exact_contract() -> None:
    req = request()
    runner = Runner(report(req))
    gate = BusinessInvestigationEvalCoordinator(runner, Reviews()).evaluate_stage(
        SCOPE,
        runtime(),
        req,
        "aip:investigation",
        created_at=NOW,
        resolve_artifact=object(),
        execute_target=object(),
        execute_judge=object(),
    )
    assert gate.gate_passed is True
    assert gate.automatic_promotion_allowed is False
    assert gate.next_allowed_commands == ["request-human-stage-decision"]
    assert runner.calls[0][1]["contract_id"] == "contract-1"
    assert runner.calls[0][1]["stage_attempt_ref"] == req.stage_attempt_ref


def test_failed_eval_only_exposes_explicit_review_command() -> None:
    req = request()
    gate = BusinessInvestigationEvalCoordinator(
        Runner(report(req, passed=0, failed=1, gate_passed=False)), Reviews()
    ).evaluate_stage(
        SCOPE,
        runtime(),
        req,
        "owner",
        created_at=NOW,
        resolve_artifact=object(),
        execute_target=object(),
        execute_judge=object(),
    )
    assert gate.automatic_promotion_allowed is False
    assert gate.next_allowed_commands == ["open-review-issue"]
    reviews = Reviews()
    coordinator = BusinessInvestigationEvalCoordinator(Runner(report(req)), reviews)
    issue = CreateReviewIssueRequest(
        rule_ref=exact("EvalRuleRevision", "rule-1", "7"),
        severity=ReviewSeverity.ERROR,
        artifact_ref=ExactArtifactRef(
            artifact_id="artifact-1", content_hash="b" * 64
        ),
        eval_report_ref=gate.eval_report_ref,
        location={"stage": "portrait"},
        suggested_fix="revise evidence-backed portrait",
        return_stage="portrait",
    )
    assert coordinator.open_review_issue(SCOPE, gate, "owner", "issue-1", issue) == "issue"
    assert reviews.calls[0][0] == "create"
    with pytest.raises(BusinessInvestigationEvalBlocked, match="ARTIFACT_DRIFTED"):
        coordinator.open_review_issue(
            SCOPE,
            gate,
            "owner",
            "issue-2",
            issue.model_copy(
                update={"artifact_ref": ExactArtifactRef(
                    artifact_id="other", content_hash="b" * 64
                )}
            ),
        )


def test_runtime_attempt_or_report_drift_fails_closed() -> None:
    req = request()
    with pytest.raises(BusinessInvestigationEvalBlocked, match="CHECKPOINT_REQUIRED"):
        BusinessInvestigationEvalCoordinator(Runner(report(req)), Reviews()).evaluate_stage(
            SCOPE,
            runtime(checkpoint=False),
            req,
            "owner",
            created_at=NOW,
            resolve_artifact=object(),
            execute_target=object(),
            execute_judge=object(),
        )
    drifted = report(req).model_copy(
        update={"eval_contract_ref": EvalContractRevisionRef(
            resource_id="other", revision=1, content_hash="a" * 64
        )}
    )
    with pytest.raises(BusinessInvestigationEvalBlocked, match="REPORT_CONTRACT_DRIFTED"):
        BusinessInvestigationEvalCoordinator(Runner(drifted), Reviews()).evaluate_stage(
            SCOPE,
            runtime(),
            req,
            "owner",
            created_at=NOW,
            resolve_artifact=object(),
            execute_target=object(),
            execute_judge=object(),
        )


def test_return_issue_is_explicit_and_runtime_bound() -> None:
    req = request()
    reviews = Reviews()
    coordinator = BusinessInvestigationEvalCoordinator(Runner(report(req)), reviews)
    issue = ReviewIssue(
        tenant=TenantContext(org_id="org-org", project_id="dev-project"),
        issue_id="issue-1",
        status=ReviewIssueStatus.OPEN,
        version=1,
        created_by="owner",
        created_at=NOW,
        updated_by="owner",
        updated_at=NOW,
        rule_ref=exact("EvalRuleRevision", "rule-1", "7"),
        severity=ReviewSeverity.ERROR,
        artifact_ref=ExactArtifactRef(
            artifact_id="artifact-1", content_hash="b" * 64
        ),
        eval_report_ref=exact("EvalReportRevision", "report-1", "f"),
        location={"stage": "portrait"},
        suggested_fix="revise portrait",
        return_stage="portrait",
    )
    command = ReturnReviewIssueRequest(
        expected_version=1,
        run_id="task-run-1",
        target_stage="portrait",
        reason="failed evidence gate",
        attempt_idempotency_key="return-attempt-1",
    )
    assert coordinator.return_review_issue(
        SCOPE, runtime(), issue, "owner", "return-1", command
    ) == "decision"
    assert reviews.calls[0][0] == "return"
    with pytest.raises(BusinessInvestigationEvalBlocked, match="RETURN_RUN_DRIFTED"):
        coordinator.return_review_issue(
            SCOPE,
            runtime(),
            issue,
            "owner",
            "return-2",
            command.model_copy(update={"run_id": "other-run"}),
        )
