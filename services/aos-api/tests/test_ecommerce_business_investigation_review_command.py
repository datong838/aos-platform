"""BI-W8-04 Workshop-to-AIP canonical stage review command tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from aos_api.aip_business_investigation_compile_saga import (
    BusinessInvestigationCompilationReceipt,
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
    ExactArtifactRef,
    ExactRevisionRef,
    ReturnDecision,
    ReviewIssue,
    ReviewIssueStatus,
    ReviewSeverity,
)
from aos_api.ecommerce_business_investigation_projection import (
    BusinessInvestigationProjectionSource,
    BusinessInvestigationRuntimeSource,
    BusinessInvestigationStagePlanSource,
)
from aos_api.ecommerce_business_investigation_review_command import (
    BusinessInvestigationReviewCommandBlocked,
    BusinessInvestigationStageReviewCommand,
    EcommerceBusinessInvestigationReviewCommandService,
)
from aos_api.ecommerce_business_investigation_run import BusinessInvestigationRunView
from aos_api.tenant_scope import TenantScope
from test_ecommerce_business_investigation_lifecycle import draft_case, requested_run
from test_ecommerce_business_investigation_projection import _state


SCOPE = TenantScope("org-org", "dev-project")
NOW = datetime(2026, 8, 27, 8, tzinfo=UTC)
HASH = "a" * 64


def exact(kind: str, identity: str, fill: str = "a") -> ExactRevisionRef:
    return ExactRevisionRef(
        resource_type=kind,
        resource_id=identity,
        revision=1,
        content_hash=fill * 64,
    )


def source() -> BusinessInvestigationProjectionSource:
    case = draft_case("case-1")
    run = requested_run(case)
    return BusinessInvestigationProjectionSource(
        case=case,
        run=run,
        state=_state(),
        runtime=BusinessInvestigationRuntimeSource(
            task_id="task-1",
            plan_ref=run_plan_ref(),
            task_run_id="task-run-1",
            task_run_version=3,
            task_run_status=TaskRunStatus.RUNNING,
            plan_stages=tuple(
                BusinessInvestigationStagePlanSource(stage_id=stage)
                for stage in ("portrait", "diagnosis", "solution-design")
            ),
        ),
    )


def run_plan_ref():
    from aos_api.business_investigation_shared_contracts import InvestigationExactRef

    return InvestigationExactRef(
        resource_type="PlanRevision",
        resource_id="plan-1",
        revision=1,
        content_hash="sha256:" + "b" * 64,
    )


def receipt(src: BusinessInvestigationProjectionSource) -> BusinessInvestigationCompilationReceipt:
    return BusinessInvestigationCompilationReceipt(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        receipt_id="receipt-1",
        command_id="compile-1",
        request_hash="sha256:" + "1" * 64,
        run_ref={
            "resourceType": "BusinessInvestigationRun",
            "resourceId": src.run.run_id,
            "revision": src.run.version,
            "contentHash": src.run.content_hash,
        },
        task_id="task-1",
        plan_ref=exact("PlanRevision", "plan-1", "b"),
        profile_ref=exact("InvestigationProfileRevision", "profile-1", "c"),
        logic_ref=exact("LogicRevision", "logic-1", "d"),
        skill_binding_set_ref=exact("SkillBindingSetRevision", "skills-1", "e"),
        responsibility_plan_ref=exact("ResponsibilityPlanRevision", "roles-1", "f"),
        input_hash="2" * 64,
        stage_compilation_hash="3" * 64,
        compilation_hash="4" * 64,
        created_at=NOW,
    )


def report(*, task_run_id: str = "task-run-1") -> EvalReportRevision:
    policy = AssetRevisionRef(
        asset_type=AssetType.POLICY,
        asset_id="redaction-1",
        revision="1",
        content_hash="5" * 64,
    )
    return EvalReportRevision(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        report_id="report-1",
        revision=1,
        content_hash="6" * 64,
        run_id="eval-run-1",
        suite_ref=AssetRevisionRef(
            asset_type=AssetType.EVAL_SUITE,
            asset_id="suite-1",
            revision="1",
            content_hash="7" * 64,
        ),
        eval_contract_ref=EvalContractRevisionRef(
            resource_id="contract-1", revision=1, content_hash="8" * 64
        ),
        subject_artifact_ref=EvalSubjectArtifactRef(
            resource_id="artifact-1", content_hash="9" * 64
        ),
        stage_attempt_ref=EvalStageAttemptRef(
            run_id=task_run_id,
            step_key="portrait",
            step_run_id="step-run-1",
            attempt=1,
            input_hash="0" * 64,
        ),
        gate_policy_ref=EvalGatePolicyRef(
            resource_id="policy-1", revision=1, content_hash="1" * 64
        ),
        evidence_cutoff_at=NOW,
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
        judge=JudgeRevisionRef(
            judge_id="judge-1", revision=1, content_hash="5" * 64
        ),
        results=[
            {
                "caseId": "case-1",
                "passed": False,
                "actualHash": "6" * 64,
                "detailCode": "FAIL",
                "durationMs": 1,
            }
        ],
        passed=0,
        failed=1,
        total=1,
        pass_rate=0,
        gate_passed=False,
        created_at=NOW,
    )


def issue(**changes) -> ReviewIssue:
    value = ReviewIssue(
        tenant=TenantContext(org_id=SCOPE.org_id, project_id=SCOPE.project_id),
        issue_id="issue-1",
        status=ReviewIssueStatus.OPEN,
        version=1,
        created_by="reviewer-1",
        created_at=NOW,
        updated_by="reviewer-1",
        updated_at=NOW,
        rule_ref=exact("ReviewRuleRevision", "rule-1", "7"),
        severity=ReviewSeverity.ERROR,
        artifact_ref=ExactArtifactRef(
            artifact_id="artifact-1", content_hash="9" * 64
        ),
        eval_report_ref=exact("EvalReportRevision", "report-1", "6"),
        location={"stage": "portrait"},
        suggested_fix="补充证据后重新评估",
        return_stage="portrait",
    )
    return value.model_copy(update=changes)


class FixedStore:
    def __init__(self, value):
        self.value = value

    def get(self, _scope, _identity):
        return self.value


class FixedReceiptStore:
    def __init__(self, value):
        self.value = value

    def get_for_run(self, _scope, _run_ref):
        return self.value


class FixedProjectionReader:
    def __init__(self, value):
        self.value = value

    def read(self, _scope, _run_id):
        return self.value


class Reports:
    def __init__(self, value):
        self.value = value

    def get_report(self, *_args):
        return self.value


class Reviews:
    def __init__(self, value: ReviewIssue):
        self.value = value
        self.calls = []

    def list_review_issues(self, _scope):
        return SimpleNamespace(items=[self.value])

    def get_review_issue(self, _scope, _issue_id):
        return self.value

    def resolve_review_issue(self, _scope, _actor, _issue_id, key, body):
        self.calls.append(("accept", key, body))
        self.value = self.value.model_copy(
            update={"status": ReviewIssueStatus.RESOLVED, "version": 2}
        )
        return self.value

    def return_review_issue(self, _scope, actor, _issue_id, key, body):
        self.calls.append(("return", key, body))
        self.value = self.value.model_copy(
            update={"status": ReviewIssueStatus.RETURNED, "version": 2}
        )
        return ReturnDecision(
            tenant=self.value.tenant,
            decision_id="decision-1",
            issue_id=self.value.issue_id,
            issue_version=2,
            run_id=body.run_id,
            step_key=body.target_stage,
            step_run_id="step-run-2",
            attempt=2,
            attempt_idempotency_key=body.attempt_idempotency_key,
            reason=body.reason,
            impact_readiness="legacy_unavailable",
            decision_hash="8" * 64,
            actor=actor,
            created_at=NOW,
        )


def service(*, current_issue=None, current_report=None):
    src = source()
    reviews = Reviews(current_issue or issue())
    return (
        EcommerceBusinessInvestigationReviewCommandService(
            run_store=FixedStore(
                BusinessInvestigationRunView(authority=src.run, state=src.state)
            ),
            case_store=FixedStore(src.case),
            receipt_store=FixedReceiptStore(receipt(src)),
            projection_reader=FixedProjectionReader(src),
            reviews=reviews,
            reports=Reports(current_report or report()),
        ),
        reviews,
    )


def command(decision="accept", **changes):
    value = {
        "decision": decision,
        "issueId": "issue-1",
        "expectedIssueVersion": 1,
        "reason": "人工复核后的明确结论",
    }
    value.update(changes)
    return BusinessInvestigationStageReviewCommand.model_validate(value)


def test_projection_exposes_only_canonical_current_run_issue() -> None:
    target, _ = service()
    projection = target.projection(SCOPE, "run-1")
    assert projection.task_run_ref.resource_id == "task-run-1"
    assert projection.items[0].stage == "portrait"
    assert projection.items[0].allowed_decisions == ["accept", "return"]
    assert projection.items[0].eval_report_ref == issue().eval_report_ref
    assert projection.external_effects_allowed is False


def test_accept_derives_exact_resolution_refs_and_returns_canonical_issue() -> None:
    target, reviews = service()
    result = target.review_stage(
        SCOPE,
        "run-1",
        command(),
        expected_state_version=1,
        idempotency_key="review-command-1",
        actor="reviewer-1",
    )
    assert result.issue.status is ReviewIssueStatus.RESOLVED
    assert result.return_decision is None
    assert {ref.resource_type for ref in reviews.calls[0][2].resolution_refs} == {
        "Artifact", "EvalReportRevision"
    }


def test_return_derives_task_run_stage_and_attempt_key() -> None:
    target, reviews = service()
    result = target.review_stage(
        SCOPE,
        "run-1",
        command("return"),
        expected_state_version=1,
        idempotency_key="review-command-2",
        actor="reviewer-1",
    )
    assert result.issue.status is ReviewIssueStatus.RETURNED
    assert result.return_decision is not None
    body = reviews.calls[0][2]
    assert body.run_id == "task-run-1"
    assert body.target_stage == "portrait"
    assert body.attempt_idempotency_key.startswith("bi-review-return-")


@pytest.mark.parametrize(
    ("decision", "version", "report_value", "code"),
    [
        ("request_more", 1, None, "REQUEST_MORE_CANONICAL_AUTHORITY_UNAVAILABLE"),
        ("accept", 2, None, "RUN_STATE_VERSION_DRIFTED"),
        ("accept", 1, report(task_run_id="other-run"), "ISSUE_RUN_LINEAGE_DRIFTED"),
    ],
)
def test_unowned_or_unavailable_review_edges_fail_before_write(
    decision, version, report_value, code
) -> None:
    target, reviews = service(current_report=report_value)
    with pytest.raises(BusinessInvestigationReviewCommandBlocked, match=code):
        target.review_stage(
            SCOPE,
            "run-1",
            command(decision),
            expected_state_version=version,
            idempotency_key="review-command-blocked",
            actor="reviewer-1",
        )
    assert reviews.calls == []
