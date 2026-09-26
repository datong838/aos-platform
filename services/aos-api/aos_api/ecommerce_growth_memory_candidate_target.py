"""Third accepted-feedback segment: a governed, pending-only AIP method candidate."""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping

from aos_api.aip_contracts import ArtifactRef, ResourceRef
from aos_api.aip_memory_contracts import (
    KnowledgeScope, KnowledgeSourceKind, KnowledgeSourceRef,
    RuntimeMemoryLayer, SubmitMemoryCandidateRequest,
)
from aos_api.aip_memory_store import AipMemoryStore
from aos_api.ecommerce_growth_effect_review_owner import EffectReviewOwner
from aos_api.ecommerce_growth_feedback_port import (
    BoundEcommerceGrowthFeedbackPort, EcommerceGrowthFeedbackConflict, _strict_exact_ref,
)
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostError, HostTransaction
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable
from aos_api.tenant_scope import TenantScope


class MemoryCandidateUnknown(RuntimeError):
    """The transaction may have committed; reconcile read-only, never submit again."""


def _unwired_target(**_kwargs):
    raise EcommerceGrowthFeedbackConflict("feedback target is not wired")


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class BoundMemoryCandidateTarget:
    """The AIP candidate is the target authority; feedback only stores its exact Receipt."""

    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("candidate target requires a scoped host transaction")
        self._transaction = transaction
        self._scope = scope
        self._store = AipMemoryStore()

    def _candidate_row(self, target_id: str):
        return self._transaction.execute(
            """SELECT c.*,s.source_ref,s.content_hash AS source_hash,
                     e.event_hash,e.event_type,e.to_status
                 FROM public.aip_memory_candidate c
                 JOIN public.aip_memory_source_revision s
                   ON s.org_id=c.org_id AND s.project_id=c.project_id
                  AND s.source_id=c.source_id AND s.revision=c.source_revision
                 JOIN public.aip_memory_candidate_event e
                   ON e.org_id=c.org_id AND e.project_id=c.project_id
                  AND e.candidate_id=c.candidate_id AND e.sequence=1
                WHERE c.org_id=%s AND c.project_id=%s AND c.candidate_id=%s""",
            (*self._scope.key, target_id),
        ).fetchone()

    @staticmethod
    def _receipt(row: Mapping[str, Any]) -> dict[str, Any]:
        stable = {
            "candidateId": row["candidate_id"], "taskId": row["task_id"],
            "runId": row["run_id"], "subjectRef": row["subject_ref"],
            "payloadRef": row["payload_ref"], "sourceRef": row["source_ref"],
            "sourceHash": row["source_hash"], "markings": row["markings"],
            "initialEventHash": row["event_hash"],
        }
        return {
            "resourceType": "MemoryCandidateReceipt", "resourceId": row["candidate_id"],
            "revision": 1,
            "contentHash": "sha256:" + hashlib.sha256(_canonical(stable).encode()).hexdigest(),
        }

    def read_receipt(
        self, *, target_id: str, expected_receipt: Mapping[str, Any], **_kwargs,
    ) -> Mapping[str, Any]:
        expected = _strict_exact_ref(dict(expected_receipt), name="memory candidate Receipt")
        if type(target_id) is not str or expected["resourceId"] != target_id:
            raise EcommerceGrowthFeedbackConflict("memory candidate identity drifted")
        row = self._candidate_row(target_id)
        if (
            row is None or row["memory_layer"] != "episodic" or row["scope"] != "workspace"
            or row["source_revision"] != 1
            or row["event_type"] != "submitted" or row["to_status"] != "pending"
            or "insufficient_evidence" not in row["markings"]
            or type(row["source_ref"]) is not dict
            or row["source_ref"].get("resourceType") != "EffectReviewRevision"
            or row["source_ref"].get("revision") != "1"
            or row["source_ref"].get("authority") != "aip-effect-review"
        ):
            raise EcommerceGrowthFeedbackConflict("memory candidate authority drifted")
        origins = self._transaction.execute(
            """SELECT c.task_ref,c.artifact_ref,c.review_receipt_ref,
                      second.target_receipt_ref
                 FROM public.ecommerce_growth_feedback_command c
                 JOIN public.ecommerce_growth_feedback_segment third
                   ON third.org_id=c.org_id AND third.project_id=c.project_id
                  AND third.command_id=c.command_id AND third.sequence=3
                 JOIN public.ecommerce_growth_feedback_segment second
                   ON second.org_id=c.org_id AND second.project_id=c.project_id
                  AND second.command_id=c.command_id AND second.sequence=2
                WHERE c.org_id=%s AND c.project_id=%s AND c.decision='ACCEPT'
                  AND third.kind='memory_candidate' AND third.target_id=%s
                  AND second.kind='improvement_observation' AND second.state='acked'""",
            (*self._scope.key, target_id),
        ).fetchall()
        if len(origins) != 1:
            raise EcommerceGrowthFeedbackConflict("memory candidate original command is ambiguous")
        origin = origins[0]
        artifact = _strict_exact_ref(origin["artifact_ref"], name="candidate source Artifact")
        review_receipt = _strict_exact_ref(origin["review_receipt_ref"], name="candidate review Receipt")
        second_receipt = _strict_exact_ref(
            origin["target_receipt_ref"], name="candidate improvement Receipt",
        )
        expected_subject = ResourceRef(
            resource_type="ContentReviewReceipt", resource_id=review_receipt["resourceId"],
            revision=str(review_receipt["revision"]), authority="ecommerce-growth",
        ).model_dump(mode="json", by_alias=True)
        expected_payload = ArtifactRef(
            artifact_id=artifact["resourceId"], artifact_type="ecommerce_content",
            revision=str(artifact["revision"]), content_hash=artifact["contentHash"][7:],
        ).model_dump(mode="json", by_alias=True)
        if (
            row["task_id"] != origin["task_ref"].get("resourceId")
            or row["subject_ref"] != expected_subject
            or row["payload_ref"] != expected_payload
        ):
            raise EcommerceGrowthFeedbackConflict("memory candidate exact source drifted")
        review = self._transaction.execute(
            """SELECT * FROM public.aip_effect_review_revision
                WHERE org_id=%s AND project_id=%s AND review_id=%s AND revision=1""",
            (*self._scope.key, row["source_ref"].get("resourceId")),
        ).fetchone()
        if review is None or review["content_hash"] != row["source_hash"]:
            raise EcommerceGrowthFeedbackConflict("memory candidate effect source drifted")
        effect_subject = "content-effect-" + second_receipt["contentHash"][7:47]
        EffectReviewOwner._verify_review(
            review, effect_subject, second_receipt["resourceId"],
        )
        receipt = self._receipt(row)
        if expected != receipt:
            raise EcommerceGrowthFeedbackConflict("memory candidate Receipt hash drifted")
        return receipt

    def put(
        self, *, command_id: str, command: Mapping[str, Any], claim: Mapping[str, Any],
        review: Mapping[str, Any], now: datetime,
    ) -> Mapping[str, Any]:
        if (
            command_id != command.get("commandId")
            or claim.get("sequence") != 3 or claim.get("kind") != "memory_candidate"
            or claim.get("attempt") != 1 or type(claim.get("targetId")) is not str
            or not claim["targetId"].startswith("memory_candidate-")
            or claim.get("payload", {}).get("kind") != "memory_candidate"
            or claim.get("payload", {}).get("targetId") != claim["targetId"]
            or command.get("decision") != "ACCEPT"
            or review["revision"] != 1 or review["accepted"] is not False
            or review["effect_completed"] is not False
            or review["maturity_status"] != "insufficient"
            or review["sample_count"] != 0
        ):
            raise EcommerceGrowthFeedbackConflict("pending memory candidate input drifted")
        artifact = _strict_exact_ref(command["artifactRef"], name="candidate artifact")
        task = _strict_exact_ref(command["taskRef"], name="candidate task")
        review_receipt = _strict_exact_ref(command["reviewReceiptRef"], name="content review Receipt")
        artifact_row = self._transaction.execute(
            """SELECT a.run_id FROM public.aip_artifact a
                JOIN public.aip_task_run r ON r.org_id=a.org_id AND r.project_id=a.project_id
                 AND r.run_id=a.run_id AND r.task_id=%s AND r.status='succeeded'
               WHERE a.org_id=%s AND a.project_id=%s AND a.artifact_id=%s
                 AND a.artifact_type='ecommerce_content'
                 AND a.content_hash=%s AND coalesce(a.family_revision,1)=%s""",
            (task["resourceId"], *self._scope.key, artifact["resourceId"],
             artifact["contentHash"][7:], artifact["revision"]),
        ).fetchone()
        if artifact_row is None:
            raise EcommerceGrowthFeedbackConflict("candidate original Artifact/Run drifted")
        source_id = "effect-source-" + review["content_hash"][:40]
        prior_candidate = self._candidate_row(claim["targetId"])
        prior_source = self._transaction.execute(
            """SELECT 1 FROM public.aip_memory_source_revision
                WHERE org_id=%s AND project_id=%s AND source_id=%s AND revision=1""",
            (*self._scope.key, source_id),
        ).fetchone()
        if prior_candidate is not None or prior_source is not None:
            raise EcommerceGrowthFeedbackConflict(
                "candidate target already exists before pristine claim; reconcile without resend"
            )
        source = KnowledgeSourceRef(
            source_kind=KnowledgeSourceKind.EFFECT_REVIEW,
            source_ref=ResourceRef(
                resource_type="EffectReviewRevision", resource_id=review["review_id"],
                revision="1", authority="aip-effect-review",
            ),
            observed_at=review["created_at"],
            freshness_expires_at=review["created_at"] + timedelta(days=30),
            license_id="aos-internal", usage_policy="pending-governance-only",
            content_hash=review["content_hash"], provider="aos-feedback",
            provider_version="1", applicability=["ecommerce-content-method"],
        )
        request = SubmitMemoryCandidateRequest(
            candidate_layer=RuntimeMemoryLayer.EPISODIC,
            task_id=task["resourceId"], run_id=artifact_row["run_id"],
            subject=ResourceRef(
                resource_type="ContentReviewReceipt", resource_id=review_receipt["resourceId"],
                revision=str(review_receipt["revision"]), authority="ecommerce-growth",
            ),
            payload=ArtifactRef(
                artifact_id=artifact["resourceId"], artifact_type="ecommerce_content",
                revision=str(artifact["revision"]), content_hash=artifact["contentHash"][7:],
            ),
            source=source, confidence=0.0,
            marking=["internal", "insufficient_evidence", "pending_governance"],
        )
        self._store.create_source_revision_in_transaction(
            self._scope, source_id, 1, source, actor="ecommerce-memory-candidate",
            transaction=self._transaction,
        )
        self._store.submit_candidate_in_transaction(
            self._scope, claim["targetId"], request, source_id=source_id,
            source_revision=1, knowledge_scope=KnowledgeScope.WORKSPACE,
            actor="ecommerce-memory-candidate", occurred_at=now,
            transaction=self._transaction,
        )
        row = self._candidate_row(claim["targetId"])
        if row is None:
            raise EcommerceGrowthFeedbackConflict("memory candidate was not persisted")
        receipt = self._receipt(row)
        return self.read_receipt(target_id=claim["targetId"], expected_receipt=receipt)


class MemoryCandidateFeedbackWorker:
    """A single current third segment; post-commit uncertainty stops the worker."""

    def __init__(self, *, connect=connect_serializable, connect_read=None) -> None:
        self._connect = connect
        self._connect_read = (
            connect_read if connect_read is not None
            else connect_read_only if connect is connect_serializable else connect
        )

    @staticmethod
    def _port(transaction: HostTransaction, scope: TenantScope, target: BoundMemoryCandidateTarget):
        return BoundEcommerceGrowthFeedbackPort(
            transaction, scope, actor="ecommerce-memory-candidate", checked_at=datetime.now(UTC),
            target_receipt_readers={
                "daily_review": _unwired_target,
                "improvement_observation": _unwired_target,
                "memory_candidate": target.read_receipt,
                "content_return_target": _unwired_target,
            },
        )

    def run_one(self, scope: TenantScope, command_id: str) -> dict[str, Any]:
        if type(scope) is not TenantScope or type(command_id) is not str or not command_id.strip():
            raise ValueError("scoped memory candidate command is required")
        with self._connect(scope) as conn:
            transaction = HostTransaction(conn)
            target = BoundMemoryCandidateTarget(transaction, scope)
            port = self._port(transaction, scope, target)
            command = port.read(command_id=command_id)
            if command is None or command["decision"] != "ACCEPT" or len(command["segments"]) != 3:
                raise EcommerceGrowthFeedbackConflict("accepted candidate command is missing")
            third = command["segments"][2]
            if command["checkpoint"]["completedSequence"] == 3:
                receipt = target.read_receipt(
                    target_id=third["payload"]["targetId"],
                    expected_receipt=third["targetReceiptRef"],
                )
                return {"status": "ALREADY_ACKED", "commandId": command_id, "receiptRef": receipt}
            if (
                command["checkpoint"]["completedSequence"] != 2
                or third["state"] != "pending" or third["attempt"] != 0
                or third["targetReceiptRef"] is not None
                or third["payload"].get("kind") != "memory_candidate"
            ):
                raise EcommerceGrowthFeedbackConflict("candidate segment is not pristine")
            second_ref = EffectReviewOwner._source(transaction, scope, command_id)
            subject_id = "content-effect-" + second_ref["contentHash"][7:47]
            review = EffectReviewOwner._existing(transaction, scope, subject_id)
            EffectReviewOwner._verify_review(review, subject_id, second_ref["resourceId"])
            claim = port.claim_current(command_id=command_id, worker="ecommerce-memory-candidate")
            if claim is None:
                return {"status": "NOT_CLAIMED", "commandId": command_id}
            port.require_current_origin(command_id=command_id)
            receipt = target.put(
                command_id=command_id, command=command, claim=claim, review=review,
                now=datetime.now(UTC),
            )
            checkpoint = port.acknowledge(
                command_id=command_id, claim=claim, target_receipt_ref=receipt,
            )
            if checkpoint["completedSequence"] != 3:
                raise EcommerceGrowthFeedbackConflict("candidate checkpoint drifted")
            try:
                conn.commit()
            except Exception as exc:
                raise MemoryCandidateUnknown(
                    "memory candidate commit result unknown; reconcile without resend"
                ) from exc
        try:
            with self._connect_read(scope) as conn:
                transaction = HostTransaction(conn)
                BoundMemoryCandidateTarget(transaction, scope).read_receipt(
                    target_id=third["payload"]["targetId"], expected_receipt=receipt,
                )
                row = transaction.execute(
                    """SELECT p.completed_sequence,s.state,s.target_receipt_ref
                       FROM public.ecommerce_growth_feedback_checkpoint p
                       JOIN public.ecommerce_growth_feedback_segment s
                         ON s.org_id=p.org_id AND s.project_id=p.project_id
                        AND s.command_id=p.command_id AND s.sequence=3
                      WHERE p.org_id=%s AND p.project_id=%s AND p.command_id=%s""",
                    (*scope.key, command_id),
                ).fetchone()
                if row is None or row["completed_sequence"] != 3 or row["state"] != "acked" or row["target_receipt_ref"] != receipt:
                    raise EcommerceGrowthFeedbackConflict("candidate independent checkpoint readback drifted")
        except Exception as exc:
            raise MemoryCandidateUnknown(
                "memory candidate post-commit result unknown; reconcile without resend"
            ) from exc
        return {"status": "MEMORY_CANDIDATE_ACKED", "commandId": command_id, "receiptRef": receipt}


_PENDING_MEMORY_CANDIDATE = """SELECT c.command_id
  FROM public.ecommerce_growth_feedback_command c
  JOIN public.ecommerce_growth_feedback_checkpoint p
    ON p.org_id=c.org_id AND p.project_id=c.project_id AND p.command_id=c.command_id
  JOIN public.ecommerce_growth_feedback_segment s
    ON s.org_id=c.org_id AND s.project_id=c.project_id AND s.command_id=c.command_id
   AND s.sequence=3
  JOIN public.ecommerce_growth_feedback_segment second
    ON second.org_id=c.org_id AND second.project_id=c.project_id
   AND second.command_id=c.command_id AND second.sequence=2
  JOIN public.aip_effect_review_head h
    ON h.org_id=c.org_id AND h.project_id=c.project_id
   AND h.subject_id='content-effect-'||substr(second.target_receipt_ref->>'contentHash',8,40)
  JOIN public.aip_effect_review_revision r
    ON r.org_id=h.org_id AND r.project_id=h.project_id
   AND r.subject_id=h.subject_id AND r.revision=h.current_revision
  JOIN public.extension_operation_dispatch_binding d
    ON d.org_id=c.org_id AND d.project_id=c.project_id
   AND d.operation_id='ecommerce_growth_content_review'
  JOIN public.extension_runtime_binding b
    ON b.org_id=d.org_id AND b.project_id=d.project_id
   AND b.installation_id=d.installation_id AND b.generation=d.generation
 WHERE c.org_id=%s AND c.project_id=%s AND c.decision='ACCEPT'
   AND p.completed_sequence=2 AND s.kind='memory_candidate'
   AND s.state='pending' AND s.attempt=0 AND s.target_receipt_ref IS NULL
   AND s.payload->>'targetId'=s.target_id
   AND second.kind='improvement_observation' AND second.state='acked'
   AND r.accepted=false AND r.effect_completed=false
   AND r.maturity_status='insufficient' AND r.sample_count=0
   AND d.handler_kind='extension' AND d.operation_fence=false
   AND b.execution_epoch=d.execution_epoch AND b.desired_state='enabled'
   AND b.observed_state='ready' AND b.enabled=true AND b.operation_fence=false
   AND (SELECT count(*) FROM public.ecommerce_growth_runtime_command_receipt origin
         WHERE origin.org_id=c.org_id AND origin.project_id=c.project_id
           AND origin.operation_id='ecommerce_growth_content_review'
           AND origin.target_receipt_ref=c.review_receipt_ref
           AND origin.dispatch_revision=d.revision
           AND origin.installation_id=d.installation_id AND origin.generation=d.generation
           AND origin.execution_epoch=d.execution_epoch
           AND origin.cutover_group_id=d.cutover_group_id
           AND origin.cutover_group_revision=d.cutover_group_revision
           AND origin.runtime_revision=b.revision)=1
   AND NOT EXISTS(SELECT 1 FROM public.aip_memory_candidate candidate
     WHERE candidate.org_id=c.org_id AND candidate.project_id=c.project_id
       AND candidate.candidate_id=s.target_id)
 ORDER BY c.created_at,c.command_id LIMIT %s"""


class CurrentMemoryCandidateConsumer:
    """Bounded read-only route; the owner revalidates every source under Host locks."""

    def __init__(self, *, connect=connect_read_only, worker=None) -> None:
        self._connect = connect
        self._worker = worker if worker is not None else MemoryCandidateFeedbackWorker()

    def list_pending(self, scope: TenantScope, *, limit: int = 32) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("bounded candidate selector and tenant scope required")
        with self._connect(scope) as conn:
            rows = conn.execute(_PENDING_MEMORY_CANDIDATE, (*scope.key, limit)).fetchall()
        result = [row["command_id"] for row in rows]
        if any(type(item) is not str or not item for item in result):
            raise EcommerceGrowthFeedbackConflict("candidate selector identity drifted")
        return result

    def run_once(self, scope: TenantScope, *, limit: int = 32) -> list[dict[str, str]]:
        statuses = []
        for command_id in self.list_pending(scope, limit=limit):
            try:
                result = self._worker.run_one(scope, command_id)
            except (EcommerceGrowthFeedbackConflict, EcommerceGrowthHostError):
                statuses.append({"commandId": command_id, "status": "BLOCKED_CURRENT_AUTHORITY"})
                continue
            statuses.append({"commandId": command_id, "status": result["status"]})
        return statuses

    async def serve(self, stop, *, host_ready, interval_seconds: int = 15) -> None:
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("memory candidate worker interval is invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("memory candidate worker Runtime Host became unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


__all__ = [
    "BoundMemoryCandidateTarget", "MemoryCandidateFeedbackWorker",
    "CurrentMemoryCandidateConsumer", "MemoryCandidateUnknown",
]
