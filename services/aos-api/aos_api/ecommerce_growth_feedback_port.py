"""Transaction-bound durable feedback port for the ecommerce growth package."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Mapping
from uuid import UUID

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_PLAN_FIELDS = {
    "commandId",
    "requestHash",
    "decision",
    "reviewReceiptRef",
    "artifactRef",
    "taskRef",
    "briefRef",
    "segments",
    "sideEffects",
}
_ZERO_EFFECT_FIELDS = {
    "providerInvocationCount",
    "externalPublicationCount",
    "externalBusinessMutationCount",
    "taskCreatedCount",
    "budgetSettlementCount",
}
_KINDS = {
    "ACCEPT": ("daily_review", "improvement_observation", "memory_candidate"),
    "RETURN": ("content_return_target",),
}
TargetReceiptAuthorityReader = Callable[..., Mapping[str, Any]]


class EcommerceGrowthFeedbackError(RuntimeError):
    """Feedback persistence failed without exposing database details."""


class EcommerceGrowthFeedbackConflict(EcommerceGrowthFeedbackError):
    """A stable command, lease, checkpoint or target Receipt drifted."""


def _strict_exact_ref(value: Any, *, name: str) -> dict[str, Any]:
    if (
        type(value) is not dict
        or set(value) - {"resourceType", "resourceId", "revision", "contentHash", "receiptId"}
        or not {"resourceType", "resourceId", "revision", "contentHash"} <= set(value)
        or type(value["resourceType"]) is not str
        or not value["resourceType"].strip()
        or type(value["resourceId"]) is not str
        or not value["resourceId"].strip()
        or type(value["revision"]) is not int
        or value["revision"] <= 0
        or type(value["contentHash"]) is not str
        or not _SHA256.fullmatch(value["contentHash"])
        or ("receiptId" in value and (type(value["receiptId"]) is not str or not value["receiptId"].strip()))
    ):
        raise ValueError(f"{name} must be an exact reference")
    return deepcopy(value)


def _strict_plan(review_receipt: Mapping[str, Any], plan: Mapping[str, Any]) -> dict[str, Any]:
    if type(review_receipt) is not dict or type(plan) is not dict or set(plan) != _PLAN_FIELDS:
        raise ValueError("feedback requires strict review Receipt and plan mappings")
    receipt_ref = _strict_exact_ref(review_receipt.get("receiptRef"), name="review receipt")
    if receipt_ref != _strict_exact_ref(plan["reviewReceiptRef"], name="plan review receipt"):
        raise ValueError("feedback review Receipt lineage drifted")
    for name in ("artifactRef", "taskRef", "briefRef"):
        _strict_exact_ref(plan[name], name=name)
    if plan["decision"] not in _KINDS or type(plan["commandId"]) is not str or not plan["commandId"].strip():
        raise ValueError("feedback command identity or decision drifted")
    if type(plan["requestHash"]) is not str or not _SHA256.fullmatch(plan["requestHash"]):
        raise ValueError("feedback request hash drifted")
    effects = plan["sideEffects"]
    if (
        type(effects) is not dict
        or set(effects) != _ZERO_EFFECT_FIELDS
        or any(type(value) is not int or value != 0 for value in effects.values())
    ):
        raise ValueError("feedback external side-effect boundary drifted")
    segments = plan["segments"]
    if type(segments) is not list or tuple(item.get("kind") for item in segments) != _KINDS[plan["decision"]]:
        raise ValueError("feedback segment set or order drifted")
    for index, segment in enumerate(segments, start=1):
        if (
            type(segment) is not dict
            or set(segment) != {"sequence", "kind", "targetId", "businessTitle", "businessSummary", "targetPhase"}
            or segment["sequence"] != index
            or type(segment["targetId"]) is not str
            or not segment["targetId"].strip()
            or type(segment["businessTitle"]) is not str
            or not segment["businessTitle"].strip()
            or type(segment["businessSummary"]) is not str
            or not segment["businessSummary"].strip()
        ):
            raise ValueError("feedback segment shape drifted")
        if (segment["kind"] == "content_return_target") != (segment["targetPhase"] == "content_generation"):
            raise ValueError("feedback return target phase drifted")
    command_identity = {
        "reviewReceiptRef": plan["reviewReceiptRef"],
        "decision": plan["decision"],
    }
    encoded_identity = json.dumps(
        command_identity, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    expected_command_id = "feedback-" + hashlib.sha256(encoded_identity.encode("utf-8")).hexdigest()[:40]
    if plan["commandId"] != expected_command_id:
        raise ValueError("feedback canonical command identity drifted")
    canonical = {
        "decision": plan["decision"],
        "reviewReceiptRef": plan["reviewReceiptRef"],
        "artifactRef": plan["artifactRef"],
        "taskRef": plan["taskRef"],
        "briefRef": plan["briefRef"],
        "segments": plan["segments"],
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if plan["requestHash"] != "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest():
        raise ValueError("feedback canonical request hash drifted")
    return deepcopy(plan)


class BoundEcommerceGrowthFeedbackPort:
    """A feedback port bound to the caller's already locked host transaction."""

    def __init__(
        self,
        transaction: HostTransaction,
        scope: TenantScope,
        *,
        actor: str,
        checked_at: datetime,
        target_receipt_readers: Mapping[str, TargetReceiptAuthorityReader],
    ) -> None:
        if not isinstance(transaction, HostTransaction) or not scope.org_id.strip() or not scope.project_id.strip():
            raise ValueError("feedback port requires a locked transaction and tenant scope")
        if type(actor) is not str or not actor.strip() or checked_at.utcoffset() is None:
            raise ValueError("feedback actor and authoritative time are required")
        if (
            type(target_receipt_readers) is not dict
            or set(target_receipt_readers) != {kind for kinds in _KINDS.values() for kind in kinds}
            or any(not callable(reader) for reader in target_receipt_readers.values())
        ):
            raise ValueError("feedback requires one authoritative target Receipt reader per segment kind")
        self._transaction = transaction
        self._scope = scope
        self._actor = actor.strip()
        self._checked_at = checked_at
        self._target_receipt_readers = dict(target_receipt_readers)

    def enqueue(
        self,
        *,
        review_receipt: Mapping[str, Any],
        feedback_plan: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        plan = _strict_plan(review_receipt, feedback_plan)
        try:
            row = self._transaction.execute(
                """SELECT * FROM ecommerce_growth_feedback_enqueue_ar2_004(
                  %s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s)""",
                (
                    plan["commandId"],
                    plan["requestHash"],
                    plan["decision"],
                    json.dumps(plan["reviewReceiptRef"]),
                    json.dumps(plan["artifactRef"]),
                    json.dumps(plan["taskRef"]),
                    json.dumps(plan["briefRef"]),
                    json.dumps(plan["segments"], ensure_ascii=False),
                    self._actor,
                    self._checked_at,
                ),
            ).fetchone()
            if row is None:
                raise EcommerceGrowthFeedbackConflict("feedback enqueue returned no Receipt")
            return {
                "commandId": row["command_id"],
                "requestHash": row["request_hash"],
                "segmentCount": int(row["segment_count"]),
                "replayed": bool(row["replayed"]),
            }
        except (ValueError, EcommerceGrowthFeedbackError):
            raise
        except Exception as exc:
            raise EcommerceGrowthFeedbackConflict("feedback command could not be persisted") from exc

    def read(self, *, command_id: str) -> Mapping[str, Any] | None:
        """Read the complete immutable enqueue authority inside the host transaction."""

        if type(command_id) is not str or not command_id.strip():
            raise ValueError("feedback command identity is required")
        try:
            command = self._transaction.execute(
                """SELECT request_hash,decision,review_receipt_ref,artifact_ref,
                          task_ref,brief_ref
                     FROM public.ecommerce_growth_feedback_command
                    WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                (*self._scope.key, command_id.strip()),
            ).fetchone()
            if command is None:
                return None
            segments = self._transaction.execute(
                """SELECT sequence,payload,state,attempt,lease_token,lease_expires_at,
                          target_receipt_ref,reason_code
                     FROM public.ecommerce_growth_feedback_segment
                    WHERE org_id=%s AND project_id=%s AND command_id=%s
                    ORDER BY sequence""",
                (*self._scope.key, command_id.strip()),
            ).fetchall()
            checkpoint = self._transaction.execute(
                """SELECT completed_sequence,version
                     FROM public.ecommerce_growth_feedback_checkpoint
                    WHERE org_id=%s AND project_id=%s AND command_id=%s""",
                (*self._scope.key, command_id.strip()),
            ).fetchone()
            if checkpoint is None:
                raise EcommerceGrowthFeedbackConflict("feedback checkpoint authority is missing")
            return {
                "commandId": command_id.strip(),
                "requestHash": command["request_hash"],
                "decision": command["decision"],
                "reviewReceiptRef": deepcopy(command["review_receipt_ref"]),
                "artifactRef": deepcopy(command["artifact_ref"]),
                "taskRef": deepcopy(command["task_ref"]),
                "briefRef": deepcopy(command["brief_ref"]),
                "segments": [
                    {
                        "sequence": int(row["sequence"]),
                        "payload": deepcopy(row["payload"]),
                        "state": row["state"],
                        "attempt": int(row["attempt"]),
                        "leaseToken": None if row["lease_token"] is None else str(row["lease_token"]),
                        "leaseExpiresAt": None
                        if row["lease_expires_at"] is None
                        else row["lease_expires_at"].isoformat(),
                        "targetReceiptRef": deepcopy(row["target_receipt_ref"]),
                        "reasonCode": row["reason_code"],
                    }
                    for row in segments
                ],
                "checkpoint": {
                    "completedSequence": int(checkpoint["completed_sequence"]),
                    "version": int(checkpoint["version"]),
                },
            }
        except (ValueError, EcommerceGrowthFeedbackError):
            raise
        except Exception as exc:
            raise EcommerceGrowthFeedbackConflict("feedback command could not be read") from exc

    def claim(self, *, command_id: str, worker: str, lease_seconds: int = 60) -> Mapping[str, Any] | None:
        if not command_id.strip() or not worker.strip() or not 1 <= lease_seconds <= 300:
            raise ValueError("bounded feedback claim identity is required")
        try:
            row = self._transaction.execute(
                "SELECT * FROM ecommerce_growth_feedback_claim_ar2_004(%s,%s,%s)",
                (command_id, worker, lease_seconds),
            ).fetchone()
            if row is None:
                return None
            return {
                "sequence": int(row["sequence"]),
                "kind": row["kind"],
                "targetId": row["target_id"],
                "payload": deepcopy(row["payload"]),
                "attempt": int(row["attempt"]),
                "leaseToken": str(row["lease_token"]),
                "checkpointVersion": int(row["checkpoint_version"]),
            }
        except (ValueError, EcommerceGrowthFeedbackError):
            raise
        except Exception as exc:
            raise EcommerceGrowthFeedbackConflict("feedback segment could not be claimed") from exc

    def mark_unknown(self, *, command_id: str, claim: Mapping[str, Any], reason_code: str) -> None:
        lease = self._claim_identity(claim)
        if type(reason_code) is not str or not reason_code.strip():
            raise ValueError("unknown feedback requires a reason code")
        try:
            self._transaction.execute(
                "SELECT ecommerce_growth_feedback_unknown_ar2_004(%s,%s,%s,%s)",
                (command_id, lease["sequence"], lease["leaseToken"], reason_code.strip()),
            ).fetchone()
        except ValueError:
            raise
        except Exception as exc:
            raise EcommerceGrowthFeedbackConflict("feedback unknown state could not be persisted") from exc

    def claim_reconciliation(self, *, command_id: str) -> Mapping[str, Any] | None:
        """Reload the sole unknown segment after restart without executing or incrementing attempt."""

        if type(command_id) is not str or not command_id.strip():
            raise ValueError("feedback reconciliation command identity is required")
        try:
            row = self._transaction.execute(
                "SELECT * FROM ecommerce_growth_feedback_reconcile_claim_ar2_004(%s)",
                (command_id,),
            ).fetchone()
            if row is None:
                return None
            return {
                "sequence": int(row["sequence"]),
                "kind": row["kind"],
                "targetId": row["target_id"],
                "payload": deepcopy(row["payload"]),
                "attempt": int(row["attempt"]),
                "leaseToken": str(row["lease_token"]),
                "checkpointVersion": int(row["checkpoint_version"]),
            }
        except (ValueError, EcommerceGrowthFeedbackError):
            raise
        except Exception as exc:
            raise EcommerceGrowthFeedbackConflict("feedback reconciliation could not be loaded") from exc

    def acknowledge(
        self,
        *,
        command_id: str,
        claim: Mapping[str, Any],
        target_receipt_ref: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        lease = self._claim_identity(claim)
        target = _strict_exact_ref(dict(target_receipt_ref), name="target Receipt")
        persisted = _strict_exact_ref(
            dict(
                self._target_receipt_readers[lease["kind"]](
                    transaction=self._transaction,
                    scope=self._scope,
                    target_id=lease["targetId"],
                    expected_receipt=deepcopy(target),
                )
            ),
            name="persisted target Receipt",
        )
        if target != persisted:
            raise EcommerceGrowthFeedbackConflict("target Receipt authority readback drifted")
        try:
            row = self._transaction.execute(
                "SELECT * FROM ecommerce_growth_feedback_ack_ar2_004(%s,%s,%s,%s,%s::jsonb)",
                (
                    command_id,
                    lease["sequence"],
                    lease["leaseToken"],
                    lease["checkpointVersion"],
                    json.dumps(target),
                ),
            ).fetchone()
            if row is None:
                raise EcommerceGrowthFeedbackConflict("feedback acknowledgement returned no checkpoint")
            return {
                "completedSequence": int(row["completed_sequence"]),
                "checkpointVersion": int(row["checkpoint_version"]),
                "receiptRef": deepcopy(row["receipt_ref"]),
            }
        except (ValueError, EcommerceGrowthFeedbackError):
            raise
        except Exception as exc:
            raise EcommerceGrowthFeedbackConflict("feedback checkpoint could not advance") from exc

    def reconcile(
        self,
        *,
        command_id: str,
        claim: Mapping[str, Any],
        target_receipt_ref: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Unknown recovery only reads the deterministic target and then acknowledges it."""

        return self.acknowledge(
            command_id=command_id,
            claim=claim,
            target_receipt_ref=target_receipt_ref,
        )

    @staticmethod
    def _claim_identity(claim: Mapping[str, Any]) -> dict[str, Any]:
        if (
            type(claim) is not dict
            or type(claim.get("sequence")) is not int
            or claim["sequence"] < 1
            or type(claim.get("checkpointVersion")) is not int
            or claim["checkpointVersion"] < 1
            or claim.get("kind") not in {kind for kinds in _KINDS.values() for kind in kinds}
            or type(claim.get("targetId")) is not str
            or not claim["targetId"].strip()
        ):
            raise ValueError("feedback claim checkpoint identity drifted")
        try:
            token = UUID(str(claim.get("leaseToken")))
        except (TypeError, ValueError) as exc:
            raise ValueError("feedback claim lease identity drifted") from exc
        return {
            "sequence": claim["sequence"],
            "checkpointVersion": claim["checkpointVersion"],
            "leaseToken": token,
            "kind": claim["kind"],
            "targetId": claim["targetId"],
        }


__all__ = [
    "BoundEcommerceGrowthFeedbackPort",
    "EcommerceGrowthFeedbackConflict",
    "EcommerceGrowthFeedbackError",
]
