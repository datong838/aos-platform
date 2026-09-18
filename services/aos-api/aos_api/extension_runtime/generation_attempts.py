"""Durable generation attempts and the fail-closed drain authority."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from uuid import UUID, uuid4

from aos_api.tenant_scope import TenantScope

from .consumer_connection import consumer_connection
from .lifecycle_store import RuntimeConflict, RuntimeRevisionConflict, _require_transaction, _values
from .storage_ports import require_runtime_role

_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_ERROR_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,159}$")
_TERMINAL = ("succeeded", "failed", "abandoned")
_TERMINAL_REASONS = frozenset({
    "RECOVERABLE_EXECUTION_EXCEPTION",
    "RECOVERABLE_INGRESS_CANCELLED",
    "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED",
    "RECOVERABLE_HEARTBEAT_FAILED",
    "RECOVERABLE_HEARTBEAT_STOP_TIMEOUT",
    "ATTEMPT_LEASE_EXPIRED",
    "READ_ACCESS_REVOKED",
    "READ_FAILED",
    "READ_RESULT_INVALID",
    "READ_OUTCOME_UNKNOWN",
    "READ_DEADLINE_EXPIRED",
    "READ_RUNTIME_CHANGED",
})


@dataclass(frozen=True, slots=True)
class RuntimeAttemptLease:
    attempt_id: UUID
    state: str
    revision: int
    execute_once: bool


def _token_hash(token: str) -> str:
    if type(token) is not str or len(token) < 32 or len(token) > 512:
        raise ValueError("opaque attempt owner token required")
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _identity(value, label: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"exact {label} required") from exc


def _scope(conn, org_id: str, project_id: str) -> None:
    if type(org_id) is not str or not org_id or type(project_id) is not str or not project_id:
        raise ValueError("exact runtime tenant scope required")
    row = conn.execute(
        "SELECT current_setting('aos.org_id',true) AS org_id,"
        "current_setting('aos.project_id',true) AS project_id"
    ).fetchone()
    if row is None or _values(row, ("org_id", "project_id")) != (org_id, project_id):
        raise PermissionError("runtime attempt tenant scope mismatch")


def _event(conn, *, org_id: str, project_id: str, attempt_id: UUID, sequence: int,
           event_type: str, state: str, revision: int,
           terminal_reason_code: str | None = None,
           terminal_error_type: str | None = None) -> None:
    conn.execute(
        """INSERT INTO extension_runtime_execution_attempt_event
           (org_id,project_id,attempt_id,sequence,event_id,type,state,revision,
            terminal_reason_code,terminal_error_type)
           VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (org_id, project_id, attempt_id, sequence, uuid4(), event_type, state, revision,
         terminal_reason_code, terminal_error_type),
    )


class PostgresRuntimeAttemptStore:
    def begin(self, conn, *, org_id: str, project_id: str, installation_id, generation,
              execution_epoch: int, operation_kind: str, operation_key: str,
              idempotency_key: str, request_hash: str, owner_token: str,
              lease_until: datetime) -> RuntimeAttemptLease:
        _require_transaction(conn)
        _scope(conn, org_id, project_id)
        installation_id = _identity(installation_id, "installation id")
        generation = _identity(generation, "generation")
        if type(execution_epoch) is not int or execution_epoch < 1:
            raise ValueError("positive execution epoch required")
        if operation_kind != "signed_read":
            raise ValueError("signed-read runtime operation kind required")
        if type(operation_key) is not str or not 1 <= len(operation_key) <= 160:
            raise ValueError("exact runtime operation key required")
        if type(idempotency_key) is not str or not 1 <= len(idempotency_key) <= 240:
            raise ValueError("exact runtime idempotency key required")
        if type(request_hash) is not str or _HASH.fullmatch(request_hash) is None:
            raise ValueError("canonical runtime request hash required")
        if not isinstance(lease_until, datetime) or lease_until.tzinfo is None:
            raise ValueError("aware runtime attempt lease required")
        owner_hash = _token_hash(owner_token)
        conn.execute(
            """SELECT pg_advisory_xact_lock(hashtextextended(
               'runtime-attempt:'||jsonb_build_array(%s::text,%s::text,%s::uuid::text,
               %s::uuid::text,%s::bigint,%s::text,%s::text)::text,0))""",
            (org_id, project_id, installation_id, generation, execution_epoch,
             operation_kind, idempotency_key),
        )
        replay = conn.execute(
            """SELECT attempt_id,operation_key,request_hash,state,revision
                 FROM extension_runtime_execution_attempt
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                  AND execution_epoch=%s AND operation_kind=%s AND idempotency_key=%s
                FOR UPDATE""",
            (org_id, project_id, installation_id, generation, execution_epoch,
             operation_kind, idempotency_key),
        ).fetchone()
        if replay is not None:
            attempt_id, stored_key, stored_hash, state, revision = _values(
                replay, ("attempt_id", "operation_key", "request_hash", "state", "revision")
            )
            if (stored_key, stored_hash) != (operation_key, request_hash):
                raise RuntimeConflict("runtime attempt idempotency conflict")
            return RuntimeAttemptLease(attempt_id, state, revision, False)
        valid_lease = conn.execute(
            "SELECT %s > clock_timestamp() AND %s <= clock_timestamp()+interval '5 minutes' AS valid",
            (lease_until, lease_until),
        ).fetchone()
        if valid_lease is None or _values(valid_lease, ("valid",))[0] is not True:
            raise ValueError("runtime attempt lease must be current and bounded")
        binding = conn.execute(
            """SELECT enabled,operation_fence,execution_epoch
                 FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                FOR SHARE""",
            (org_id, project_id, installation_id, generation),
        ).fetchone()
        if binding is None:
            raise PermissionError("runtime binding unavailable")
        enabled, fenced, current_epoch = _values(
            binding, ("enabled", "operation_fence", "execution_epoch")
        )
        if enabled is not True or fenced is not False or current_epoch != execution_epoch:
            raise PermissionError("runtime generation is not accepting attempts")
        attempt_id = uuid4()
        conn.execute(
            """INSERT INTO extension_runtime_execution_attempt
               (org_id,project_id,attempt_id,installation_id,generation,execution_epoch,
                operation_kind,operation_key,idempotency_key,request_hash,owner_token_hash,state,lease_until)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'running',%s)""",
            (org_id, project_id, attempt_id, installation_id, generation, execution_epoch,
             operation_kind, operation_key, idempotency_key, request_hash, owner_hash, lease_until),
        )
        _event(conn, org_id=org_id, project_id=project_id, attempt_id=attempt_id,
               sequence=1, event_type="attempt_accepted", state="running", revision=1)
        return RuntimeAttemptLease(attempt_id, "running", 1, True)

    def begin_recoverable_store(
        self, conn, *, org_id: str, project_id: str, installation_id, generation,
        execution_epoch: int, operation_key: str, idempotency_key: str,
        request_hash: str, owner_token: str, lease_until: datetime,
    ) -> RuntimeAttemptLease:
        """Claim one retry generation for an exact idempotent Store operation.

        A live or succeeded generation is never re-executed.  Only a terminal
        failed/abandoned generation permits the next ordinal, under one
        transaction advisory lock.  The caller still owns current authority
        and must commit this transaction before starting Store work.
        """
        _require_transaction(conn)
        _scope(conn, org_id, project_id)
        installation_id = _identity(installation_id, "installation id")
        generation = _identity(generation, "generation")
        if type(execution_epoch) is not int or execution_epoch < 1:
            raise ValueError("positive execution epoch required")
        if type(operation_key) is not str or not 1 <= len(operation_key) <= 160:
            raise ValueError("exact runtime operation key required")
        if type(idempotency_key) is not str or not 1 <= len(idempotency_key) <= 220:
            raise ValueError("bounded recoverable idempotency key required")
        if type(request_hash) is not str or _HASH.fullmatch(request_hash) is None:
            raise ValueError("canonical runtime request hash required")
        if not isinstance(lease_until, datetime) or lease_until.tzinfo is None:
            raise ValueError("aware runtime attempt lease required")
        owner_hash = _token_hash(owner_token)
        conn.execute(
            """SELECT pg_advisory_xact_lock(hashtextextended(
               'recoverable-runtime-attempt:'||jsonb_build_array(%s::text,%s::text,%s::uuid::text,
               %s::uuid::text,%s::bigint,%s::text)::text,0))""",
            (org_id, project_id, installation_id, generation, execution_epoch, operation_key),
        )
        rows = conn.execute(
            """SELECT attempt_id,idempotency_key,request_hash,state,revision
                 FROM extension_runtime_execution_attempt
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                  AND execution_epoch=%s AND operation_kind='recoverable_store'
                  AND operation_key=%s ORDER BY accepted_at,attempt_id FOR UPDATE""",
            (org_id, project_id, installation_id, generation, execution_epoch, operation_key),
        ).fetchall()
        columns = ("attempt_id", "idempotency_key", "request_hash", "state", "revision")
        if any(_values(row, columns)[2] != request_hash for row in rows):
            raise RuntimeConflict("recoverable runtime attempt request drifted")
        if rows:
            attempt_id, _, _, state, revision = _values(
                rows[-1], columns
            )
            if state in ("running", "succeeded"):
                return RuntimeAttemptLease(attempt_id, state, revision, False)
            if state not in ("failed", "abandoned"):
                raise RuntimeConflict("recoverable runtime attempt state differs")
        ordinal = len(rows) + 1
        stored_key = f"{idempotency_key}:{ordinal}"
        if len(stored_key) > 240:
            raise ValueError("recoverable idempotency key exceeds storage limit")
        valid_lease = conn.execute(
            "SELECT %s > clock_timestamp() AND %s <= clock_timestamp()+interval '5 minutes' AS valid",
            (lease_until, lease_until),
        ).fetchone()
        if valid_lease is None or _values(valid_lease, ("valid",))[0] is not True:
            raise ValueError("runtime attempt lease must be current and bounded")
        binding = conn.execute(
            """SELECT enabled,operation_fence,execution_epoch
                 FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                FOR SHARE""",
            (org_id, project_id, installation_id, generation),
        ).fetchone()
        if binding is None:
            raise PermissionError("runtime binding unavailable")
        enabled, fenced, current_epoch = _values(
            binding, ("enabled", "operation_fence", "execution_epoch")
        )
        if enabled is not True or fenced is not False or current_epoch != execution_epoch:
            raise PermissionError("runtime generation is not accepting attempts")
        attempt_id = uuid4()
        conn.execute(
            """INSERT INTO extension_runtime_execution_attempt
               (org_id,project_id,attempt_id,installation_id,generation,execution_epoch,
                operation_kind,operation_key,idempotency_key,request_hash,owner_token_hash,state,lease_until)
               VALUES(%s,%s,%s,%s,%s,%s,'recoverable_store',%s,%s,%s,%s,'running',%s)""",
            (org_id, project_id, attempt_id, installation_id, generation, execution_epoch,
             operation_key, stored_key, request_hash, owner_hash, lease_until),
        )
        _event(conn, org_id=org_id, project_id=project_id, attempt_id=attempt_id,
               sequence=1, event_type="attempt_accepted", state="running", revision=1)
        return RuntimeAttemptLease(attempt_id, "running", 1, True)

    def heartbeat(self, conn, *, org_id: str, project_id: str, attempt_id,
                  expected_revision: int, owner_token: str, lease_until: datetime) -> RuntimeAttemptLease:
        _require_transaction(conn)
        _scope(conn, org_id, project_id)
        attempt_id = _identity(attempt_id, "attempt id")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("positive attempt revision required")
        if not isinstance(lease_until, datetime) or lease_until.tzinfo is None:
            raise ValueError("aware runtime attempt lease required")
        row = conn.execute(
            """SELECT state,revision,owner_token_hash,lease_until,
                      lease_until>clock_timestamp() AS live
                 FROM extension_runtime_execution_attempt
                WHERE org_id=%s AND project_id=%s AND attempt_id=%s FOR UPDATE""",
            (org_id, project_id, attempt_id),
        ).fetchone()
        if row is None:
            raise LookupError("runtime attempt not found")
        state, revision, owner_hash, current_lease, live = _values(
            row, ("state", "revision", "owner_token_hash", "lease_until", "live")
        )
        if owner_hash != _token_hash(owner_token):
            raise PermissionError("runtime attempt owner token mismatch")
        if revision != expected_revision:
            raise RuntimeRevisionConflict("runtime attempt revision changed")
        if state != "running" or live is not True:
            raise RuntimeConflict("runtime attempt cannot be renewed")
        if lease_until <= current_lease:
            raise ValueError("runtime attempt lease must advance")
        valid_lease = conn.execute(
            "SELECT %s > clock_timestamp() AND %s <= clock_timestamp()+interval '5 minutes' AS valid",
            (lease_until, lease_until),
        ).fetchone()
        if valid_lease is None or _values(valid_lease, ("valid",))[0] is not True:
            raise ValueError("runtime attempt lease must be current and bounded")
        revision += 1
        conn.execute(
            """UPDATE extension_runtime_execution_attempt
                  SET lease_until=%s,heartbeat_at=clock_timestamp(),revision=%s
                WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
            (lease_until, revision, org_id, project_id, attempt_id),
        )
        _event(conn, org_id=org_id, project_id=project_id, attempt_id=attempt_id,
               sequence=revision, event_type="attempt_heartbeat", state="running", revision=revision)
        return RuntimeAttemptLease(attempt_id, "running", revision, False)

    def settle(self, conn, *, org_id: str, project_id: str, attempt_id,
               expected_revision: int, owner_token: str, state: str,
               terminal_reason_code: str | None = None,
               terminal_error_type: str | None = None) -> RuntimeAttemptLease:
        _require_transaction(conn)
        _scope(conn, org_id, project_id)
        attempt_id = _identity(attempt_id, "attempt id")
        if state not in ("succeeded", "failed"):
            raise ValueError("known runtime attempt terminal state required")
        if state == "succeeded":
            if terminal_reason_code is not None or terminal_error_type is not None:
                raise ValueError("successful runtime attempt has no terminal reason")
        elif terminal_reason_code not in _TERMINAL_REASONS:
            raise ValueError("known runtime attempt terminal reason required")
        if terminal_error_type is not None and (
            type(terminal_error_type) is not str or _ERROR_TYPE.fullmatch(terminal_error_type) is None
        ):
            raise ValueError("safe runtime attempt terminal error type required")
        if type(expected_revision) is not int or expected_revision < 1:
            raise ValueError("positive attempt revision required")
        row = conn.execute(
            """SELECT state,revision,owner_token_hash FROM extension_runtime_execution_attempt
                WHERE org_id=%s AND project_id=%s AND attempt_id=%s FOR UPDATE""",
            (org_id, project_id, attempt_id),
        ).fetchone()
        if row is None:
            raise LookupError("runtime attempt not found")
        current, revision, owner_hash = _values(row, ("state", "revision", "owner_token_hash"))
        if owner_hash != _token_hash(owner_token):
            raise PermissionError("runtime attempt owner token mismatch")
        if revision != expected_revision:
            raise RuntimeRevisionConflict("runtime attempt revision changed")
        if current != "running":
            raise RuntimeConflict("runtime attempt is already terminal")
        revision += 1
        conn.execute(
            """UPDATE extension_runtime_execution_attempt
                  SET state=%s,completed_at=clock_timestamp(),revision=%s,
                      terminal_reason_code=%s,terminal_error_type=%s
                WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
            (state, revision, terminal_reason_code, terminal_error_type,
             org_id, project_id, attempt_id),
        )
        _event(conn, org_id=org_id, project_id=project_id, attempt_id=attempt_id,
               sequence=revision, event_type="attempt_" + state, state=state, revision=revision,
               terminal_reason_code=terminal_reason_code,
               terminal_error_type=terminal_error_type)
        return RuntimeAttemptLease(attempt_id, state, revision, False)

    def abandon_expired_reads(self, conn, *, org_id: str, project_id: str, limit: int = 100) -> tuple[UUID, ...]:
        _require_transaction(conn)
        _scope(conn, org_id, project_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("attempt recovery limit must be 1..100")
        rows = conn.execute(
            """SELECT attempt_id,revision FROM extension_runtime_execution_attempt
                WHERE org_id=%s AND project_id=%s
                  AND operation_kind IN ('signed_read','recoverable_store')
                  AND state='running' AND lease_until<=clock_timestamp()
                ORDER BY attempt_id FOR UPDATE SKIP LOCKED LIMIT %s""",
            (org_id, project_id, limit),
        ).fetchall()
        result = []
        for row in rows:
            attempt_id, revision = _values(row, ("attempt_id", "revision"))
            revision += 1
            conn.execute(
                """UPDATE extension_runtime_execution_attempt
                      SET state='abandoned',completed_at=clock_timestamp(),revision=%s,
                          terminal_reason_code='ATTEMPT_LEASE_EXPIRED',terminal_error_type=NULL
                    WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                (revision, org_id, project_id, attempt_id),
            )
            _event(conn, org_id=org_id, project_id=project_id, attempt_id=attempt_id,
                   sequence=revision, event_type="attempt_abandoned", state="abandoned", revision=revision,
                   terminal_reason_code="ATTEMPT_LEASE_EXPIRED")
            result.append(attempt_id)
        return tuple(result)


class ExpiredSignedReadAttemptRecovery:
    """Tenant-scoped, bounded recovery; never replays the external read."""

    def __init__(self, *, connect) -> None:
        if not callable(connect):
            raise ValueError("trusted runtime connection factory required")
        self._connect = connect
        self._store = PostgresRuntimeAttemptStore()

    def run_once(
        self, *, org_id: str, project_id: str, limit: int = 100
    ) -> tuple[UUID, ...]:
        TenantScope(org_id, project_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("attempt recovery limit must be 1..100")
        scope = {"org_id": org_id, "project_id": project_id}
        with consumer_connection(self._connect, scope) as conn:
            require_runtime_role(
                conn,
                **scope,
                protected_tables=(
                    "extension_runtime_execution_attempt",
                    "extension_runtime_execution_attempt_event",
                ),
            )
            return self._store.abandon_expired_reads(conn, **scope, limit=limit)


class GenerationDrainReader:
    def __call__(self, conn, *, org_id: str, project_id: str, installation_id,
                 generation, fence_epoch: int) -> bool:
        _require_transaction(conn)
        _scope(conn, org_id, project_id)
        installation_id = _identity(installation_id, "installation id")
        generation = _identity(generation, "generation")
        if type(fence_epoch) is not int or fence_epoch < 2:
            raise ValueError("exact fence epoch required")
        binding = conn.execute(
            """SELECT enabled,operation_fence,execution_epoch FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                FOR SHARE""",
            (org_id, project_id, installation_id, generation),
        ).fetchone()
        if binding is None:
            raise LookupError("runtime binding not found")
        enabled, fenced, current_epoch = _values(
            binding, ("enabled", "operation_fence", "execution_epoch")
        )
        if enabled is not False or fenced is not True or current_epoch != fence_epoch:
            raise RuntimeConflict("runtime generation is not at the expected fence")
        future = conn.execute(
            """SELECT 1 FROM extension_runtime_execution_attempt
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                  AND execution_epoch>=%s LIMIT 1""",
            (org_id, project_id, installation_id, generation, fence_epoch),
        ).fetchone()
        if future is not None:
            raise RuntimeConflict("runtime attempt exists at or beyond the fence epoch")
        pending = conn.execute(
            """SELECT 1 FROM extension_runtime_execution_attempt
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND generation=%s
                  AND execution_epoch<%s AND state<>ALL(%s) LIMIT 1""",
            (org_id, project_id, installation_id, generation, fence_epoch, list(_TERMINAL)),
        ).fetchone()
        return pending is None
