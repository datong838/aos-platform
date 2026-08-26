"""Tenant-bound fenced delivery control for the DataRequirement Outbox."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

import psycopg

from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]
DeliveryState = Literal["acked", "failed", "unknown"]


class DataRequirementOutboxError(RuntimeError):
    code = "DATA_REQUIREMENT_OUTBOX_ERROR"


class DataRequirementOutboxConflict(DataRequirementOutboxError):
    code = "DATA_REQUIREMENT_OUTBOX_FENCE_CONFLICT"


class DataRequirementOutboxValidationError(DataRequirementOutboxError):
    code = "DATA_REQUIREMENT_OUTBOX_VALIDATION_ERROR"


@dataclass(frozen=True, slots=True)
class DataRequirementOutboxClaim:
    outbox_id: str
    requirement_id: str
    requirement_revision: int
    event_id: str
    topic: str
    payload: dict[str, Any]
    content_hash: str
    attempt: int
    lease_token: str
    lease_expires_at: datetime


@dataclass(frozen=True, slots=True)
class DataRequirementOutboxTransition:
    state: DeliveryState
    replayed: bool


class DataRequirementOutboxStore:
    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or db_connect

    def claim_next(
        self,
        scope: TenantScope,
        *,
        topic: str,
        worker_id: str,
        lease_token: str,
        lease_seconds: int,
    ) -> DataRequirementOutboxClaim | None:
        self._required("topic", topic)
        self._required("worker id", worker_id)
        self._required("lease token", lease_token)
        if lease_seconds < 1 or lease_seconds > 3600:
            raise DataRequirementOutboxValidationError("lease seconds must be between 1 and 3600")
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT outbox_id,requirement_id,requirement_revision,event_id,topic,
                              payload,content_hash,attempt,lease_token,lease_expires_at
                         FROM data_requirement_outbox_claim_biw2_004(%s,%s,%s,%s)""",
                    (topic, worker_id, lease_token, lease_seconds),
                ).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            self._translate(exc)
            raise
        if row is None:
            return None
        return DataRequirementOutboxClaim(
            outbox_id=str(row["outbox_id"]),
            requirement_id=str(row["requirement_id"]),
            requirement_revision=int(row["requirement_revision"]),
            event_id=str(row["event_id"]),
            topic=str(row["topic"]),
            payload=dict(row["payload"]),
            content_hash=f"sha256:{str(row['content_hash']).strip()}",
            attempt=int(row["attempt"]),
            lease_token=str(row["lease_token"]),
            lease_expires_at=row["lease_expires_at"],
        )

    def ack(self, scope: TenantScope, outbox_id: str, lease_token: str) -> DataRequirementOutboxTransition:
        return self._finish(scope, "ack", outbox_id, lease_token, reason_code="")

    def fail(
        self, scope: TenantScope, outbox_id: str, lease_token: str, *, reason_code: str
    ) -> DataRequirementOutboxTransition:
        self._required("reason code", reason_code)
        return self._finish(scope, "fail", outbox_id, lease_token, reason_code=reason_code)

    def mark_unknown(
        self, scope: TenantScope, outbox_id: str, lease_token: str, *, reason_code: str
    ) -> DataRequirementOutboxTransition:
        self._required("reason code", reason_code)
        return self._finish(scope, "unknown", outbox_id, lease_token, reason_code=reason_code)

    def reconcile_unknown(
        self, scope: TenantScope, outbox_id: str, receipt_id: str
    ) -> DataRequirementOutboxTransition:
        self._required("outbox id", outbox_id)
        self._required("receipt id", receipt_id)
        return self._execute_transition(
            scope,
            "SELECT state,replayed FROM data_requirement_outbox_reconcile_biw2_004(%s,%s)",
            (outbox_id, receipt_id),
        )

    def _finish(
        self,
        scope: TenantScope,
        operation: Literal["ack", "fail", "unknown"],
        outbox_id: str,
        lease_token: str,
        *,
        reason_code: str,
    ) -> DataRequirementOutboxTransition:
        self._required("outbox id", outbox_id)
        self._required("lease token", lease_token)
        return self._execute_transition(
            scope,
            f"SELECT state,replayed FROM data_requirement_outbox_{operation}_biw2_004(%s,%s,%s)",
            (outbox_id, lease_token, reason_code),
        )

    def _execute_transition(
        self, scope: TenantScope, sql: str, params: tuple[str, ...]
    ) -> DataRequirementOutboxTransition:
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(sql, params).fetchone()
                if row is None:
                    raise DataRequirementOutboxConflict("Outbox delivery command did not match current authority")
                conn.commit()
        except psycopg.Error as exc:
            self._translate(exc)
            raise
        return DataRequirementOutboxTransition(state=row["state"], replayed=bool(row["replayed"]))

    @staticmethod
    def _required(name: str, value: str) -> None:
        if not value.strip() or len(value) > 200:
            raise DataRequirementOutboxValidationError(f"{name} must be non-empty and bounded")

    @staticmethod
    def _translate(exc: psycopg.Error) -> None:
        if exc.sqlstate == "DO001":
            raise DataRequirementOutboxValidationError(str(exc)) from exc
        if exc.sqlstate in {"DO002", "DO003", "23505"}:
            raise DataRequirementOutboxConflict(str(exc)) from exc
