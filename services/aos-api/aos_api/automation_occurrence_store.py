"""Tenant-scoped persistent authority for natural schedule/event occurrences."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID, uuid5

from psycopg.types.json import Jsonb

from aos_api.db import connect as db_connect
from aos_api.tenant_scope import TenantScope


SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
OPERATION_ID = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,159}")
OCCURRENCE_NAMESPACE = UUID("84f14892-9dd4-48dc-bd3c-acde3875a7bb")
ConnectFactory = Callable[..., AbstractContextManager[Any]]


class AutomationOccurrenceError(RuntimeError):
    pass


class AutomationOccurrenceConflict(AutomationOccurrenceError):
    pass


class AutomationOccurrenceNotReady(AutomationOccurrenceError):
    pass


@dataclass(frozen=True, slots=True)
class ScheduleBinding:
    policy_id: str
    policy_revision: int
    policy_hash: str
    operation_id: str
    installation_id: UUID
    generation: UUID
    execution_epoch: int
    cadence: Literal["once", "weekly", "event"]
    effective_from: datetime
    effective_until: datetime | None = None
    weekly_day: int | None = None
    local_time: str | None = None
    approved: bool = False
    enabled: bool = False

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or self.policy_revision <= 0 or self.execution_epoch <= 0:
            raise ValueError("schedule binding identity is required")
        if not SHA256.fullmatch(self.policy_hash):
            raise ValueError("invalid policy hash")
        if not OPERATION_ID.fullmatch(self.operation_id):
            raise ValueError("invalid operation id")
        if not isinstance(self.installation_id, UUID) or not isinstance(self.generation, UUID):
            raise ValueError("runtime identity must be canonical UUID")
        if self.effective_from.utcoffset() is None or (
            self.effective_until is not None and self.effective_until.utcoffset() is None
        ):
            raise ValueError("effective bounds must include timezone")
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("empty effective interval")
        if self.cadence == "weekly":
            if self.weekly_day not in range(1, 8) or self.local_time is None:
                raise ValueError("weekly binding requires weekday and local time")
            datetime.strptime(self.local_time, "%H:%M")
        elif self.weekly_day is not None or self.local_time is not None:
            raise ValueError("non-weekly binding cannot carry weekly fields")


@dataclass(frozen=True, slots=True)
class OccurrenceWrite:
    occurrence_id: UUID
    status: str
    replayed: bool


@dataclass(frozen=True, slots=True)
class ClaimedOccurrence:
    occurrence_id: UUID
    policy_id: str
    policy_revision: int
    operation_id: str
    installation_id: UUID
    generation: UUID
    execution_epoch: int
    claim_owner: str
    claim_until: datetime
    attempt_id: UUID
    target_idempotency_key: str


def _canonical_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _utc_seconds(value: datetime, name: str) -> datetime:
    if value.utcoffset() is None or value.utcoffset() != timedelta(0) or value.microsecond:
        raise ValueError(f"{name} must be UTC with second precision")
    return value.astimezone(UTC)


class AutomationOccurrenceStore:
    def __init__(
        self,
        connect_factory: ConnectFactory | None = None,
        *,
        schema: str = "public",
    ) -> None:
        if re.fullmatch(r"[a-z_][a-z0-9_]*", schema) is None:
            raise ValueError("occurrence authority schema is invalid")
        self._connect_factory = connect_factory or db_connect
        self._schema = schema

    def put_binding(self, scope: TenantScope, binding: ScheduleBinding) -> None:
        with self._connect_factory(scope) as conn:
            self._lock_policy(conn, scope, binding.policy_id)
            dispatch = conn.execute(
                """SELECT handler_kind,installation_id,generation,execution_epoch
                   FROM extension_operation_dispatch_binding
                   WHERE org_id=%s AND project_id=%s AND operation_id=%s""",
                (*scope.key, binding.operation_id),
            ).fetchone()
            expected = (
                "extension",
                binding.installation_id,
                binding.generation,
                binding.execution_epoch,
            )
            actual = None if dispatch is None else (
                dispatch["handler_kind"],
                dispatch["installation_id"],
                dispatch["generation"],
                dispatch["execution_epoch"],
            )
            if actual != expected:
                raise AutomationOccurrenceNotReady("schedule binding does not match current dispatch")
            conn.execute(
                """SELECT policy_revision FROM automation_schedule_binding
                   WHERE org_id=%s AND project_id=%s AND policy_id=%s
                   ORDER BY policy_revision FOR UPDATE""",
                (*scope.key, binding.policy_id),
            ).fetchall()
            conn.execute(
                """UPDATE automation_schedule_binding
                      SET enabled=false,revision=revision+1
                    WHERE org_id=%s AND project_id=%s AND policy_id=%s
                      AND policy_revision<>%s AND enabled""",
                (*scope.key, binding.policy_id, binding.policy_revision),
            )
            row = conn.execute(
                """INSERT INTO automation_schedule_binding(
                     org_id,project_id,policy_id,policy_revision,policy_hash,operation_id,
                     installation_id,generation,execution_epoch,timezone,cadence,weekly_day,
                     local_time,effective_from,effective_until,approved,enabled)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'Asia/Shanghai',%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT(org_id,project_id,policy_id,policy_revision) DO NOTHING
                   RETURNING policy_hash,operation_id,installation_id,generation,execution_epoch,
                     cadence,weekly_day,local_time,effective_from,effective_until,approved,enabled""",
                (
                    *scope.key,
                    binding.policy_id,
                    binding.policy_revision,
                    binding.policy_hash,
                    binding.operation_id,
                    binding.installation_id,
                    binding.generation,
                    binding.execution_epoch,
                    binding.cadence,
                    binding.weekly_day,
                    binding.local_time,
                    binding.effective_from,
                    binding.effective_until,
                    binding.approved,
                    binding.enabled,
                ),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    """SELECT policy_hash,operation_id,installation_id,generation,execution_epoch,
                         cadence,weekly_day,local_time,effective_from,effective_until,approved,enabled
                       FROM automation_schedule_binding
                       WHERE org_id=%s AND project_id=%s AND policy_id=%s AND policy_revision=%s""",
                    (*scope.key, binding.policy_id, binding.policy_revision),
                ).fetchone()
                expected_existing = {
                    "policy_hash": binding.policy_hash,
                    "operation_id": binding.operation_id,
                    "installation_id": binding.installation_id,
                    "generation": binding.generation,
                    "execution_epoch": binding.execution_epoch,
                    "cadence": binding.cadence,
                    "weekly_day": binding.weekly_day,
                    "local_time": None if binding.local_time is None else datetime.strptime(binding.local_time, "%H:%M").time(),
                    "effective_from": binding.effective_from,
                    "effective_until": binding.effective_until,
                    "approved": binding.approved,
                    "enabled": binding.enabled,
                }
                if row is None or dict(row) != expected_existing:
                    raise AutomationOccurrenceConflict("schedule binding replay drifted")
            conn.commit()

    def disable_policy_bindings(
        self,
        scope: TenantScope,
        policy_id: str,
        *,
        keep_revision: int | None = None,
    ) -> None:
        if not policy_id.strip() or len(policy_id) > 200:
            raise ValueError("bounded policy_id is required")
        if keep_revision is not None and (type(keep_revision) is not int or keep_revision <= 0):
            raise ValueError("keep_revision must be a positive integer")
        with self._connect_factory(scope) as conn:
            self._lock_policy(conn, scope, policy_id)
            conn.execute(
                """SELECT policy_revision FROM automation_schedule_binding
                   WHERE org_id=%s AND project_id=%s AND policy_id=%s
                   ORDER BY policy_revision FOR UPDATE""",
                (*scope.key, policy_id),
            ).fetchall()
            conn.execute(
                """UPDATE automation_schedule_binding
                      SET enabled=false,revision=revision+1
                    WHERE org_id=%s AND project_id=%s AND policy_id=%s AND enabled
                      AND (%s::bigint IS NULL OR policy_revision<>%s)""",
                (*scope.key, policy_id, keep_revision, keep_revision),
            )
            conn.commit()

    @staticmethod
    def _lock_policy(conn: Any, scope: TenantScope, policy_id: str) -> None:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"{scope.org_id}\x1f{scope.project_id}\x1fautomation-policy\x1f{policy_id}",),
        )

    def record_scheduled(
        self,
        scope: TenantScope,
        binding: ScheduleBinding,
        *,
        scheduled_at: datetime,
        local_slot: str,
        deadline: datetime,
        status: Literal["pending", "missed", "not_applicable"] = "pending",
    ) -> OccurrenceWrite:
        if binding.cadence not in {"once", "weekly"}:
            raise ValueError("event binding cannot create a scheduled occurrence")
        scheduled_at = _utc_seconds(scheduled_at, "scheduled_at")
        deadline = _utc_seconds(deadline, "deadline")
        if deadline <= scheduled_at or not local_slot.strip():
            raise ValueError("scheduled occurrence requires a local slot and later deadline")
        occurrence_id = uuid5(
            OCCURRENCE_NAMESPACE,
            f"schedule:{scope.org_id}:{scope.project_id}:{binding.policy_id}:{scheduled_at.isoformat()}",
        )
        return self._record(
            scope,
            binding,
            occurrence_id=occurrence_id,
            scheduled_at=scheduled_at,
            local_slot=local_slot,
            source_event_id=None,
            trigger_source="schedule",
            deadline=deadline,
            status=status,
        )

    def record_event(
        self,
        scope: TenantScope,
        binding: ScheduleBinding,
        *,
        source_event_id: str,
        deadline: datetime,
    ) -> OccurrenceWrite:
        if binding.cadence != "event":
            raise ValueError("only an event binding can consume source events")
        deadline = _utc_seconds(deadline, "deadline")
        if not source_event_id.strip() or len(source_event_id) > 240:
            raise ValueError("authenticated source_event_id is required")
        occurrence_id = uuid5(
            OCCURRENCE_NAMESPACE,
            f"event:{scope.org_id}:{scope.project_id}:{binding.policy_id}:{source_event_id}",
        )
        return self._record(
            scope,
            binding,
            occurrence_id=occurrence_id,
            scheduled_at=None,
            local_slot=None,
            source_event_id=source_event_id,
            trigger_source="event",
            deadline=deadline,
            status="pending",
        )

    def record_event_batch(
        self,
        scope: TenantScope,
        binding: ScheduleBinding,
        *,
        events: list[tuple[str, datetime]] | tuple[tuple[str, datetime], ...],
    ) -> tuple[OccurrenceWrite, ...]:
        """Commit a bounded batch and its outbox atomically, without a watermark.

        Trusted callers authenticate source identities and freeze deadlines
        before this call. Replays must reuse those deadlines. Sequence numbers
        are not commit-order cursors: late committed events remain eligible.
        """
        if binding.cadence != "event":
            raise ValueError("only an event binding can consume source events")
        if not isinstance(events, (list, tuple)) or not 1 <= len(events) <= 100:
            raise ValueError("event batch must contain 1 to 100 items")
        checked: list[tuple[str, datetime]] = []
        seen: set[str] = set()
        for item in events:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError("event batch item must contain identity and deadline")
            source_event_id, deadline = item
            if (not isinstance(source_event_id, str) or not source_event_id.strip()
                    or source_event_id.strip() != source_event_id or len(source_event_id) > 240
                    or source_event_id in seen or not isinstance(deadline, datetime)):
                raise ValueError("event batch identity or deadline is invalid")
            checked.append((source_event_id, _utc_seconds(deadline, "deadline")))
            seen.add(source_event_id)
        with self._connect_factory(scope) as conn:
            self._lock_binding(conn, scope, binding)
            writes = tuple(
                self._insert_occurrence(
                    conn, scope, binding,
                    occurrence_id=uuid5(
                        OCCURRENCE_NAMESPACE,
                        f"event:{scope.org_id}:{scope.project_id}:{binding.policy_id}:{source_event_id}",
                    ),
                    scheduled_at=None, local_slot=None, source_event_id=source_event_id,
                    trigger_source="event", deadline=deadline, status="pending",
                )
                for source_event_id, deadline in checked
            )
            conn.commit()
        return writes

    def _record(
        self,
        scope: TenantScope,
        binding: ScheduleBinding,
        *,
        occurrence_id: UUID,
        scheduled_at: datetime | None,
        local_slot: str | None,
        source_event_id: str | None,
        trigger_source: str,
        deadline: datetime,
        status: str,
    ) -> OccurrenceWrite:
        with self._connect_factory(scope) as conn:
            self._lock_binding(conn, scope, binding)
            result = self._insert_occurrence(
                conn,
                scope,
                binding,
                occurrence_id=occurrence_id,
                scheduled_at=scheduled_at,
                local_slot=local_slot,
                source_event_id=source_event_id,
                trigger_source=trigger_source,
                deadline=deadline,
                status=status,
            )
            conn.commit()
        return result

    @staticmethod
    def _lock_binding(
        conn: Any,
        scope: TenantScope,
        binding: ScheduleBinding,
        *,
        expected_watermark: datetime | None | object = Ellipsis,
    ) -> datetime | None:
        row = conn.execute(
            """SELECT policy_hash,operation_id,installation_id,generation,execution_epoch,
                     cadence,weekly_day,local_time,effective_from,effective_until,
                     approved,enabled,watermark
                 FROM automation_schedule_binding
                WHERE org_id=%s AND project_id=%s AND policy_id=%s AND policy_revision=%s
                FOR UPDATE""",
            (*scope.key, binding.policy_id, binding.policy_revision),
        ).fetchone()
        expected = {
            "policy_hash": binding.policy_hash,
            "operation_id": binding.operation_id,
            "installation_id": binding.installation_id,
            "generation": binding.generation,
            "execution_epoch": binding.execution_epoch,
            "cadence": binding.cadence,
            "weekly_day": binding.weekly_day,
            "local_time": None if binding.local_time is None else datetime.strptime(binding.local_time, "%H:%M").time(),
            "effective_from": binding.effective_from,
            "effective_until": binding.effective_until,
            "approved": True,
            "enabled": True,
        }
        if row is None or {key: row[key] for key in expected} != expected:
            raise AutomationOccurrenceNotReady("schedule binding authority drifted or is not executable")
        if expected_watermark is not Ellipsis and row["watermark"] != expected_watermark:
            raise AutomationOccurrenceConflict("schedule watermark changed")
        return row["watermark"]

    def _insert_occurrence(
        self,
        conn: Any,
        scope: TenantScope,
        binding: ScheduleBinding,
        *,
        occurrence_id: UUID,
        scheduled_at: datetime | None,
        local_slot: str | None,
        source_event_id: str | None,
        trigger_source: str,
        deadline: datetime,
        status: str,
    ) -> OccurrenceWrite:
        payload = {
            "occurrenceId": str(occurrence_id),
            "policyId": binding.policy_id,
            "policyRevision": binding.policy_revision,
            "operationId": binding.operation_id,
            "scheduledAt": scheduled_at.isoformat() if scheduled_at else None,
            "sourceEventId": source_event_id,
        }
        event_id = uuid5(OCCURRENCE_NAMESPACE, f"outbox:{occurrence_id}")
        row = conn.execute(
            """INSERT INTO automation_occurrence(
                 org_id,project_id,occurrence_id,policy_id,policy_revision,policy_hash,
                 operation_id,installation_id,generation,execution_epoch,scheduled_at,
                 local_slot,trigger_source,source_event_id,status,deadline)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT(org_id,project_id,occurrence_id) DO NOTHING
               RETURNING occurrence_id,status""",
            (
                *scope.key,
                occurrence_id,
                binding.policy_id,
                binding.policy_revision,
                binding.policy_hash,
                binding.operation_id,
                binding.installation_id,
                binding.generation,
                binding.execution_epoch,
                scheduled_at,
                local_slot,
                trigger_source,
                source_event_id,
                status,
                deadline,
            ),
        ).fetchone()
        replayed = row is None
        if row is None:
            row = conn.execute(
                """SELECT occurrence_id,status,policy_revision,policy_hash,operation_id,
                     installation_id,generation,execution_epoch,scheduled_at,local_slot,
                     trigger_source,source_event_id,deadline
                   FROM automation_occurrence
                   WHERE org_id=%s AND project_id=%s AND occurrence_id=%s""",
                (*scope.key, occurrence_id),
            ).fetchone()
            expected_existing = {
                "occurrence_id": occurrence_id,
                "status": row["status"] if row is not None else None,
                "policy_revision": binding.policy_revision,
                "policy_hash": binding.policy_hash,
                "operation_id": binding.operation_id,
                "installation_id": binding.installation_id,
                "generation": binding.generation,
                "execution_epoch": binding.execution_epoch,
                "scheduled_at": scheduled_at,
                "local_slot": local_slot,
                "trigger_source": trigger_source,
                "source_event_id": source_event_id,
                "deadline": deadline,
            }
            if row is None or dict(row) != expected_existing:
                raise AutomationOccurrenceConflict("occurrence replay drifted")
        conn.execute(
            """INSERT INTO automation_occurrence_outbox(
                 org_id,project_id,event_id,occurrence_id,payload,payload_hash)
               VALUES(%s,%s,%s,%s,%s,%s)
               ON CONFLICT(org_id,project_id,occurrence_id) DO NOTHING""",
            (*scope.key, event_id, occurrence_id, Jsonb(payload), _canonical_hash(payload)),
        )
        if row is None:
            raise AutomationOccurrenceConflict("occurrence write returned no authority")
        return OccurrenceWrite(UUID(str(row["occurrence_id"])), str(row["status"]), replayed)

    def record_due_batch(
        self,
        scope: TenantScope,
        binding: ScheduleBinding,
        *,
        expected_watermark: datetime | None,
        new_watermark: datetime,
        slots: list[tuple[datetime, str, datetime, Literal["pending", "missed"]]],
    ) -> list[OccurrenceWrite]:
        """Persist every enumerated slot, its outbox and the watermark atomically."""
        new_watermark = _utc_seconds(new_watermark, "new_watermark")
        expected_watermark = (
            _utc_seconds(expected_watermark, "expected_watermark")
            if expected_watermark is not None
            else None
        )
        if expected_watermark is not None and new_watermark <= expected_watermark:
            raise ValueError("schedule watermark must move forward")
        results: list[OccurrenceWrite] = []
        with self._connect_factory(scope) as conn:
            self._lock_binding(conn, scope, binding, expected_watermark=expected_watermark)
            for scheduled_at, local_slot, deadline, status in slots:
                scheduled_at = _utc_seconds(scheduled_at, "scheduled_at")
                deadline = _utc_seconds(deadline, "deadline")
                occurrence_id = uuid5(
                    OCCURRENCE_NAMESPACE,
                    f"schedule:{scope.org_id}:{scope.project_id}:{binding.policy_id}:{scheduled_at.isoformat()}",
                )
                results.append(
                    self._insert_occurrence(
                        conn,
                        scope,
                        binding,
                        occurrence_id=occurrence_id,
                        scheduled_at=scheduled_at,
                        local_slot=local_slot,
                        source_event_id=None,
                        trigger_source="schedule",
                        deadline=deadline,
                        status=status,
                    )
                )
            row = conn.execute(
                """UPDATE automation_schedule_binding SET watermark=%s,revision=revision+1
                    WHERE org_id=%s AND project_id=%s AND policy_id=%s AND policy_revision=%s
                    RETURNING policy_id""",
                (
                    new_watermark,
                    *scope.key,
                    binding.policy_id,
                    binding.policy_revision,
                ),
            ).fetchone()
            if row is None:
                raise AutomationOccurrenceConflict("schedule watermark changed")
            conn.commit()
        return results

    def claim_next(
        self,
        scope: TenantScope,
        *,
        owner: str,
        now: datetime,
        lease: timedelta = timedelta(minutes=5),
    ) -> ClaimedOccurrence | None:
        now = _utc_seconds(now, "now")
        if not owner.strip() or lease <= timedelta(0) or lease > timedelta(minutes=30):
            raise ValueError("bounded claim owner and lease are required")
        claim_until = now + lease
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                f"""WITH candidate AS (
                     SELECT o.occurrence_id FROM automation_occurrence o
                     JOIN automation_schedule_binding b USING(org_id,project_id,policy_id,policy_revision)
                     JOIN extension_operation_dispatch_binding d
                       ON d.org_id=o.org_id AND d.project_id=o.project_id AND d.operation_id=o.operation_id
                     JOIN extension_runtime_binding r
                       ON r.org_id=o.org_id AND r.project_id=o.project_id
                      AND r.installation_id=o.installation_id AND r.generation=o.generation
                    WHERE o.org_id=%s AND o.project_id=%s
                      AND o.status='pending'
                      AND o.scheduled_at<=%s AND o.deadline>%s AND b.approved AND b.enabled
                      AND d.handler_kind='extension' AND NOT d.operation_fence
                      AND d.installation_id=o.installation_id AND d.generation=o.generation
                      AND d.execution_epoch=o.execution_epoch
                      AND r.enabled AND NOT r.operation_fence AND r.observed_state='ready'
                      AND r.execution_epoch=o.execution_epoch
                      AND NOT EXISTS (
                        SELECT 1 FROM {self._schema}.extension_dispatch_claim_gate g
                         WHERE g.org_id=o.org_id AND g.project_id=o.project_id
                           AND g.cutover_group_id=d.cutover_group_id AND g.claim_paused)
                    ORDER BY o.created_at,o.occurrence_id FOR UPDATE OF o,b SKIP LOCKED LIMIT 1
                   ) UPDATE automation_occurrence o
                     SET status='claimed',claim_owner=%s,claim_until=%s,updated_at=clock_timestamp()
                    FROM candidate c
                   WHERE o.org_id=%s AND o.project_id=%s AND o.occurrence_id=c.occurrence_id
                   RETURNING o.*""",
                (*scope.key, now, now, owner, claim_until, *scope.key),
            ).fetchone()
            if row is not None:
                attempt_id = uuid5(OCCURRENCE_NAMESPACE, f"dispatch:{row['occurrence_id']}")
                target_key = f"automation-occurrence:{row['occurrence_id']}"
                conn.execute(
                    """INSERT INTO automation_occurrence_dispatch_attempt(
                         org_id,project_id,attempt_id,occurrence_id,claim_owner,
                         target_idempotency_key,status,claimed_at,claim_until)
                       VALUES(%s,%s,%s,%s,%s,%s,'claimed',%s,%s)""",
                    (*scope.key, attempt_id, row["occurrence_id"], owner, target_key, now, claim_until),
                )
            conn.commit()
        if row is None:
            return None
        return ClaimedOccurrence(
            occurrence_id=UUID(str(row["occurrence_id"])),
            policy_id=str(row["policy_id"]),
            policy_revision=int(row["policy_revision"]),
            operation_id=str(row["operation_id"]),
            installation_id=UUID(str(row["installation_id"])),
            generation=UUID(str(row["generation"])),
            execution_epoch=int(row["execution_epoch"]),
            claim_owner=str(row["claim_owner"]),
            claim_until=row["claim_until"],
            attempt_id=attempt_id,
            target_idempotency_key=target_key,
        )

    def record_target_receipt(
        self,
        scope: TenantScope,
        *,
        occurrence_id: UUID,
        owner: str,
        receipt_ref: dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        occurred_at = _utc_seconds(occurred_at, "occurred_at")
        if not receipt_ref or not owner.strip():
            raise ValueError("target receipt and claim owner are required")
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """UPDATE automation_occurrence
                      SET status='accepted',receipt_ref=%s,claim_owner=NULL,claim_until=NULL,
                          updated_at=%s
                    WHERE org_id=%s AND project_id=%s AND occurrence_id=%s
                      AND status='claimed' AND claim_owner=%s AND claim_until>%s
                    RETURNING occurrence_id""",
                (Jsonb(receipt_ref), occurred_at, *scope.key, occurrence_id, owner, occurred_at),
            ).fetchone()
            if row is None:
                raise AutomationOccurrenceConflict("claim changed before target receipt commit")
            conn.execute(
                """UPDATE automation_occurrence_outbox
                      SET delivered_at=%s,claim_until=NULL
                    WHERE org_id=%s AND project_id=%s AND occurrence_id=%s""",
                (occurred_at, *scope.key, occurrence_id),
            )
            attempt = conn.execute(
                """UPDATE automation_occurrence_dispatch_attempt
                      SET status='receipt_recorded',receipt_ref=%s,resolved_at=%s
                    WHERE org_id=%s AND project_id=%s AND occurrence_id=%s
                      AND status='claimed' AND claim_owner=%s
                    RETURNING attempt_id""",
                (Jsonb(receipt_ref), occurred_at, *scope.key, occurrence_id, owner),
            ).fetchone()
            if attempt is None:
                raise AutomationOccurrenceConflict("dispatch attempt missing before target receipt commit")
            conn.commit()

    def mark_needs_attention(
        self,
        scope: TenantScope,
        *,
        occurrence_id: UUID,
        owner: str,
        occurred_at: datetime,
    ) -> None:
        occurred_at = _utc_seconds(occurred_at, "occurred_at")
        with self._connect_factory(scope) as conn:
            row = conn.execute(
                """UPDATE automation_occurrence
                      SET status='needs_attention',claim_owner=NULL,claim_until=NULL,
                          updated_at=%s
                    WHERE org_id=%s AND project_id=%s AND occurrence_id=%s
                      AND status='claimed' AND claim_owner=%s
                    RETURNING occurrence_id""",
                (occurred_at, *scope.key, occurrence_id, owner),
            ).fetchone()
            if row is None:
                raise AutomationOccurrenceConflict("claim changed before reconciliation hold")
            attempt = conn.execute(
                """UPDATE automation_occurrence_dispatch_attempt
                      SET status='unknown',resolved_at=%s
                    WHERE org_id=%s AND project_id=%s AND occurrence_id=%s
                      AND status='claimed' AND claim_owner=%s
                    RETURNING attempt_id""",
                (occurred_at, *scope.key, occurrence_id, owner),
            ).fetchone()
            if attempt is None:
                raise AutomationOccurrenceConflict("dispatch attempt missing before reconciliation hold")
            conn.commit()

    def reconcile_expired_claims(self, scope: TenantScope, *, now: datetime) -> int:
        """Move expired external attempts to reconcile-only; never redispatch them."""
        now = _utc_seconds(now, "now")
        with self._connect_factory(scope) as conn:
            rows = conn.execute(
                """UPDATE automation_occurrence o
                      SET status='needs_attention',claim_owner=NULL,claim_until=NULL,updated_at=%s
                    WHERE o.org_id=%s AND o.project_id=%s AND o.status='claimed' AND o.claim_until<=%s
                    RETURNING o.occurrence_id""",
                (now, *scope.key, now),
            ).fetchall()
            for row in rows:
                attempt = conn.execute(
                    """UPDATE automation_occurrence_dispatch_attempt
                          SET status='unknown',resolved_at=%s
                        WHERE org_id=%s AND project_id=%s AND occurrence_id=%s AND status='claimed'
                        RETURNING attempt_id""",
                    (now, *scope.key, row["occurrence_id"]),
                ).fetchone()
                if attempt is None:
                    raise AutomationOccurrenceConflict("expired occurrence has no dispatch attempt")
            conn.commit()
        return len(rows)

    def reconcile_target_receipt(
        self,
        scope: TenantScope,
        *,
        occurrence_id: UUID,
        receipt_ref: dict[str, Any],
        occurred_at: datetime,
    ) -> None:
        """Settle a held unknown result from the target Receipt without dispatching again."""
        occurred_at = _utc_seconds(occurred_at, "occurred_at")
        if not receipt_ref:
            raise ValueError("target receipt is required")
        with self._connect_factory(scope) as conn:
            occurrence = conn.execute(
                """UPDATE automation_occurrence
                      SET status='accepted',receipt_ref=%s,updated_at=%s
                    WHERE org_id=%s AND project_id=%s AND occurrence_id=%s
                      AND status='needs_attention' AND receipt_ref IS NULL
                    RETURNING occurrence_id""",
                (Jsonb(receipt_ref), occurred_at, *scope.key, occurrence_id),
            ).fetchone()
            if occurrence is None:
                raise AutomationOccurrenceConflict("occurrence is not awaiting target reconciliation")
            attempt = conn.execute(
                """UPDATE automation_occurrence_dispatch_attempt
                      SET status='receipt_recorded',receipt_ref=%s,resolved_at=%s
                    WHERE org_id=%s AND project_id=%s AND occurrence_id=%s AND status='unknown'
                    RETURNING attempt_id""",
                (Jsonb(receipt_ref), occurred_at, *scope.key, occurrence_id),
            ).fetchone()
            if attempt is None:
                raise AutomationOccurrenceConflict("unknown dispatch attempt is missing")
            conn.execute(
                """UPDATE automation_occurrence_outbox SET delivered_at=%s,claim_until=NULL
                    WHERE org_id=%s AND project_id=%s AND occurrence_id=%s""",
                (occurred_at, *scope.key, occurrence_id),
            )
            conn.commit()


__all__ = [
    "AutomationOccurrenceConflict",
    "AutomationOccurrenceError",
    "AutomationOccurrenceNotReady",
    "AutomationOccurrenceStore",
    "ClaimedOccurrence",
    "OccurrenceWrite",
    "ScheduleBinding",
]
