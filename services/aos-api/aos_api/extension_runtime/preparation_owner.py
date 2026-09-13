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
    def __init__(self, factories, commit, *, lease_seconds, health_clock=None):
        factories = tuple(factories)
        if (not 1 <= len(factories) <= 64 or not all(callable(f) for f in factories)
                or not callable(commit) or (health_clock is not None and not callable(health_clock))
                or isinstance(lease_seconds, bool)
                or not isinstance(lease_seconds, (int, float))
                or not math.isfinite(lease_seconds) or not 0 < lease_seconds <= 300):
            raise ValueError("bounded trusted preparation inputs required")
        self._health_clock = health_clock
        self._ready = asyncio.get_running_loop().create_future()
        self._ready.add_done_callback(_observe)
        self._started = False
        self._cleaning = False
        self._sessions = []
        self._invocations = set()
        self._invocation_lock = asyncio.Lock()
        self._verification = None
        self._control = None
        self._lease_timer = None
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
                    async with asyncio.timeout(lease_seconds) as lease_timer:
                        self._lease_timer = lease_timer
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
                    if self._control is not None:
                        children.append(self._control)
                    children.extend(self._invocations)
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

    async def _health_observation(self):
        if self._health_clock is None:
            await self._check_health()
            return datetime.now(timezone.utc)
        # Anchor before probing: probe and transaction latency consume freshness.
        observed = await self._health_clock()
        if not isinstance(observed, datetime) or observed.utcoffset() is None:
            raise ValueError('trusted database health clock required')
        await self._check_health()
        return observed

    async def verify(self, commit):
        """Trusted callback must settle DB work before propagating cancellation."""
        await self.prepared()
        if (self._stopping or self._cleaning or self._task.done()
                or self._verification is not None):
            raise RuntimeError('verification requires exclusive live ownership')
        if not callable(commit):
            raise TypeError('trusted verification callback required')
        async def execute():
            observed = await self._health_observation()
            return await commit(observed)
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

    async def control(self, commit):
        """Serialize trusted post-verification commits while retaining resources.

        The callback must settle DB work before propagating cancellation, just
        like verify. This is ownership, not authorization to enable a binding.
        """
        await self.prepared()
        verification = self._verification
        previous = self._control
        if (self._stopping or self._cleaning or self._task.done()
                or verification is None or not verification.done()
                or verification.cancelled() or verification.exception() is not None
                or (previous is not None and (not previous.done()
                    or previous.cancelled() or previous.exception() is not None))):
            raise RuntimeError('control requires exclusive verified live ownership')
        if not callable(commit):
            raise TypeError('trusted control callback required')

        async def execute():
            observed = await self._health_observation()
            return await commit(observed)

        # Admission and registration are indivisible on this event loop. Keep
        # only the latest task; failed tasks can never be replaced.
        task = asyncio.create_task(execute())
        self._control = task

        def supervised(done):
            failed = done.cancelled() or done.exception() is not None
            if failed and not self._cleaning and not self._task.done():
                self._stopping = True
                self._task.cancel()

        task.add_done_callback(supervised)
        return await asyncio.shield(task)

    async def renew(self, commit):
        """Extend only after verified ownership and a settled durable lease commit.

        The trusted callback returns the DB expiry, never a requested duration.
        A cancelled/expired owner cannot be revived by a late database result.
        """
        if not callable(commit):
            raise TypeError('trusted lease commit required')
        async def execute(observed):
            expires = await commit(observed)
            if not isinstance(expires, datetime) or expires.utcoffset() is None:
                raise ValueError('durable lease expiry required')
            remaining = (expires - datetime.now(timezone.utc)).total_seconds()
            timer = self._lease_timer
            if (not 0 < remaining <= 300 or timer is None or timer.expired()
                    or self._stopping or self._cleaning or self._task.done()):
                raise RuntimeError('lease cannot renew a closed or expired owner')
            timer.reschedule(asyncio.get_running_loop().time() + remaining)
            return expires
        return await self.control(execute)

    async def invoke_once(self, session_index, operation, payload):
        """Invoke one operation through an owned live session without exporting it."""
        if (
            type(session_index) is not int
            or session_index < 0
            or type(operation) is not str
            or not operation
            or type(payload) is not dict
        ):
            raise ValueError("exact owned session invocation required")
        await self.prepared()
        async with self._invocation_lock:
            if (
                self._stopping
                or self._cleaning
                or self._task.done()
                or session_index >= len(self._sessions)
            ):
                raise RuntimeError("invocation requires live preparation ownership")
            task = asyncio.create_task(
                self._sessions[session_index].invoke(operation, payload)
            )
            self._invocations.add(task)
            try:
                return await task
            finally:
                self._invocations.discard(task)

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
