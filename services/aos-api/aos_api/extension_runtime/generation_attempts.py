"""Durable generation attempts and the fail-closed drain authority."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re
from uuid import UUID, uuid4

from .lifecycle_store import RuntimeConflict, RuntimeRevisionConflict, _require_transaction, _values

_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_TERMINAL = ("succeeded", "failed", "abandoned")


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
           event_type: str, state: str, revision: int) -> None:
    conn.execute(
        """INSERT INTO extension_runtime_execution_attempt_event
           (org_id,project_id,attempt_id,sequence,event_id,type,state,revision)
           VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
        (org_id, project_id, attempt_id, sequence, uuid4(), event_type, state, revision),
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
               expected_revision: int, owner_token: str, state: str) -> RuntimeAttemptLease:
        _require_transaction(conn)
        _scope(conn, org_id, project_id)
        attempt_id = _identity(attempt_id, "attempt id")
        if state not in ("succeeded", "failed"):
            raise ValueError("known runtime attempt terminal state required")
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
                  SET state=%s,completed_at=clock_timestamp(),revision=%s
                WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
            (state, revision, org_id, project_id, attempt_id),
        )
        _event(conn, org_id=org_id, project_id=project_id, attempt_id=attempt_id,
               sequence=revision, event_type="attempt_" + state, state=state, revision=revision)
        return RuntimeAttemptLease(attempt_id, state, revision, False)

    def abandon_expired_reads(self, conn, *, org_id: str, project_id: str, limit: int = 100) -> tuple[UUID, ...]:
        _require_transaction(conn)
        _scope(conn, org_id, project_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("attempt recovery limit must be 1..100")
        rows = conn.execute(
            """SELECT attempt_id,revision FROM extension_runtime_execution_attempt
                WHERE org_id=%s AND project_id=%s AND operation_kind='signed_read'
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
                      SET state='abandoned',completed_at=clock_timestamp(),revision=%s
                    WHERE org_id=%s AND project_id=%s AND attempt_id=%s""",
                (revision, org_id, project_id, attempt_id),
            )
            _event(conn, org_id=org_id, project_id=project_id, attempt_id=attempt_id,
                   sequence=revision, event_type="attempt_abandoned", state="abandoned", revision=revision)
            result.append(attempt_id)
        return tuple(result)


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
