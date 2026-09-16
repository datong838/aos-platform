import asyncio
from contextlib import contextmanager
from threading import Event
from types import SimpleNamespace
import pytest
from aos_api.pipeline_control_service import PipelineControlServiceFactory
from aos_api import main
from aos_api.pipeline_snapshot_schedule_worker import PipelineSnapshotScheduleWorker


def application():
    return SimpleNamespace(state=SimpleNamespace(runtime_background_tasks=[],runtime_stop_events=(),
        extension_runtime_host_task=None,extension_runtime_control_plane=None))


def test_default_disabled_and_explicit_missing_host_fail_closed(monkeypatch):
    async def scenario():
        app=application();monkeypatch.delenv('AOS_SNAPSHOT_GROUP_WORKER_ENABLED',raising=False)
        await main._start_snapshot_group_worker(app)
        assert app.state.snapshot_group_worker_status=='DISABLED' and app.state.runtime_background_tasks==[]
        monkeypatch.setenv('AOS_SNAPSHOT_GROUP_WORKER_ENABLED','true')
        with pytest.raises(RuntimeError,match='host'):
            await main._start_snapshot_group_worker(app)
        assert app.state.snapshot_group_worker_status=='FAILED_CLOSED'
    asyncio.run(scenario())


@pytest.mark.parametrize('topology',['cohosted','independent'])
def test_application_shutdown_disposes_store_only_after_thread_exit(monkeypatch,topology):
    import aos_api.pipeline_controlled_runtime as controlled
    import aos_api.jdbc_connector_runtime as jdbc
    monkeypatch.setenv('AOS_SNAPSHOT_GROUP_WORKER_ENABLED','true')
    monkeypatch.setenv('AOS_SNAPSHOT_GROUP_WORKER_TOPOLOGY',topology)
    monkeypatch.setattr(jdbc,'jdbc_runtime_shutdown',lambda:None)
    started,stopping,release,exited=Event(),Event(),Event(),Event();disposed=[]
    @contextmanager
    def store():
        try:yield 'named-store-context'
        finally:
            assert exited.is_set()
            disposed.append(True)
    monkeypatch.setattr(controlled,'_authoritative_store',store)
    worker=object.__new__(PipelineSnapshotScheduleWorker)
    def tick(*,cancel_event):
        started.set()
        try:
            assert cancel_event.wait(5);stopping.set();assert release.wait(5)
            return []
        finally:exited.set()
    worker.tick=tick
    def build(scope,*,store):
        assert scope.key==('org-org','dev-project') and store=='named-store-context'
        return worker
    async def until(predicate):
        async def wait():
            while not predicate():await asyncio.sleep(.005)
        await asyncio.wait_for(wait(),2)
    async def scenario():
        app=application();host_stop=asyncio.Event()
        host=asyncio.create_task(host_stop.wait())
        app.state.runtime_stop_events=(host_stop,)
        app.state.runtime_background_tasks=[host]
        app.state.extension_runtime_host_task=host if topology=='cohosted' else None
        factory=object.__new__(PipelineControlServiceFactory)
        object.__setattr__(factory,'build_snapshot_worker',build)
        app.state.extension_runtime_control_plane=SimpleNamespace(pipeline_control_factory=factory)
        await main._start_snapshot_group_worker(app)
        if topology=='independent':assert app.state.extension_runtime_host_task is None
        await until(started.is_set)
        shutdown=asyncio.create_task(main._shutdown_application_runtime_body(app))
        try:
            await until(stopping.is_set)
            assert not shutdown.done() and disposed==[] and worker.status=='STOPPING'
            release.set();await shutdown
            assert disposed==[True] and worker.status=='STOPPED'
            assert app.state.snapshot_group_worker_status=='STOPPED'
        finally:
            release.set();host_stop.set()
            await shutdown
    asyncio.run(scenario())


def test_construction_failure_is_not_advertised_as_running(monkeypatch):
    import aos_api.pipeline_controlled_runtime as controlled
    monkeypatch.setenv('AOS_SNAPSHOT_GROUP_WORKER_ENABLED','true')
    closed=[]
    @contextmanager
    def store():
        try:yield object()
        finally:closed.append(True)
    monkeypatch.setattr(controlled,'_authoritative_store',store)
    def fail(*_,**__):raise ValueError('named invalid source asset root')
    async def scenario():
        app=application();stop=asyncio.Event();host=asyncio.create_task(stop.wait())
        app.state.extension_runtime_host_task=host
        app.state.extension_runtime_control_plane=SimpleNamespace(pipeline_control_factory=SimpleNamespace(build_snapshot_worker=fail))
        try:
            with pytest.raises(RuntimeError,match='startup'):
                await main._start_snapshot_group_worker(app)
            assert app.state.snapshot_group_worker_status=='FAILED_CLOSED'
            assert app.state.snapshot_group_worker_error_code=='SNAPSHOT_WORKER_FAILED'
            assert closed==[True]
        finally:stop.set();await host
    asyncio.run(scenario())


@pytest.mark.parametrize('mode',['invalid','independent'])
def test_unknown_topology_or_missing_factory_fails_closed(monkeypatch,mode):
    monkeypatch.setenv('AOS_SNAPSHOT_GROUP_WORKER_ENABLED','true')
    monkeypatch.setenv('AOS_SNAPSHOT_GROUP_WORKER_TOPOLOGY',mode)
    async def scenario():
        app=application()
        with pytest.raises(RuntimeError):await main._start_snapshot_group_worker(app)
        assert app.state.snapshot_group_worker_status=='FAILED_CLOSED'
        assert not app.state.runtime_background_tasks
    asyncio.run(scenario())
