import asyncio
from contextlib import asynccontextmanager

import pytest

from aos_api.extension_runtime.preparation_owner import PreparationOwner


class Process:
    def __init__(self):
        self.exited = asyncio.Event()

    async def wait(self):
        await self.exited.wait()
        return 1


def test_owner_holds_resources_after_cancelled_wait_and_cleans_reverse_order():
    async def run():
        events = []
        ready = asyncio.Event()
        processes = [Process(), Process()]

        def factory(index):
            @asynccontextmanager
            async def open_resource():
                events.append(('open', index))
                try:
                    yield type('Session', (), {'process': processes[index]})()
                finally:
                    events.append(('close', index))
            return open_resource

        async def commit():
            await ready.wait()
            return 'prepared-ref'

        owner = PreparationOwner([factory(0), factory(1)], commit, lease_seconds=5)
        waiter = asyncio.create_task(owner.prepared())
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        ready.set()
        assert await owner.prepared() == 'prepared-ref'
        assert events == [('open', 0), ('open', 1)]
        await owner.stop()
        await owner.stop()
        assert events == [('open', 0), ('open', 1), ('close', 1), ('close', 0)]
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())


def test_immediate_stop_never_opens_resource_or_leaves_prepared_waiting():
    async def run():
        @asynccontextmanager
        async def resource():
            pytest.fail('stopped owner must not open resources')
            yield
        async def commit():
            pytest.fail('stopped owner must not commit')
        owner = PreparationOwner([resource], commit, lease_seconds=5)
        await owner.stop()
        with pytest.raises(RuntimeError, match='stopped'):
            await owner.prepared()
    asyncio.run(run())


def test_cancelling_stop_waiter_does_not_interrupt_cleanup():
    async def run():
        cleaning = asyncio.Event()
        release = asyncio.Event()
        closed = []
        @asynccontextmanager
        async def resource():
            try:
                yield type('Session', (), {'process': Process()})()
            finally:
                cleaning.set()
                await release.wait()
                closed.append(True)
        async def commit():
            return 'ref'
        owner = PreparationOwner([resource], commit, lease_seconds=.03)
        await owner.prepared()
        stopping = asyncio.create_task(owner.stop())
        await cleaning.wait()
        stopping.cancel()
        await asyncio.sleep(.05)
        assert not stopping.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await stopping
        await owner.stop()
        assert closed == [True]
    asyncio.run(run())


@pytest.mark.parametrize('reason', ['stop', 'exit'])
def test_commit_settlement_crossing_lease_preserves_failure(reason):
    async def run():
        started = asyncio.Event()
        settling = asyncio.Event()
        release = asyncio.Event()
        process = Process()
        closed = []
        @asynccontextmanager
        async def resource():
            try:
                yield type('Session', (), {'process': process})()
            finally:
                closed.append(True)
        async def commit():
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                settling.set()
                await release.wait()
                raise ValueError('commit outcome uncertain')
        owner = PreparationOwner([resource], commit, lease_seconds=.03)
        await started.wait()
        if reason == 'stop':
            waiter = asyncio.create_task(owner.stop())
        else:
            process.exited.set()
            waiter = asyncio.create_task(owner.wait_closed())
        await settling.wait()
        await asyncio.sleep(.05)
        assert not waiter.done() and closed == []
        release.set()
        with pytest.raises(ValueError, match='commit outcome uncertain'):
            await waiter
        with pytest.raises(ValueError, match='commit outcome uncertain'):
            await owner.prepared()
        assert closed == [True]
    asyncio.run(run())


@pytest.mark.parametrize('failure', ['startup', 'commit', 'exit', 'lease', 'cleanup'])
def test_owner_failure_is_observable_and_cleanup_is_not_lost(failure):
    async def run():
        closed = []
        process = Process()

        @asynccontextmanager
        async def resource():
            if failure == 'startup':
                raise ValueError('startup')
            try:
                yield type('Session', (), {'process': process})()
            finally:
                closed.append(True)
                if failure == 'cleanup':
                    raise ValueError('cleanup')

        async def commit():
            if failure == 'commit':
                raise ValueError('commit')
            return 'ref'

        owner = PreparationOwner([resource], commit, lease_seconds=.03 if failure == 'lease' else 5)
        if failure in {'startup', 'commit'}:
            with pytest.raises(ValueError, match=failure):
                await owner.prepared()
        else:
            assert await owner.prepared() == 'ref'
            if failure == 'exit':
                process.exited.set()
            if failure == 'cleanup':
                with pytest.raises(ValueError, match='cleanup'):
                    await owner.stop()
        with pytest.raises((ValueError, RuntimeError, TimeoutError)):
            await owner.wait_closed()
        assert closed == ([] if failure == 'startup' else [True])
        assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    asyncio.run(run())
