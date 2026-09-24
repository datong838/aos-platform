"""Opt-in Host lease client; never implies worker-side fencing or fleet proof."""

from __future__ import annotations

import asyncio
import inspect
from uuid import UUID, uuid4

from aos_api.tenant_scope import TenantScope


class HostLeaseBlocked(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class OptInHostLease:
    def __init__(self, *, connect, scope: TenantScope, ttl_seconds: int = 30,
                 renew_interval_seconds: int = 5):
        if (not callable(connect) or inspect.iscoroutinefunction(connect)
                or type(scope) is not TenantScope
                or type(ttl_seconds) is not int or not 5 <= ttl_seconds <= 30
                or type(renew_interval_seconds) is not int
                or not 1 <= renew_interval_seconds < ttl_seconds // 2):
            raise ValueError("exact bounded opt-in Host lease dependencies required")
        self._connect = connect
        self._scope = scope
        self._ttl = ttl_seconds
        self._interval = renew_interval_seconds
        self._token: UUID | None = None
        self._epoch: int | None = None

    def _call(self, statement: str, values: tuple):
        try:
            with self._connect() as conn:
                conn.execute("SET ROLE aos_extension_directory")
                conn.execute("SELECT set_config('aos.org_id',%s,true),"
                             "set_config('aos.project_id',%s,true)", self._scope.key)
                return conn.execute(statement, values).fetchone()
        except Exception:
            raise HostLeaseBlocked("HOST_LEASE_DATABASE_GATE_FAILED") from None

    def acquire(self) -> int:
        if self._token is not None:
            raise HostLeaseBlocked("HOST_LEASE_ALREADY_ATTEMPTED")
        token = uuid4()
        # Preserve the attempted token in memory so an unknown commit boundary
        # cannot cause an automatic second acquire in this process.
        self._token = token
        row = self._call(
            "SELECT epoch,expires_at FROM "
            "public.extension_runtime_host_lease_acquire_a0v_093(%s,%s,%s,%s)",
            (*self._scope.key, token, self._ttl),
        )
        if row is None or type(row["epoch"]) is not int or row["epoch"] < 1:
            raise HostLeaseBlocked("HOST_LEASE_ACQUIRE_READBACK_DIFFERS")
        self._epoch = row["epoch"]
        return self._epoch

    def renew(self) -> None:
        if self._token is None or self._epoch is None:
            raise HostLeaseBlocked("HOST_LEASE_NOT_ACQUIRED")
        row = self._call(
            "SELECT public.extension_runtime_host_lease_renew_a0v_093(%s,%s,%s,%s,%s) "
            "AS expires_at", (*self._scope.key, self._token, self._epoch, self._ttl),
        )
        if row is None or row["expires_at"] is None:
            raise HostLeaseBlocked("HOST_LEASE_RENEW_READBACK_DIFFERS")

    def release(self) -> None:
        if self._token is None or self._epoch is None:
            raise HostLeaseBlocked("HOST_LEASE_NOT_ACQUIRED")
        self._call(
            "SELECT public.extension_runtime_host_lease_release_a0v_093(%s,%s,%s,%s)",
            (*self._scope.key, self._token, self._epoch),
        )

    async def renew_until_stopped(self, stop_event: asyncio.Event) -> None:
        if self._epoch is None:
            raise HostLeaseBlocked("HOST_LEASE_NOT_ACQUIRED")
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self._interval)
            except TimeoutError:
                await asyncio.to_thread(self.renew)
