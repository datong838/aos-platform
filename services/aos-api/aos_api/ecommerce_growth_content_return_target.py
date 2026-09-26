"""Acknowledge an existing human RETURN and its queued repair attempt.

This target never creates a new attempt or invokes a Provider. The immutable
ReturnDecision and the queued StepRun are its persistent target authority.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any, Mapping

from aos_api.aip_production_contract_store import canonical_hash as decision_hash
from aos_api.aip_budget_reservation_store import canonical_hash as budget_hash
from aos_api.ecommerce_growth_feedback_port import (
    BoundEcommerceGrowthFeedbackPort, EcommerceGrowthFeedbackConflict, _strict_exact_ref,
)
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostError, HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import (
    ContentReviewHostService, _analysis_command_hash, _request_hash,
    _strict_content_review_command,
)
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable
from aos_api.tenant_scope import TenantScope


class ContentReturnUnknown(RuntimeError):
    """Commit or independent readback is unknown; reconcile, never reclaim."""


def _unwired_target(**_kwargs):
    raise EcommerceGrowthFeedbackConflict("feedback target is not wired")


class BoundContentReturnTarget:
    """Read an exact RETURN decision and already queued AIP repair attempt."""

    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("return target requires a scoped host transaction")
        self._transaction = transaction
        self._scope = scope

    def _source(self, target_id: str, *, require_queued: bool = False) -> dict[str, Any]:
        rows = self._transaction.execute(
            """SELECT c.command_id,c.decision,c.review_receipt_ref,c.artifact_ref,
                      c.task_ref,c.brief_ref,s.payload,s.kind,s.target_id,
                      runtime.response,runtime.idempotency_key,runtime.request_hash,
                      artifact.run_id,artifact.metadata,artifact.content_hash AS artifact_hash,
                      artifact.family_revision,
                      issue.issue_id,issue.version AS issue_version,issue.status AS issue_status,
                      decision.decision_id,decision.issue_version AS decision_issue_version,
                      decision.run_id AS decision_run_id,decision.step_key,decision.step_run_id,
                      decision.attempt,decision.attempt_idempotency_key,decision.reason,
                      decision.decision_hash,decision.actor,decision.impact_decisions,
                      step.status AS step_status,step.input_refs,step.attempt AS step_attempt,
                      (SELECT max(later.attempt) FROM public.aip_step_run later
                        WHERE later.org_id=step.org_id AND later.project_id=step.project_id
                          AND later.run_id=step.run_id AND later.step_key=step.step_key)
                        AS latest_attempt,
                      run.status AS run_status,task.task_id,task.status AS task_status
                 FROM public.ecommerce_growth_feedback_command c
                 JOIN public.ecommerce_growth_feedback_segment s
                   ON s.org_id=c.org_id AND s.project_id=c.project_id
                  AND s.command_id=c.command_id AND s.sequence=1
                 JOIN public.ecommerce_growth_runtime_command_receipt runtime
                   ON runtime.org_id=c.org_id AND runtime.project_id=c.project_id
                  AND runtime.operation_id='ecommerce_growth_content_review'
                  AND runtime.target_receipt_ref=c.review_receipt_ref
                 JOIN public.aip_artifact artifact
                   ON artifact.org_id=c.org_id AND artifact.project_id=c.project_id
                  AND artifact.artifact_id=c.artifact_ref->>'resourceId'
                 JOIN public.aip_review_issue issue
                   ON issue.org_id=c.org_id AND issue.project_id=c.project_id
                  AND issue.issue_id=runtime.response->'reviewIssueRef'->>'resourceId'
                 JOIN public.aip_return_decision decision
                   ON decision.org_id=issue.org_id AND decision.project_id=issue.project_id
                  AND decision.issue_id=issue.issue_id AND decision.issue_version=issue.version-1
                 JOIN public.aip_step_run step
                   ON step.org_id=decision.org_id AND step.project_id=decision.project_id
                  AND step.step_run_id=decision.step_run_id
                  AND step.run_id=decision.run_id AND step.step_key=decision.step_key
                 JOIN public.aip_task_run run
                   ON run.org_id=artifact.org_id AND run.project_id=artifact.project_id
                  AND run.run_id=artifact.run_id AND run.run_id=decision.run_id
                 JOIN public.aip_task task
                   ON task.org_id=run.org_id AND task.project_id=run.project_id
                  AND task.task_id=run.task_id
                WHERE c.org_id=%s AND c.project_id=%s AND s.target_id=%s
                  AND c.decision='RETURN' AND s.kind='content_return_target'
                LIMIT 2""",
            (*self._scope.key, target_id),
        ).fetchall()
        if len(rows) != 1:
            raise EcommerceGrowthFeedbackConflict("unique durable return target unavailable")
        row = dict(rows[0])
        response, metadata = row["response"], row["metadata"]
        artifact = metadata.get("ecommerceGrowthContentArtifact") if type(metadata) is dict else None
        if type(response) is not dict or type(artifact) is not dict:
            raise EcommerceGrowthFeedbackConflict("return source projection unavailable")
        try:
            command = {
                "operation": "content.review",
                **{name: response[name] for name in (
                    "artifactRef", "taskRef", "briefRef", "reviewIssueRef",
                    "reviewerAuthorityRef", "decision", "returnStage")},
                **{name: artifact[name] for name in ("growthPlanRef", "sourceArtifactRefs")},
                "artifactContentHash": response["artifactRef"]["contentHash"],
                "idempotencyKey": row["idempotency_key"],
                "requestHash": response["requestHash"],
            }
            _strict_content_review_command(command)
            review_ref = _strict_exact_ref(row["review_receipt_ref"], name="return review Receipt")
            review_body = {name: value for name, value in response.items() if name != "receiptRef"}
            if (
                row["request_hash"] != _request_hash(command)
                or response["receiptRef"] != review_ref
                or review_ref["contentHash"] != _analysis_command_hash(review_body)
                or response["decision"] != "RETURN"
                or response["returnStage"] != "content_generation"
                or row["artifact_ref"] != response["artifactRef"]
                or row["task_ref"] != response["taskRef"]
                or row["brief_ref"] != response["briefRef"]
                or row["artifact_hash"] != command["artifactRef"]["contentHash"][7:]
                or (row["family_revision"] or 1) != command["artifactRef"]["revision"]
                or row["issue_status"] != "returned" or row["issue_version"] != 2
                or row["decision_issue_version"] != 1
                or row["decision_run_id"] != row["run_id"]
                or row["task_id"] != command["taskRef"]["resourceId"]
                or row["step_key"] != "content_generate"
                or row["step_status"] not in {"queued", "running", "succeeded", "failed", "skipped", "unknown"}
                or (require_queued and row["step_status"] != "queued")
                or row["step_attempt"] != row["attempt"] or row["attempt"] < 2
                or (require_queued and row["latest_attempt"] != row["attempt"])
                or (require_queued and (
                    row["run_status"] != "running" or row["task_status"] != "executing"))
                or type(row["payload"]) is not dict
                or row["payload"].get("kind") != "content_return_target"
                or row["payload"].get("targetId") != target_id
                or row["payload"].get("targetPhase") != "content_generation"
                or target_id != "content_return_target-" + budget_hash({
                    "commandId": row["command_id"], "kind": "content_return_target"
                })[:40]
            ):
                raise EcommerceGrowthFeedbackConflict("return source lineage drifted")
            expected_hash = decision_hash({
                "issueId": row["issue_id"], "issueVersion": row["decision_issue_version"],
                "runId": row["decision_run_id"], "stepKey": row["step_key"],
                "stepRunId": row["step_run_id"], "attempt": row["attempt"],
                "attemptIdempotencyKey": row["attempt_idempotency_key"],
                "reason": row["reason"], "actor": row["actor"],
            })
            refs = row["input_refs"]
            if (
                row["decision_hash"] != expected_hash
                or type(refs) is not list
                or {"resourceType": "ReturnDecision", "resourceId": row["decision_id"],
                    "revision": 1, "contentHash": expected_hash} not in refs
                or {"resourceType": "ReviewIssue", "resourceId": row["issue_id"],
                    "version": row["decision_issue_version"]} not in refs
                or {"resourceType": "Artifact", "resourceId": command["artifactRef"]["resourceId"],
                    "contentHash": row["artifact_hash"]} not in refs
                or type(row["impact_decisions"]) is not list
            ):
                raise EcommerceGrowthFeedbackConflict("return decision or repair attempt drifted")
        except (KeyError, TypeError, ValueError) as exc:
            raise EcommerceGrowthFeedbackConflict("return source cannot be reconstructed") from exc
        row["command"] = command
        row["review_ref"] = review_ref
        return row

    @staticmethod
    def _receipt(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "resourceType": "ContentReturnTargetReceipt", "resourceId": row["target_id"],
            "revision": 1,
            "contentHash": _request_hash({
                "commandId": row["command_id"], "reviewReceiptRef": row["review_ref"],
                "returnDecisionId": row["decision_id"], "decisionHash": row["decision_hash"],
                "stepRunId": row["step_run_id"], "attempt": row["attempt"],
            }),
        }

    def read_receipt(self, *, target_id: str, expected_receipt: Mapping[str, Any], **_kwargs):
        expected = _strict_exact_ref(dict(expected_receipt), name="return target Receipt")
        if type(target_id) is not str or expected["resourceId"] != target_id:
            raise EcommerceGrowthFeedbackConflict("return target identity drifted")
        receipt = self._receipt(self._source(target_id))
        if receipt != expected:
            raise EcommerceGrowthFeedbackConflict("return target Receipt drifted")
        return receipt

    def read_existing(self, *, command_id: str, command: Mapping[str, Any],
                      claim: Mapping[str, Any], origin: Mapping[str, Any]):
        if (
            type(command_id) is not str or command.get("commandId") != command_id
            or command.get("decision") != "RETURN"
            or claim.get("sequence") != 1 or claim.get("kind") != "content_return_target"
            or claim.get("attempt") != 1
            or type(claim.get("targetId")) is not str
            or not claim["targetId"].startswith("content_return_target-")
            or type(claim.get("payload")) is not dict
            or claim["payload"].get("kind") != "content_return_target"
            or claim["payload"].get("targetId") != claim["targetId"]
            or claim["payload"].get("targetPhase") != "content_generation"
            or origin.get("reviewReceiptRef") != command.get("reviewReceiptRef")
        ):
            raise EcommerceGrowthFeedbackConflict("return claim input drifted")
        row = self._source(claim["targetId"], require_queued=True)
        if row["command_id"] != command_id or row["review_ref"] != command["reviewReceiptRef"]:
            raise EcommerceGrowthFeedbackConflict("return feedback command drifted")
        service = ContentReviewHostService()
        service.revalidate(transaction=self._transaction, scope=self._scope,
            dispatch=origin["dispatch"], command=row["command"])
        if service.verify_receipt(transaction=self._transaction, scope=self._scope,
                dispatch=origin["dispatch"], command=row["command"],
                receipt=row["response"]) != row["response"]:
            raise EcommerceGrowthFeedbackConflict("return Host Receipt drifted")
        return self._receipt(row)


class ContentReturnFeedbackWorker:
    """Acknowledge one pristine RETURN target; never run its queued repair step."""

    def __init__(self, *, connect=connect_serializable, connect_read=None) -> None:
        self._connect = connect
        self._connect_read = (connect_read if connect_read is not None
            else connect_read_only if connect is connect_serializable else connect)

    @staticmethod
    def _port(transaction, scope, target):
        return BoundEcommerceGrowthFeedbackPort(transaction, scope,
            actor="ecommerce-content-return", checked_at=datetime.now(UTC),
            target_receipt_readers={
                "daily_review": _unwired_target,
                "improvement_observation": _unwired_target,
                "memory_candidate": _unwired_target,
                "content_return_target": target.read_receipt,
            })

    def run_one(self, scope: TenantScope, command_id: str) -> dict[str, Any]:
        if type(scope) is not TenantScope or type(command_id) is not str or not command_id.strip():
            raise ValueError("scoped return command is required")
        with self._connect(scope) as conn:
            transaction = HostTransaction(conn)
            target = BoundContentReturnTarget(transaction, scope)
            port = self._port(transaction, scope, target)
            command = port.read(command_id=command_id)
            if command is None or command["decision"] != "RETURN" or len(command["segments"]) != 1:
                raise EcommerceGrowthFeedbackConflict("return feedback command unavailable")
            segment = command["segments"][0]
            if command["checkpoint"]["completedSequence"] == 1:
                receipt = target.read_receipt(target_id=segment["payload"]["targetId"],
                    expected_receipt=segment["targetReceiptRef"])
                return {"status": "ALREADY_ACKED", "commandId": command_id, "receiptRef": receipt}
            if (command["checkpoint"]["completedSequence"] != 0 or segment["state"] != "pending"
                or segment["attempt"] != 0 or segment["targetReceiptRef"] is not None):
                raise EcommerceGrowthFeedbackConflict("return segment is not pristine")
            claim = port.claim_current(command_id=command_id, worker="ecommerce-content-return")
            if claim is None:
                return {"status": "NOT_CLAIMED", "commandId": command_id}
            origin = port.require_current_origin(command_id=command_id)
            receipt = target.read_existing(command_id=command_id, command=command,
                claim=claim, origin=origin)
            checkpoint = port.acknowledge(command_id=command_id, claim=claim,
                target_receipt_ref=receipt)
            if checkpoint["completedSequence"] != 1:
                raise EcommerceGrowthFeedbackConflict("return checkpoint drifted")
            try:
                conn.commit()
            except Exception as exc:
                raise ContentReturnUnknown("return commit unknown; reconcile without resend") from exc
        try:
            with self._connect_read(scope) as conn:
                read_target = BoundContentReturnTarget(HostTransaction(conn), scope)
                read_target.read_receipt(target_id=claim["targetId"], expected_receipt=receipt)
                current = self._port(HostTransaction(conn), scope, read_target).read(command_id=command_id)
                if (current is None or current["decision"] != "RETURN"
                    or current["reviewReceiptRef"] != command["reviewReceiptRef"]
                    or current["checkpoint"]["completedSequence"] != 1
                    or len(current["segments"]) != 1
                    or current["segments"][0]["state"] != "acked"
                    or current["segments"][0]["attempt"] != 1
                    or current["segments"][0]["targetReceiptRef"] != receipt):
                    raise EcommerceGrowthFeedbackConflict("return independent readback drifted")
        except Exception as exc:
            raise ContentReturnUnknown("return post-commit unknown; reconcile without resend") from exc
        return {"status": "CONTENT_RETURN_ACKED", "commandId": command_id, "receiptRef": receipt}


_PENDING_RETURN = """SELECT c.command_id
  FROM public.ecommerce_growth_feedback_command c
  JOIN public.ecommerce_growth_feedback_checkpoint p
    ON p.org_id=c.org_id AND p.project_id=c.project_id AND p.command_id=c.command_id
  JOIN public.ecommerce_growth_feedback_segment s
    ON s.org_id=c.org_id AND s.project_id=c.project_id
   AND s.command_id=c.command_id AND s.sequence=1
  JOIN public.ecommerce_growth_runtime_command_receipt origin
    ON origin.org_id=c.org_id AND origin.project_id=c.project_id
   AND origin.operation_id='ecommerce_growth_content_review'
   AND origin.target_receipt_ref=c.review_receipt_ref
  JOIN public.extension_operation_dispatch_binding d
    ON d.org_id=c.org_id AND d.project_id=c.project_id
   AND d.operation_id='ecommerce_growth_content_review'
  JOIN public.extension_runtime_binding b
    ON b.org_id=d.org_id AND b.project_id=d.project_id
   AND b.installation_id=d.installation_id AND b.generation=d.generation
  JOIN public.aip_review_issue issue
    ON issue.org_id=c.org_id AND issue.project_id=c.project_id
   AND issue.issue_id=origin.response->'reviewIssueRef'->>'resourceId'
  JOIN public.aip_return_decision decision
    ON decision.org_id=issue.org_id AND decision.project_id=issue.project_id
   AND decision.issue_id=issue.issue_id AND decision.issue_version=issue.version-1
  JOIN public.aip_step_run step
    ON step.org_id=decision.org_id AND step.project_id=decision.project_id
   AND step.step_run_id=decision.step_run_id AND step.run_id=decision.run_id
  JOIN public.aip_task_run run
    ON run.org_id=step.org_id AND run.project_id=step.project_id
   AND run.run_id=step.run_id
  JOIN public.aip_task task
    ON task.org_id=run.org_id AND task.project_id=run.project_id
   AND task.task_id=run.task_id
 WHERE c.org_id=%s AND c.project_id=%s AND c.decision='RETURN'
   AND p.completed_sequence=0 AND s.kind='content_return_target'
   AND s.state='pending' AND s.attempt=0 AND s.target_receipt_ref IS NULL
   AND s.payload->>'targetId'=s.target_id
   AND s.payload->>'targetPhase'='content_generation'
   AND origin.response->>'decision'='RETURN'
   AND origin.response->>'returnStage'='content_generation'
   AND origin.dispatch_revision=d.revision
   AND origin.installation_id=d.installation_id AND origin.generation=d.generation
   AND origin.execution_epoch=d.execution_epoch
   AND origin.cutover_group_id=d.cutover_group_id
   AND origin.cutover_group_revision=d.cutover_group_revision
   AND origin.runtime_revision=b.revision
   AND d.handler_kind='extension' AND d.operation_fence=false
   AND b.execution_epoch=d.execution_epoch AND b.desired_state='enabled'
   AND b.observed_state='ready' AND b.enabled=true AND b.operation_fence=false
   AND issue.status='returned' AND step.step_key='content_generate'
   AND step.status='queued' AND step.attempt=decision.attempt
   AND NOT EXISTS (SELECT 1 FROM public.aip_step_run later
      WHERE later.org_id=step.org_id AND later.project_id=step.project_id
        AND later.run_id=step.run_id AND later.step_key=step.step_key
        AND later.attempt>step.attempt)
   AND run.status='running' AND task.status='executing'
 ORDER BY c.created_at,c.command_id LIMIT %s"""


class CurrentContentReturnConsumer:
    """Bounded current selector; the owner revalidates under the Host locks."""

    def __init__(self, *, connect=connect_read_only, worker=None) -> None:
        self._connect = connect
        self._worker = worker if worker is not None else ContentReturnFeedbackWorker()

    def list_pending(self, scope: TenantScope, *, limit: int = 32) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("bounded scoped return selector required")
        with self._connect(scope) as conn:
            rows = conn.execute(_PENDING_RETURN, (*scope.key, limit)).fetchall()
        values = [row["command_id"] for row in rows]
        if any(type(value) is not str or not value for value in values) or len(values) != len(set(values)):
            raise EcommerceGrowthFeedbackConflict("return selector identity drifted")
        return values

    def run_once(self, scope: TenantScope, *, limit: int = 32) -> list[dict[str, str]]:
        statuses = []
        for command_id in self.list_pending(scope, limit=limit):
            try:
                result = self._worker.run_one(scope, command_id)
            except ContentReturnUnknown:
                raise
            except (EcommerceGrowthFeedbackConflict, EcommerceGrowthHostError):
                statuses.append({"commandId": command_id, "status": "BLOCKED_CURRENT_AUTHORITY"})
                continue
            statuses.append({"commandId": command_id, "status": result["status"]})
        return statuses

    async def serve(self, stop, *, host_ready, interval_seconds: int = 15) -> None:
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("return worker interval is invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("return worker Runtime Host became unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


__all__ = ["BoundContentReturnTarget", "ContentReturnFeedbackWorker",
    "CurrentContentReturnConsumer", "ContentReturnUnknown"]
