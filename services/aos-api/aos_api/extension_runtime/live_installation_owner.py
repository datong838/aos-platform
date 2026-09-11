"""Process-owned lifecycle delivery for one exact live installation."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from .lifecycle_store import RuntimeConflict
from .oci_driver import CleanupUncertainError
from .owned_control_consumer import OwnedControlConsumer, _settled
from .preparation_consumer import PreparationConsumer
from .preparation_owner import _observe


@dataclass(frozen=True, slots=True)
class LiveInstallationTick:
    preparation: object | None
    verification: object | None
    enablement: object | None


class LiveInstallationLifecycleOwner:
    """Retains the sole PreparedJob while delivering its ordered controls."""

    def __init__(self, *, preparation: PreparationConsumer) -> None:
        if type(preparation) is not PreparationConsumer:
            raise TypeError("exact preparation consumer required")
        self.preparation = preparation
        self._current_tick: asyncio.Task[LiveInstallationTick] | None = None
        self._close_task: asyncio.Task[None] | None = None
        self._closing = False

    def _owned(self, kind: str, job) -> OwnedControlConsumer:
        return OwnedControlConsumer(
            connect=self.preparation.connect,
            job=job,
            kind=kind,
            **self.preparation.scope,
        )

    async def _run(self) -> LiveInstallationTick:
        preparation = await _settled(self.preparation.run_once())
        job = self.preparation.job
        if job is None:
            return LiveInstallationTick(preparation, None, None)

        verifier = self._owned("runtime-verify", job)
        verification = await _settled(verifier.run_once())
        if self.preparation.job is not job:
            raise RuntimeConflict("live preparation owner changed during lifecycle tick")
        if verification is not None and verification.operation_status != "succeeded":
            return LiveInstallationTick(preparation, verification, None)

        enabler = self._owned("enable", job)
        enablement = await _settled(enabler.run_once())
        if self.preparation.job is not job:
            raise RuntimeConflict("live preparation owner changed during lifecycle tick")
        return LiveInstallationTick(preparation, verification, enablement)

    async def run_once(self) -> LiveInstallationTick:
        if self._closing:
            raise RuntimeError("live installation lifecycle owner is closing")
        if self._current_tick is not None and not self._current_tick.done():
            raise RuntimeError("live installation lifecycle tick already in progress")
        self._current_tick = asyncio.create_task(self._run())
        self._current_tick.add_done_callback(_observe)
        return await asyncio.shield(self._current_tick)

    async def wait_idle(self) -> LiveInstallationTick | None:
        if self._current_tick is None:
            return None
        return await asyncio.shield(self._current_tick)

    async def _close(self) -> None:
        original: BaseException | None = None
        try:
            await _settled(self.wait_idle())
        except BaseException as exc:
            original = exc
        try:
            await _settled(self.preparation.stop())
        except BaseException as cleanup:
            if isinstance(original, CleanupUncertainError) and original is not cleanup:
                raise original from cleanup
            raise
        if original is not None:
            raise original

    async def stop(self) -> None:
        self._closing = True
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
            self._close_task.add_done_callback(_observe)
        await asyncio.shield(self._close_task)
