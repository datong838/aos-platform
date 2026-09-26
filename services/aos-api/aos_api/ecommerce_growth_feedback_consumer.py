"""Bounded natural pickup of reviewed content feedback, without unknown replay."""

from __future__ import annotations

import asyncio

from aos_api.ecommerce_growth_daily_review_target import DailyReviewFeedbackWorker
from aos_api.ecommerce_growth_feedback_port import EcommerceGrowthFeedbackConflict
from aos_api.ecommerce_growth_host_ports import EcommerceGrowthHostError
from aos_api.ecommerce_growth_runtime_connection import connect_read_only
from aos_api.tenant_scope import TenantScope


_PENDING_CURRENT_DAILY_REVIEW = """SELECT c.command_id
  FROM public.ecommerce_growth_feedback_command c
  JOIN public.ecommerce_growth_feedback_checkpoint p
    ON p.org_id=c.org_id AND p.project_id=c.project_id AND p.command_id=c.command_id
  JOIN public.ecommerce_growth_feedback_segment s
    ON s.org_id=c.org_id AND s.project_id=c.project_id AND s.command_id=c.command_id
   AND s.sequence=1
  JOIN public.extension_operation_dispatch_binding d
    ON d.org_id=c.org_id AND d.project_id=c.project_id
   AND d.operation_id='ecommerce_growth_content_review'
  JOIN public.extension_runtime_binding b
    ON b.org_id=d.org_id AND b.project_id=d.project_id
   AND b.installation_id=d.installation_id AND b.generation=d.generation
 WHERE c.org_id=%s AND c.project_id=%s AND c.decision='ACCEPT'
   AND p.completed_sequence=0 AND p.version>=1
   AND s.kind='daily_review' AND s.state='pending' AND s.attempt=0
   AND s.target_receipt_ref IS NULL
   AND s.payload->>'targetId'=s.target_id
   AND s.payload->>'kind'='daily_review'
   AND d.handler_kind='extension' AND d.operation_fence=false
   AND b.execution_epoch=d.execution_epoch
   AND b.desired_state='enabled' AND b.observed_state='ready'
   AND b.enabled=true AND b.operation_fence=false
   AND (SELECT count(*) FROM public.ecommerce_growth_runtime_command_receipt r
         WHERE r.org_id=c.org_id AND r.project_id=c.project_id
           AND r.operation_id='ecommerce_growth_content_review'
           AND r.target_receipt_ref=c.review_receipt_ref
           AND r.dispatch_revision=d.revision
           AND r.installation_id=d.installation_id AND r.generation=d.generation
           AND r.execution_epoch=d.execution_epoch
           AND r.cutover_group_id=d.cutover_group_id
           AND r.cutover_group_revision=d.cutover_group_revision
           AND r.runtime_revision=b.revision
           AND r.response->'receiptRef'=c.review_receipt_ref
           AND r.response->>'decision'='ACCEPT'
           AND r.response->'artifactRef'=c.artifact_ref
           AND r.response->'taskRef'=c.task_ref
           AND r.response->'briefRef'=c.brief_ref)=1
   AND NOT EXISTS(SELECT 1 FROM public.ecommerce_growth_daily_review_target t
         WHERE t.org_id=c.org_id AND t.project_id=c.project_id
           AND t.target_id=s.target_id)
 ORDER BY c.created_at,c.command_id LIMIT %s"""


class CurrentFeedbackConsumer:
    """Only pristine pending first segments are eligible for automatic pickup."""

    def __init__(self, *, connect=connect_read_only, worker=None) -> None:
        self._connect = connect
        self._worker = worker if worker is not None else DailyReviewFeedbackWorker()

    def list_pending(self, scope: TenantScope, *, limit: int = 32) -> list[str]:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError("bounded feedback selector and trusted tenant scope required")
        with self._connect(scope) as conn:
            rows = conn.execute(_PENDING_CURRENT_DAILY_REVIEW, (*scope.key, limit)).fetchall()
        command_ids = [row["command_id"] for row in rows]
        if any(type(item) is not str or not item for item in command_ids):
            raise EcommerceGrowthFeedbackConflict("feedback selector returned invalid command identity")
        return command_ids

    def run_once(self, scope: TenantScope, *, limit: int = 32) -> list[dict[str, str]]:
        command_ids = self.list_pending(scope, limit=limit)
        statuses = []
        for command_id in command_ids:
            try:
                result = self._worker.run_one(scope, command_id)
            except (EcommerceGrowthFeedbackConflict, EcommerceGrowthHostError):
                statuses.append({"commandId": command_id, "status": "BLOCKED_CURRENT_AUTHORITY"})
                continue
            statuses.append({"commandId": command_id, "status": result["status"]})
        return statuses

    async def serve(self, stop, *, host_ready, interval_seconds: int = 15) -> None:
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("feedback worker interval is invalid")
        scope = TenantScope("org-org", "dev-project")
        while not stop.is_set():
            if not host_ready():
                raise RuntimeError("feedback worker Runtime Host became unavailable")
            await asyncio.to_thread(self.run_once, scope)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            except TimeoutError:
                pass


__all__ = ["CurrentFeedbackConsumer"]
