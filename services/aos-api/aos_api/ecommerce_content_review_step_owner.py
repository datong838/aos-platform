"""Complete the original AIP Run only after one exact accepted review Receipt.

No Provider call or background worker is wired here. An unknown commit/readback
must be reconciled from persisted rows, never interpreted as permission to retry.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from types import SimpleNamespace
from uuid import UUID

from aos_api.aip_task_store import AipTaskStore
from aos_api.ecommerce_growth_host_ports import (
    EcommerceGrowthHostError, HostTransaction, LockedEcommerceGrowthHostPort,
)
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentReviewHostService, TransactionBoundConnectFactory,
    _analysis_command_hash, _request_hash, _strict_content_review_command,
)
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable
from aos_api.tenant_scope import TenantScope


class ContentReviewStepConflict(RuntimeError):
    """Review Receipt, original Run or current installation cannot be reconciled."""


class ContentReviewStepUnknown(ContentReviewStepConflict):
    """The committed terminal boundary has not been independently proven."""


@dataclass(frozen=True)
class ContentReviewStepProof:
    receipt_id: str
    run_id: str
    task_id: str
    command: dict
    receipt: dict
    dispatch_ref: SimpleNamespace
    feedback_command_id: str
    run_status: str
    task_status: str


_EXACT_RECEIPT = """SELECT receipt.idempotency_key,receipt.request_hash AS runtime_request_hash,
       receipt.response,receipt.target_receipt_ref,receipt.dispatch_revision,
       receipt.installation_id,receipt.generation,receipt.execution_epoch,
       receipt.cutover_group_id,receipt.cutover_group_revision,receipt.runtime_revision,
       dispatch.handler_kind,feedback.command_id,feedback.decision AS feedback_decision,
       feedback.review_receipt_ref,feedback.artifact_ref AS feedback_artifact_ref,
       feedback.task_ref AS feedback_task_ref,feedback.brief_ref AS feedback_brief_ref,
       segment.kind AS feedback_kind,segment.payload AS feedback_payload,
       segment.state AS feedback_state,segment.attempt AS feedback_attempt,
       segment.target_receipt_ref AS feedback_target_receipt_ref,
       artifact.run_id,artifact.content_hash AS artifact_hash,
       artifact.family_revision AS artifact_revision,artifact.metadata,
       run.task_id,run.status AS run_status,run.plan_revision_id,
       task.status AS task_status,plan.approval_status,plan.steps
  FROM public.ecommerce_growth_runtime_command_receipt receipt
  JOIN public.extension_operation_dispatch_binding dispatch
    ON dispatch.org_id=receipt.org_id AND dispatch.project_id=receipt.project_id
   AND dispatch.operation_id=receipt.operation_id
   AND dispatch.handler_kind='extension' AND dispatch.operation_fence=false
   AND dispatch.revision=receipt.dispatch_revision
   AND dispatch.installation_id=receipt.installation_id
   AND dispatch.generation=receipt.generation
   AND dispatch.execution_epoch=receipt.execution_epoch
   AND dispatch.cutover_group_id=receipt.cutover_group_id
   AND dispatch.cutover_group_revision=receipt.cutover_group_revision
  JOIN public.extension_runtime_binding binding
    ON binding.org_id=receipt.org_id AND binding.project_id=receipt.project_id
   AND binding.installation_id=receipt.installation_id
   AND binding.generation=receipt.generation
   AND binding.revision=receipt.runtime_revision
   AND binding.execution_epoch=receipt.execution_epoch
   AND binding.desired_state='enabled' AND binding.observed_state='ready'
   AND binding.enabled=true AND binding.operation_fence=false
  JOIN public.ecommerce_growth_feedback_command feedback
    ON feedback.org_id=receipt.org_id AND feedback.project_id=receipt.project_id
   AND feedback.review_receipt_ref=receipt.target_receipt_ref
  JOIN public.ecommerce_growth_feedback_segment segment
    ON segment.org_id=feedback.org_id AND segment.project_id=feedback.project_id
   AND segment.command_id=feedback.command_id AND segment.sequence=1
  JOIN public.aip_artifact artifact
    ON artifact.org_id=receipt.org_id AND artifact.project_id=receipt.project_id
   AND artifact.artifact_id=receipt.response->'artifactRef'->>'resourceId'
   AND artifact.artifact_type='ecommerce_content'
  JOIN public.aip_task_run run
    ON run.org_id=artifact.org_id AND run.project_id=artifact.project_id
   AND run.run_id=artifact.run_id
   AND run.task_id=receipt.response->'taskRef'->>'resourceId'
  JOIN public.aip_task task
    ON task.org_id=run.org_id AND task.project_id=run.project_id AND task.task_id=run.task_id
  JOIN public.aip_plan_revision plan
    ON plan.org_id=run.org_id AND plan.project_id=run.project_id
   AND plan.plan_revision_id=run.plan_revision_id AND plan.task_id=run.task_id
 WHERE receipt.org_id=%s AND receipt.project_id=%s
   AND receipt.operation_id='ecommerce_growth_content_review'
   AND receipt.target_receipt_ref->>'resourceId'=%s"""


_PENDING = """SELECT receipt.target_receipt_ref->>'resourceId' AS receipt_id
  FROM public.ecommerce_growth_runtime_command_receipt receipt
  JOIN public.ecommerce_growth_feedback_command feedback
    ON feedback.org_id=receipt.org_id AND feedback.project_id=receipt.project_id
   AND feedback.review_receipt_ref=receipt.target_receipt_ref
  JOIN public.ecommerce_growth_feedback_segment segment
    ON segment.org_id=feedback.org_id AND segment.project_id=feedback.project_id
   AND segment.command_id=feedback.command_id AND segment.sequence=1
   AND segment.kind='daily_review' AND segment.state='pending'
   AND segment.attempt=0 AND segment.target_receipt_ref IS NULL
  JOIN public.aip_artifact artifact
    ON artifact.org_id=receipt.org_id AND artifact.project_id=receipt.project_id
   AND artifact.artifact_id=receipt.response->'artifactRef'->>'resourceId'
   AND artifact.artifact_type='ecommerce_content'
  JOIN public.aip_task_run r
    ON r.org_id=artifact.org_id AND r.project_id=artifact.project_id
   AND r.run_id=artifact.run_id AND r.status='running'
  JOIN public.aip_task t
    ON t.org_id=r.org_id AND t.project_id=r.project_id
   AND t.task_id=r.task_id AND t.status='executing'
  JOIN public.extension_operation_dispatch_binding d
    ON d.org_id=receipt.org_id AND d.project_id=receipt.project_id
   AND d.operation_id=receipt.operation_id AND d.handler_kind='extension'
   AND d.operation_fence=false AND d.revision=receipt.dispatch_revision
   AND d.installation_id=receipt.installation_id AND d.generation=receipt.generation
   AND d.execution_epoch=receipt.execution_epoch
   AND d.cutover_group_id=receipt.cutover_group_id
   AND d.cutover_group_revision=receipt.cutover_group_revision
  JOIN public.extension_runtime_binding b
    ON b.org_id=receipt.org_id AND b.project_id=receipt.project_id
   AND b.installation_id=receipt.installation_id AND b.generation=receipt.generation
   AND b.revision=receipt.runtime_revision AND b.execution_epoch=receipt.execution_epoch
   AND b.desired_state='enabled' AND b.observed_state='ready'
   AND b.enabled=true AND b.operation_fence=false
 WHERE receipt.org_id=%s AND receipt.project_id=%s
   AND receipt.operation_id='ecommerce_growth_content_review'
   AND receipt.response->>'decision'='ACCEPT' AND feedback.decision='ACCEPT'
   AND NOT EXISTS (SELECT 1 FROM public.aip_step_run step
     WHERE step.org_id=r.org_id AND step.project_id=r.project_id AND step.run_id=r.run_id
       AND step.step_key='content_review')
 ORDER BY receipt.occurred_at,receipt.idempotency_key LIMIT %s"""


class ContentReviewStepSource:
    """Read one persisted Host Receipt; the write transaction rechecks Host authority."""

    def read(self, conn, scope: TenantScope, receipt_id: str) -> ContentReviewStepProof:
        if type(scope) is not TenantScope or type(receipt_id) is not str:
            raise ValueError("exact scoped content review Receipt required")
        try:
            UUID(receipt_id)
        except ValueError as exc:
            raise ValueError("exact content review Receipt UUID required") from exc
        rows = conn.execute(_EXACT_RECEIPT, (*scope.key, receipt_id)).fetchall()
        if len(rows) != 1:
            raise ContentReviewStepConflict("unique current content review Receipt unavailable")
        row = rows[0]
        response = row["response"]
        metadata = row["metadata"]
        projection = metadata.get("ecommerceGrowthContentArtifact") if type(metadata) is dict else None
        if type(response) is not dict or type(projection) is not dict:
            raise ContentReviewStepConflict("review Receipt or Artifact projection unavailable")
        try:
            command = {
                "operation": "content.review",
                **{name: response[name] for name in (
                    "artifactRef", "taskRef", "briefRef", "reviewIssueRef",
                    "reviewerAuthorityRef", "decision", "returnStage")},
                **{name: projection[name] for name in ("growthPlanRef", "sourceArtifactRefs")},
                "artifactContentHash": response["artifactRef"]["contentHash"],
                "idempotencyKey": row["idempotency_key"],
                "requestHash": response["requestHash"],
            }
            _strict_content_review_command(command)
        except (KeyError, TypeError, ValueError) as exc:
            raise ContentReviewStepConflict("review command cannot be reconstructed exactly") from exc
        if type(row["steps"]) is not list:
            raise ContentReviewStepConflict("original review Plan steps unavailable")
        if (
            row["runtime_request_hash"] != _request_hash(command)
            or row["target_receipt_ref"] != response.get("receiptRef")
            or response["receiptRef"].get("resourceId") != receipt_id
            or response["decision"] != "ACCEPT" or response["returnStage"] is not None
            or row["feedback_decision"] != "ACCEPT"
            or row["review_receipt_ref"] != response["receiptRef"]
            or row["feedback_artifact_ref"] != response["artifactRef"]
            or row["feedback_task_ref"] != response["taskRef"]
            or row["feedback_brief_ref"] != response["briefRef"]
            or row["feedback_kind"] != "daily_review"
            or type(row["feedback_payload"]) is not dict
            or row["feedback_payload"].get("kind") != "daily_review"
            or (row["run_status"] == "running" and (
                row["feedback_state"] != "pending" or row["feedback_attempt"] != 0
                or row["feedback_target_receipt_ref"] is not None))
            or row["artifact_hash"] != response["artifactRef"]["contentHash"].removeprefix("sha256:")
            or row["artifact_revision"] not in (None, response["artifactRef"]["revision"])
            or row["approval_status"] != "approved"
            or [step.get("stepKey") for step in row["steps"]]
                != ["content_generate", "content_review"]
            or (row["run_status"], row["task_status"])
                not in {("running", "executing"), ("succeeded", "completed")}
        ):
            raise ContentReviewStepConflict("review Receipt, feedback or original Run drifted")
        dispatch_ref = SimpleNamespace(
            org_id=scope.org_id, project_id=scope.project_id,
            operation_id="ecommerce_growth_content_review",
            handler_kind=row["handler_kind"],
            dispatch_revision=row["dispatch_revision"],
            installation_id=row["installation_id"], generation=row["generation"],
            execution_epoch=row["execution_epoch"],
            cutover_group_id=row["cutover_group_id"],
            cutover_group_revision=row["cutover_group_revision"],
        )
        return ContentReviewStepProof(receipt_id, row["run_id"], row["task_id"],
            command, response, dispatch_ref, row["command_id"],
            row["run_status"], row["task_status"])


class ContentReviewStepOwner:
    actor = "ecommerce-content-review-step-owner"

    def __init__(self, *, source=None, connect_read=connect_read_only,
                 connect_write=connect_serializable, store_factory=AipTaskStore):
        self.source = source or ContentReviewStepSource()
        self.connect_read = connect_read
        self.connect_write = connect_write
        self.store_factory = store_factory

    def list_pending(self, scope: TenantScope, *, limit: int = 16) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 16:
            raise ValueError("bounded scoped content review selector required")
        with self.connect_read(scope) as conn:
            rows = conn.execute(_PENDING, (*scope.key, limit)).fetchall()
        values = [row["receipt_id"] for row in rows]
        if any(type(value) is not str or not value for value in values) or len(values) != len(set(values)):
            raise ContentReviewStepConflict("review selector identity drifted")
        return values

    def run_once(self, scope: TenantScope, *, limit: int = 16) -> list[dict[str, str]]:
        statuses = []
        for receipt_id in self.list_pending(scope, limit=limit):
            try:
                result = self.run_one(scope, receipt_id)
            except ContentReviewStepUnknown:
                raise  # Unknown commit/readback freezes the entire worker.
            except (ContentReviewStepConflict, EcommerceGrowthHostError):
                statuses.append({"receiptId": receipt_id,
                                 "status": "BLOCKED_CURRENT_AUTHORITY"})
                continue
            statuses.append({"receiptId": receipt_id, "status": result["status"]})
        return statuses

    async def serve(self, stop, *, host_ready, interval_seconds: int = 15) -> None:
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("content review step worker interval invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("content review step Runtime Host unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass

    def run_one(self, scope: TenantScope, receipt_id: str) -> dict[str, str]:
        with self.connect_write(scope) as conn:
            proof = self.source.read(conn, scope, receipt_id)
            if proof.run_status == "succeeded":
                return self._readback(conn, scope, proof, None)
            snapshot = LockedEcommerceGrowthHostPort._lock_and_revalidate(
                conn, scope, proof.dispatch_ref)
            if self.source.read(conn, scope, receipt_id) != proof:
                raise ContentReviewStepConflict("review authority drifted after Host lock")
            service = ContentReviewHostService()
            transaction = HostTransaction(conn)
            service.revalidate(transaction=transaction, scope=scope,
                dispatch=snapshot, command=proof.command)
            if service.verify_receipt(transaction=transaction, scope=scope,
                    dispatch=snapshot, command=proof.command,
                    receipt=proof.receipt) != proof.receipt:
                raise ContentReviewStepConflict("review Host Receipt independent proof failed")
            checkpoint_id = self._complete_transaction(conn, scope, proof)
            conn.commit()
        with self.connect_read(scope) as conn:
            if self.source.read(conn, scope, receipt_id) != replace(
                proof, run_status="succeeded", task_status="completed"
            ):
                raise ContentReviewStepUnknown("review Receipt/feedback commit readback unknown")
            return self._readback(conn, scope, proof, checkpoint_id)

    def _complete_transaction(self, conn, scope: TenantScope,
                              proof: ContentReviewStepProof) -> str:
        existing = conn.execute(
            """SELECT status FROM public.aip_step_run WHERE org_id=%s AND project_id=%s
                AND run_id=%s AND step_key='content_review'
                ORDER BY attempt DESC LIMIT 1 FOR UPDATE""",
            (*scope.key, proof.run_id),
        ).fetchone()
        if existing is not None:
            raise ContentReviewStepConflict("review attempt already exists; reconcile before retry")
        store = self.store_factory(TransactionBoundConnectFactory(HostTransaction(conn), scope))
        lease = store.claim_step(scope, proof.run_id, "content_review", self.actor,
            lease_seconds=60)
        phases = (
            ("think", {"kind": "human_accept_reconciliation", "reviewIssueRef":
                proof.command["reviewIssueRef"]}),
            ("act", {"kind": "already_persisted_content_review",
                "reviewReceiptRef": proof.receipt["receiptRef"]}),
            ("verify", {"passed": True, "reviewReceiptRef": proof.receipt["receiptRef"]}),
            ("observe", {"artifactRef": proof.command["artifactRef"],
                "reviewIssueRef": proof.command["reviewIssueRef"],
                "feedbackCommandId": proof.feedback_command_id}),
        )
        for phase, payload in phases:
            store.record_step_phase(scope, lease.step_run_id, self.actor, lease.fence,
                self.actor, phase, payload)
        checkpoint_id = store.complete_step(scope, lease.step_run_id, self.actor,
            lease.fence, self.actor)
        store.complete_run(scope, proof.run_id)
        return checkpoint_id

    @staticmethod
    def _readback(conn, scope: TenantScope, proof: ContentReviewStepProof,
                  checkpoint_id: str | None) -> dict[str, str]:
        row = conn.execute(
            """SELECT step.step_run_id,step.attempt,step.status,step.think_ref,
                      step.action_ref,step.verify_ref,step.observe_ref,
                      run.status AS run_status,task.status AS task_status
                 FROM public.aip_step_run step
                 JOIN public.aip_task_run run ON run.org_id=step.org_id
                  AND run.project_id=step.project_id AND run.run_id=step.run_id
                 JOIN public.aip_task task ON task.org_id=run.org_id
                  AND task.project_id=run.project_id AND task.task_id=run.task_id
                WHERE step.org_id=%s AND step.project_id=%s AND step.run_id=%s
                  AND step.step_key='content_review' ORDER BY step.attempt DESC LIMIT 1""",
            (*scope.key, proof.run_id),
        ).fetchone()
        if (row is None or row["status"] != "succeeded" or row["attempt"] != 1
            or row["run_status"] != "succeeded" or row["task_status"] != "completed"
            or any(row[name] is None for name in
                   ("think_ref", "action_ref", "verify_ref", "observe_ref"))):
            raise ContentReviewStepUnknown("content review terminal commit/readback unknown")
        checkpoint = conn.execute(
            """SELECT checkpoint_id,state_snapshot_ref FROM public.aip_checkpoint
                WHERE org_id=%s AND project_id=%s AND run_id=%s
                  AND step_key='content_review' AND attempt=1""",
            (*scope.key, proof.run_id),
        ).fetchone()
        observation = conn.execute(
            """SELECT payload FROM public.aip_evidence WHERE org_id=%s AND project_id=%s
                AND evidence_id=%s AND run_id=%s AND evidence_type='taor.observe'""",
            (*scope.key, row["observe_ref"]["evidenceId"], proof.run_id),
        ).fetchone()
        action = conn.execute(
            """SELECT payload FROM public.aip_evidence WHERE org_id=%s AND project_id=%s
                AND evidence_id=%s AND run_id=%s AND evidence_type='taor.act'""",
            (*scope.key, row["action_ref"]["evidenceId"], proof.run_id),
        ).fetchone()
        verification = conn.execute(
            """SELECT payload FROM public.aip_evidence WHERE org_id=%s AND project_id=%s
                AND evidence_id=%s AND run_id=%s AND evidence_type='taor.verify'""",
            (*scope.key, row["verify_ref"]["evidenceId"], proof.run_id),
        ).fetchone()
        if (checkpoint is None or (checkpoint_id is not None
                and checkpoint["checkpoint_id"] != checkpoint_id)
            or type(checkpoint["state_snapshot_ref"]) is not dict
            or checkpoint["state_snapshot_ref"].get("stepRunId") != row["step_run_id"]
            or checkpoint["state_snapshot_ref"].get("status") != "succeeded"
            or observation is None or type(observation["payload"]) is not dict
            or action is None or type(action["payload"]) is not dict
            or action["payload"].get("payload", {}).get("reviewReceiptRef")
                != proof.receipt["receiptRef"]
            or verification is None or type(verification["payload"]) is not dict
            or verification["payload"].get("payload", {}).get("reviewReceiptRef")
                != proof.receipt["receiptRef"]
            or observation["payload"].get("payload", {}).get("artifactRef")
                != proof.command["artifactRef"]
            or observation["payload"].get("payload", {}).get("reviewIssueRef")
                != proof.command["reviewIssueRef"]
            or observation["payload"].get("payload", {}).get("feedbackCommandId")
                != proof.feedback_command_id):
            raise ContentReviewStepUnknown("content review checkpoint/lineage readback unknown")
        return {"status": "CONTENT_REVIEW_RUN_SUCCEEDED", "runId": proof.run_id,
            "stepRunId": row["step_run_id"], "checkpointId": checkpoint["checkpoint_id"]}


__all__ = ["ContentReviewStepOwner", "ContentReviewStepSource",
           "ContentReviewStepConflict", "ContentReviewStepUnknown"]
