"""Heartbeat-owned runtime drain entry for exact idempotent Store recovery."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import secrets
from threading import Event, Lock, Thread
from time import monotonic

from aos_api.tenant_scope import TenantScope

from .consumer_connection import consumer_connection
from .generation_attempts import PostgresRuntimeAttemptStore, RuntimeAttemptLease
from .lifecycle_store import RuntimeConflict


def _error_type(error: BaseException | None) -> str:
    name = type(error).__name__ if error is not None else "RuntimeConflict"
    return name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,159}", name) else "Exception"


def _terminal_failure(exc: BaseException | None, heartbeat_error: BaseException | None,
                      heartbeat_stopped: bool) -> tuple[str, str]:
    if not heartbeat_stopped:
        return "RECOVERABLE_HEARTBEAT_STOP_TIMEOUT", "RuntimeConflict"
    if heartbeat_error is not None:
        return "RECOVERABLE_HEARTBEAT_FAILED", _error_type(heartbeat_error)
    error_type = _error_type(exc)
    code = str(exc) if exc is not None else ""
    if code == "INGRESS_CANCELLED":
        return "RECOVERABLE_INGRESS_CANCELLED", error_type
    if code == "INGRESS_DEADLINE_EXCEEDED":
        return "RECOVERABLE_INGRESS_DEADLINE_EXCEEDED", error_type
    return "RECOVERABLE_EXECUTION_EXCEPTION", error_type


class _CombinedCancelEvent:
    """Event-compatible view that fails closed when either owner stops."""

    def __init__(self, *events) -> None:
        self._events = events

    def is_set(self) -> bool:
        return any(event.is_set() for event in self._events)

    def wait(self, timeout: float | None = None) -> bool:
        if self.is_set():
            return True
        deadline = None if timeout is None else monotonic() + max(0.0, timeout)
        while deadline is None or monotonic() < deadline:
            remaining = None if deadline is None else max(0.0, deadline - monotonic())
            self._events[0].wait(.05 if remaining is None else min(.05, remaining))
            if self.is_set():
                return True
        return self.is_set()


class RecoverableStoreAttempt:
    def __init__(self, *, connect, scope: TenantScope, lease: RuntimeAttemptLease,
                 owner_token: str, heartbeat_seconds: float, lease_seconds: float) -> None:
        if not lease.execute_once or lease.state != "running":
            raise RuntimeConflict("recoverable Store attempt is not executable")
        self._connect = connect
        self._scope = scope
        self._lease = lease
        self._token = owner_token
        self._heartbeat_seconds = heartbeat_seconds
        self._lease_seconds = lease_seconds
        self._stop = Event()
        self._lock = Lock()
        self._error: BaseException | None = None
        self._thread: Thread | None = None

    @property
    def attempt_id(self):
        return self._lease.attempt_id

    def cancellation(self, caller_event=None):
        """Combine caller shutdown with loss of the attempt heartbeat Lease."""
        if caller_event is None:
            return self._stop
        return _CombinedCancelEvent(self._stop, caller_event)

    def _heartbeat(self) -> None:
        store = PostgresRuntimeAttemptStore()
        while not self._stop.wait(self._heartbeat_seconds):
            try:
                with self._lock:
                    expected = self._lease.revision
                deadline = datetime.now(timezone.utc) + timedelta(seconds=self._lease_seconds)
                with consumer_connection(self._connect, dict(
                    org_id=self._scope.org_id, project_id=self._scope.project_id,
                )) as conn:
                    renewed = store.heartbeat(
                        conn, org_id=self._scope.org_id, project_id=self._scope.project_id,
                        attempt_id=self._lease.attempt_id, expected_revision=expected,
                        owner_token=self._token, lease_until=deadline,
                    )
                with self._lock:
                    if self._lease.revision != expected:
                        raise RuntimeConflict("recoverable Store attempt revision raced")
                    self._lease = renewed
            except BaseException as exc:
                self._error = exc
                self._stop.set()
                return

    def __enter__(self):
        if self._thread is not None:
            raise RuntimeConflict("recoverable Store attempt already started")
        self._thread = Thread(
            target=self._heartbeat,
            name=f"aos-store-attempt-{self._lease.attempt_id}",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self._stop.set()
        heartbeat_stopped = True
        if self._thread is not None:
            self._thread.join(timeout=max(5.0, self._heartbeat_seconds + 5.0))
            if self._thread.is_alive():
                heartbeat_stopped = False
                self._error = RuntimeConflict("recoverable Store heartbeat did not stop")
        failure = exc is not None or self._error is not None
        reason = error_type = None
        if failure:
            reason, error_type = _terminal_failure(exc, self._error, heartbeat_stopped)
        with self._lock:
            expected = self._lease.revision
        with consumer_connection(self._connect, dict(
            org_id=self._scope.org_id, project_id=self._scope.project_id,
        )) as conn:
            settled = PostgresRuntimeAttemptStore().settle(
                conn, org_id=self._scope.org_id, project_id=self._scope.project_id,
                attempt_id=self._lease.attempt_id, expected_revision=expected,
                owner_token=self._token, state="failed" if failure else "succeeded",
                terminal_reason_code=reason, terminal_error_type=error_type,
            )
        with self._lock:
            self._lease = settled
        if exc is None and self._error is not None:
            raise RuntimeConflict("recoverable Store heartbeat failed") from self._error
        return False


class RecoverableStoreAttemptOwner:
    """Create one committed attempt handle; caller starts it only after commit."""

    def __init__(self, *, connect, heartbeat_seconds: float = 30.0,
                 lease_seconds: float = 120.0) -> None:
        if not callable(connect):
            raise TypeError("trusted runtime connection factory required")
        if not 0.05 <= heartbeat_seconds < lease_seconds <= 300.0:
            raise ValueError("bounded recoverable Store heartbeat required")
        self._connect = connect
        self._heartbeat_seconds = heartbeat_seconds
        self._lease_seconds = lease_seconds

    def claim(self, conn, *, scope: TenantScope, installation_id, generation,
              execution_epoch: int, operation_key: str, idempotency_key: str,
              request_hash: str) -> RecoverableStoreAttempt:
        if type(scope) is not TenantScope:
            raise TypeError("exact recoverable Store tenant required")
        token = secrets.token_urlsafe(48)
        deadline = datetime.now(timezone.utc) + timedelta(seconds=self._lease_seconds)
        lease = PostgresRuntimeAttemptStore().begin_recoverable_store(
            conn, org_id=scope.org_id, project_id=scope.project_id,
            installation_id=installation_id, generation=generation,
            execution_epoch=execution_epoch, operation_key=operation_key,
            idempotency_key=idempotency_key, request_hash=request_hash,
            owner_token=token, lease_until=deadline,
        )
        if not lease.execute_once:
            raise RuntimeConflict(
                "recoverable Store attempt is already active or completed"
            )
        return RecoverableStoreAttempt(
            connect=self._connect, scope=scope, lease=lease, owner_token=token,
            heartbeat_seconds=self._heartbeat_seconds, lease_seconds=self._lease_seconds,
        )


__all__ = ["RecoverableStoreAttempt", "RecoverableStoreAttemptOwner"]
