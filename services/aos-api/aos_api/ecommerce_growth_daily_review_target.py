"""First durable feedback target: a reviewed content item awaiting real effect data."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any, Mapping
from uuid import UUID

from aos_api.ecommerce_growth_feedback_port import (
    BoundEcommerceGrowthFeedbackPort,
    EcommerceGrowthFeedbackConflict,
    _strict_exact_ref,
)
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_connection import connect_serializable
from aos_api.tenant_scope import TenantScope


def _unwired_target(**_kwargs):
    raise EcommerceGrowthFeedbackConflict("feedback target is not wired")


class BoundDailyReviewTarget:
    """Host-transaction target with a database-enforced immutable Receipt."""

    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("daily review target requires a scoped host transaction")
        self._transaction = transaction
        self._scope = scope

    def put(
        self, *, command_id: str, command: Mapping[str, Any], claim: Mapping[str, Any],
        origin: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if (
            type(command_id) is not str or not command_id.strip()
            or command.get("decision") != "ACCEPT"
            or claim.get("kind") != "daily_review"
            or claim.get("sequence") != 1
            or type(claim.get("targetId")) is not str
            or not claim["targetId"].startswith("daily_review-")
            or type(claim.get("payload")) is not dict
            or claim["payload"].get("kind") != "daily_review"
            or claim["payload"].get("targetId") != claim["targetId"]
            or type(claim.get("checkpointVersion")) is not int
            or claim["checkpointVersion"] < 1
            or origin.get("reviewReceiptRef") != command.get("reviewReceiptRef")
        ):
            raise EcommerceGrowthFeedbackConflict("daily review target input drifted")
        try:
            lease_token = UUID(str(claim["leaseToken"]))
            refs = [
                _strict_exact_ref(command[key], name=key)
                for key in ("reviewReceiptRef", "artifactRef", "taskRef", "briefRef")
            ]
            row = self._transaction.execute(
                """SELECT * FROM public.ecommerce_growth_daily_review_put_a0v_100(
                     %s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb)""",
                (
                    command_id, claim["targetId"], lease_token, claim["checkpointVersion"],
                    json.dumps(claim["payload"], ensure_ascii=False),
                    *(json.dumps(ref, ensure_ascii=False) for ref in refs),
                ),
            ).fetchone()
            if row is None:
                raise EcommerceGrowthFeedbackConflict("daily review target returned no Receipt")
            return _strict_exact_ref(row["receipt_ref"], name="daily review Receipt")
        except (ValueError, EcommerceGrowthFeedbackConflict):
            raise
        except Exception as exc:
            raise EcommerceGrowthFeedbackConflict("daily review target write failed") from exc

    def read_receipt(
        self, *, target_id: str, expected_receipt: Mapping[str, Any], **_kwargs,
    ) -> Mapping[str, Any]:
        expected = _strict_exact_ref(dict(expected_receipt), name="daily review expected Receipt")
        if type(target_id) is not str or target_id != expected["resourceId"]:
            raise EcommerceGrowthFeedbackConflict("daily review target identity drifted")
        row = self._transaction.execute(
            """SELECT receipt_ref,body,
                      'sha256:'||encode(digest(convert_to(body::text,'UTF8'),'sha256'),'hex') AS computed_hash
                 FROM public.ecommerce_growth_daily_review_target
                WHERE org_id=%s AND project_id=%s AND target_id=%s""",
            (*self._scope.key, target_id),
        ).fetchone()
        if (
            row is None or type(row["body"]) is not dict
            or row["computed_hash"] != expected["contentHash"]
            or row["receipt_ref"] != expected
            or expected["resourceType"] != "DailyReviewReceipt"
        ):
            raise EcommerceGrowthFeedbackConflict("daily review Receipt readback drifted")
        return expected


class DailyReviewFeedbackWorker:
    """Process only the first accepted-feedback segment; no external effect."""

    def __init__(self, *, connect=connect_serializable) -> None:
        self._connect = connect

    def run_one(self, scope: TenantScope, command_id: str, *, worker: str = "ecommerce-daily-review") -> dict[str, Any]:
        if type(scope) is not TenantScope or type(command_id) is not str or not command_id.strip():
            raise ValueError("scoped daily review command is required")
        with self._connect(scope) as conn:
            transaction = HostTransaction(conn)
            target = BoundDailyReviewTarget(transaction, scope)
            readers = {
                "daily_review": target.read_receipt,
                "improvement_observation": _unwired_target,
                "memory_candidate": _unwired_target,
                "content_return_target": _unwired_target,
            }
            port = BoundEcommerceGrowthFeedbackPort(
                transaction, scope, actor=worker, checked_at=datetime.now(UTC),
                target_receipt_readers=readers,
            )
            command = port.read(command_id=command_id)
            if command is None:
                raise EcommerceGrowthFeedbackConflict("daily review feedback command is missing")
            if command["decision"] != "ACCEPT":
                return {"status": "NOT_APPLICABLE", "commandId": command_id}
            if len(command["segments"]) != 3 or command["segments"][0]["payload"].get("kind") != "daily_review":
                raise EcommerceGrowthFeedbackConflict("daily review segment sequence drifted")
            first = command["segments"][0]
            if command["checkpoint"]["completedSequence"] >= 1:
                receipt = target.read_receipt(
                    target_id=first["payload"]["targetId"],
                    expected_receipt=first["targetReceiptRef"],
                )
                return {"status": "ALREADY_ACKED", "commandId": command_id, "receiptRef": receipt}
            claim = port.claim_current(command_id=command_id, worker=worker)
            if claim is None:
                return {"status": "NOT_CLAIMED", "commandId": command_id}
            if claim["sequence"] != 1 or claim["kind"] != "daily_review":
                raise RuntimeError("unsupported feedback segment; transaction must roll back")
            origin = port.require_current_origin(command_id=command_id)
            receipt = target.put(command_id=command_id, command=command, claim=claim, origin=origin)
            target.read_receipt(target_id=claim["targetId"], expected_receipt=receipt)
            checkpoint = port.acknowledge(command_id=command_id, claim=claim, target_receipt_ref=receipt)
            readback = port.read(command_id=command_id)
            if (
                checkpoint["completedSequence"] != 1
                or readback is None
                or readback["checkpoint"]["completedSequence"] != 1
                or readback["segments"][0]["state"] != "acked"
                or readback["segments"][0]["targetReceiptRef"] != receipt
            ):
                raise EcommerceGrowthFeedbackConflict("daily review feedback checkpoint drifted")
            conn.commit()
            return {"status": "DAILY_REVIEW_ACKED", "commandId": command_id, "receiptRef": receipt}


__all__ = ["BoundDailyReviewTarget", "DailyReviewFeedbackWorker"]
