"""Real threads, named tick seam; no database or source execution."""
import asyncio
from threading import Event
import pytest
from aos_api.pipeline_snapshot_schedule_worker import (
    PipelineSnapshotScheduleWorker,
    _SAVED_RECOVERY_TIMEOUT_SECONDS,
    _error_origin,
    _error_reason,
    _safe_origin_name,
)


def test_saved_recovery_budget_matches_bounded_store_attempt():
    assert _SAVED_RECOVERY_TIMEOUT_SECONDS == 1800.0


def test_error_origin_is_bounded_and_never_uses_exception_message():
    try:
        raise PermissionError('secret source text')
    except PermissionError as exc:
        assert _error_origin(exc)=='test_error_origin_is_bounded_and_never_uses_exception_message'
    assert _error_origin(PermissionError('unraised secret'))=='unknown'
    assert _safe_origin_name('bad-origin/name')=='unknown'
    assert _safe_origin_name('x'*81)=='unknown'


def test_error_reason_only_maps_registered_static_guard_messages():
    assert _error_reason(ValueError('recovery bindings are not current'))=='RECOVERY_BINDINGS_NOT_CURRENT'
    assert _error_reason(ValueError('canonical object required'))=='CANONICAL_RELATIONSHIP_OBJECT_REQUIRED'
    assert _error_reason(PermissionError('runtime request is not currently admitted'))=='RUNTIME_REQUEST_NOT_CURRENTLY_ADMITTED'
    assert _error_reason(RuntimeError('named secret must not be exposed'))=='RUNTIMEERROR'
    assert _error_reason(RuntimeError('recovery bindings are not current','extra'))=='RUNTIMEERROR'


async def until(predicate):
    async def wait():
        while not predicate():await asyncio.sleep(.005)
    await asyncio.wait_for(wait(),2)


@pytest.mark.parametrize('reason',['cancel','stop','host'])
def test_shutdown_waits_for_actual_thread_cleanup(reason):
    async def scenario():
        worker=object.__new__(PipelineSnapshotScheduleWorker)
        started,stopping,released,exited=Event(),Event(),Event(),Event()
        stop=asyncio.Event();host=[True];calls=[]
        def tick(*,cancel_event,**_):
            calls.append(1);started.set()
            try:
                assert cancel_event.wait(5)
                stopping.set()
                assert released.wait(5)
                return []
            finally:exited.set()
        worker.tick=tick
        task=asyncio.create_task(worker.serve(stop,host_ready=lambda:host[0],interval=.02))
        try:
            await until(started.is_set)
            if reason=='cancel':task.cancel()
            elif reason=='stop':stop.set()
            else:host[0]=False
            await until(stopping.is_set)
            assert worker.status=='STOPPING' and not task.done() and not exited.is_set()
            if reason=='cancel':
                task.cancel()
                await asyncio.sleep(.02)
                assert not task.done()
            released.set()
            if reason=='cancel':
                with pytest.raises(asyncio.CancelledError):await task
            else:await task
            assert exited.is_set() and worker.status=='STOPPED' and calls==[1]
        finally:
            released.set();stop.set()
            if not task.done():
                try:await task
                except asyncio.CancelledError:pass
    asyncio.run(scenario())


def test_pre_stopped_host_and_duplicate_loop_never_start_extra_thread():
    async def scenario():
        worker=object.__new__(PipelineSnapshotScheduleWorker)
        worker.tick=lambda **_:pytest.fail('pre-stopped tick')
        stop=asyncio.Event();stop.set()
        await worker.serve(stop,host_ready=lambda:True,interval=.01)
        assert worker.status=='STOPPED'
        await worker.serve(asyncio.Event(),host_ready=lambda:False,interval=.01)
        assert worker.status=='STOPPED'
        worker._serving=True
        with pytest.raises(RuntimeError,match='already serving'):
            await worker.serve(asyncio.Event(),host_ready=lambda:True,interval=.01)
    asyncio.run(scenario())


def test_unknown_tick_stops_before_an_automatic_retry():
    async def scenario():
        worker=object.__new__(PipelineSnapshotScheduleWorker)
        calls=[]
        def tick(**_):
            calls.append(1)
            return [{'status':'unknown','errorCode':'SNAPSHOT_EXECUTION_UNCONFIRMED'}]
        worker.tick=tick
        await worker.serve(asyncio.Event(),host_ready=lambda:True,interval=.01)
        assert calls==[1]
        assert worker.last_error=='SNAPSHOT_TICK_UNCONFIRMED'
        assert worker.status=='STOPPED'
    asyncio.run(scenario())
