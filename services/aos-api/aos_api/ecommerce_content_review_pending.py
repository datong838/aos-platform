"""Read-only candidate for a settled content Artifact's human review.

This is not a GET route and does not run Eval or create a ReviewIssue. A
candidate only names already-persisted, independently verifiable records.
"""

from __future__ import annotations

from dataclasses import dataclass

from aos_api.aip_eval_runner import AipEvalRunner, compute_eval_report_hash
from aos_api.aip_production_contract_store import AipProductionContractStore
from aos_api.aip_release_publication_service import AipReleasePublicationError, AipReleasePublicationService
from aos_api.ecommerce_content_eval_plan_gate import require_original_content_eval_gate
from aos_api.ecommerce_content_pre_review_authority import require_current_content_pre_review_gate
from aos_api.ecommerce_content_step_owner import ContentGenerationStepOwner, ContentGenerationStepSource
from aos_api.ecommerce_growth_runtime_adapters import _request_hash
from aos_api.ecommerce_growth_runtime_connection import connect_read_only
from aos_api.tenant_scope import TenantScope


class ContentReviewPendingBlocked(ValueError):
    """Authority drift or ambiguity; never manufacture a report or issue."""


@dataclass(frozen=True)
class ContentReviewPendingCandidate:
    reservation_id: str
    run_id: str
    task_id: str
    artifact_id: str
    artifact_hash: str
    step_run_id: str
    report_id: str
    report_revision: int
    report_hash: str


class ContentReviewPendingReader:
    def __init__(self, *, source=None, connect_read=connect_read_only):
        self.source = source or ContentGenerationStepSource()
        self.connect_read = connect_read

    @staticmethod
    def _current_dispatch(conn, scope: TenantScope, command: dict) -> None:
        if (
            type(command) is not dict
            or type(command.get("idempotencyKey")) is not str
            or type(command.get("requestHash")) is not str
        ):
            raise ContentReviewPendingBlocked("content original dispatch command is missing")
        row = conn.execute(
            """SELECT o.request_hash,o.response
                 FROM public.ecommerce_growth_runtime_command_receipt o
                 JOIN public.extension_operation_dispatch_binding d
                   ON d.org_id=o.org_id AND d.project_id=o.project_id
                  AND d.operation_id=o.operation_id
                 JOIN public.extension_runtime_binding b
                   ON b.org_id=o.org_id AND b.project_id=o.project_id
                  AND b.installation_id=o.installation_id AND b.generation=o.generation
                WHERE o.org_id=%s AND o.project_id=%s
                  AND o.operation_id='ecommerce_growth_content_generate'
                  AND o.idempotency_key=%s
                  AND d.handler_kind='extension' AND d.operation_fence=false
                  AND d.revision=o.dispatch_revision
                  AND d.installation_id=o.installation_id AND d.generation=o.generation
                  AND d.execution_epoch=o.execution_epoch
                  AND d.cutover_group_id=o.cutover_group_id
                  AND d.cutover_group_revision=o.cutover_group_revision
                  AND b.revision=o.runtime_revision
                  AND b.execution_epoch=o.execution_epoch
                  AND b.desired_state='enabled' AND b.observed_state='ready'
                  AND b.enabled=true AND b.operation_fence=false""",
            (*scope.key, command["idempotencyKey"]),
        ).fetchone()
        if (
            row is None or row["request_hash"] != _request_hash(command)
            or type(row["response"]) is not dict
            or row["response"].get("state") != "PENDING"
        ):
            raise ContentReviewPendingBlocked("content current dispatch is unavailable")

    def read_one(self, scope: TenantScope, reservation_id: str) -> ContentReviewPendingCandidate | None:
        if type(scope) is not TenantScope or type(reservation_id) is not str or not reservation_id:
            raise ValueError("exact scoped content reservation required")
        with self.connect_read(scope) as conn:
            proof = self.source.read(conn, scope, reservation_id)
            ContentGenerationStepOwner._readback(conn, scope, proof, None)
            evidence = self.source.journal.read(conn, scope, reservation_id)
            if type(evidence) is not dict:
                raise ContentReviewPendingBlocked("content original command is missing")
            self._current_dispatch(conn, scope, evidence.get("command"))
            try:
                gate = require_current_content_pre_review_gate(conn, scope)
                require_original_content_eval_gate(conn, scope, proof.run_id, gate)
            except ValueError as exc:
                raise ContentReviewPendingBlocked("content current Eval/Plan gate is unavailable") from exc
            step = conn.execute(
                """SELECT step_run_id,attempt,input_hash,status FROM public.aip_step_run
                    WHERE org_id=%s AND project_id=%s AND run_id=%s
                      AND step_key='content_generate'
                    ORDER BY attempt DESC LIMIT 1""",
                (*scope.key, proof.run_id),
            ).fetchone()
            if step is None or step["status"] != "succeeded":
                raise ContentReviewPendingBlocked("content latest generation step is not succeeded")
            reports = conn.execute(
                """SELECT * FROM public.aip_eval_report_revision
                    WHERE org_id=%s AND project_id=%s
                      AND subject_artifact_ref->>'resourceId'=%s
                    ORDER BY created_at DESC,report_id DESC LIMIT 2""",
                (*scope.key, proof.artifact_id),
            ).fetchall()
            if not reports:
                return None
            if len(reports) != 1:
                raise ContentReviewPendingBlocked("content subject EvalReport is ambiguous")
            report = AipEvalRunner._report_from_row(scope, reports[0])
            if (
                compute_eval_report_hash(report) != report.content_hash
                or report.gate_passed is not True or report.failed != 0
                or report.subject_artifact_ref is None
                or report.subject_artifact_ref.resource_id != proof.artifact_id
                or report.subject_artifact_ref.content_hash != proof.artifact_hash
                or report.stage_attempt_ref is None
                or report.stage_attempt_ref.run_id != proof.run_id
                or report.stage_attempt_ref.step_key != "content_generate"
                or report.stage_attempt_ref.step_run_id != step["step_run_id"]
                or report.stage_attempt_ref.attempt != int(step["attempt"])
                or report.stage_attempt_ref.input_hash != step["input_hash"]
                or report.eval_contract_ref is None
                or report.gate_policy_ref is None
                or report.eval_contract_ref.resource_id != gate.resource_id
                or report.eval_contract_ref.revision != gate.revision
                or report.eval_contract_ref.content_hash != gate.content_hash
                or report.gate_policy_ref.model_dump(mode="json", by_alias=True)
                    != report.eval_contract_ref.model_dump(mode="json", by_alias=True)
            ):
                raise ContentReviewPendingBlocked("content subject EvalReport drifted")
            contract = AipProductionContractStore().get_eval_contract(
                scope, gate.resource_id, gate.revision, conn=conn,
            )
            if (
                report.suite_ref.asset_id != contract.suite_ref.resource_id
                or report.suite_ref.revision != str(contract.suite_ref.revision)
                or report.suite_ref.content_hash != contract.suite_ref.content_hash
            ):
                raise ContentReviewPendingBlocked("content subject Suite drifted")
            run = conn.execute(
                """SELECT * FROM public.aip_eval_run
                    WHERE org_id=%s AND project_id=%s AND run_id=%s""",
                (*scope.key, report.run_id),
            ).fetchone()
            if run is None:
                raise ContentReviewPendingBlocked("content subject EvalRun is missing")
            if any(
                run[key] != getattr(report, attribute).model_dump(mode="json", by_alias=True)
                for key, attribute in (
                    ("eval_contract_ref", "eval_contract_ref"),
                    ("subject_artifact_ref", "subject_artifact_ref"),
                    ("stage_attempt_ref", "stage_attempt_ref"),
                    ("gate_policy_ref", "gate_policy_ref"),
                )
            ):
                raise ContentReviewPendingBlocked("content subject EvalRun binding drifted")
            try:
                AipReleasePublicationService._verify_run(report, run)
            except (AipReleasePublicationError, ValueError) as exc:
                raise ContentReviewPendingBlocked("content subject EvalRun drifted") from exc
            issue = conn.execute(
                """SELECT issue_id FROM public.aip_review_issue
                    WHERE org_id=%s AND project_id=%s AND artifact_id=%s
                    LIMIT 1""",
                (*scope.key, proof.artifact_id),
            ).fetchone()
            if issue is not None:
                return None
            return ContentReviewPendingCandidate(
                reservation_id=reservation_id, run_id=proof.run_id, task_id=proof.task_id,
                artifact_id=proof.artifact_id, artifact_hash=proof.artifact_hash,
                step_run_id=step["step_run_id"], report_id=report.report_id,
                report_revision=report.revision, report_hash=report.content_hash,
            )
