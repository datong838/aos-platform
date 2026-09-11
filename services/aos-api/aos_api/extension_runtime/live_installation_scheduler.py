"""Bounded process ownership for live installation lifecycle workers."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

from .live_installation_owner import (
    LiveInstallationLifecycleOwner,
    LiveInstallationTick,
)
from .owned_control_consumer import _settled
from .pending_preparation_directory import (
    LiveInstallationOwnerFactory,
    PendingPreparationDescriptor,
    PostgresPendingPreparationDirectory,
)
from .preparation_owner import _observe


@dataclass(frozen=True, slots=True)
class LiveInstallationSchedulerTick:
    deliveries: tuple[tuple[UUID, LiveInstallationTick], ...]


class LiveInstallationScheduler:
    LIMIT = 100

    def __init__(
        self,
        *,
        directory: PostgresPendingPreparationDirectory,
        factory: LiveInstallationOwnerFactory,
    ) -> None:
        if (
            type(directory) is not PostgresPendingPreparationDirectory
            or type(factory) is not LiveInstallationOwnerFactory
            or directory.scope != factory.scope
        ):
            raise TypeError("exact same-scope live installation scheduler inputs required")
        self.directory = directory
        self.factory = factory
        self._owners: dict[UUID, LiveInstallationLifecycleOwner] = {}
        self._current_tick: asyncio.Task[LiveInstallationSchedulerTick] | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._closing = False
        self._revoking = False

    @property
    def owners(self) -> tuple[tuple[UUID, LiveInstallationLifecycleOwner], ...]:
        return tuple(sorted(self._owners.items()))

    def find_owner(self, installation_id: UUID) -> LiveInstallationLifecycleOwner | None:
        if type(installation_id) is not UUID:
            raise TypeError("exact installation identity required")
        return self._owners.get(installation_id)

    async def _run(self) -> LiveInstallationSchedulerTick:
        descriptors = await _settled(
            asyncio.to_thread(self.directory.read_descriptors)
        )
        if (
            type(descriptors) is not tuple
            or len(descriptors) > self.LIMIT
            or any(type(item) is not PendingPreparationDescriptor for item in descriptors)
        ):
            raise TypeError("bounded pending preparation descriptors required")
        for descriptor in descriptors:
            installation = descriptor.installation_id
            if installation not in self._owners:
                if len(self._owners) >= self.LIMIT:
                    raise RuntimeError("live installation owner limit exceeded")
                owner = self.factory(descriptor)
                if type(owner) is not LiveInstallationLifecycleOwner:
                    raise TypeError("live installation factory returned invalid owner")
                self._owners[installation] = owner

        deliveries = []
        for installation, owner in self.owners:
            result = await _settled(owner.run_once())
            if type(result) is not LiveInstallationTick:
                raise TypeError("live installation owner returned invalid tick")
            deliveries.append((installation, result))
        return LiveInstallationSchedulerTick(tuple(deliveries))

    async def run_once(self) -> LiveInstallationSchedulerTick:
        if self._closing or self._revoking:
            raise RuntimeError("live installation scheduler is closing")
        if self._current_tick is not None and not self._current_tick.done():
            raise RuntimeError("live installation scheduler tick already in progress")
        self._current_tick = asyncio.create_task(self._run())
        self._current_tick.add_done_callback(_observe)
        return await asyncio.shield(self._current_tick)

    async def wait_idle(self) -> LiveInstallationSchedulerTick | None:
        if self._current_tick is None:
            return None
        return await asyncio.shield(self._current_tick)

    async def revoke(
        self, installation_id: UUID, expected_owner: LiveInstallationLifecycleOwner
    ) -> None:
        if self._closing or self._revoking:
            raise RuntimeError("live installation scheduler is closing")
        if type(installation_id) is not UUID or type(expected_owner) is not LiveInstallationLifecycleOwner:
            raise TypeError("exact live installation revocation required")
        self._revoking = True
        try:
            await _settled(self.wait_idle())
            current = self._owners.get(installation_id)
            if current is not expected_owner:
                raise LookupError("live installation owner identity changed")
            del self._owners[installation_id]
            await _settled(current.stop())
        finally:
            self._revoking = False

    async def _close(self) -> None:
        original: BaseException | None = None
        try:
            await _settled(self.wait_idle())
        except BaseException as exc:
            original = exc
        owners = tuple(owner for _, owner in self.owners)
        self._owners.clear()
        for owner in owners:
            try:
                await _settled(owner.stop())
            except BaseException as exc:
                if original is None:
                    original = exc
        if original is not None:
            raise original

    async def stop(self) -> None:
        self._closing = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
            self._close_task.add_done_callback(_observe)
        await asyncio.shield(self._close_task)
