import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest

from aos_api.extension_runtime.preparation_owner import PreparationOwner


def make_owner(events, *, lease=5, exited=None, health_failure=None):
    @asynccontextmanager
    async def resource():
        class Session:
            process = type('Process', (), {'wait': lambda self: (exited or asyncio.Event()).wait()})()

            async def check_health(self):
                events.append('health')
                if health_failure and health_failure.is_set():
                    raise ValueError('health failed')
        try:
            yield Session()
        finally:
            events.append('closed')

    async def prepare():
        return 'prepared'
    return PreparationOwner([resource], prepare, lease_seconds=lease)


async def verified(observed):
    return 'verified'


def test_control_requires_successful_verification_and_serializes_admission():
    async def run():
        events = []
        owner = make_owner(events)
        await owner.prepared()
        with pytest.raises(RuntimeError):
            await owner.control(verified)
        entered, release = asyncio.Event(), asyncio.Event()

        async def blocked(observed):
            entered.set()
            await release.wait()
            return 'verified'

        checking = asyncio.create_task(owner.verify(blocked))
        await entered.wait()
        with pytest.raises(RuntimeError):
            await owner.control(verified)
        release.set()
        await checking
        entered.clear()
        release.clear()
        controlling = asyncio.create_task(owner.control(blocked))
        await entered.wait()
        with pytest.raises(RuntimeError):
            await owner.control(verified)
        with pytest.raises(RuntimeError):
            await owner.verify(verified)
        release.set()
        await controlling
        for _ in range(3):
            assert await owner.control(verified) == 'verified'
        await owner.stop()
        with pytest.raises(RuntimeError):
            await owner.control(verified)
        assert events == ['health'] * 5 + ['closed']
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())


@pytest.mark.parametrize('mode', ['health', 'commit', 'verification'])
def test_control_failure_stops_owned_group(mode):
    async def run():
        events = []
        fail_health = asyncio.Event()
        owner = make_owner(events, health_failure=fail_health)
        await owner.prepared()

        async def failure(observed):
            raise ValueError('commit failed')

        if mode == 'verification':
            with pytest.raises(ValueError):
                await owner.verify(failure)
        else:
            await owner.verify(verified)
            if mode == 'health':
                fail_health.set()
            with pytest.raises(ValueError):
                await owner.control(failure if mode == 'commit' else verified)
        with pytest.raises(ValueError):
            await owner.wait_closed()
        with pytest.raises(RuntimeError):
            await owner.control(verified)
        assert events[-1] == 'closed'
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())


@pytest.mark.parametrize('reason', ['stop', 'lease', 'exit', 'request_cancel'])
def test_control_settles_before_resources_exit(reason):
    async def run():
        entered, release, exited = asyncio.Event(), asyncio.Event(), asyncio.Event()
        events = []
        owner = make_owner(events, lease=.05 if reason == 'lease' else 5, exited=exited)
        await owner.verify(verified)
        events.clear()

        async def commit(observed):
            assert 0 <= (datetime.now(timezone.utc) - observed).total_seconds() < 1
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            events.append('committed')
            return 'controlled'

        waiter = asyncio.create_task(owner.control(commit))
        await entered.wait()
        if reason == 'stop':
            closing = asyncio.create_task(owner.stop())
        elif reason == 'exit':
            exited.set()
            closing = asyncio.create_task(owner.wait_closed())
        elif reason == 'lease':
            closing = asyncio.create_task(owner.wait_closed())
        else:
            waiter.cancel()
            closing = None
        await asyncio.sleep(.08)
        assert events == ['health']
        release.set()
        if reason == 'request_cancel':
            with pytest.raises(asyncio.CancelledError):
                await waiter
            await owner.stop()
        else:
            await asyncio.gather(waiter, closing, return_exceptions=True)
        assert events == ['health', 'committed', 'closed']
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())
