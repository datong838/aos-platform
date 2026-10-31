"""Unwired, bounded original reinstall calls; native qualification is separate.

Trusted assembly only, not a Python sandbox or a permission/signature grant.
Never retry an unknown commit, or infer server cleanup from a client close.
"""
from __future__ import annotations

from collections.abc import Collection, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import math
from threading import Event, Lock, Timer, get_ident
from time import monotonic
from typing import Any

import psycopg
from psycopg.rows import dict_row

from aos_api.asset_registry.composition_store import PostgresCompositionStore
from aos_api.asset_registry.installation_service import InstallationService
from aos_api.asset_registry.installation_store import CommandReceipt, PostgresInstallationStore
from aos_api.asset_registry.reinstall_contracts import ReinstallInstallationRequest
from aos_api.asset_registry.reinstall_origin_service import ReinstallOriginService


_ATTEMPT_SECONDS = 60.0
_CANCEL_SECONDS = 1.0
_JOIN_SECONDS = 2.0
_TIMEOUT_SQL = (
    "SELECT set_config('statement_timeout', %s, true), "
    "set_config('lock_timeout', %s, true)"
)
_CURRENT: ContextVar[_AttemptBudget | None] = ContextVar("reinstall_attempt", default=None)


class ReinstallOriginAttemptError(RuntimeError):
    """Fixed safe labels; original errors remain in the cause chain."""

    def __init__(self, *, reason: str, commit_outcome: str, cleanup_outcome: str):
        super().__init__("bounded reinstall attempt failed")
        self.reason = reason
        self.commit_outcome = commit_outcome
        self.cleanup_outcome = cleanup_outcome


class _AttemptFailure(RuntimeError):
    pass


@dataclass(frozen=True, slots=True, repr=False)
class ReinstallConnectionSettings:
    host: str
    port: int
    dbname: str
    user: str
    password: str

    def __post_init__(self) -> None:
        for value in (self.host, self.dbname, self.user, self.password):
            if type(value) is not str or not value or "\x00" in value:
                raise ValueError("explicit reinstall connection settings required")
        if (not self.host.startswith("/") or "," in self.host
                or any(c.isspace() for c in self.host)
                or ".." in self.host.split("/")
                or type(self.port) is not int or not 1 <= self.port <= 65535
                or self.dbname != self.dbname.strip() or self.user != self.user.strip()):
            raise ValueError("single explicit reinstall socket endpoint required")


class _AttemptBudget:
    def __init__(self, owner: ReinstallOriginTransactions):
        self.owner = owner
        self.thread = get_ident()
        self.deadline = monotonic() + _ATTEMPT_SECONDS
        self.lock = Lock()
        self.expired = False
        self.finished = False
        self.failed = False
        self.cancel_failed = False
        self.cleanup_failed = False
        self.connections: set[_BoundedReinstallConnection] = set()
        self.active: _BoundedReinstallConnection | None = None
        self.opened = 0
        self.connecting = False
        self.commit_outcome = "not_started"
        self.timer = Timer(_ATTEMPT_SECONDS, self._expire)
        self.timer.daemon = True

    def _check_locked(self) -> None:
        if (_CURRENT.get() is not self or get_ident() != self.thread
                or self.finished or self.failed):
            raise _AttemptFailure("inactive_attempt")
        if self.expired or monotonic() >= self.deadline:
            self.expired = True
            raise _AttemptFailure("deadline")

    def check(self) -> float:
        with self.lock:
            self._check_locked()
            return self.deadline - monotonic()

    def register(self, conn: _BoundedReinstallConnection) -> None:
        with self.lock:
            self._check_locked()
            if self.connections or (self.opened and self.commit_outcome != "acknowledged"):
                raise _AttemptFailure("unexpected_connection")
            self.connections.add(conn)
            self.opened += 1

    @contextmanager
    def io(self, conn: _BoundedReinstallConnection) -> Iterator[None]:
        with self.lock:
            self._check_locked()
            if conn not in self.connections or self.active is not None:
                raise _AttemptFailure("unexpected_io")
            self.active = conn
        try:
            yield
        finally:
            with self.lock:
                self.active = None
        self.check()

    def _expire(self) -> None:
        with self.lock:
            if self.finished:
                return
            self.expired = True
            conn = self.active
            if conn is not None:
                conn._cancel_done.clear()
        if conn is not None:
            try:
                # Pre-connect capability check prevents old-libpq blocking fallback.
                psycopg.Connection.cancel_safe(conn, timeout=_CANCEL_SECONDS)
            except BaseException:
                with self.lock:
                    self.cancel_failed = True
            finally:
                conn._cancel_done.set()

    def close_connection(self, conn: _BoundedReinstallConnection) -> None:
        if not conn._cancel_done.wait(_JOIN_SECONDS):
            self.cleanup_failed = True
            return
        try:
            # A close is not a rollback/durability or server lock-release proof.
            psycopg.Connection.close(conn)
            if not conn.closed:
                raise _AttemptFailure("close_unconfirmed")
        except BaseException:
            self.cleanup_failed = True
            raise
        finally:
            if conn.closed:
                with self.lock:
                    self.connections.discard(conn)

    def stop(self) -> None:
        with self.lock:
            self.finished = True
        self.timer.cancel()
        self.timer.join(_JOIN_SECONDS)
        if self.timer.is_alive() or self.connections:
            self.cleanup_failed = True
        if monotonic() >= self.deadline:
            self.expired = True


class _BoundedReinstallConnection(psycopg.Connection):
    @classmethod
    def connect(cls, conninfo="", **kwargs):
        budget = _CURRENT.get()
        if budget is None:
            raise _AttemptFailure("missing_attempt")
        budget.check()
        if not budget.connecting or conninfo != "":
            raise _AttemptFailure("explicit_factory_required")
        return super().connect(conninfo, **kwargs)

    def __init__(self, pgconn, row_factory=dict_row):
        budget = _CURRENT.get()
        # Take ownership before a deadline/registration check can raise.
        super().__init__(pgconn, row_factory=row_factory)
        try:
            if budget is None:
                raise _AttemptFailure("missing_attempt")
            budget.check()
            self._budget = budget
            self._cancel_done = Event()
            self._cancel_done.set()
            self._postcommit_read = budget.opened > 0
            self.cursor_factory = _BoundedReinstallCursor
            budget.register(self)
        except BaseException:
            try:
                psycopg.Connection.close(self)
            except BaseException:
                if budget is not None:
                    budget.cleanup_failed = True
                raise
            raise

    def cursor(self, name="", *, binary=False, row_factory=None, scrollable=None,
               withhold=False):
        self._budget.check()
        if (type(name) is not str or name or scrollable is not None or withhold
                or row_factory not in (None, dict_row)
                or self.cursor_factory is not _BoundedReinstallCursor):
            raise _AttemptFailure("unsupported_channel")
        return super().cursor(binary=binary, row_factory=row_factory)

    def commit(self) -> None:
        budget = self._budget
        with budget.io(self):
            with budget.lock:
                if self._postcommit_read or budget.commit_outcome != "not_started":
                    raise _AttemptFailure("unexpected_commit")
                # Once native commit begins, any error is conservatively unknown.
                budget.commit_outcome = "unknown"
            super().commit()
            with budget.lock:
                budget.commit_outcome = "acknowledged"

    def rollback(self) -> None:
        if self._budget.commit_outcome == "unknown":
            raise _AttemptFailure("unknown_commit")
        with self._budget.io(self):
            super().rollback()

    def close(self) -> None:
        self._budget.close_connection(self)

    def __enter__(self):
        raise _AttemptFailure("native_context_not_allowed")

    def __exit__(self, *args):
        raise _AttemptFailure("native_context_not_allowed")

    def _unsupported(self, *args, **kwargs):
        raise _AttemptFailure("unsupported_channel")

    transaction = pipeline = tpc_begin = tpc_prepare = _unsupported
    tpc_commit = tpc_rollback = tpc_recover = _unsupported
    set_autocommit = set_read_only = set_deferrable = set_isolation_level = _unsupported


class _BoundedReinstallCursor(psycopg.Cursor):
    def __init__(self, connection, *, row_factory=None):
        if type(connection) is not _BoundedReinstallConnection:
            raise _AttemptFailure("exact_connection_required")
        connection._budget.check()
        super().__init__(connection, row_factory=row_factory)

    def execute(self, query, params=None, *, prepare=None, binary=None):
        conn = self.connection
        budget = conn._budget
        with budget.io(conn):
            remaining = budget.check()
            milliseconds = max(1, math.floor(remaining * 1000))
            # Base cursor: exactly one non-recursive fixed control round trip.
            control = psycopg.Cursor(conn, row_factory=dict_row)
            try:
                control.execute(_TIMEOUT_SQL, (str(min(10000, milliseconds)),
                                               str(min(1000, milliseconds))))
            finally:
                control.close()
            budget.check()
            super().execute(query, params, prepare=prepare, binary=binary)
        return self

    def fetchone(self):
        with self.connection._budget.io(self.connection):
            result = super().fetchone()
        return result

    def fetchmany(self, size=0):
        with self.connection._budget.io(self.connection):
            result = super().fetchmany(size)
        return result

    def fetchall(self):
        with self.connection._budget.io(self.connection):
            result = super().fetchall()
        return result

    def __iter__(self):
        while (row := self.fetchone()) is not None:
            yield row

    def _unsupported(self, *args, **kwargs):
        raise _AttemptFailure("unsupported_channel")

    copy = stream = executemany = nextset = _unsupported


class ReinstallOriginTransactions:
    """Explicit trusted assembly, never a default application connection factory."""

    def __init__(self, settings: ReinstallConnectionSettings):
        if type(settings) is not ReinstallConnectionSettings:
            raise ValueError("exact reinstall connection settings required")
        self._settings = settings

    @contextmanager
    def connection_factory(self):
        budget = _CURRENT.get()
        if budget is None or budget.owner is not self:
            raise _AttemptFailure("missing_attempt")
        remaining = budget.check()
        with budget.lock:
            if (budget.connections or budget.connecting
                    or (budget.opened and budget.commit_outcome != "acknowledged")):
                raise _AttemptFailure("unexpected_connection")
        if not psycopg.capabilities.has_cancel_safe():
            raise _AttemptFailure("bounded_cancel_unavailable")
        timeout = math.floor(min(5.0, remaining))
        if timeout < 2:
            raise _AttemptFailure("connect_budget")
        milliseconds = max(1, math.floor(remaining * 1000))
        options = (f"-c statement_timeout={min(10000, milliseconds)} "
                   f"-c lock_timeout={min(1000, milliseconds)}")
        if budget.opened:
            options += " -c default_transaction_read_only=on"
        settings = self._settings
        # No conninfo, environment lookup, service file, default DSN or pool.
        with budget.lock:
            budget.connecting = True
        try:
            conn = _BoundedReinstallConnection.connect(
                host=settings.host, port=settings.port, dbname=settings.dbname,
                user=settings.user, password=settings.password, passfile="/dev/null",
                connect_timeout=timeout, options=options, autocommit=False,
                row_factory=dict_row, cursor_factory=_BoundedReinstallCursor,
            )
        except BaseException:
            budget.failed = True
            # Native connect may fail after cls(pgconn) registered ownership but
            # before returning rv. No connection was yielded to a caller yet.
            for registered in tuple(budget.connections):
                try:
                    budget.close_connection(registered)
                except BaseException:
                    # Preserve the primary connect exception; never retry close
                    # or pretend that a client-side failure proves rollback.
                    budget.cleanup_failed = True
            raise
        finally:
            with budget.lock:
                budget.connecting = False
        error = None
        try:
            budget.check()
            if type(conn) is not _BoundedReinstallConnection or conn._budget is not budget:
                raise _AttemptFailure("exact_connection_required")
            yield conn
        except BaseException as exc:
            error = exc
            raise
        finally:
            try:
                # Do not issue cleanup SQL after expiry, failure or unknown commit.
                if (not budget.expired and monotonic() < budget.deadline
                        and budget.commit_outcome != "unknown" and not conn.broken):
                    conn.rollback()
            except BaseException:
                budget.cleanup_failed = True
                if error is None:
                    raise
            finally:
                try:
                    budget.close_connection(conn)
                except BaseException:
                    if error is None:
                        raise
                finally:
                    if error is not None or budget.cleanup_failed:
                        budget.failed = True
            if budget.cleanup_failed and error is None:
                raise _AttemptFailure("cleanup_unconfirmed")

    def _matches_factory(self, factory) -> bool:
        return (getattr(factory, "__self__", None) is self
                and getattr(factory, "__func__", None)
                is ReinstallOriginTransactions.connection_factory)

    def bind(self, service: ReinstallOriginService) -> ReinstallOriginExecutor:
        if type(service) is not ReinstallOriginService:
            raise ValueError("original reinstall graph required")
        store, installation = service._store, service._installation_service
        if (type(store) is not PostgresInstallationStore
                or type(installation) is not InstallationService
                or installation._store is not store
                or type(installation._composition_store) is not PostgresCompositionStore
                or not self._matches_factory(store._connect_factory)
                or not self._matches_factory(installation._composition_store._connect_factory)):
            raise ValueError("original reinstall graph required")
        return ReinstallOriginExecutor(self, service)


class ReinstallOriginExecutor:
    """Same original service signature and receipt, with a per-call root budget."""

    def __init__(self, owner: ReinstallOriginTransactions, service: ReinstallOriginService):
        if type(owner) is not ReinstallOriginTransactions or type(service) is not ReinstallOriginService:
            raise ValueError("exact original reinstall assembly required")
        self._owner = owner
        self._service = service

    def reinstall(
        self, *, installation_id: str,
        request: ReinstallInstallationRequest | dict[str, Any],
        org_id: str, project_id: str, actor: str,
        roles: Collection[str], markings: Collection[str],
        idempotency_key: str | None, if_match: str | None,
    ) -> CommandReceipt:
        if _CURRENT.get() is not None:
            raise ReinstallOriginAttemptError(reason="nested_attempt",
                commit_outcome="not_started", cleanup_outcome="not_opened")
        budget = _AttemptBudget(self._owner)
        context_token = _CURRENT.set(budget)
        error: BaseException | None = None
        result = None
        started = False
        try:
            # Recheck mutable assembly before every invocation, not only at bind.
            self._owner.bind(self._service)
            budget.timer.start()
            started = True
            budget.check()
            result = self._service.reinstall(
                installation_id=installation_id, request=request,
                org_id=org_id, project_id=project_id, actor=actor,
                roles=roles, markings=markings,
                idempotency_key=idempotency_key, if_match=if_match,
            )
            budget.check()
            if type(result) is not CommandReceipt:
                raise _AttemptFailure("exact_receipt_required")
        except BaseException as exc:
            error = exc
        finally:
            try:
                if started:
                    budget.stop()
            except BaseException as exc:
                budget.cleanup_failed = True
                if error is None:
                    error = exc
            finally:
                _CURRENT.reset(context_token)
        if error is not None and not isinstance(error, Exception):
            raise error
        if error is not None or budget.expired or budget.cancel_failed or budget.cleanup_failed:
            reason = ("deadline" if budget.expired else
                      "cleanup" if budget.cleanup_failed or budget.cancel_failed else
                      "original_call_failed")
            failure = ReinstallOriginAttemptError(
                reason=reason, commit_outcome=budget.commit_outcome,
                cleanup_outcome="unconfirmed" if budget.cleanup_failed else
                                "closed" if budget.opened else "not_opened",
            )
            raise failure from error
        return result
