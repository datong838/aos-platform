"""Second accepted-feedback target: an immutable request for effect observation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
from typing import Any, Mapping
from uuid import UUID

from aos_api.ecommerce_growth_feedback_port import (
    BoundEcommerceGrowthFeedbackPort,
    EcommerceGrowthFeedbackConflict,
    _strict_exact_ref,
)
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostError, HostTransaction
from aos_api.ecommerce_growth_runtime_connection import connect_read_only, connect_serializable
from aos_api.tenant_scope import TenantScope


def _unwired_target(**_kwargs):
    raise EcommerceGrowthFeedbackConflict("feedback target is not wired")


class BoundImprovementPendingTarget:
    """The same host transaction writes and verifies a pending-only Receipt."""

    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("improvement target requires a scoped host transaction")
        self._transaction = transaction
        self._scope = scope

    def put(
        self, *, command_id: str, command: Mapping[str, Any], claim: Mapping[str, Any],
        origin: Mapping[str, Any], daily_receipt_ref: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if (
            type(command_id) is not str or not command_id.strip()
            or command.get("decision") != "ACCEPT"
            or claim.get("kind") != "improvement_observation"
            or claim.get("sequence") != 2
            or type(claim.get("targetId")) is not str
            or not claim["targetId"].startswith("improvement_observation-")
            or type(claim.get("payload")) is not dict
            or claim["payload"].get("kind") != "improvement_observation"
            or claim["payload"].get("targetId") != claim["targetId"]
            or type(claim.get("checkpointVersion")) is not int
            or claim["checkpointVersion"] < 1
            or claim.get("attempt") != 1
            or origin.get("reviewReceiptRef") != command.get("reviewReceiptRef")
        ):
            raise EcommerceGrowthFeedbackConflict("improvement target input drifted")
        try:
            UUID(str(claim["leaseToken"]))
            refs = [
                _strict_exact_ref(command[key], name=key)
                for key in ("reviewReceiptRef", "artifactRef", "taskRef", "briefRef")
            ]
            daily = _strict_exact_ref(dict(daily_receipt_ref), name="daily review Receipt")
            if daily["resourceType"] != "DailyReviewReceipt":
                raise EcommerceGrowthFeedbackConflict("daily review Receipt kind drifted")
            row = self._transaction.execute(
                """SELECT * FROM public.ecommerce_growth_improvement_put_a0v_106(
                     %s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb)""",
                (
                    command_id, claim["targetId"], UUID(str(claim["leaseToken"])),
                    claim["checkpointVersion"], json.dumps(claim["payload"], ensure_ascii=False),
                    *(json.dumps(ref, ensure_ascii=False) for ref in refs),
                    json.dumps(daily, ensure_ascii=False),
                ),
            ).fetchone()
            if row is None:
                raise EcommerceGrowthFeedbackConflict("improvement target returned no Receipt")
            return _strict_exact_ref(row["receipt_ref"], name="improvement Receipt")
        except (ValueError, EcommerceGrowthFeedbackConflict):
            raise
        except Exception as exc:
            raise EcommerceGrowthFeedbackConflict("improvement target write failed") from exc

    def read_receipt(
        self, *, target_id: str, expected_receipt: Mapping[str, Any], **_kwargs,
    ) -> Mapping[str, Any]:
        expected = _strict_exact_ref(dict(expected_receipt), name="improvement expected Receipt")
        if type(target_id) is not str or target_id != expected["resourceId"]:
            raise EcommerceGrowthFeedbackConflict("improvement target identity drifted")
        row = self._transaction.execute(
            """SELECT receipt_ref,body,
                      'sha256:'||encode(digest(convert_to(body::text,'UTF8'),'sha256'),'hex') AS computed_hash
                 FROM public.ecommerce_growth_improvement_target
                WHERE org_id=%s AND project_id=%s AND target_id=%s""",
            (*self._scope.key, target_id),
        ).fetchone()
        if (
            row is None or type(row["body"]) is not dict
            or row["computed_hash"] != expected["contentHash"]
            or row["receipt_ref"] != expected
            or expected["resourceType"] != "ImprovementPendingReceipt"
            or row["body"].get("effectStatus") != "AWAITING_COMPARABLE_EVIDENCE"
        ):
            raise EcommerceGrowthFeedbackConflict("improvement Receipt readback drifted")
        return expected


class ImprovementFeedbackWorker:
    """Consume only a pristine second segment after the original daily Receipt."""

    def __init__(self, *, connect=connect_serializable) -> None:
        self._connect = connect

    def run_one(
        self, scope: TenantScope, command_id: str, *, worker: str = "ecommerce-improvement"
    ) -> dict[str, Any]:
        if type(scope) is not TenantScope or type(command_id) is not str or not command_id.strip():
            raise ValueError("scoped improvement command is required")
        with self._connect(scope) as conn:
            transaction = HostTransaction(conn)
            target = BoundImprovementPendingTarget(transaction, scope)
            port = BoundEcommerceGrowthFeedbackPort(
                transaction, scope, actor=worker, checked_at=datetime.now(UTC),
                target_receipt_readers={
                    "daily_review": _unwired_target,
                    "improvement_observation": target.read_receipt,
                    "memory_candidate": _unwired_target,
                    "content_return_target": _unwired_target,
                },
            )
            command = port.read(command_id=command_id)
            if command is None:
                raise EcommerceGrowthFeedbackConflict("improvement feedback command is missing")
            if command["decision"] != "ACCEPT":
                return {"status": "NOT_APPLICABLE", "commandId": command_id}
            segments = command["segments"]
            if (
                len(segments) != 3
                or segments[0]["payload"].get("kind") != "daily_review"
                or segments[1]["payload"].get("kind") != "improvement_observation"
            ):
                raise EcommerceGrowthFeedbackConflict("improvement sequence drifted")
            second = segments[1]
            if command["checkpoint"]["completedSequence"] >= 2:
                receipt = target.read_receipt(
                    target_id=second["payload"]["targetId"],
                    expected_receipt=second["targetReceiptRef"],
                )
                return {"status": "ALREADY_ACKED", "commandId": command_id, "receiptRef": receipt}
            if (
                command["checkpoint"]["completedSequence"] != 1
                or segments[0]["state"] != "acked"
                or segments[0]["targetReceiptRef"] is None
                or second["state"] != "pending" or second["attempt"] != 0
            ):
                raise EcommerceGrowthFeedbackConflict("improvement is not pristine after daily review")
            claim = port.claim_current(command_id=command_id, worker=worker)
            if claim is None:
                return {"status": "NOT_CLAIMED", "commandId": command_id}
            if claim["sequence"] != 2 or claim["kind"] != "improvement_observation" or claim["attempt"] != 1:
                raise RuntimeError("unsupported improvement segment; transaction must roll back")
            origin = port.require_current_origin(command_id=command_id)
            receipt = target.put(
                command_id=command_id, command=command, claim=claim, origin=origin,
                daily_receipt_ref=segments[0]["targetReceiptRef"],
            )
            target.read_receipt(target_id=claim["targetId"], expected_receipt=receipt)
            checkpoint = port.acknowledge(command_id=command_id, claim=claim, target_receipt_ref=receipt)
            readback = port.read(command_id=command_id)
            if (
                checkpoint["completedSequence"] != 2
                or readback is None
                or readback["checkpoint"]["completedSequence"] != 2
                or readback["segments"][1]["state"] != "acked"
                or readback["segments"][1]["targetReceiptRef"] != receipt
            ):
                raise EcommerceGrowthFeedbackConflict("improvement checkpoint drifted")
            conn.commit()
            return {"status": "IMPROVEMENT_PENDING_ACKED", "commandId": command_id, "receiptRef": receipt}


_PENDING_CURRENT_IMPROVEMENT = """SELECT c.command_id
  FROM public.ecommerce_growth_feedback_command c
  JOIN public.ecommerce_growth_feedback_checkpoint p
    ON p.org_id=c.org_id AND p.project_id=c.project_id AND p.command_id=c.command_id
  JOIN public.ecommerce_growth_feedback_segment first
    ON first.org_id=c.org_id AND first.project_id=c.project_id
   AND first.command_id=c.command_id AND first.sequence=1
  JOIN public.ecommerce_growth_feedback_segment second
    ON second.org_id=c.org_id AND second.project_id=c.project_id
   AND second.command_id=c.command_id AND second.sequence=2
  JOIN public.ecommerce_growth_daily_review_target daily
    ON daily.org_id=c.org_id AND daily.project_id=c.project_id
   AND daily.command_id=c.command_id AND daily.target_id=first.target_id
  JOIN public.extension_operation_dispatch_binding d
    ON d.org_id=c.org_id AND d.project_id=c.project_id
   AND d.operation_id='ecommerce_growth_content_review'
  JOIN public.extension_runtime_binding b
    ON b.org_id=d.org_id AND b.project_id=d.project_id
   AND b.installation_id=d.installation_id AND b.generation=d.generation
  JOIN public.aip_artifact a
    ON a.org_id=c.org_id AND a.project_id=c.project_id
   AND a.artifact_id=c.artifact_ref->>'resourceId'
   AND a.artifact_type='ecommerce_content'
   AND c.artifact_ref->>'contentHash'='sha256:'||a.content_hash
   AND c.artifact_ref->'revision'=to_jsonb(coalesce(a.family_revision,1))
  JOIN public.aip_task_run r
    ON r.org_id=a.org_id AND r.project_id=a.project_id AND r.run_id=a.run_id
   AND r.task_id=c.task_ref->>'resourceId' AND r.status='succeeded'
  JOIN public.aip_task t
    ON t.org_id=r.org_id AND t.project_id=r.project_id AND t.task_id=r.task_id
   AND t.status='completed'
 WHERE c.org_id=%s AND c.project_id=%s AND c.decision='ACCEPT'
   AND p.completed_sequence=1 AND first.kind='daily_review'
   AND first.state='acked' AND first.target_receipt_ref=daily.receipt_ref
   AND second.kind='improvement_observation' AND second.state='pending'
   AND second.attempt=0 AND second.target_receipt_ref IS NULL
   AND second.payload->>'targetId'=second.target_id
   AND second.payload->>'kind'='improvement_observation'
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
           AND origin.runtime_revision=b.revision
           AND origin.response->'receiptRef'=c.review_receipt_ref
           AND origin.response->>'decision'='ACCEPT'
           AND origin.response->'artifactRef'=c.artifact_ref
           AND origin.response->'taskRef'=c.task_ref
           AND origin.response->'briefRef'=c.brief_ref)=1
   AND NOT EXISTS(SELECT 1 FROM public.ecommerce_growth_improvement_target pending
         WHERE pending.org_id=c.org_id AND pending.project_id=c.project_id
           AND pending.target_id=second.target_id)
 ORDER BY c.created_at,c.command_id LIMIT %s"""


class CurrentImprovementConsumer:
    """Bounded natural pickup; the selector never grants execution authority."""

    def __init__(self, *, connect=connect_read_only, worker=None) -> None:
        self._connect = connect
        self._worker = worker if worker is not None else ImprovementFeedbackWorker()

    def list_pending(self, scope: TenantScope, *, limit: int = 32) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("bounded improvement selector and tenant scope required")
        with self._connect(scope) as conn:
            rows = conn.execute(_PENDING_CURRENT_IMPROVEMENT, (*scope.key, limit)).fetchall()
        command_ids = [row["command_id"] for row in rows]
        if any(type(item) is not str or not item for item in command_ids):
            raise EcommerceGrowthFeedbackConflict("improvement selector returned invalid command identity")
        return command_ids

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
            raise ValueError("improvement worker interval is invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("improvement worker Runtime Host became unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


__all__ = ["BoundImprovementPendingTarget", "ImprovementFeedbackWorker", "CurrentImprovementConsumer"]
