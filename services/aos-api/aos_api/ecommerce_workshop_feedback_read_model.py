"""One read-only snapshot of the accepted feedback chain for the task cockpit."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aos_api.aip_contracts import TenantContext
from aos_api.db import connect_read_only
from aos_api.ecommerce_growth_daily_review_target import BoundDailyReviewTarget
from aos_api.ecommerce_growth_effect_review_owner import EffectReviewOwner
from aos_api.ecommerce_growth_feedback_port import (
    BoundEcommerceGrowthFeedbackPort, EcommerceGrowthFeedbackConflict, _strict_exact_ref,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_improvement_target import BoundImprovementPendingTarget
from aos_api.ecommerce_growth_memory_candidate_target import BoundMemoryCandidateTarget
from aos_api.ecommerce_workshop_feedback_read_contracts import (
    FeedbackAuditDetails, FeedbackBusinessItem, FeedbackExactRef,
    FeedbackReadEnvelope, FeedbackSegmentView,
)
from aos_api.tenant_scope import TenantScope


class FeedbackReadUnavailable(RuntimeError):
    """No partial business success is returned after source or Receipt drift."""


_KINDS = ("daily_review", "improvement_observation", "memory_candidate")
_CANDIDATE_LABELS = {
    "pending": "待治理", "quarantined": "已隔离", "rejected": "已驳回",
    "approved": "已批准待入库", "promoted": "已入库",
}
_ACK_LABELS = (
    "复盘记录已接收", "待补可比较效果证据", "待治理经验候选已形成",
)


class EcommerceWorkshopFeedbackReadModel:
    """Historical business read; never grants current execution authority."""

    def __init__(self, *, connect=connect_read_only) -> None:
        self._connect = connect

    @staticmethod
    def _target_refs(command: dict[str, Any], transaction, scope):
        daily = BoundDailyReviewTarget(transaction, scope)
        improvement = BoundImprovementPendingTarget(transaction, scope)
        candidate = BoundMemoryCandidateTarget(transaction, scope)
        readers = (daily.read_receipt, improvement.read_receipt, candidate.read_receipt)
        checkpoint = command["checkpoint"]["completedSequence"]
        if type(checkpoint) is not int or not 0 <= checkpoint <= 3:
            raise EcommerceGrowthFeedbackConflict("feedback checkpoint is invalid")
        views = []
        receipts = []
        for index, (kind, segment, reader) in enumerate(zip(_KINDS, command["segments"], readers), start=1):
            payload = segment["payload"]
            if (
                segment["sequence"] != index or payload.get("kind") != kind
                or type(payload.get("businessTitle")) is not str
                or type(payload.get("businessSummary")) is not str
                or not payload["businessTitle"].strip()
                or not payload["businessSummary"].strip()
                or type(payload.get("targetId")) is not str
            ):
                raise EcommerceGrowthFeedbackConflict("feedback business segment drifted")
            acked = segment["state"] == "acked"
            if acked != (index <= checkpoint):
                raise EcommerceGrowthFeedbackConflict("feedback checkpoint/segment order drifted")
            if acked:
                exact = _strict_exact_ref(segment["targetReceiptRef"], name="feedback target Receipt")
                reader(target_id=payload["targetId"], expected_receipt=exact)
                receipts.append(FeedbackExactRef.model_validate(exact))
                state = "acknowledged"
                label = _ACK_LABELS[index - 1]
            else:
                if segment["targetReceiptRef"] is not None:
                    raise EcommerceGrowthFeedbackConflict("unacknowledged feedback has a target Receipt")
                if segment["state"] not in {"pending", "claimed", "unknown"}:
                    raise EcommerceGrowthFeedbackConflict("unacknowledged feedback has an invalid state")
                receipts.append(None)
                state = "unknown" if segment["state"] in {"claimed", "unknown"} else "pending"
                label = "状态待核对" if state == "unknown" else "等待接收"
            views.append(FeedbackSegmentView(
                sequence=index, kind=kind, title=payload["businessTitle"],
                summary=payload["businessSummary"], state=state, status_label=label,
            ))
        return views, receipts

    @staticmethod
    def _original_run(transaction: HostTransaction, scope: TenantScope, command: dict[str, Any], checkpoint: int):
        artifact = _strict_exact_ref(command["artifactRef"], name="feedback Artifact")
        task = _strict_exact_ref(command["taskRef"], name="feedback Task")
        row = transaction.execute(
            """SELECT a.content_hash,a.family_revision,r.status AS run_status,t.status AS task_status
                 FROM public.aip_artifact a
                 JOIN public.aip_task_run r ON r.org_id=a.org_id AND r.project_id=a.project_id
                  AND r.run_id=a.run_id AND r.task_id=%s
                 JOIN public.aip_task t ON t.org_id=r.org_id AND t.project_id=r.project_id
                  AND t.task_id=r.task_id
                WHERE a.org_id=%s AND a.project_id=%s AND a.artifact_id=%s
                  AND a.artifact_type='ecommerce_content'""",
            (task["resourceId"], *scope.key, artifact["resourceId"]),
        ).fetchone()
        if (
            row is None or artifact["contentHash"] != "sha256:" + row["content_hash"]
            or artifact["revision"] != (row["family_revision"] or 1)
            or (checkpoint > 0 and (row["run_status"] != "succeeded" or row["task_status"] != "completed"))
        ):
            raise EcommerceGrowthFeedbackConflict("feedback original Artifact/Run drifted")

    @staticmethod
    def _formal_review(transaction: HostTransaction, scope: TenantScope, second_receipt):
        if second_receipt is None:
            return None
        subject_id = "content-effect-" + second_receipt.content_hash[7:47]
        row = EffectReviewOwner._existing(transaction, scope, subject_id)
        if row is None:
            return None
        EffectReviewOwner._verify_review(row, subject_id, second_receipt.resource_id)
        return FeedbackExactRef(
            resource_type="EffectReviewRevision", resource_id=row["review_id"],
            revision=1, content_hash="sha256:" + row["content_hash"],
        )

    @staticmethod
    def _candidate_status(transaction: HostTransaction, scope: TenantScope, third_receipt):
        if third_receipt is None:
            return "尚未形成"
        rows = transaction.execute(
            """SELECT status FROM public.aip_memory_candidate
                WHERE org_id=%s AND project_id=%s AND candidate_id=%s""",
            (*scope.key, third_receipt.resource_id),
        ).fetchall()
        if len(rows) != 1 or rows[0]["status"] not in _CANDIDATE_LABELS:
            raise EcommerceGrowthFeedbackConflict("feedback candidate status is unavailable")
        if rows[0]["status"] == "promoted":
            items = transaction.execute(
                """SELECT memory_item_id FROM public.aip_memory_item_revision
                    WHERE org_id=%s AND project_id=%s AND candidate_id=%s""",
                (*scope.key, third_receipt.resource_id),
            ).fetchall()
            if len(items) != 1:
                raise EcommerceGrowthFeedbackConflict("promoted candidate lacks unique knowledge item")
        return _CANDIDATE_LABELS[rows[0]["status"]]

    def read(self, scope: TenantScope, *, limit: int = 20) -> FeedbackReadEnvelope:
        if type(scope) is not TenantScope or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError("scoped bounded feedback read is required")
        try:
            with self._connect(scope) as conn:
                transaction = HostTransaction(conn)
                cutoff = transaction.execute(
                    "SELECT transaction_timestamp() AS cutoff"
                ).fetchone()["cutoff"]
                rows = transaction.execute(
                    """SELECT command_id,created_at FROM public.ecommerce_growth_feedback_command
                        WHERE org_id=%s AND project_id=%s AND decision='ACCEPT'
                          AND created_at<=%s
                        ORDER BY created_at DESC,command_id DESC LIMIT %s""",
                    (*scope.key, cutoff, limit + 1),
                ).fetchall()
                daily = BoundDailyReviewTarget(transaction, scope)
                improvement = BoundImprovementPendingTarget(transaction, scope)
                candidate = BoundMemoryCandidateTarget(transaction, scope)
                port = BoundEcommerceGrowthFeedbackPort(
                    transaction, scope, actor="ecommerce-cockpit-feedback-read",
                    checked_at=cutoff,
                    target_receipt_readers={
                        "daily_review": daily.read_receipt,
                        "improvement_observation": improvement.read_receipt,
                        "memory_candidate": candidate.read_receipt,
                        "content_return_target": lambda **_: None,
                    },
                )
                items = []
                for row in rows[:limit]:
                    command = port.read(command_id=row["command_id"])
                    if command is None or command["decision"] != "ACCEPT" or len(command["segments"]) != 3:
                        raise EcommerceGrowthFeedbackConflict("feedback original command is missing")
                    segments, target_receipts = self._target_refs(command, transaction, scope)
                    checkpoint = command["checkpoint"]["completedSequence"]
                    self._original_run(transaction, scope, command, checkpoint)
                    effect_ref = self._formal_review(transaction, scope, target_receipts[1])
                    if target_receipts[2] is not None and effect_ref is None:
                        raise EcommerceGrowthFeedbackConflict("candidate cannot precede formal EffectReview")
                    candidate_status = self._candidate_status(transaction, scope, target_receipts[2])
                    items.append(FeedbackBusinessItem(
                        title=segments[0].title, created_at=row["created_at"],
                        segments=segments,
                        effect_status="证据不足" if effect_ref else "待观察",
                        candidate_status=candidate_status,
                        audit_details=FeedbackAuditDetails(
                            command_id=row["command_id"],
                            review_receipt_ref=FeedbackExactRef.model_validate(
                                _strict_exact_ref(command["reviewReceiptRef"], name="review Receipt")),
                            artifact_ref=FeedbackExactRef.model_validate(
                                _strict_exact_ref(command["artifactRef"], name="Artifact")),
                            task_ref=FeedbackExactRef.model_validate(
                                _strict_exact_ref(command["taskRef"], name="Task")),
                            target_receipt_refs=target_receipts,
                            effect_review_ref=effect_ref,
                        ),
                    ))
                return FeedbackReadEnvelope(
                    tenant=TenantContext(org_id=scope.org_id, project_id=scope.project_id),
                    evaluated_at=cutoff, data_cutoff=cutoff,
                    items=items, has_more=len(rows) > limit,
                )
        except (ValueError, EcommerceGrowthFeedbackConflict, FeedbackReadUnavailable):
            raise
        except Exception as exc:
            raise FeedbackReadUnavailable("feedback read authority is unavailable") from exc


__all__ = ["EcommerceWorkshopFeedbackReadModel", "FeedbackReadUnavailable"]
