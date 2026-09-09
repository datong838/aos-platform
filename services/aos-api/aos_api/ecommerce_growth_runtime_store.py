"""Tenant-scoped invocation Receipt journal for ecommerce growth host adapters."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Mapping
from uuid import UUID

from aos_api.ecommerce_growth_host_ports import EcommerceGrowthDispatchSnapshot, HostTransaction
from aos_api.tenant_scope import TenantScope


_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_OPERATIONS = frozenset(
    {
        "ecommerce_growth_investigation_describe",
        "ecommerce_growth_case_put",
        "ecommerce_growth_schedule_put",
        "ecommerce_growth_schedule_trigger",
        "ecommerce_growth_data_fulfill",
        "ecommerce_growth_analysis_advance",
        "ecommerce_growth_review_advance",
        "ecommerce_growth_content_generate",
        "ecommerce_growth_content_review",
    }
)


class EcommerceGrowthRuntimeReceiptConflict(RuntimeError):
    """A replay or persisted Receipt no longer matches the exact invocation."""


def _strict_exact_ref(value: Any) -> dict[str, Any]:
    fields = {"resourceType", "resourceId", "revision", "contentHash", "receiptId"}
    required = fields - {"receiptId"}
    if (
        type(value) is not dict
        or set(value) - fields
        or not required <= set(value)
        or type(value["resourceType"]) is not str
        or not value["resourceType"].strip()
        or type(value["resourceId"]) is not str
        or not value["resourceId"].strip()
        or type(value["revision"]) is not int
        or value["revision"] < 1
        or type(value["contentHash"]) is not str
        or not _SHA256.fullmatch(value["contentHash"])
        or (
            "receiptId" in value
            and (type(value["receiptId"]) is not str or not value["receiptId"].strip())
        )
    ):
        raise ValueError("runtime target Receipt must be an exact reference")
    return deepcopy(value)


def _strict_response(value: Any, target_receipt_ref: Mapping[str, Any]) -> dict[str, Any]:
    if type(value) is not dict or not value:
        raise ValueError("runtime response must be a non-empty strict mapping")
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise ValueError("runtime response must be a strict JSON tree") from exc
    target_json = json.dumps(
        target_receipt_ref, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    )
    if not any(
        type(candidate) is dict
        and json.dumps(
            candidate, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
        )
        == target_json
        for candidate in decoded.values()
    ):
        raise ValueError("runtime response must contain its exact target Receipt")
    return decoded


@dataclass(frozen=True, slots=True)
class RuntimeReceiptRecord:
    response: dict[str, Any]
    replayed: bool


class BoundEcommerceGrowthRuntimeStore:
    """Persists the adapter response only after its domain Receipt is readable."""

    def __init__(self, transaction: HostTransaction, scope: TenantScope) -> None:
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("runtime Receipt store requires a locked host transaction and scope")
        self._transaction = transaction
        self._scope = scope

    def put(
        self,
        *,
        operation_id: str,
        idempotency_key: str,
        request_hash: str,
        dispatch: EcommerceGrowthDispatchSnapshot,
        response: Mapping[str, Any],
        target_receipt_ref: Mapping[str, Any],
        actor: str,
        occurred_at: datetime,
    ) -> RuntimeReceiptRecord:
        if operation_id not in _OPERATIONS or operation_id != dispatch.operation_id:
            raise ValueError("runtime Receipt operation drifted")
        if type(idempotency_key) is not str or not 1 <= len(idempotency_key.strip()) <= 200:
            raise ValueError("runtime Receipt idempotency key is required and bounded")
        if type(request_hash) is not str or not _SHA256.fullmatch(request_hash):
            raise ValueError("runtime Receipt request hash is invalid")
        if type(actor) is not str or not 1 <= len(actor.strip()) <= 240:
            raise ValueError("runtime Receipt actor is required and bounded")
        if not isinstance(occurred_at, datetime) or occurred_at.utcoffset() is None:
            raise ValueError("runtime Receipt time must include timezone")
        target = _strict_exact_ref(dict(target_receipt_ref))
        payload = _strict_response(dict(response), target)
        row = self._transaction.execute(
            """SELECT * FROM ecommerce_growth_runtime_receipt_put_ar2_005(
                 %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)""",
            (
                operation_id,
                idempotency_key.strip(),
                request_hash,
                dispatch.dispatch_revision,
                dispatch.installation_id,
                dispatch.generation,
                dispatch.execution_epoch,
                dispatch.cutover_group_id,
                dispatch.cutover_group_revision,
                dispatch.runtime_revision,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                json.dumps(target, ensure_ascii=False, sort_keys=True),
                actor.strip(),
                occurred_at,
            ),
        ).fetchone()
        if row is None or type(row.get("response")) is not dict or type(row.get("replayed")) is not bool:
            raise EcommerceGrowthRuntimeReceiptConflict("runtime Receipt persistence returned invalid data")
        persisted = deepcopy(row["response"])
        if persisted != payload:
            raise EcommerceGrowthRuntimeReceiptConflict("runtime Receipt persistence drifted")
        return RuntimeReceiptRecord(response=persisted, replayed=row["replayed"])

    def read(
        self,
        *,
        operation_id: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        if operation_id not in _OPERATIONS or not idempotency_key.strip():
            raise ValueError("runtime Receipt lookup identity is invalid")
        row = self._transaction.execute(
            """SELECT response FROM public.ecommerce_growth_runtime_command_receipt
                 WHERE org_id=%s AND project_id=%s AND operation_id=%s AND idempotency_key=%s""",
            (*self._scope.key, operation_id, idempotency_key.strip()),
        ).fetchone()
        if row is None:
            return None
        if type(row.get("response")) is not dict:
            raise EcommerceGrowthRuntimeReceiptConflict("persisted runtime Receipt shape drifted")
        return deepcopy(row["response"])

    def read_exact(
        self,
        *,
        operation_id: str,
        receipt_ref: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Read one immutable domain Receipt through its complete persisted exact ref."""

        if operation_id not in _OPERATIONS:
            raise ValueError("runtime Receipt lookup operation is invalid")
        target = _strict_exact_ref(dict(receipt_ref))
        rows = self._transaction.execute(
            """SELECT idempotency_key,request_hash,response,target_receipt_ref
                 FROM public.ecommerce_growth_runtime_command_receipt
                WHERE org_id=%s AND project_id=%s AND operation_id=%s
                  AND target_receipt_ref=%s::jsonb""",
            (
                *self._scope.key,
                operation_id,
                json.dumps(target, ensure_ascii=False, sort_keys=True),
            ),
        ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise EcommerceGrowthRuntimeReceiptConflict(
                "persisted runtime exact Receipt is not unique"
            )
        row = rows[0]
        if (
            type(row.get("idempotency_key")) is not str
            or not 1 <= len(row["idempotency_key"].strip()) <= 200
            or type(row.get("request_hash")) is not str
            or not _SHA256.fullmatch(row["request_hash"])
            or type(row.get("target_receipt_ref")) is not dict
        ):
            raise EcommerceGrowthRuntimeReceiptConflict(
                "persisted runtime exact Receipt authority drifted"
            )
        persisted_target = _strict_exact_ref(row["target_receipt_ref"])
        if json.dumps(persisted_target, sort_keys=True, separators=(",", ":")) != json.dumps(
            target, sort_keys=True, separators=(",", ":")
        ):
            raise EcommerceGrowthRuntimeReceiptConflict(
                "persisted runtime exact Receipt target drifted"
            )
        try:
            response = _strict_response(row.get("response"), target)
        except (TypeError, ValueError) as exc:
            raise EcommerceGrowthRuntimeReceiptConflict(
                "persisted runtime exact Receipt response drifted"
            ) from exc
        if "requestHash" in response and response["requestHash"] != row["request_hash"]:
            raise EcommerceGrowthRuntimeReceiptConflict(
                "persisted runtime exact Receipt request hash drifted"
            )
        return response


__all__ = [
    "BoundEcommerceGrowthRuntimeStore",
    "EcommerceGrowthRuntimeReceiptConflict",
    "RuntimeReceiptRecord",
]
