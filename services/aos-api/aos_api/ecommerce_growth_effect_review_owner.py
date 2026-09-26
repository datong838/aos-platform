"""Current accepted feedback to a formal, insufficient-evidence EffectReview."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from aos_api.aip_contracts import ResourceRef
from aos_api.aip_effect_review import CreateEffectReviewRequest
from aos_api.aip_effect_review_store import AipEffectReviewStore, _hash
from aos_api.ecommerce_growth_daily_review_target import BoundDailyReviewTarget
from aos_api.ecommerce_growth_feedback_port import (
    BoundEcommerceGrowthFeedbackPort, EcommerceGrowthFeedbackConflict, _strict_exact_ref,
)
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostError, HostTransaction
from aos_api.ecommerce_growth_improvement_target import BoundImprovementPendingTarget
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable
from aos_api.tenant_scope import TenantScope


_REASON = "content_accepted_effect_evidence_pending"


class EffectReviewUnknown(RuntimeError):
    """The write boundary may have committed; only read-only reconciliation is safe."""


def _unwired_target(**_kwargs):
    raise EcommerceGrowthFeedbackConflict("effect review does not acknowledge feedback segments")


def _subject_id(receipt: dict[str, Any]) -> str:
    return "content-effect-" + receipt["contentHash"][7:47]


class EffectReviewOwner:
    """One formal review for one exact pending-improvement Receipt, never a mature effect."""

    def __init__(self, *, connect=connect_serializable, connect_read=None) -> None:
        self._connect = connect
        self._connect_read = connect if connect_read is None else connect_read

    @staticmethod
    def _existing(transaction: HostTransaction, scope: TenantScope, subject_id: str):
        return transaction.execute(
            """SELECT r.* FROM public.aip_effect_review_revision r
               JOIN public.aip_effect_review_head h
                 ON h.org_id=r.org_id AND h.project_id=r.project_id
                AND h.subject_id=r.subject_id AND h.current_revision=r.revision
              WHERE r.org_id=%s AND r.project_id=%s AND r.subject_id=%s""",
            (*scope.key, subject_id),
        ).fetchone()

    @staticmethod
    def _verify_review(row: dict[str, Any], subject_id: str, target_id: str) -> None:
        if row is None:
            raise EcommerceGrowthFeedbackConflict("formal effect review is missing")
        subject = row["subject_ref"]
        if type(subject) is not dict:
            raise EcommerceGrowthFeedbackConflict("effect review subject is invalid")
        payload = {
            "subjectId": row["subject_id"], "revision": row["revision"],
            "subjectRef": subject, "observationRefs": row["observation_refs"],
            "metricKeys": row["metric_keys"], "sampleCount": row["sample_count"],
            "minSample": row["min_sample"], "cutoffAt": row["cutoff_at"].isoformat(),
            "eventTimeAt": row["event_time_at"].isoformat(),
            "accepted": row["accepted"], "effectCompleted": row["effect_completed"],
            "maturityStatus": row["maturity_status"], "reasonCode": row["reason_code"],
        }
        expected_subject = ResourceRef(
            resource_type="ImprovementPendingReceipt", resource_id=target_id,
            revision="1", authority="ecommerce-growth",
        ).model_dump(mode="json", by_alias=True)
        if (
            row["subject_id"] != subject_id or row["revision"] != 1
            or subject != expected_subject or row["observation_refs"] != []
            or row["metric_keys"] != [] or row["sample_count"] != 0
            or row["min_sample"] != 1 or row["accepted"] is not False
            or row["effect_completed"] is not False
            or row["maturity_status"] != "insufficient"
            or row["reason_code"] != _REASON
            or row["content_hash"] != _hash(payload)
        ):
            raise EcommerceGrowthFeedbackConflict("formal effect review lineage or maturity drifted")

    @staticmethod
    def _source(transaction: HostTransaction, scope: TenantScope, command_id: str):
        port = BoundEcommerceGrowthFeedbackPort(
            transaction, scope, actor="ecommerce-effect-review", checked_at=datetime.now(UTC),
            target_receipt_readers={kind: _unwired_target for kind in (
                "daily_review", "improvement_observation", "memory_candidate", "content_return_target")},
        )
        command = port.read(command_id=command_id)
        if command is None or command["decision"] != "ACCEPT":
            raise EcommerceGrowthFeedbackConflict("accepted feedback command is missing")
        segments = command["segments"]
        if (
            command["checkpoint"]["completedSequence"] != 2
            or len(segments) != 3
            or segments[0]["state"] != "acked"
            or segments[0]["payload"].get("kind") != "daily_review"
            or segments[1]["state"] != "acked"
            or segments[1]["payload"].get("kind") != "improvement_observation"
            or segments[2]["state"] != "pending" or segments[2]["attempt"] != 0
        ):
            raise EcommerceGrowthFeedbackConflict("formal effect review requires exact second checkpoint")
        origin = port.require_current_origin(command_id=command_id)
        first_ref = _strict_exact_ref(segments[0]["targetReceiptRef"], name="daily review Receipt")
        second_ref = _strict_exact_ref(segments[1]["targetReceiptRef"], name="improvement Receipt")
        BoundDailyReviewTarget(transaction, scope).read_receipt(
            target_id=segments[0]["payload"]["targetId"], expected_receipt=first_ref)
        BoundImprovementPendingTarget(transaction, scope).read_receipt(
            target_id=segments[1]["payload"]["targetId"], expected_receipt=second_ref)
        target = transaction.execute(
            """SELECT body FROM public.ecommerce_growth_improvement_target
                WHERE org_id=%s AND project_id=%s AND target_id=%s AND command_id=%s""",
            (*scope.key, second_ref["resourceId"], command_id),
        ).fetchone()
        snapshot = origin["dispatch"]
        if target is None or type(target["body"]) is not dict:
            raise EcommerceGrowthFeedbackConflict("improvement target is unavailable")
        body = target["body"]
        if (
            body.get("commandId") != command_id
            or body.get("targetId") != second_ref["resourceId"]
            or body.get("dailyReviewReceiptRef") != first_ref
            or body.get("effectStatus") != "AWAITING_COMPARABLE_EVIDENCE"
            or body.get("installationId") != str(snapshot.installation_id)
            or body.get("generation") != str(snapshot.generation)
            or body.get("executionEpoch") != snapshot.execution_epoch
            or any(body.get(key) != command[key] for key in (
                "reviewReceiptRef", "artifactRef", "taskRef", "briefRef"))
        ):
            raise EcommerceGrowthFeedbackConflict("improvement target origin drifted")
        artifact = _strict_exact_ref(command["artifactRef"], name="effect artifact")
        task = _strict_exact_ref(command["taskRef"], name="effect task")
        terminal = transaction.execute(
            """SELECT a.artifact_id FROM public.aip_artifact a
                JOIN public.aip_task_run r ON r.org_id=a.org_id AND r.project_id=a.project_id
                  AND r.run_id=a.run_id AND r.task_id=%s AND r.status='succeeded'
                JOIN public.aip_task t ON t.org_id=r.org_id AND t.project_id=r.project_id
                  AND t.task_id=r.task_id AND t.status='completed'
               WHERE a.org_id=%s AND a.project_id=%s AND a.artifact_id=%s
                 AND a.artifact_type='ecommerce_content'
                 AND %s='sha256:'||a.content_hash
                 AND %s=coalesce(a.family_revision,1)""",
            (task["resourceId"], *scope.key, artifact["resourceId"],
                artifact["contentHash"], artifact["revision"]),
        ).fetchone()
        if terminal is None:
            raise EcommerceGrowthFeedbackConflict("effect review original Run is not terminal")
        return second_ref

    def run_one(self, scope: TenantScope, command_id: str) -> dict[str, Any]:
        if type(scope) is not TenantScope or type(command_id) is not str or not command_id.strip():
            raise ValueError("scoped effect review command is required")
        with self._connect(scope) as conn:
            transaction = HostTransaction(conn)
            target_ref = self._source(transaction, scope, command_id)
            subject_id = _subject_id(target_ref)
            existing = self._existing(transaction, scope, subject_id)
            if existing is not None:
                self._verify_review(existing, subject_id, target_ref["resourceId"])
                return {"status": "ALREADY_REVIEWED", "commandId": command_id,
                    "reviewId": existing["review_id"]}
            now = datetime.now(UTC)
            request = CreateEffectReviewRequest(
                subject_id=subject_id,
                subject_ref=ResourceRef(resource_type="ImprovementPendingReceipt",
                    resource_id=target_ref["resourceId"], revision="1",
                    authority="ecommerce-growth"),
                observation_refs=[], metric_keys=[], sample_count=0, min_sample=1,
                cutoff_at=now, event_time_at=now, accepted=False, expected_revision=0,
                reason_code=_REASON,
            )
            created = AipEffectReviewStore().create_review_in_transaction(
                scope, request, "ecommerce-effect-review", now=now, transaction=transaction)
            self._verify_review(self._existing(transaction, scope, subject_id),
                subject_id, target_ref["resourceId"])
            conn.commit()
        try:
            with self._connect_read(scope) as conn:
                self._verify_review(self._existing(HostTransaction(conn), scope, subject_id),
                    subject_id, target_ref["resourceId"])
        except Exception as exc:
            raise EffectReviewUnknown(
                "effect review post-commit readback is unknown; reconcile without resend"
            ) from exc
        return {"status": "EFFECT_REVIEW_INSUFFICIENT", "commandId": command_id,
            "reviewId": created.review_id}


_PENDING_EFFECT_REVIEW = """SELECT c.command_id
  FROM public.ecommerce_growth_feedback_command c
  JOIN public.ecommerce_growth_feedback_checkpoint p
    ON p.org_id=c.org_id AND p.project_id=c.project_id AND p.command_id=c.command_id
  JOIN public.ecommerce_growth_feedback_segment s
    ON s.org_id=c.org_id AND s.project_id=c.project_id
   AND s.command_id=c.command_id AND s.sequence=2
  JOIN public.ecommerce_growth_improvement_target target
    ON target.org_id=c.org_id AND target.project_id=c.project_id
   AND target.command_id=c.command_id AND target.target_id=s.target_id
  JOIN public.extension_operation_dispatch_binding d
    ON d.org_id=c.org_id AND d.project_id=c.project_id
   AND d.operation_id='ecommerce_growth_content_review'
  JOIN public.extension_runtime_binding b
    ON b.org_id=d.org_id AND b.project_id=d.project_id
   AND b.installation_id=d.installation_id AND b.generation=d.generation
 WHERE c.org_id=%s AND c.project_id=%s AND c.decision='ACCEPT'
   AND p.completed_sequence=2 AND s.kind='improvement_observation'
   AND s.state='acked' AND s.target_receipt_ref=target.receipt_ref
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
   AND NOT EXISTS(SELECT 1 FROM public.aip_effect_review_head h
         WHERE h.org_id=c.org_id AND h.project_id=c.project_id
           AND h.subject_id='content-effect-'||substr(target.receipt_ref->>'contentHash',8,40))
 ORDER BY c.created_at,c.command_id LIMIT %s"""


class CurrentEffectReviewConsumer:
    """Read-only bounded routing; run_one still revalidates all authority under lock."""

    def __init__(self, *, connect=connect_read_only, owner=None) -> None:
        self._connect = connect
        self._owner = owner if owner is not None else EffectReviewOwner()

    def list_pending(self, scope: TenantScope, *, limit: int = 32) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("bounded effect review selector and tenant scope required")
        with self._connect(scope) as conn:
            rows = conn.execute(_PENDING_EFFECT_REVIEW, (*scope.key, limit)).fetchall()
        command_ids = [row["command_id"] for row in rows]
        if any(type(item) is not str or not item for item in command_ids):
            raise EcommerceGrowthFeedbackConflict("effect review selector returned invalid command identity")
        return command_ids

    def run_once(self, scope: TenantScope, *, limit: int = 32) -> list[dict[str, str]]:
        statuses = []
        for command_id in self.list_pending(scope, limit=limit):
            try:
                result = self._owner.run_one(scope, command_id)
            except (EcommerceGrowthFeedbackConflict, EcommerceGrowthHostError):
                statuses.append({"commandId": command_id, "status": "BLOCKED_CURRENT_AUTHORITY"})
                continue
            statuses.append({"commandId": command_id, "status": result["status"]})
        return statuses

    async def serve(self, stop, *, host_ready, interval_seconds: int = 15) -> None:
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("effect review worker interval is invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("effect review worker Runtime Host became unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


__all__ = ["EffectReviewOwner", "CurrentEffectReviewConsumer", "EffectReviewUnknown"]
