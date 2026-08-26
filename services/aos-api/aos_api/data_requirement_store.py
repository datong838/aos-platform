"""Tenant-bound BI-W2 DataRequirement request/transition Store.

The Store has no routing surface.  All state changes are delegated to the
single SECURITY DEFINER CAS function installed by ``biw2_002``; table UPDATE
privileges remain unavailable to the runtime role.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

import psycopg

from aos_api.business_investigation_shared_contracts import (
    DataRequirementStatus,
    InvestigationExactRef,
)
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord
from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class DataRequirementStoreError(RuntimeError):
    code = "DATA_REQUIREMENT_STORE_ERROR"


class DataRequirementConflict(DataRequirementStoreError):
    code = "DATA_REQUIREMENT_VERSION_CONFLICT"


class DataRequirementIdempotencyConflict(DataRequirementStoreError):
    code = "DATA_REQUIREMENT_IDEMPOTENCY_CONFLICT"


class DataRequirementInvalidTransition(DataRequirementStoreError):
    code = "DATA_REQUIREMENT_INVALID_TRANSITION"


class DataRequirementValidationError(DataRequirementStoreError):
    code = "DATA_REQUIREMENT_VALIDATION_ERROR"


@dataclass(frozen=True, slots=True)
class DataRequirementApplyResult:
    exact_ref: InvestigationExactRef
    version: int
    etag: str
    replayed: bool


def canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _revision_hash_payload(item: DataRequirementRevisionRecord) -> dict[str, Any]:
    payload = item.model_dump(mode="python", by_alias=True)
    payload.pop("contentHash", None)
    return payload


def canonical_revision_content_hash(item: DataRequirementRevisionRecord) -> str:
    """Return the exact hash of the normalized immutable revision payload."""
    return f"sha256:{canonical_hash(_revision_hash_payload(item))}"


class DataRequirementStore:
    _TARGETS = {
        "request": DataRequirementStatus.REQUESTED,
        "accept": DataRequirementStatus.ACCEPTED,
        "reject": DataRequirementStatus.REJECTED,
        "cancel": DataRequirementStatus.CANCELLED,
    }

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def request(
        self,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        item: DataRequirementRevisionRecord,
        *,
        expected_version: int,
    ) -> DataRequirementApplyResult:
        return self._apply(
            scope,
            actor,
            idempotency_key,
            item,
            operation="request",
            expected_version=expected_version,
        )

    def accept(
        self,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        item: DataRequirementRevisionRecord,
        *,
        expected_version: int,
    ) -> DataRequirementApplyResult:
        return self._apply(scope, actor, idempotency_key, item, operation="accept", expected_version=expected_version)

    def reject(
        self,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        item: DataRequirementRevisionRecord,
        *,
        expected_version: int,
    ) -> DataRequirementApplyResult:
        return self._apply(scope, actor, idempotency_key, item, operation="reject", expected_version=expected_version)

    def cancel(
        self,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        item: DataRequirementRevisionRecord,
        *,
        expected_version: int,
    ) -> DataRequirementApplyResult:
        return self._apply(scope, actor, idempotency_key, item, operation="cancel", expected_version=expected_version)

    def _apply(
        self,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        item: DataRequirementRevisionRecord,
        *,
        operation: str,
        expected_version: int,
    ) -> DataRequirementApplyResult:
        self._validate(scope, actor, idempotency_key, item, operation, expected_version)
        payload = item.model_dump(mode="json", by_alias=True)
        request_hash = canonical_hash(
            {
                "expectedVersion": expected_version,
                "operation": operation,
                "revision": payload,
            }
        )
        event_id = f"data-requirement-event-{uuid.uuid4().hex}"
        outbox_id = f"data-requirement-outbox-{uuid.uuid4().hex}"
        params = (
            item.requirement_id,
            expected_version,
            operation,
            idempotency_key,
            request_hash,
            item.revision,
            None if item.prior_ref is None else item.prior_ref.revision,
            item.content_hash.removeprefix("sha256:"),
            item.status.value,
            json.dumps(payload["caseRef"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(payload["runRef"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(payload["checkpointRef"], ensure_ascii=False, separators=(",", ":")),
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            actor,
            event_id,
            outbox_id,
        )
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT requirement_revision,result_content_hash,head_version,replayed
                       FROM data_requirement_apply_biw2_002(
                         %s,%s,%s,%s,%s,%s,%s,%s,%s,
                         %s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,%s
                       )""",
                    params,
                ).fetchone()
                if row is None:
                    raise DataRequirementStoreError("CAS function returned no result")
                conn.commit()
        except psycopg.Error as exc:
            self._translate_database_error(exc)
            raise
        revision = int(row["requirement_revision"])
        content_hash = f"sha256:{str(row['result_content_hash']).strip()}"
        exact_ref = InvestigationExactRef(
            resource_type="DataRequirementRevision",
            resource_id=item.requirement_id,
            revision=revision,
            content_hash=content_hash,
        )
        return DataRequirementApplyResult(
            exact_ref=exact_ref,
            version=int(row["head_version"]),
            etag=content_hash,
            replayed=bool(row["replayed"]),
        )

    @classmethod
    def _validate(
        cls,
        scope: TenantScope,
        actor: str,
        idempotency_key: str,
        item: DataRequirementRevisionRecord,
        operation: str,
        expected_version: int,
    ) -> None:
        if scope.key != (item.tenant.org_id, item.tenant.project_id):
            raise DataRequirementValidationError("tenant scope mismatch")
        if not actor or actor != item.created_by:
            raise DataRequirementValidationError("actor must match createdBy")
        if not idempotency_key.strip() or len(idempotency_key) > 200:
            raise DataRequirementValidationError("idempotency key must be non-empty and bounded")
        if expected_version < 0:
            raise DataRequirementValidationError("expected version must be non-negative")
        target = cls._TARGETS[operation]
        if item.status is not target:
            raise DataRequirementValidationError(f"{operation} requires {target.value} status")
        if operation == "request" and (
            expected_version != 0 or item.revision != 1 or item.prior_ref is not None
        ):
            raise DataRequirementValidationError("request requires requested revision 1 and expectedVersion 0")
        if operation != "request" and (
            expected_version < 1
            or item.revision != expected_version + 1
            or item.prior_ref is None
            or item.prior_ref.revision != expected_version
        ):
            raise DataRequirementValidationError("transition revision must follow expectedVersion")
        expected_hash = canonical_revision_content_hash(item)
        if item.content_hash != expected_hash:
            raise DataRequirementValidationError("content hash does not match canonical revision payload")

    @staticmethod
    def _translate_database_error(exc: psycopg.Error) -> None:
        if exc.sqlstate == "DR002":
            raise DataRequirementIdempotencyConflict("idempotency key was reused for a different request") from exc
        if exc.sqlstate == "DR003":
            raise DataRequirementInvalidTransition("DataRequirement transition is not allowed") from exc
        if exc.sqlstate in {"DR001", "23505"}:
            raise DataRequirementConflict("DataRequirement version conflict") from exc
        if exc.sqlstate == "DR004":
            raise DataRequirementValidationError("tenant scope is required") from exc
