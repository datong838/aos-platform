"""Process-owned runtime reconciliation host over concrete trusted workers.

The host schedules already-authorized worker objects.  It does not discover
tenants, create consumers from request data, or turn delivery into authority.
"""
from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from uuid import UUID

from aos_api.tenant_scope import TenantScope

from .configuration_consumer import ConfigurationConsumer
from .disable_consumer import RuntimeDisableConsumer
from .owned_control_consumer import _settled
from .preparation_owner import _observe
from .resource_recovery import ExpiredResourceRecovery, RecoveryPage


_SYNC_CONSUMERS = (ConfigurationConsumer, RuntimeDisableConsumer)


@dataclass(frozen=True, slots=True)
class RuntimeTenantAssignment:
    scope: TenantScope
    recovery: ExpiredResourceRecovery | None = None
    consumers: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if type(self.scope) is not TenantScope:
            raise TypeError("runtime assignment requires TenantScope")
        if self.recovery is not None and type(self.recovery) is not ExpiredResourceRecovery:
            raise TypeError("runtime assignment requires concrete recovery worker")
        if type(self.consumers) is not tuple or any(
            type(consumer) not in _SYNC_CONSUMERS for consumer in self.consumers
        ):
            raise TypeError("runtime assignment requires concrete consumers")
        kinds = tuple(
            "configure" if type(consumer) is ConfigurationConsumer else "disable"
            for consumer in self.consumers
        )
        if len(kinds) != len(set(kinds)):
            raise ValueError("duplicate runtime consumer kind")
        object.__setattr__(
            self,
            "consumers",
            tuple(
                sorted(
                    self.consumers,
                    key=lambda consumer: 0
                    if type(consumer) is ConfigurationConsumer
                    else 1,
                )
            ),
        )
        if self.recovery is None and not self.consumers:
            raise ValueError("runtime assignment has no worker")


@dataclass(frozen=True, slots=True)
class RuntimeTenantTick:
    scope: TenantScope
    recovery: RecoveryPage | None
    deliveries: tuple[object | None, ...]


@dataclass(frozen=True, slots=True)
class RuntimeHostTick:
    tenants: tuple[RuntimeTenantTick, ...]


class RuntimeHost:
    """Serial, bounded scheduler.  One failed tenant fails the current tick."""

    def __init__(self, *, assignments, recovery_page_size: int = 100) -> None:
        if not callable(assignments) or inspect.iscoroutinefunction(assignments):
            raise ValueError("trusted runtime assignment source required")
        if type(recovery_page_size) is not int or not 1 <= recovery_page_size <= 100:
            raise ValueError("recovery page size must be 1..100")
        self._assignments = assignments
        self._recovery_page_size = recovery_page_size
        self._recovery_cursors: dict[tuple[str, str], UUID | None] = {}
        self._current_tick: asyncio.Task[RuntimeHostTick] | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._closing = False

    def _current_assignments(self) -> tuple[RuntimeTenantAssignment, ...]:
        current = self._assignments()
        if inspect.isawaitable(current):
            close = getattr(current, "close", None)
            if callable(close):
                close()
            raise TypeError("runtime assignment source must be synchronous")
        if type(current) is not tuple or len(current) > 1000:
            raise TypeError("runtime assignments must be a bounded tuple")
        if any(not isinstance(item, RuntimeTenantAssignment) for item in current):
            raise TypeError("invalid runtime assignment")
        ordered = tuple(sorted(current, key=lambda item: item.scope.key))
        keys = tuple(item.scope.key for item in ordered)
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate runtime tenant assignment")
        return ordered

    async def _recover(self, assignment: RuntimeTenantAssignment) -> RecoveryPage | None:
        if assignment.recovery is None:
            return None
        key = assignment.scope.key
        cursor = self._recovery_cursors.get(key)
        page = await _settled(
            asyncio.to_thread(
                assignment.recovery.run_batch,
                org_id=assignment.scope.org_id,
                project_id=assignment.scope.project_id,
                limit=self._recovery_page_size,
                after=cursor,
            )
        )
        if not isinstance(page, RecoveryPage):
            raise TypeError("recovery worker returned an invalid page")
        self._recovery_cursors[key] = page.cursor if page.results else None
        return page

    def _contains_assignment(self, assignment: RuntimeTenantAssignment) -> bool:
        # Identity is the in-process assignment revision.  Replacing a worker
        # object for the same tenant revokes the old snapshot for this tick.
        return any(item is assignment for item in self._current_assignments())

    async def _consume(self, assignment: RuntimeTenantAssignment, consumer: object):
        return await _settled(
            asyncio.to_thread(
                consumer.run_once,
                org_id=assignment.scope.org_id,
                project_id=assignment.scope.project_id,
            )
        )

    async def _run_tick(self) -> RuntimeHostTick:
        tenants: list[RuntimeTenantTick] = []
        for assignment in self._current_assignments():
            recovery = await self._recover(assignment)
            deliveries = []
            for consumer in assignment.consumers:
                # A directory revocation after recovery closes the remainder of
                # this tenant's tick.  It never ACKs or rewrites the claim.
                if not self._contains_assignment(assignment):
                    break
                deliveries.append(await self._consume(assignment, consumer))
            tenants.append(
                RuntimeTenantTick(
                    scope=assignment.scope,
                    recovery=recovery,
                    deliveries=tuple(deliveries),
                )
            )
        return RuntimeHostTick(tuple(tenants))

    async def run_once(self) -> RuntimeHostTick:
        if self._closing:
            raise RuntimeError("runtime host is closing")
        if self._current_tick is not None and not self._current_tick.done():
            raise RuntimeError("runtime host tick already in progress")
        self._current_tick = asyncio.create_task(self._run_tick())
        self._current_tick.add_done_callback(_observe)
        return await asyncio.shield(self._current_tick)

    async def _close(self) -> None:
        if self._current_tick is not None:
            await asyncio.shield(self._current_tick)

    async def stop(self) -> None:
        self._closing = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
            self._close_task.add_done_callback(_observe)
        await asyncio.shield(self._close_task)

    async def serve(self, stop_event: asyncio.Event, *, interval_seconds: int = 5) -> None:
        if not isinstance(stop_event, asyncio.Event):
            raise TypeError("runtime host stop event required")
        if type(interval_seconds) is not int or not 1 <= interval_seconds <= 300:
            raise ValueError("runtime host interval must be 1..300 seconds")
        try:
            while not stop_event.is_set():
                await self.run_once()
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                except TimeoutError:
                    continue
        finally:
            await self.stop()
