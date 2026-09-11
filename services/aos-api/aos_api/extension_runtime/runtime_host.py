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
from .disable_consumer import ClaimedDisableDelivery, RuntimeDisableConsumer
from .generation_attempts import ExpiredSignedReadAttemptRecovery
from .owned_control_consumer import _settled
from .preparation_owner import _observe
from .resource_recovery import ExpiredResourceRecovery, RecoveryPage
from .live_installation_scheduler import (
    LiveInstallationScheduler,
    LiveInstallationSchedulerTick,
)


_SYNC_CONSUMERS = (ConfigurationConsumer, RuntimeDisableConsumer)


@dataclass(frozen=True, slots=True)
class RuntimeTenantAssignment:
    scope: TenantScope
    recovery: ExpiredResourceRecovery | None = None
    attempt_recovery: ExpiredSignedReadAttemptRecovery | None = None
    lifecycle: LiveInstallationScheduler | None = None
    consumers: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if type(self.scope) is not TenantScope:
            raise TypeError("runtime assignment requires TenantScope")
        if self.recovery is not None and type(self.recovery) is not ExpiredResourceRecovery:
            raise TypeError("runtime assignment requires concrete recovery worker")
        if (
            self.attempt_recovery is not None
            and type(self.attempt_recovery) is not ExpiredSignedReadAttemptRecovery
        ):
            raise TypeError("runtime assignment requires concrete attempt recovery worker")
        if self.lifecycle is not None and (
            type(self.lifecycle) is not LiveInstallationScheduler
            or self.lifecycle.directory.scope != self.scope
        ):
            raise TypeError("runtime assignment requires same-scope lifecycle scheduler")
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
        if (self.recovery is None and self.attempt_recovery is None
                and self.lifecycle is None and not self.consumers):
            raise ValueError("runtime assignment has no worker")


@dataclass(frozen=True, slots=True)
class RuntimeTenantTick:
    scope: TenantScope
    recovery: RecoveryPage | None
    recovered_attempts: tuple[UUID, ...]
    lifecycle: LiveInstallationSchedulerTick | None
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
        self._lifecycles: dict[int, tuple[RuntimeTenantAssignment, LiveInstallationScheduler]] = {}
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
        if any(type(item) is not RuntimeTenantAssignment for item in current):
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

    async def _retire_assignment(self, assignment: RuntimeTenantAssignment) -> None:
        owned=self._lifecycles.pop(id(assignment),None)
        if owned is not None:
            await _settled(owned[1].stop())

    async def _still_current(self, assignment: RuntimeTenantAssignment) -> bool:
        if self._contains_assignment(assignment):return True
        await self._retire_assignment(assignment)
        return False

    async def _synchronize_lifecycles(
        self, assignments: tuple[RuntimeTenantAssignment, ...]
    ) -> None:
        current={id(item) for item in assignments}
        stale=tuple(value for key,value in self._lifecycles.items() if key not in current)
        for assignment,_ in stale:
            await self._retire_assignment(assignment)
        for assignment in assignments:
            if assignment.lifecycle is not None:
                self._lifecycles[id(assignment)]=(assignment,assignment.lifecycle)

    async def _consume(self, assignment: RuntimeTenantAssignment, consumer: object):
        if type(consumer) is RuntimeDisableConsumer and assignment.lifecycle is not None:
            claimed=await _settled(asyncio.to_thread(
                consumer.claim_once,org_id=assignment.scope.org_id,
                project_id=assignment.scope.project_id))
            if claimed is None:return None
            if type(claimed) is not ClaimedDisableDelivery:
                raise TypeError("disable consumer returned invalid claim")
            owner=assignment.lifecycle.find_owner(claimed.installation_id)
            if owner is not None:
                await _settled(assignment.lifecycle.revoke(claimed.installation_id,owner))
            if not await self._still_current(assignment):return None
            return await _settled(asyncio.to_thread(consumer.finish_claimed,claimed))
        return await _settled(
            asyncio.to_thread(
                consumer.run_once,
                org_id=assignment.scope.org_id,
                project_id=assignment.scope.project_id,
            )
        )

    async def _recover_attempts(
        self, assignment: RuntimeTenantAssignment
    ) -> tuple[UUID, ...]:
        if assignment.attempt_recovery is None:
            return ()
        result = await _settled(
            asyncio.to_thread(
                assignment.attempt_recovery.run_once,
                org_id=assignment.scope.org_id,
                project_id=assignment.scope.project_id,
            )
        )
        if type(result) is not tuple or any(type(item) is not UUID for item in result):
            raise TypeError("attempt recovery returned an invalid result")
        return result

    async def _run_tick(self) -> RuntimeHostTick:
        tenants: list[RuntimeTenantTick] = []
        assignments=self._current_assignments()
        await self._synchronize_lifecycles(assignments)
        for assignment in assignments:
            recovery = await self._recover(assignment)
            recovered_attempts: tuple[UUID, ...] = ()
            if await self._still_current(assignment):
                recovered_attempts = await self._recover_attempts(assignment)
            lifecycle=None
            if assignment.lifecycle is not None and await self._still_current(assignment):
                lifecycle=await _settled(assignment.lifecycle.run_once())
            deliveries = []
            current=await self._still_current(assignment)
            for consumer in assignment.consumers if current else ():
                # A directory revocation after recovery closes the remainder of
                # this tenant's tick.  It never ACKs or rewrites the claim.
                if not await self._still_current(assignment):
                    break
                deliveries.append(await self._consume(assignment, consumer))
            tenants.append(
                RuntimeTenantTick(
                    scope=assignment.scope,
                    recovery=recovery,
                    recovered_attempts=recovered_attempts,
                    lifecycle=lifecycle,
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
        original=None
        try:
            if self._current_tick is not None:
                await asyncio.shield(self._current_tick)
        except BaseException as exc:original=exc
        owned=tuple(self._lifecycles.values())
        self._lifecycles.clear()
        for _,scheduler in owned:
            try:await _settled(scheduler.stop())
            except BaseException as exc:
                if original is None:original=exc
        if original is not None:raise original

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
