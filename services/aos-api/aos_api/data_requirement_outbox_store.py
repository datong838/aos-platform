"""Tenant-bound fenced delivery control for the DataRequirement Outbox."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Literal

import psycopg
from psycopg.types.json import Jsonb

from aos_api.business_investigation_shared_contracts import InvestigationExactRef
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
        return self._claim_next(
            scope, topic=topic, worker_id=worker_id, lease_token=lease_token,
            lease_seconds=lease_seconds, pending_only=False,
        )

    def claim_pending_next(
        self,
        scope: TenantScope,
        *,
        topic: str,
        worker_id: str,
        lease_token: str,
        lease_seconds: int,
    ) -> DataRequirementOutboxClaim | None:
        """Analysis-only claim: never recycle an expired, ambiguous attempt."""
        return self._claim_next(
            scope, topic=topic, worker_id=worker_id, lease_token=lease_token,
            lease_seconds=lease_seconds, pending_only=True,
        )

    def _claim_next(
        self,
        scope: TenantScope,
        *,
        topic: str,
        worker_id: str,
        lease_token: str,
        lease_seconds: int,
        pending_only: bool,
    ) -> DataRequirementOutboxClaim | None:
        self._required("topic", topic)
        self._required("worker id", worker_id)
        self._required("lease token", lease_token)
        if lease_seconds < 1 or lease_seconds > 3600:
            raise DataRequirementOutboxValidationError("lease seconds must be between 1 and 3600")
        try:
            with self._connect_factory(scope) as conn:
                function = (
                    "data_requirement_outbox_claim_pending_a0v_095"
                    if pending_only else "data_requirement_outbox_claim_biw2_004"
                )
                row = conn.execute(
                    "SELECT outbox_id,requirement_id,requirement_revision,event_id,topic,"
                    "payload,content_hash,attempt,lease_token,lease_expires_at "
                    f"FROM {function}(%s,%s,%s,%s)",
                    (topic, worker_id, lease_token, lease_seconds),
                ).fetchone()
                conn.commit()
        except psycopg.Error as exc:
            self._translate(exc)
            raise
        if row is None:
            return None
        return self._claim_from_row(row)

    def read_ambiguous_next(
        self, scope: TenantScope, *, topic: str
    ) -> DataRequirementOutboxClaim | None:
        """Read a frozen unknown or expired claim without acquiring a new attempt."""
        self._required("topic", topic)
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT o.outbox_id,o.requirement_id,o.requirement_revision,o.event_id,
                              o.topic,o.payload,o.content_hash,d.attempt,d.lease_token,
                              d.lease_expires_at
                         FROM public.data_requirement_outbox_delivery d
                         JOIN public.data_requirement_outbox o
                           USING(org_id,project_id,outbox_id)
                        WHERE d.org_id=%s AND d.project_id=%s AND o.topic=%s
                          AND (d.state='unknown' OR
                               (d.state='claimed' AND d.lease_expires_at<=NOW()))
                        ORDER BY o.created_at,o.outbox_id
                        LIMIT 1""",
                    (*scope.key, topic),
                ).fetchone()
        except psycopg.Error as exc:
            self._translate(exc)
            raise
        return None if row is None else self._claim_from_row(row)

    def read_unknown_next(
        self, scope: TenantScope, *, topic: str
    ) -> DataRequirementOutboxClaim | None:
        """Read one immutable unknown attempt for exact Receipt reconciliation."""
        self._required("topic", topic)
        try:
            with self._connect_factory(scope) as conn:
                row = conn.execute(
                    """SELECT o.outbox_id,o.requirement_id,o.requirement_revision,o.event_id,
                              o.topic,o.payload,o.content_hash,d.attempt,d.lease_token,
                              d.lease_expires_at
                         FROM public.data_requirement_outbox_delivery d
                         JOIN public.data_requirement_outbox o
                           USING(org_id,project_id,outbox_id)
                        WHERE d.org_id=%s AND d.project_id=%s AND d.state='unknown'
                          AND o.topic=%s
                        ORDER BY o.created_at,o.outbox_id
                        LIMIT 1""",
                    (*scope.key, topic),
                ).fetchone()
        except psycopg.Error as exc:
            self._translate(exc)
            raise
        return None if row is None else self._claim_from_row(row)

    @staticmethod
    def _claim_from_row(row: Any) -> DataRequirementOutboxClaim:
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

    def complete(
        self,
        scope: TenantScope,
        claim: DataRequirementOutboxClaim,
        fulfillment_ref: InvestigationExactRef,
        analysis_ref: InvestigationExactRef,
    ) -> DataRequirementOutboxTransition:
        return self._complete(
            scope, "complete", claim, fulfillment_ref, analysis_ref
        )

    def reconcile_completed(
        self,
        scope: TenantScope,
        claim: DataRequirementOutboxClaim,
        fulfillment_ref: InvestigationExactRef,
        analysis_ref: InvestigationExactRef,
    ) -> DataRequirementOutboxTransition:
        return self._complete(
            scope, "reconcile_completed", claim, fulfillment_ref, analysis_ref
        )

    def _complete(
        self,
        scope: TenantScope,
        operation: Literal["complete", "reconcile_completed"],
        claim: DataRequirementOutboxClaim,
        fulfillment_ref: InvestigationExactRef,
        analysis_ref: InvestigationExactRef,
    ) -> DataRequirementOutboxTransition:
        self._completion_claim(claim)
        self._completion_ref(fulfillment_ref, "DataFulfillmentReceipt")
        self._completion_ref(analysis_ref, "AnalysisRuntimeReceipt")
        return self._execute_transition(
            scope,
            f"SELECT state,replayed FROM data_requirement_outbox_{operation}_a0v_050(%s,%s,%s,%s,%s)",
            (
                claim.outbox_id,
                claim.attempt,
                claim.lease_token,
                Jsonb(fulfillment_ref.model_dump(mode="json", by_alias=True, exclude_none=True)),
                Jsonb(analysis_ref.model_dump(mode="json", by_alias=True, exclude_none=True)),
            ),
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
        self, scope: TenantScope, sql: str, params: tuple[Any, ...]
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

    @classmethod
    def _completion_claim(cls, claim: DataRequirementOutboxClaim) -> None:
        if type(claim) is not DataRequirementOutboxClaim:
            raise DataRequirementOutboxValidationError("completion requires an exact Outbox claim")
        for name, value in (
            ("outbox id", claim.outbox_id),
            ("requirement id", claim.requirement_id),
            ("event id", claim.event_id),
            ("lease token", claim.lease_token),
        ):
            cls._required(name, value)
        if claim.topic != "data.requirement.request":
            raise DataRequirementOutboxValidationError("completion claim topic is not supported")
        if (
            isinstance(claim.requirement_revision, bool)
            or not isinstance(claim.requirement_revision, int)
            or claim.requirement_revision < 1
            or isinstance(claim.attempt, bool)
            or not isinstance(claim.attempt, int)
            or claim.attempt < 1
            or re.fullmatch(r"sha256:[0-9a-f]{64}", claim.content_hash) is None
        ):
            raise DataRequirementOutboxValidationError("completion claim identity is invalid")

    @staticmethod
    def _completion_ref(ref: InvestigationExactRef, expected_type: str) -> None:
        if (
            type(ref) is not InvestigationExactRef
            or ref.resource_type != expected_type
            or ref.revision != 1
            or ref.receipt_id != ref.resource_id
        ):
            raise DataRequirementOutboxValidationError(
                f"completion requires an exact {expected_type} receipt reference"
            )

    @staticmethod
    def _translate(exc: psycopg.Error) -> None:
        if exc.sqlstate == "DO001":
            raise DataRequirementOutboxValidationError(str(exc)) from exc
        if exc.sqlstate in {"DO002", "DO003", "23505"}:
            raise DataRequirementOutboxConflict(str(exc)) from exc
