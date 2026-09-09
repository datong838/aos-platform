from datetime import UTC, datetime, timedelta

import pytest
from psycopg.types.json import Jsonb

from aos_api.aip_eval_contracts import EvalReportRevision
from aos_api.aip_eval_runner import compute_eval_report_hash
from aos_api.aip_production_contracts import ReviewIssue
from aos_api.db import connect_serializable
from aos_api.ecommerce_business_investigation_review_command import review_issue_exact_ref
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import ReviewAdvanceHostService
from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
NOW = datetime(2026, 9, 9, 7, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64


def report(*, artifact_id: str, artifact_hash: str = HASH_A) -> EvalReportRevision:
    value = EvalReportRevision.model_validate(
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "reportId": "review-eval-report-1",
            "revision": 1,
            "contentHash": "0" * 64,
            "runId": "review-eval-run-1",
            "suiteRef": {
                "assetType": "eval_suite",
                "assetId": "review-suite-1",
                "revision": "1",
                "contentHash": HASH_A,
            },
            "subjectArtifactRef": {
                "resourceType": "Artifact",
                "resourceId": artifact_id,
                "contentHash": artifact_hash,
            },
            "stageAttemptRef": {
                "resourceType": "StepRunAttempt",
                "runId": "investigation-run-1",
                "stepKey": "diagnosis",
                "stepRunId": "step-run-diagnosis-1",
                "attempt": 1,
                "inputHash": HASH_B,
            },
            "gatePolicyRef": {
                "resourceType": "MediaGatePolicyRevision",
                "resourceId": "review-policy-1",
                "revision": 1,
                "contentHash": HASH_C,
            },
            "evidenceCutoffAt": NOW - timedelta(hours=1),
            "target": {
                "assetType": "logic_graph",
                "assetId": "review-target-1",
                "revision": "1",
                "contentHash": HASH_A,
            },
            "dataset": {
                "datasetId": "review-dataset-1",
                "revision": 1,
                "contentHash": HASH_B,
                "sourceHash": HASH_C,
                "redactionPolicy": {
                    "assetType": "policy",
                    "assetId": "redaction-policy-1",
                    "revision": "1",
                    "contentHash": HASH_A,
                },
            },
            "judge": {
                "judgeId": "review-judge-1",
                "revision": 1,
                "contentHash": HASH_B,
            },
            "results": [
                {
                    "caseId": "review-case-1",
                    "passed": True,
                    "actualHash": HASH_A,
                    "detailCode": "PASS",
                    "durationMs": 1,
                }
            ],
            "passed": 1,
            "failed": 0,
            "total": 1,
            "passRate": 1.0,
            "gatePassed": True,
            "createdAt": NOW,
        }
    )
    return value.model_copy(update={"content_hash": compute_eval_report_hash(value)})


def issue(*, report_value: EvalReportRevision) -> ReviewIssue:
    return ReviewIssue.model_validate(
        {
            "tenant": {"orgId": SCOPE.org_id, "projectId": SCOPE.project_id},
            "issueId": "review-issue-1",
            "ruleRef": {
                "resourceType": "ReviewRuleRevision",
                "resourceId": "review-rule-1",
                "revision": 1,
                "contentHash": HASH_C,
            },
            "severity": "error",
            "artifactRef": {"artifactId": "review-artifact-1", "contentHash": HASH_A},
            "evalReportRef": {
                "resourceType": "EvalReportRevision",
                "resourceId": report_value.report_id,
                "revision": report_value.revision,
                "contentHash": report_value.content_hash,
            },
            "location": {"stage": "diagnosis"},
            "evidenceRefs": [],
            "suggestedFix": "补齐诊断依据",
            "returnStage": "diagnosis",
            "status": "open",
            "version": 1,
            "createdBy": "user:reviewer",
            "createdAt": NOW,
            "updatedBy": "user:reviewer",
            "updatedAt": NOW,
        }
    )


def command(issue_value: ReviewIssue, report_value: EvalReportRevision) -> dict[str, object]:
    return {
        "reviewIssueRef": review_issue_exact_ref(issue_value).model_dump(
            mode="json", by_alias=True
        ),
        "evalReportRef": {
            "resourceType": "EvalReportRevision",
            "resourceId": report_value.report_id,
            "revision": report_value.revision,
            "contentHash": "sha256:" + report_value.content_hash,
        },
    }


def issue_row(value: ReviewIssue) -> dict[str, object]:
    return {
        "issue_id": value.issue_id,
        "rule_ref": value.rule_ref.model_dump(mode="json", by_alias=True),
        "severity": value.severity.value,
        "artifact_id": value.artifact_ref.artifact_id,
        "artifact_hash": value.artifact_ref.content_hash,
        "eval_report_id": value.eval_report_ref.resource_id,
        "eval_report_revision": value.eval_report_ref.revision,
        "eval_report_hash": value.eval_report_ref.content_hash,
        "location": value.location,
        "evidence_refs": [],
        "suggested_fix": value.suggested_fix,
        "return_stage": value.return_stage,
        "status": value.status.value,
        "version": value.version,
        "created_by": value.created_by,
        "created_at": value.created_at,
        "updated_by": value.updated_by,
        "updated_at": value.updated_at,
    }


def report_row(value: EvalReportRevision) -> dict[str, object]:
    return {
        "report_id": value.report_id,
        "revision": value.revision,
        "content_hash": value.content_hash,
        "run_id": value.run_id,
        "suite_ref": value.suite_ref.model_dump(mode="json", by_alias=True),
        "eval_contract_ref": None,
        "subject_artifact_ref": value.subject_artifact_ref.model_dump(mode="json", by_alias=True),
        "stage_attempt_ref": value.stage_attempt_ref.model_dump(mode="json", by_alias=True),
        "gate_policy_ref": value.gate_policy_ref.model_dump(mode="json", by_alias=True),
        "evidence_cutoff_at": value.evidence_cutoff_at,
        "target_ref": value.target.model_dump(mode="json", by_alias=True),
        "dataset_ref": value.dataset.model_dump(mode="json", by_alias=True),
        "judge_ref": value.judge.model_dump(mode="json", by_alias=True),
        "results": [item.model_dump(mode="json", by_alias=True) for item in value.results],
        "passed": value.passed,
        "failed": value.failed,
        "total": value.total,
        "pass_rate": value.pass_rate,
        "gate_passed": value.gate_passed,
        "created_at": value.created_at,
    }


class FakeTransaction:
    def __init__(self, *rows):
        self._rows = iter(rows)

    def execute(self, _query, _params):
        row = next(self._rows)

        class Result:
            def fetchone(self):
                return row

        return Result()


@pytest.mark.parametrize("drift", ["issue_boolean_revision", "eval_boolean_passed"])
def test_review_issue_eval_rejects_raw_json_type_drift(drift):
    valid_report = report(artifact_id="review-artifact-1")
    valid_issue = issue(report_value=valid_report)
    raw_issue = issue_row(valid_issue)
    raw_report = report_row(valid_report)
    if drift == "issue_boolean_revision":
        raw_issue["rule_ref"] = {**raw_issue["rule_ref"], "revision": True}
    else:
        raw_report["results"] = [{**raw_report["results"][0], "passed": 1}]
    with pytest.raises(ValueError, match="current OPEN|exact authority"):
        ReviewAdvanceHostService._revalidate_issue_eval(
            transaction=FakeTransaction(raw_issue, raw_report),
            scope=SCOPE,
            command=command(valid_issue, valid_report),
        )


def test_review_issue_eval_rejects_subject_artifact_drift():
    mismatched_report = report(artifact_id="other-artifact")
    linked_issue = issue(report_value=mismatched_report)
    with pytest.raises(ValueError, match="lineage drifted"):
        ReviewAdvanceHostService._revalidate_issue_eval(
            transaction=FakeTransaction(
                issue_row(linked_issue), report_row(mismatched_report)
            ),
            scope=SCOPE,
            command=command(linked_issue, mismatched_report),
        )


def test_review_issue_eval_requires_current_open_public_lineage_and_rolls_back():
    host = ReviewAdvanceHostService()
    valid_report = report(artifact_id="review-artifact-1")
    valid_issue = issue(report_value=valid_report)
    with connect_serializable(SCOPE) as conn:
        transaction = HostTransaction(conn)
        conn.execute(
            """INSERT INTO public.aip_artifact
                (org_id,project_id,artifact_id,artifact_type,content_hash,created_by,created_at)
                VALUES(%s,%s,%s,'business_investigation_diagnosis',%s,%s,%s)""",
            (*SCOPE.key, valid_issue.artifact_ref.artifact_id, HASH_A, "user:reviewer", NOW),
        )
        conn.execute(
            """INSERT INTO public.aip_eval_run
                (org_id,project_id,run_id,suite_id,suite_revision,suite_hash,target_ref,
                 dataset_ref,judge_ref,status,idempotency_key,created_by,started_at,finished_at)
                VALUES(%s,%s,%s,'review-suite-1',1,%s,%s,%s,%s,'succeeded',%s,%s,%s,%s)""",
            (
                *SCOPE.key,
                valid_report.run_id,
                HASH_A,
                Jsonb(valid_report.target.model_dump(mode="json", by_alias=True)),
                Jsonb(valid_report.dataset.model_dump(mode="json", by_alias=True)),
                Jsonb(valid_report.judge.model_dump(mode="json", by_alias=True)),
                valid_report.run_id,
                "user:reviewer",
                NOW,
                NOW,
            ),
        )
        conn.execute(
            """INSERT INTO public.aip_eval_report_revision
                (org_id,project_id,report_id,revision,content_hash,run_id,suite_ref,
                 target_ref,dataset_ref,judge_ref,results,passed,failed,total,pass_rate,
                 gate_passed,created_at,subject_artifact_ref,stage_attempt_ref,
                 gate_policy_ref,evidence_cutoff_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *SCOPE.key,
                valid_report.report_id,
                valid_report.revision,
                valid_report.content_hash,
                valid_report.run_id,
                Jsonb(valid_report.suite_ref.model_dump(mode="json", by_alias=True)),
                Jsonb(valid_report.target.model_dump(mode="json", by_alias=True)),
                Jsonb(valid_report.dataset.model_dump(mode="json", by_alias=True)),
                Jsonb(valid_report.judge.model_dump(mode="json", by_alias=True)),
                Jsonb([item.model_dump(mode="json", by_alias=True) for item in valid_report.results]),
                valid_report.passed,
                valid_report.failed,
                valid_report.total,
                valid_report.pass_rate,
                valid_report.gate_passed,
                valid_report.created_at,
                Jsonb(valid_report.subject_artifact_ref.model_dump(mode="json", by_alias=True)),
                Jsonb(valid_report.stage_attempt_ref.model_dump(mode="json", by_alias=True)),
                Jsonb(valid_report.gate_policy_ref.model_dump(mode="json", by_alias=True)),
                valid_report.evidence_cutoff_at,
            ),
        )
        conn.execute(
            """INSERT INTO public.aip_review_issue
                (org_id,project_id,issue_id,rule_ref,severity,artifact_id,artifact_hash,
                 eval_report_id,eval_report_revision,eval_report_hash,location,evidence_refs,
                 suggested_fix,return_stage,status,version,created_by,created_at,updated_by,updated_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *SCOPE.key,
                valid_issue.issue_id,
                Jsonb(valid_issue.rule_ref.model_dump(mode="json", by_alias=True)),
                valid_issue.severity.value,
                valid_issue.artifact_ref.artifact_id,
                valid_issue.artifact_ref.content_hash,
                valid_issue.eval_report_ref.resource_id,
                valid_issue.eval_report_ref.revision,
                valid_issue.eval_report_ref.content_hash,
                Jsonb(valid_issue.location),
                Jsonb([]),
                valid_issue.suggested_fix,
                valid_issue.return_stage,
                valid_issue.status.value,
                valid_issue.version,
                valid_issue.created_by,
                valid_issue.created_at,
                valid_issue.updated_by,
                valid_issue.updated_at,
            ),
        )
        valid_command = command(valid_issue, valid_report)
        host._revalidate_issue_eval(transaction=transaction, scope=SCOPE, command=valid_command)

        tampered = {**valid_command, "evalReportRef": {**valid_command["evalReportRef"], "contentHash": "sha256:" + HASH_B}}
        with pytest.raises(ValueError, match="EvalReport exact authority"):
            host._revalidate_issue_eval(transaction=transaction, scope=SCOPE, command=tampered)
        with pytest.raises(ValueError, match="missing"):
            host._revalidate_issue_eval(transaction=transaction, scope=CANARY, command=valid_command)

        conn.execute("CREATE TEMP TABLE aip_review_issue (LIKE public.aip_review_issue INCLUDING DEFAULTS)")
        conn.execute("CREATE TEMP TABLE aip_eval_report_revision (LIKE public.aip_eval_report_revision INCLUDING DEFAULTS)")
        host._revalidate_issue_eval(transaction=transaction, scope=SCOPE, command=valid_command)

        conn.execute(
            """UPDATE public.aip_review_issue SET status='resolved',version=2,
                       updated_by='user:reviewer',updated_at=%s
                WHERE org_id=%s AND project_id=%s AND issue_id=%s""",
            (NOW + timedelta(minutes=1), *SCOPE.key, valid_issue.issue_id),
        )
        with pytest.raises(ValueError, match="current OPEN"):
            host._revalidate_issue_eval(transaction=transaction, scope=SCOPE, command=valid_command)

        conn.rollback()
        assert conn.execute(
            """SELECT count(*) AS n FROM public.aip_review_issue
                WHERE org_id=%s AND project_id=%s AND issue_id=%s""",
            (*SCOPE.key, valid_issue.issue_id),
        ).fetchone()["n"] == 0
