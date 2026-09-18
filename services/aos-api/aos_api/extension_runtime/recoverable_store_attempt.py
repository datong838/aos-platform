"""Heartbeat-owned runtime drain entry for exact idempotent Store recovery."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from threading import Event, Lock, Thread

from aos_api.tenant_scope import TenantScope

from .consumer_connection import consumer_connection
from .generation_attempts import PostgresRuntimeAttemptStore, RuntimeAttemptLease
from .lifecycle_store import RuntimeConflict


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
        if self._thread is not None:
            self._thread.join(timeout=max(5.0, self._heartbeat_seconds + 5.0))
            if self._thread.is_alive():
                self._error = RuntimeConflict("recoverable Store heartbeat did not stop")
        failure = exc is not None or self._error is not None
        with self._lock:
            expected = self._lease.revision
        with consumer_connection(self._connect, dict(
            org_id=self._scope.org_id, project_id=self._scope.project_id,
        )) as conn:
            settled = PostgresRuntimeAttemptStore().settle(
                conn, org_id=self._scope.org_id, project_id=self._scope.project_id,
                attempt_id=self._lease.attempt_id, expected_revision=expected,
                owner_token=self._token, state="failed" if failure else "succeeded",
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
