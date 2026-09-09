"""PostgreSQL authority for receipt-first capability budget reservations."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

from aos_api.aip_budget_reservation_contracts import (
    BudgetBucketAuthority,
    BudgetExactRef,
    BudgetReservationRevision,
    ReserveBudgetRequest,
    derive_bucket_authorities,
    exact_ref_payload,
    usage_cost_minor,
)
from aos_api.db import connect_serializable
from aos_api.tenant_scope import TenantScope


ConnectFactory = Callable[..., AbstractContextManager[Any]]


class BudgetReservationError(RuntimeError):
    code = "AIP_BUDGET_RESERVATION_ERROR"


class BudgetReservationConflict(BudgetReservationError):
    code = "AIP_BUDGET_RESERVATION_CONFLICT"


class BudgetReservationBlocked(BudgetReservationError):
    code = "AIP_BUDGET_RESERVATION_BLOCKED"


class BudgetReservationNotFound(BudgetReservationError):
    code = "AIP_BUDGET_RESERVATION_NOT_FOUND"


def canonical_hash(value: Any, *, prefixed: bool = False) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"sha256:{digest}" if prefixed else digest


def _stored_hash(value: str) -> str:
    return value.removeprefix("sha256:")


class AipBudgetReservationStore:
    """Keep all three bucket movements in one serializable tenant transaction."""

    def __init__(
        self,
        connect_factory: ConnectFactory | None = None,
        *,
        authority_schema: str = "public",
    ) -> None:
        if re.fullmatch(r"[a-z_][a-z0-9_]*", authority_schema) is None:
            raise ValueError("authority schema is invalid")
        self._connect_factory = connect_factory or connect_serializable
        self._authority_schema = authority_schema

    def reserve(
        self,
        scope: TenantScope,
        request: ReserveBudgetRequest,
        *,
        actor: str,
    ) -> BudgetReservationRevision:
        actor = self._identity(actor, "actor")
        request_hash = request.request_hash()
        with self._connect_factory(scope) as conn:
            self._lock_invocation(conn, scope, request.operation_id, request.invocation_key)
            existing = self._reservation_by_key(
                conn, scope, request.operation_id, request.invocation_key, lock=True
            )
            if existing is not None:
                if existing["request_hash"] != request_hash:
                    raise BudgetReservationConflict("invocation key payload drifted")
                return self._view(conn, scope, existing, replayed=True)

            checked_at = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            budget = self._budget_authority(conn, scope, request.policy_ref, checked_at)
            self._task_authority(conn, scope, request.task_ref)
            self._price_authority(conn, scope, request.pricing_ref, checked_at)
            self._approval_authority(
                conn,
                scope,
                request.approval_ref,
                checked_at,
                task_ref=request.task_ref,
                operation_id=request.operation_id,
                upper_bound_minor=request.upper_bound_minor,
            )
            buckets = derive_bucket_authorities(
                request,
                checked_at=checked_at,
                budget_effective_from=budget["effective_from"],
                budget_effective_until=budget["effective_until"],
                daily_limit_minor=int(budget["daily_limit_minor"]),
                pilot_limit_minor=int(budget["monthly_limit_minor"]),
            )
            self._prepare_and_lock_buckets(conn, scope, buckets)
            for bucket in sorted(
                buckets, key=lambda item: (item.kind, item.account_id, item.period_start)
            ):
                row = self._bucket_row(conn, scope, bucket)
                if (
                    row is None
                    or row["period_end"] != bucket.period_end
                    or int(row["limit_minor"]) != bucket.limit_minor
                ):
                    raise BudgetReservationConflict("budget bucket authority drifted")
                exposure = sum(
                    int(row[name])
                    for name in (
                        "held_minor",
                        "submitted_minor",
                        "settled_minor",
                        "unknown_minor",
                    )
                )
                if exposure + request.upper_bound_minor > bucket.limit_minor:
                    raise BudgetReservationBlocked(f"{bucket.kind} budget limit exceeded")

            invocation_id = uuid.uuid4()
            reservation_id = uuid.uuid4()
            immutable = {
                "operationId": request.operation_id,
                "invocationKey": request.invocation_key,
                "requestHash": request_hash,
                "taskRef": exact_ref_payload(request.task_ref),
                "policyRef": exact_ref_payload(request.policy_ref),
                "pricingRef": exact_ref_payload(request.pricing_ref),
                "approvalRef": exact_ref_payload(request.approval_ref),
                "currency": request.currency,
                "upperBoundMinor": request.upper_bound_minor,
            }
            invocation_payload = {
                "invocationId": str(invocation_id),
                **immutable,
                "state": "prepared",
                "revision": 1,
            }
            invocation_hash = canonical_hash(invocation_payload, prefixed=True)
            content_hash = canonical_hash(
                {**immutable, "state": "held", "revision": 1}, prefixed=True
            )
            conn.execute(
                """INSERT INTO aip_capability_invocation(
                org_id,project_id,invocation_id,operation_id,invocation_key,request_hash,
                task_ref,policy_ref,approval_ref,pricing_ref,currency,upper_bound_minor,state,
                revision,content_hash,created_at,updated_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,%s,%s,
                'prepared',1,%s,%s,%s)""",
                (
                    *scope.key,
                    invocation_id,
                    request.operation_id,
                    request.invocation_key,
                    request_hash,
                    self._json(request.task_ref),
                    self._json(request.policy_ref),
                    self._json(request.approval_ref),
                    self._json(request.pricing_ref),
                    request.currency,
                    request.upper_bound_minor,
                    invocation_hash,
                    checked_at,
                    checked_at,
                ),
            )
            conn.execute(
                """INSERT INTO aip_budget_reservation(
                org_id,project_id,reservation_id,invocation_id,operation_id,invocation_key,
                task_ref,policy_ref,pricing_ref,approval_ref,currency,upper_bound_minor,
                state,request_hash,revision,content_hash,created_at,updated_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,
                %s,%s,'held',%s,1,%s,%s,%s)""",
                (
                    *scope.key,
                    reservation_id,
                    invocation_id,
                    request.operation_id,
                    request.invocation_key,
                    self._json(request.task_ref),
                    self._json(request.policy_ref),
                    self._json(request.pricing_ref),
                    self._json(request.approval_ref),
                    request.currency,
                    request.upper_bound_minor,
                    request_hash,
                    content_hash,
                    checked_at,
                    checked_at,
                ),
            )
            for bucket in buckets:
                conn.execute(
                    """UPDATE aip_budget_bucket SET held_minor=held_minor+%s,
                    version=version+1,updated_at=clock_timestamp()
                    WHERE org_id=%s AND project_id=%s AND bucket_kind=%s
                    AND account_id=%s AND period_start=%s AND currency=%s""",
                    (
                        request.upper_bound_minor,
                        *scope.key,
                        bucket.kind,
                        bucket.account_id,
                        bucket.period_start,
                        request.currency,
                    ),
                )
                conn.execute(
                    """INSERT INTO aip_budget_reservation_bucket(
                    org_id,project_id,reservation_id,bucket_kind,account_id,period_start,
                    currency,reserved_minor) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        *scope.key,
                        reservation_id,
                        bucket.kind,
                        bucket.account_id,
                        bucket.period_start,
                        request.currency,
                        request.upper_bound_minor,
                    ),
                )
            self._event(
                conn,
                scope,
                reservation_id,
                sequence=1,
                from_state=None,
                to_state="held",
                actor=actor,
                evidence_ref=request.approval_ref,
                occurred_at=checked_at,
            )
            row = self._reservation_by_id(conn, scope, reservation_id, lock=False)
            return self._view(conn, scope, row, replayed=False)

    def get(self, scope: TenantScope, reservation_id: str) -> BudgetReservationRevision:
        with self._connect_factory(scope) as conn:
            row = self._reservation_by_id(conn, scope, reservation_id, lock=False)
            return self._view(conn, scope, row, replayed=False)

    def submit(
        self,
        scope: TenantScope,
        reservation_id: str,
        *,
        provider_ref: BudgetExactRef,
        provider_idempotency_hash: str,
        actor: str,
    ) -> BudgetReservationRevision:
        if provider_ref.resource_type != "ProviderInstanceRevision":
            raise ValueError("provider_ref must reference ProviderInstanceRevision")
        self._digest(provider_idempotency_hash, "provider idempotency hash")
        actor = self._identity(actor, "actor")
        with self._connect_factory(scope) as conn:
            row = self._reservation_by_id(conn, scope, reservation_id, lock=True)
            stored = conn.execute(
                """SELECT provider_ref,provider_idempotency_hash
                FROM aip_capability_provider_request_receipt
                WHERE org_id=%s AND project_id=%s AND invocation_id=%s""",
                (*scope.key, row["invocation_id"]),
            ).fetchone()
            if stored is not None:
                if (
                    self._load(stored["provider_ref"]) != exact_ref_payload(provider_ref)
                    or stored["provider_idempotency_hash"] != provider_idempotency_hash
                ):
                    raise BudgetReservationConflict("Provider submission replay drifted")
                return self._view(conn, scope, row, replayed=True)
            if row["state"] != "held":
                raise BudgetReservationConflict("only HELD reservation may be submitted")
            self._provider_authority(conn, scope, provider_ref)
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            request_receipt_id = uuid.uuid4()
            receipt_payload = {
                "invocationId": str(row["invocation_id"]),
                "requestHash": row["request_hash"],
                "providerRef": exact_ref_payload(provider_ref),
                "providerIdempotencyHash": provider_idempotency_hash,
            }
            request_ref = BudgetExactRef(
                resourceType="CapabilityProviderRequestReceipt",
                resourceId=str(request_receipt_id),
                revision=1,
                contentHash=canonical_hash(receipt_payload, prefixed=True),
            )
            conn.execute(
                """INSERT INTO aip_capability_provider_request_receipt(
                org_id,project_id,request_receipt_id,invocation_id,request_hash,
                provider_ref,provider_idempotency_hash,revision,content_hash,submitted_at)
                VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,1,%s,%s)""",
                (
                    *scope.key,
                    request_receipt_id,
                    row["invocation_id"],
                    row["request_hash"],
                    self._json(provider_ref),
                    provider_idempotency_hash,
                    request_ref.content_hash,
                    now,
                ),
            )
            self._move_buckets(
                conn, scope, row["reservation_id"], from_column="held_minor",
                to_column="submitted_minor", settled_minor=None, now=now
            )
            self._transition_reservation(
                conn,
                scope,
                row,
                state="submitted",
                now=now,
                actor=actor,
                evidence_ref=request_ref,
                provider_request_ref=request_ref,
            )
            self._update_invocation_state(conn, scope, row["invocation_id"], "submitted", now)
            updated = self._reservation_by_id(conn, scope, row["reservation_id"], lock=False)
            return self._view(conn, scope, updated, replayed=False)

    def mark_unknown(
        self,
        scope: TenantScope,
        reservation_id: str,
        *,
        actor: str,
    ) -> BudgetReservationRevision:
        actor = self._identity(actor, "actor")
        with self._connect_factory(scope) as conn:
            row = self._reservation_by_id(conn, scope, reservation_id, lock=True)
            if row["state"] == "unknown":
                return self._view(conn, scope, row, replayed=True)
            if row["state"] != "submitted":
                raise BudgetReservationConflict("only SUBMITTED reservation may become UNKNOWN")
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            self._move_buckets(
                conn, scope, row["reservation_id"], from_column="submitted_minor",
                to_column="unknown_minor", settled_minor=None, now=now
            )
            request_ref = BudgetExactRef.model_validate(self._load(row["provider_request_receipt_ref"]))
            self._transition_reservation(
                conn, scope, row, state="unknown", now=now, actor=actor,
                evidence_ref=request_ref
            )
            self._update_invocation_state(conn, scope, row["invocation_id"], "unknown", now)
            updated = self._reservation_by_id(conn, scope, row["reservation_id"], lock=False)
            return self._view(conn, scope, updated, replayed=False)

    def release_no_effect(
        self,
        scope: TenantScope,
        reservation_id: str,
        *,
        actor: str,
        provider_result_hash: str | None = None,
        evidence_refs: tuple[BudgetExactRef, ...] = (),
    ) -> BudgetReservationRevision:
        actor = self._identity(actor, "actor")
        with self._connect_factory(scope) as conn:
            row = self._reservation_by_id(conn, scope, reservation_id, lock=True)
            if row["state"] == "released":
                self._assert_provider_receipt_replay(
                    conn,
                    scope,
                    row,
                    outcome="failed_no_effect",
                    provider_result_hash=provider_result_hash,
                    evidence_refs=evidence_refs,
                )
                return self._view(conn, scope, row, replayed=True)
            if row["state"] not in {"held", "submitted", "unknown"}:
                raise BudgetReservationConflict("terminal reservation cannot be released")
            if row["state"] == "held" and (provider_result_hash or evidence_refs):
                raise BudgetReservationConflict("HELD release must prove no Provider submission")
            if row["state"] != "held" and not provider_result_hash:
                raise BudgetReservationBlocked("submitted reservation requires reconciliation receipt")
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            evidence_ref = None
            if row["state"] != "held":
                evidence_ref = self._record_provider_receipt(
                    conn,
                    scope,
                    row,
                    outcome="failed_no_effect",
                    provider_result_hash=self._digest(provider_result_hash or "", "provider result hash"),
                    evidence_refs=evidence_refs,
                    observed_at=now,
                )
            source_column = {
                "held": "held_minor",
                "submitted": "submitted_minor",
                "unknown": "unknown_minor",
            }[row["state"]]
            self._move_buckets(
                conn, scope, row["reservation_id"], from_column=source_column,
                to_column=None, settled_minor=0, now=now
            )
            self._transition_reservation(
                conn, scope, row, state="released", now=now, actor=actor,
                evidence_ref=evidence_ref,
                reconciliation_ref=evidence_ref,
            )
            self._update_invocation_state(conn, scope, row["invocation_id"], "failed", now)
            updated = self._reservation_by_id(conn, scope, row["reservation_id"], lock=False)
            return self._view(conn, scope, updated, replayed=False)

    def settle(
        self,
        scope: TenantScope,
        reservation_id: str,
        *,
        actual_minor: int,
        provider_result_hash: str,
        usage_receipt_refs: tuple[BudgetExactRef, ...],
        evidence_refs: tuple[BudgetExactRef, ...],
        actor: str,
    ) -> BudgetReservationRevision:
        if type(actual_minor) is not int or actual_minor < 0:
            raise ValueError("actual_minor must be a non-negative CNY fen integer")
        usage_identities = {
            (item.resource_type, item.resource_id, item.revision, item.content_hash)
            for item in usage_receipt_refs
        }
        if not usage_receipt_refs or len(usage_receipt_refs) != len(usage_identities):
            raise ValueError("unique UsageReceipt refs are required")
        actor = self._identity(actor, "actor")
        provider_result_hash = self._digest(provider_result_hash, "provider result hash")
        with self._connect_factory(scope) as conn:
            row = self._reservation_by_id(conn, scope, reservation_id, lock=True)
            if row["state"] == "settled":
                if (
                    int(row["actual_minor"]) != actual_minor
                    or self._load(row["usage_receipt_refs"])
                    != [exact_ref_payload(item) for item in usage_receipt_refs]
                ):
                    raise BudgetReservationConflict("settled replay drifted")
                self._assert_provider_receipt_replay(
                    conn,
                    scope,
                    row,
                    outcome="completed",
                    provider_result_hash=provider_result_hash,
                    evidence_refs=evidence_refs,
                )
                return self._view(conn, scope, row, replayed=True)
            if row["state"] not in {"submitted", "unknown"}:
                raise BudgetReservationConflict("only SUBMITTED or UNKNOWN may settle")
            if actual_minor > int(row["upper_bound_minor"]):
                raise BudgetReservationBlocked("actual amount exceeds held amount")
            now = conn.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
            for ref in usage_receipt_refs:
                self._usage_authority(
                    conn,
                    scope,
                    ref,
                    reservation=row,
                    provider_result_hash=provider_result_hash,
                )
            calculated_actual = self._actual_from_usage(
                conn, scope, row, usage_receipt_refs
            )
            if calculated_actual != actual_minor:
                raise BudgetReservationConflict("actual amount differs from exact usage and price")
            provider_ref = self._record_provider_receipt(
                conn,
                scope,
                row,
                outcome="completed",
                provider_result_hash=provider_result_hash,
                evidence_refs=evidence_refs,
                observed_at=now,
            )
            for ref in usage_receipt_refs:
                conn.execute(
                    """INSERT INTO aip_budget_usage_settlement(
                    org_id,project_id,usage_receipt_id,reservation_id,usage_receipt_ref,
                    actual_minor,created_at) VALUES(%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                    (
                        *scope.key,
                        ref.resource_id,
                        row["reservation_id"],
                        self._json(ref),
                        actual_minor,
                        now,
                    ),
                )
            source_column = "submitted_minor" if row["state"] == "submitted" else "unknown_minor"
            self._move_buckets(
                conn, scope, row["reservation_id"], from_column=source_column,
                to_column="settled_minor", settled_minor=actual_minor, now=now
            )
            self._transition_reservation(
                conn,
                scope,
                row,
                state="settled",
                now=now,
                actor=actor,
                evidence_ref=provider_ref,
                provider_receipt_ref=provider_ref,
                usage_receipt_refs=usage_receipt_refs,
                actual_minor=actual_minor,
                reconciliation_ref=provider_ref if row["state"] == "unknown" else None,
            )
            self._update_invocation_state(conn, scope, row["invocation_id"], "completed", now)
            updated = self._reservation_by_id(conn, scope, row["reservation_id"], lock=False)
            return self._view(conn, scope, updated, replayed=False)

    def _prepare_and_lock_buckets(
        self,
        conn: Any,
        scope: TenantScope,
        buckets: tuple[BudgetBucketAuthority, ...],
    ) -> None:
        for bucket in sorted(
            buckets, key=lambda item: (item.kind, item.account_id, item.period_start)
        ):
            conn.execute(
                """INSERT INTO aip_budget_bucket(
                org_id,project_id,bucket_kind,account_id,period_start,period_end,
                currency,limit_minor) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(org_id,project_id,bucket_kind,account_id,period_start,currency)
                DO NOTHING""",
                (
                    *scope.key,
                    bucket.kind,
                    bucket.account_id,
                    bucket.period_start,
                    bucket.period_end,
                    bucket.currency,
                    bucket.limit_minor,
                ),
            )
            self._bucket_row(conn, scope, bucket, lock=True)

    def _move_buckets(
        self,
        conn: Any,
        scope: TenantScope,
        reservation_id: uuid.UUID,
        *,
        from_column: str,
        to_column: str | None,
        settled_minor: int | None,
        now: datetime,
    ) -> None:
        allowed = {"held_minor", "submitted_minor", "settled_minor", "unknown_minor"}
        if from_column not in allowed or (to_column is not None and to_column not in allowed):
            raise ValueError("unsupported budget bucket movement")
        links = conn.execute(
            """SELECT bucket_kind,account_id,period_start,currency,reserved_minor
            FROM aip_budget_reservation_bucket
            WHERE org_id=%s AND project_id=%s AND reservation_id=%s
            ORDER BY bucket_kind,account_id,period_start""",
            (*scope.key, reservation_id),
        ).fetchall()
        for link in links:
            current = int(link["reserved_minor"])
            addition = current if settled_minor is None else settled_minor
            target_sql = "" if to_column is None else f", {to_column}={to_column}+%s"
            params: list[Any] = [current]
            if to_column is not None:
                params.append(addition)
            params.extend(
                [
                    *scope.key,
                    link["bucket_kind"],
                    link["account_id"],
                    link["period_start"],
                    link["currency"],
                    current,
                ]
            )
            cursor = conn.execute(
                f"""UPDATE aip_budget_bucket SET {from_column}={from_column}-%s
                {target_sql}, version=version+1,updated_at=clock_timestamp()
                WHERE org_id=%s AND project_id=%s AND bucket_kind=%s
                AND account_id=%s AND period_start=%s AND currency=%s
                AND {from_column}>=%s""",
                tuple(params),
            )
            if cursor.rowcount != 1:
                raise BudgetReservationConflict("budget bucket movement drifted")

    def _transition_reservation(
        self,
        conn: Any,
        scope: TenantScope,
        row: Any,
        *,
        state: str,
        now: datetime,
        actor: str,
        evidence_ref: BudgetExactRef | None,
        provider_request_ref: BudgetExactRef | None = None,
        provider_receipt_ref: BudgetExactRef | None = None,
        usage_receipt_refs: tuple[BudgetExactRef, ...] | None = None,
        actual_minor: int | None = None,
        reconciliation_ref: BudgetExactRef | None = None,
    ) -> None:
        revision = int(row["revision"]) + 1
        immutable = {
            "reservationId": str(row["reservation_id"]),
            "operationId": row["operation_id"],
            "invocationKey": row["invocation_key"],
            "requestHash": row["request_hash"],
            "state": state,
            "revision": revision,
            "actualMinor": actual_minor,
            "providerRequestReceiptRef": exact_ref_payload(provider_request_ref)
            if provider_request_ref is not None
            else self._load(row["provider_request_receipt_ref"]),
            "providerReceiptRef": exact_ref_payload(provider_receipt_ref),
            "usageReceiptRefs": [exact_ref_payload(item) for item in (usage_receipt_refs or ())],
            "reconciliationEvidenceRef": exact_ref_payload(reconciliation_ref),
        }
        cursor = conn.execute(
            """UPDATE aip_budget_reservation SET state=%s,actual_minor=%s,
            provider_request_receipt_ref=COALESCE(%s::jsonb,provider_request_receipt_ref),
            provider_receipt_ref=%s::jsonb,usage_receipt_refs=%s::jsonb,
            reconciliation_evidence_ref=%s::jsonb,revision=%s,content_hash=%s,updated_at=%s
            WHERE org_id=%s AND project_id=%s AND reservation_id=%s AND revision=%s""",
            (
                state,
                actual_minor,
                None if provider_request_ref is None else self._json(provider_request_ref),
                None if provider_receipt_ref is None else self._json(provider_receipt_ref),
                self._json([exact_ref_payload(item) for item in (usage_receipt_refs or ())]),
                None if reconciliation_ref is None else self._json(reconciliation_ref),
                revision,
                canonical_hash(immutable, prefixed=True),
                now,
                *scope.key,
                row["reservation_id"],
                row["revision"],
            ),
        )
        if cursor.rowcount != 1:
            raise BudgetReservationConflict("budget reservation revision drifted")
        self._event(
            conn,
            scope,
            row["reservation_id"],
            sequence=revision,
            from_state=row["state"],
            to_state=state,
            actor=actor,
            evidence_ref=evidence_ref,
            occurred_at=now,
        )

    def _record_provider_receipt(
        self,
        conn: Any,
        scope: TenantScope,
        row: Any,
        *,
        outcome: str,
        provider_result_hash: str,
        evidence_refs: tuple[BudgetExactRef, ...],
        observed_at: datetime,
    ) -> BudgetExactRef:
        request_payload = self._load(row["provider_request_receipt_ref"])
        if request_payload is None:
            raise BudgetReservationBlocked("Provider request receipt is required")
        request_ref = BudgetExactRef.model_validate(request_payload)
        receipt_id = uuid.uuid4()
        payload = {
            "invocationId": str(row["invocation_id"]),
            "requestReceiptRef": request_payload,
            "outcome": outcome,
            "providerResultHash": provider_result_hash,
            "evidenceRefs": [exact_ref_payload(item) for item in evidence_refs],
        }
        result_ref = BudgetExactRef(
            resourceType="CapabilityProviderReceipt",
            resourceId=str(receipt_id),
            revision=1,
            contentHash=canonical_hash(payload, prefixed=True),
        )
        conn.execute(
            """INSERT INTO aip_capability_provider_receipt(
            org_id,project_id,provider_receipt_id,invocation_id,request_receipt_id,
            outcome,provider_result_hash,evidence_refs,revision,content_hash,observed_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,1,%s,%s)""",
            (
                *scope.key,
                receipt_id,
                row["invocation_id"],
                request_ref.resource_id,
                outcome,
                provider_result_hash,
                self._json([exact_ref_payload(item) for item in evidence_refs]),
                result_ref.content_hash,
                observed_at,
            ),
        )
        return result_ref

    def _assert_provider_receipt_replay(
        self,
        conn: Any,
        scope: TenantScope,
        reservation: Any,
        *,
        outcome: str,
        provider_result_hash: str | None,
        evidence_refs: tuple[BudgetExactRef, ...],
    ) -> None:
        stored_ref_payload = self._load(
            reservation["provider_receipt_ref"]
            or reservation["reconciliation_evidence_ref"]
        )
        if stored_ref_payload is None:
            if provider_result_hash is not None or evidence_refs:
                raise BudgetReservationConflict("released replay added Provider evidence")
            return
        if provider_result_hash is None:
            raise BudgetReservationConflict("terminal replay omitted Provider evidence")
        normalized_hash = self._digest(provider_result_hash, "provider result hash")
        stored_ref = BudgetExactRef.model_validate(stored_ref_payload)
        stored = conn.execute(
            """SELECT invocation_id,request_receipt_id,outcome,provider_result_hash,
            evidence_refs,revision,content_hash FROM aip_capability_provider_receipt
            WHERE org_id=%s AND project_id=%s AND provider_receipt_id=%s""",
            (*scope.key, stored_ref.resource_id),
        ).fetchone()
        if stored is None:
            raise BudgetReservationConflict("terminal Provider receipt authority missing")
        expected_payload = {
            "invocationId": str(reservation["invocation_id"]),
            "requestReceiptRef": self._load(reservation["provider_request_receipt_ref"]),
            "outcome": outcome,
            "providerResultHash": normalized_hash,
            "evidenceRefs": [exact_ref_payload(item) for item in evidence_refs],
        }
        if (
            stored["outcome"] != outcome
            or stored["provider_result_hash"] != normalized_hash
            or self._load(stored["evidence_refs"]) != expected_payload["evidenceRefs"]
            or stored_ref.content_hash != canonical_hash(expected_payload, prefixed=True)
            or stored["content_hash"] != stored_ref.content_hash
        ):
            raise BudgetReservationConflict("terminal Provider receipt replay drifted")

    def _provider_authority(
        self, conn: Any, scope: TenantScope, ref: BudgetExactRef
    ) -> None:
        row = conn.execute(
            """SELECT content_hash,lifecycle FROM aip_provider_instance_revision
            WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s AND revision=%s""",
            (*scope.key, ref.resource_id, ref.revision),
        ).fetchone()
        if (
            row is None
            or row["lifecycle"] != "active"
            or row["content_hash"] != _stored_hash(ref.content_hash)
        ):
            raise BudgetReservationBlocked("active exact ProviderInstanceRevision required")

    @classmethod
    def _update_invocation_state(
        cls,
        conn: Any,
        scope: TenantScope,
        invocation_id: uuid.UUID,
        state: str,
        now: datetime,
    ) -> None:
        row = conn.execute(
            """SELECT * FROM aip_capability_invocation
            WHERE org_id=%s AND project_id=%s AND invocation_id=%s FOR UPDATE""",
            (*scope.key, invocation_id),
        ).fetchone()
        if row is None:
            raise BudgetReservationConflict("capability invocation authority missing")
        revision = int(row["revision"]) + 1
        content_hash = canonical_hash(cls._invocation_payload(row, state, revision), prefixed=True)
        conn.execute(
            """UPDATE aip_capability_invocation SET state=%s,revision=%s,
            content_hash=%s,updated_at=%s WHERE org_id=%s AND project_id=%s
            AND invocation_id=%s""",
            (state, revision, content_hash, now, *scope.key, invocation_id),
        )

    @staticmethod
    def _invocation_payload(row: Any, state: str, revision: int) -> dict[str, Any]:
        return {
            "invocationId": str(row["invocation_id"]),
            "operationId": row["operation_id"],
            "invocationKey": row["invocation_key"],
            "requestHash": row["request_hash"],
            "taskRef": AipBudgetReservationStore._load(row["task_ref"]),
            "policyRef": AipBudgetReservationStore._load(row["policy_ref"]),
            "pricingRef": AipBudgetReservationStore._load(row["pricing_ref"]),
            "approvalRef": AipBudgetReservationStore._load(row["approval_ref"]),
            "currency": row["currency"],
            "upperBoundMinor": int(row["upper_bound_minor"]),
            "state": state,
            "revision": revision,
        }

    def _usage_authority(
        self,
        conn: Any,
        scope: TenantScope,
        ref: BudgetExactRef,
        *,
        reservation: Any,
        provider_result_hash: str,
    ) -> None:
        if ref.resource_type != "UsageReceipt":
            raise ValueError("usage receipt ref must reference UsageReceipt")
        row = conn.execute(
            """SELECT receipt_id,provider,provider_receipt_id,lineage_id,usage_kind,
            quantity,unit,currency,quality,source_hash,observed_at
            FROM aip_usage_receipt WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
            (*scope.key, ref.resource_id),
        ).fetchone()
        if row is None or ref.revision != 1:
            raise BudgetReservationBlocked("exact UsageReceipt required")
        if canonical_hash(dict(row), prefixed=True) != ref.content_hash:
            raise BudgetReservationConflict("UsageReceipt exact hash drifted")
        request_receipt = conn.execute(
            """SELECT provider_ref FROM aip_capability_provider_request_receipt
            WHERE org_id=%s AND project_id=%s AND invocation_id=%s""",
            (*scope.key, reservation["invocation_id"]),
        ).fetchone()
        provider_payload = self._load(request_receipt["provider_ref"]) if request_receipt else None
        quantity = row["quantity"]
        if (
            provider_payload is None
            or row["provider"] != provider_payload.get("resourceId")
            or row["lineage_id"] != str(reservation["invocation_id"])
            or row["source_hash"] != provider_result_hash
            or row["quality"] != "measured"
            or row["usage_kind"] not in {"input_token", "output_token", "cached_token"}
            or row["unit"] != "token"
            or row["currency"] is not None
            or not isinstance(quantity, (int, float))
            or isinstance(quantity, bool)
            or not float(quantity).is_integer()
            or not 0 <= float(quantity) <= 9_007_199_254_740_991
        ):
            raise BudgetReservationBlocked(
                "UsageReceipt must be measured integer tokens bound to this invocation and Provider result"
            )

    def _actual_from_usage(
        self,
        conn: Any,
        scope: TenantScope,
        reservation: Any,
        refs: tuple[BudgetExactRef, ...],
    ) -> int:
        price_ref = BudgetExactRef.model_validate(self._load(reservation["pricing_ref"]))
        price_row = conn.execute(
            """SELECT payload FROM aip_model_price_snapshot_revision
            WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s AND revision=%s""",
            (*scope.key, price_ref.resource_id, price_ref.revision),
        ).fetchone()
        if price_row is None:
            raise BudgetReservationBlocked("exact price snapshot missing at settlement")
        price = self._load(price_row["payload"])
        token_unit = int(price.get("tokenUnit", 1000))
        price_fields = {
            "input_token": "inputTokenPrice",
            "output_token": "outputTokenPrice",
            "cached_token": "cachedTokenPrice",
        }
        total = 0
        for ref in refs:
            usage = conn.execute(
                """SELECT usage_kind,quantity,currency,quality,unit FROM aip_usage_receipt
                WHERE org_id=%s AND project_id=%s AND receipt_id=%s""",
                (*scope.key, ref.resource_id),
            ).fetchone()
            if usage is None or usage["quantity"] is None:
                raise BudgetReservationBlocked("measured UsageReceipt required")
            price_field = price_fields.get(usage["usage_kind"])
            unit_price = price.get(price_field) if price_field else None
            if unit_price is None:
                raise BudgetReservationBlocked("UsageReceipt kind lacks exact price authority")
            total += usage_cost_minor(
                quantity=int(usage["quantity"]),
                unit_price_cny=str(unit_price),
                price_unit=token_unit,
            )
        return total

    @staticmethod
    def _bucket_row(
        conn: Any,
        scope: TenantScope,
        bucket: BudgetBucketAuthority,
        *,
        lock: bool = False,
    ) -> Any:
        return conn.execute(
            """SELECT * FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s
            AND bucket_kind=%s AND account_id=%s AND period_start=%s AND currency=%s"""
            + (" FOR UPDATE" if lock else ""),
            (*scope.key, bucket.kind, bucket.account_id, bucket.period_start, bucket.currency),
        ).fetchone()

    def _budget_authority(
        self, conn: Any, scope: TenantScope, ref: BudgetExactRef, checked_at: datetime
    ) -> Any:
        row = conn.execute(
            f"""SELECT revision,content_hash,lifecycle,daily_limit_minor,monthly_limit_minor,
            effective_from,effective_until FROM {self._authority_schema}.aip_budget_revision
            WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s""",
            (*scope.key, ref.resource_id, ref.revision),
        ).fetchone()
        if (
            row is None
            or row["lifecycle"] != "active"
            or row["content_hash"] != _stored_hash(ref.content_hash)
            or not row["effective_from"] <= checked_at < row["effective_until"]
        ):
            raise BudgetReservationBlocked("active exact BudgetRevision required")
        return row

    def _price_authority(
        self, conn: Any, scope: TenantScope, ref: BudgetExactRef, checked_at: datetime
    ) -> None:
        row = conn.execute(
            f"""SELECT content_hash,lifecycle,payload FROM {self._authority_schema}.aip_model_price_snapshot_revision
            WHERE org_id=%s AND project_id=%s AND model_price_snapshot_id=%s AND revision=%s""",
            (*scope.key, ref.resource_id, ref.revision),
        ).fetchone()
        payload = self._load(row["payload"]) if row else {}
        effective_from = payload.get("effectiveFrom")
        effective_until = payload.get("effectiveUntil")
        price_content = {
            name: value
            for name, value in payload.items()
            if name not in {"tenant", "revision", "contentHash", "createdBy", "createdAt"}
        }
        try:
            parsed_effective_from = datetime.fromisoformat(
                str(effective_from).replace("Z", "+00:00")
            )
            parsed_effective_until = (
                datetime.fromisoformat(str(effective_until).replace("Z", "+00:00"))
                if effective_until
                else None
            )
        except (TypeError, ValueError):
            parsed_effective_from = None
            parsed_effective_until = None
        if (
            row is None
            or row["lifecycle"] != "active"
            or row["content_hash"] != _stored_hash(ref.content_hash)
            or payload.get("tenant")
            != {"orgId": scope.org_id, "projectId": scope.project_id}
            or payload.get("priceSnapshotId") != ref.resource_id
            or type(payload.get("revision")) is not int
            or payload.get("revision") != ref.revision
            or payload.get("contentHash") != row["content_hash"]
            or payload.get("lifecycle") != row["lifecycle"]
            or canonical_hash(price_content) != row["content_hash"]
            or payload.get("currency") != "CNY"
            or parsed_effective_from is None
            or parsed_effective_from > checked_at
            or (parsed_effective_until is not None and parsed_effective_until <= checked_at)
        ):
            raise BudgetReservationBlocked("active exact ModelPriceSnapshotRevision required")

    def _task_authority(self, conn: Any, scope: TenantScope, ref: BudgetExactRef) -> None:
        row = conn.execute(
            f"""SELECT task_id,task_type,title,description,status,priority,goal,selection_ref,
            policy_revision,version,created_by,created_at FROM {self._authority_schema}.aip_task
            WHERE org_id=%s AND project_id=%s AND task_id=%s""",
            (*scope.key, ref.resource_id),
        ).fetchone()
        if row is None or int(row["version"]) != ref.revision:
            raise BudgetReservationBlocked("exact Task authority required")
        if canonical_hash(dict(row), prefixed=True) != ref.content_hash:
            raise BudgetReservationConflict("Task exact hash drifted")

    def _approval_authority(
        self,
        conn: Any,
        scope: TenantScope,
        ref: BudgetExactRef,
        checked_at: datetime,
        *,
        task_ref: BudgetExactRef,
        operation_id: str,
        upper_bound_minor: int,
    ) -> None:
        row = conn.execute(
            f"""SELECT approval_event_id,proposal_id,proposal_version,proposal_hash,decision,
            actor_id,reason,expires_at,created_at,action_binding_hash
            FROM {self._authority_schema}.aip_action_approval_event
            WHERE org_id=%s AND project_id=%s AND approval_event_id=%s""",
            (*scope.key, ref.resource_id),
        ).fetchone()
        if (
            row is None
            or int(row["proposal_version"]) != ref.revision
            or row["decision"] != "approved"
            or (row["expires_at"] is not None and row["expires_at"] <= checked_at)
        ):
            raise BudgetReservationBlocked("active exact ActionApprovalEvent required")
        if canonical_hash(dict(row), prefixed=True) != ref.content_hash:
            raise BudgetReservationConflict("ActionApprovalEvent exact hash drifted")
        proposal = conn.execute(
            f"""SELECT proposal_id,action_type_id,action_type_snapshot,task_id,run_id,
            object_ref,purpose,risk_level,policy_snapshot,payload,diff,evidence_refs,
            impact_preview_id,impact_preview_revision,impact_preview_hash,
            action_binding_hash,source_draft_id,source_draft_revision,source_draft_hash,
            approval_policy_hash,proposal_hash,status,expires_at,created_by
            FROM {self._authority_schema}.aip_action_proposal
            WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*scope.key, row["proposal_id"]),
        ).fetchone()
        payload = self._load(proposal["payload"]) if proposal else {}
        draft = conn.execute(
            f"""SELECT proposal_hash,snapshot FROM {self._authority_schema}.aip_action_draft
            WHERE org_id=%s AND project_id=%s AND proposal_id=%s""",
            (*scope.key, row["proposal_id"]),
        ).fetchone()
        stable = self._load(draft["snapshot"]) if draft else {}
        approved_payload = stable.get("payload") if isinstance(stable, dict) else None
        approved_upper_bound = (
            approved_payload.get("budgetUpperBoundMinor")
            if isinstance(approved_payload, dict)
            else None
        )
        impact_preview_ref = (
            {
                "resourceType": "ImpactPreviewRevision",
                "resourceId": proposal["impact_preview_id"],
                "revision": proposal["impact_preview_revision"],
                "contentHash": proposal["impact_preview_hash"],
            }
            if proposal and proposal["impact_preview_id"] is not None
            else None
        )
        source_draft_ref = (
            {
                "resourceType": "ActionDraftRevision",
                "resourceId": proposal["source_draft_id"],
                "revision": proposal["source_draft_revision"],
                "contentHash": proposal["source_draft_hash"],
            }
            if proposal and proposal["source_draft_id"] is not None
            else None
        )
        stable_expires_at = stable.get("expiresAt")
        try:
            parsed_stable_expiry = (
                datetime.fromisoformat(str(stable_expires_at).replace("Z", "+00:00"))
                if stable_expires_at
                else None
            )
        except ValueError:
            parsed_stable_expiry = None
        if (
            proposal is None
            or draft is None
            or proposal["proposal_hash"] != row["proposal_hash"]
            or draft["proposal_hash"] != proposal["proposal_hash"]
            or canonical_hash(stable) != proposal["proposal_hash"]
            or proposal["status"] != "approved"
            or proposal["task_id"] != task_ref.resource_id
            or proposal["action_type_id"] != operation_id
            or not proposal["action_binding_hash"]
            or proposal["action_binding_hash"] != row["action_binding_hash"]
            or stable.get("tenantScope")
            != {"orgId": scope.org_id, "projectId": scope.project_id}
            or stable.get("createdBy") != proposal["created_by"]
            or canonical_hash(stable.get("actionType"))
            != canonical_hash(self._load(proposal["action_type_snapshot"]))
            or stable.get("taskId") != proposal["task_id"]
            or stable.get("runId") != proposal["run_id"]
            or canonical_hash(stable.get("objectRef"))
            != canonical_hash(self._load(proposal["object_ref"]))
            or stable.get("purpose") != proposal["purpose"]
            or stable.get("riskLevel") != proposal["risk_level"]
            or canonical_hash(stable.get("policy"))
            != canonical_hash(self._load(proposal["policy_snapshot"]))
            or stable.get("approvalPolicyHash") != proposal["approval_policy_hash"]
            or canonical_hash(approved_payload) != canonical_hash(payload)
            or canonical_hash(stable.get("diff"))
            != canonical_hash(self._load(proposal["diff"]))
            or canonical_hash(stable.get("evidenceRefs"))
            != canonical_hash(self._load(proposal["evidence_refs"]))
            or canonical_hash(stable.get("impactPreviewRef"))
            != canonical_hash(impact_preview_ref)
            or stable.get("actionBindingHash") != proposal["action_binding_hash"]
            or canonical_hash(stable.get("sourceDraftRef"))
            != canonical_hash(source_draft_ref)
            or parsed_stable_expiry != proposal["expires_at"]
            or type(approved_upper_bound) is not int
            or approved_upper_bound != upper_bound_minor
        ):
            raise BudgetReservationBlocked(
                "approval must bind this Task, operation, action binding and exact budget upper bound"
            )

    @staticmethod
    def _lock_invocation(
        conn: Any, scope: TenantScope, operation_id: str, invocation_key: str
    ) -> None:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{scope.org_id}\x1f{scope.project_id}\x1f{operation_id}\x1f{invocation_key}",),
        )

    @staticmethod
    def _reservation_by_key(
        conn: Any,
        scope: TenantScope,
        operation_id: str,
        invocation_key: str,
        *,
        lock: bool,
    ) -> Any:
        return conn.execute(
            """SELECT * FROM aip_budget_reservation WHERE org_id=%s AND project_id=%s
            AND operation_id=%s AND invocation_key=%s"""
            + (" FOR UPDATE" if lock else ""),
            (*scope.key, operation_id, invocation_key),
        ).fetchone()

    @staticmethod
    def _reservation_by_id(
        conn: Any, scope: TenantScope, reservation_id: str | uuid.UUID, *, lock: bool
    ) -> Any:
        row = conn.execute(
            """SELECT * FROM aip_budget_reservation WHERE org_id=%s AND project_id=%s
            AND reservation_id=%s"""
            + (" FOR UPDATE" if lock else ""),
            (*scope.key, reservation_id),
        ).fetchone()
        if row is None:
            raise BudgetReservationNotFound("budget reservation not found")
        return row

    def _view(
        self, conn: Any, scope: TenantScope, row: Any, *, replayed: bool
    ) -> BudgetReservationRevision:
        invocation = conn.execute(
            """SELECT revision,content_hash FROM aip_capability_invocation
            WHERE org_id=%s AND project_id=%s AND invocation_id=%s""",
            (*scope.key, row["invocation_id"]),
        ).fetchone()
        if invocation is None:
            raise BudgetReservationConflict("capability invocation authority missing")
        bucket_rows = conn.execute(
            """SELECT b.* FROM aip_budget_reservation_bucket rb
            JOIN aip_budget_bucket b ON b.org_id=rb.org_id AND b.project_id=rb.project_id
             AND b.bucket_kind=rb.bucket_kind AND b.account_id=rb.account_id
             AND b.period_start=rb.period_start AND b.currency=rb.currency
            WHERE rb.org_id=%s AND rb.project_id=%s AND rb.reservation_id=%s
            ORDER BY CASE rb.bucket_kind WHEN 'task' THEN 1 WHEN 'daily' THEN 2 ELSE 3 END""",
            (*scope.key, row["reservation_id"]),
        ).fetchall()
        return BudgetReservationRevision.model_validate(
            {
                "tenant": {"orgId": scope.org_id, "projectId": scope.project_id},
                "invocationRef": {
                    "resourceType": "CapabilityInvocationRevision",
                    "resourceId": str(row["invocation_id"]),
                    "revision": invocation["revision"],
                    "contentHash": invocation["content_hash"],
                },
                "reservationRef": {
                    "resourceType": "BudgetReservationRevision",
                    "resourceId": str(row["reservation_id"]),
                    "revision": row["revision"],
                    "contentHash": row["content_hash"],
                },
                "operationId": row["operation_id"],
                "invocationKey": row["invocation_key"],
                "taskRef": self._load(row["task_ref"]),
                "policyRef": self._load(row["policy_ref"]),
                "pricingRef": self._load(row["pricing_ref"]),
                "approvalRef": self._load(row["approval_ref"]),
                "state": row["state"],
                "currency": row["currency"],
                "upperBoundMinor": row["upper_bound_minor"],
                "actualMinor": row["actual_minor"],
                "providerRequestReceiptRef": self._load(row["provider_request_receipt_ref"]),
                "providerReceiptRef": self._load(row["provider_receipt_ref"]),
                "usageReceiptRefs": tuple(self._load(row["usage_receipt_refs"])),
                "reconciliationEvidenceRef": self._load(row["reconciliation_evidence_ref"]),
                "buckets": [
                    {
                        "kind": item["bucket_kind"],
                        "accountId": item["account_id"],
                        "periodStart": item["period_start"],
                        "periodEnd": item["period_end"],
                        "currency": item["currency"],
                        "limitMinor": item["limit_minor"],
                        "heldMinor": item["held_minor"],
                        "submittedMinor": item["submitted_minor"],
                        "settledMinor": item["settled_minor"],
                        "unknownMinor": item["unknown_minor"],
                    }
                    for item in bucket_rows
                ],
                "requestHash": row["request_hash"],
                "replayed": replayed,
                "createdAt": row["created_at"],
                "updatedAt": row["updated_at"],
            }
        )

    @staticmethod
    def _event(
        conn: Any,
        scope: TenantScope,
        reservation_id: uuid.UUID,
        *,
        sequence: int,
        from_state: str | None,
        to_state: str,
        actor: str,
        evidence_ref: BudgetExactRef | None,
        occurred_at: datetime,
    ) -> None:
        payload = {
            "reservationId": str(reservation_id),
            "sequence": sequence,
            "fromState": from_state,
            "toState": to_state,
            "actor": actor,
            "evidenceRef": exact_ref_payload(evidence_ref),
            "occurredAt": occurred_at,
        }
        conn.execute(
            """INSERT INTO aip_budget_reservation_event(
            org_id,project_id,event_id,reservation_id,sequence,from_state,to_state,
            actor,evidence_ref,event_hash,created_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (
                *scope.key,
                uuid.uuid4(),
                reservation_id,
                sequence,
                from_state,
                to_state,
                actor,
                None if evidence_ref is None else json.dumps(exact_ref_payload(evidence_ref)),
                canonical_hash(payload, prefixed=True),
                occurred_at,
            ),
        )

    @staticmethod
    def _identity(value: str, name: str) -> str:
        cleaned = value.strip()
        if not cleaned or cleaned != value or len(cleaned) > 200:
            raise ValueError(f"{name} must be canonical")
        return cleaned

    @staticmethod
    def _digest(value: str, name: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(ch not in "0123456789abcdef" for ch in cleaned):
            raise ValueError(f"{name} must be a sha256 digest")
        return cleaned

    @staticmethod
    def _json(value: Any) -> str:
        if hasattr(value, "model_dump"):
            value = value.model_dump(mode="json", by_alias=True)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)

    @staticmethod
    def _load(value: Any) -> Any:
        if value is None:
            return None
        return json.loads(value) if isinstance(value, str) else value


__all__ = [
    "AipBudgetReservationStore",
    "BudgetReservationBlocked",
    "BudgetReservationConflict",
    "BudgetReservationError",
    "BudgetReservationNotFound",
    "canonical_hash",
]
