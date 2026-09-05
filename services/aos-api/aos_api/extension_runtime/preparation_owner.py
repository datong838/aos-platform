"""Internal preparation ownership, not a durable dispatcher or business capability."""
import asyncio
from contextlib import AsyncExitStack
import math
from datetime import datetime, timezone

from .journaled_session import _settle
from .oci_driver import CleanupUncertainError


def _observe(future):
    if not future.cancelled():
        future.exception()


class PreparationOwner:
    """Trusted worker owns this object; request cancellation only cancels its wait.

    Factories must be signed, journaled contexts. commit must settle any database
    thread before propagating cancellation. No session escapes this owner.
    """
    def __init__(self, factories, commit, *, lease_seconds):
        factories = tuple(factories)
        if (not 1 <= len(factories) <= 64 or not all(callable(f) for f in factories)
                or not callable(commit) or isinstance(lease_seconds, bool)
                or not isinstance(lease_seconds, (int, float))
                or not math.isfinite(lease_seconds) or not 0 < lease_seconds <= 300):
            raise ValueError("bounded trusted preparation inputs required")
        self._ready = asyncio.get_running_loop().create_future()
        self._ready.add_done_callback(_observe)
        self._started = False
        self._cleaning = False
        self._sessions = []
        self._verification = None
        self._task = asyncio.create_task(self._run(factories, commit, lease_seconds))
        self._task.add_done_callback(_observe)
        self._stopping = False

    async def _run(self, factories, commit, lease_seconds):
        children = []
        try:
            self._started = True
            if self._stopping:
                raise asyncio.CancelledError
            async with AsyncExitStack() as stack:
                try:
                    async with asyncio.timeout(lease_seconds):
                        for factory in factories:
                            session = await stack.enter_async_context(factory())
                            self._sessions.append(session)
                            children.append(asyncio.create_task(session.process.wait()))
                        committing = asyncio.create_task(commit())
                        children.append(committing)
                        done, _ = await asyncio.wait(children, return_when=asyncio.FIRST_COMPLETED)
                        if any(child in done for child in children[:-1]):
                            raise RuntimeError("preparation process exited")
                        result = committing.result()
                        self._ready.set_result(result)
                        await asyncio.wait(children[:-1], return_when=asyncio.FIRST_COMPLETED)
                        raise RuntimeError("preparation process exited")
                finally:
                    # Leave the lease timer before draining a committing DB
                    # thread. A second cancellation must not orphan its result.
                    self._cleaning = True
                    if self._verification is not None:
                        children.append(self._verification)
                    for child in children:
                        child.cancel()
                    results, _ = await _settle(asyncio.gather(*children, return_exceptions=True))
                    uncertain = next((r for r in results if isinstance(r, CleanupUncertainError)), None)
                    if uncertain is not None:
                        raise uncertain
                    for result in results:
                        if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                            raise result
        except asyncio.CancelledError:
            if not self._ready.done():
                self._ready.set_exception(RuntimeError("preparation stopped before commit"))
        except BaseException as exc:
            if not self._ready.done():
                self._ready.set_exception(exc)
            raise
        finally:
            self._sessions.clear()

    async def check_health(self):
        try:
            await self._check_health()
        except BaseException as original:
            try:
                await self.stop()
            except BaseException as stopping_error:
                if isinstance(original, CleanupUncertainError) and original is not stopping_error:
                    raise original from stopping_error
                raise
            raise

    async def _check_health(self):
        await self.prepared()
        if self._stopping or self._cleaning or self._task.done():
            raise RuntimeError('preparation is no longer owned')
        checks=[asyncio.create_task(session.check_health()) for session in self._sessions]
        try:
            await asyncio.gather(*checks)
            if self._stopping or self._cleaning or self._task.done():
                raise RuntimeError('preparation closed during health check')
        except BaseException as original:
            for check in checks:check.cancel()
            results, _ = await _settle(asyncio.gather(*checks,return_exceptions=True))
            uncertain = next((error for error in [original, *results]
                              if isinstance(error, CleanupUncertainError)), None)
            if uncertain is not None and uncertain is not original:
                raise uncertain from original
            raise

    async def verify(self, commit):
        """Trusted callback must settle DB work before propagating cancellation."""
        await self.prepared()
        if (self._stopping or self._cleaning or self._task.done()
                or self._verification is not None):
            raise RuntimeError('verification requires exclusive live ownership')
        if not callable(commit):
            raise TypeError('trusted verification callback required')
        async def execute():
            await self._check_health()
            return await commit(datetime.now(timezone.utc))
        # No await between admission check and registration. Closing sees this
        # task and settles it before the resource contexts leave.
        self._verification = asyncio.create_task(execute())
        def supervised(task):
            failed = task.cancelled() or task.exception() is not None
            if failed and not self._cleaning and not self._task.done():
                self._stopping = True
                self._task.cancel()
        self._verification.add_done_callback(supervised)
        return await asyncio.shield(self._verification)

    async def prepared(self):
        return await asyncio.shield(self._ready)

    async def wait_closed(self):
        return await asyncio.shield(self._task)

    async def stop(self):
        if not self._stopping:
            self._stopping = True
            if self._started and not self._cleaning:
                self._task.cancel()
        cancelled = False
        while not self._task.done():
            try:
                await asyncio.shield(self._task)
            except asyncio.CancelledError:
                cancelled = True
        self._task.result()
        if cancelled:
            raise asyncio.CancelledError
