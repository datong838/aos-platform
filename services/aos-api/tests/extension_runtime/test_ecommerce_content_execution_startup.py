import asyncio
from types import SimpleNamespace

import pytest

from aos_api.main import _start_content_execution_worker


def app(host_task=None):
    return SimpleNamespace(state=SimpleNamespace(
        extension_runtime_host_task=host_task,
        extension_runtime_host_status='ACTIVE' if host_task else 'DISABLED',
        runtime_background_tasks=[],runtime_stop_events=(),
    ))


def test_content_worker_is_off_by_default(monkeypatch):
    monkeypatch.delenv('AOS_ECOM_CONTENT_WORKER_ENABLED',raising=False)
    application=app()
    asyncio.run(_start_content_execution_worker(application,asyncio.Event()))
    assert application.state.content_execution_worker_status=='DISABLED'
    assert application.state.runtime_background_tasks==[]


def test_enabled_content_worker_requires_live_runtime_host(monkeypatch):
    monkeypatch.setenv('AOS_ECOM_CONTENT_WORKER_ENABLED','true')
    application=app()
    with pytest.raises(RuntimeError,match='active Runtime Host'):
        asyncio.run(_start_content_execution_worker(application,asyncio.Event()))
    assert application.state.content_execution_worker_status=='FAILED_CLOSED'


def test_invalid_content_worker_flag_fails_closed(monkeypatch):
    monkeypatch.setenv('AOS_ECOM_CONTENT_WORKER_ENABLED','maybe')
    application=app()
    with pytest.raises(RuntimeError,match='enable flag is invalid'):
        asyncio.run(_start_content_execution_worker(application,asyncio.Event()))
    assert application.state.content_execution_worker_status=='FAILED_CLOSED'


def test_enabled_content_worker_is_managed_and_stops_with_host(monkeypatch):
    monkeypatch.setenv('AOS_ECOM_CONTENT_WORKER_ENABLED','true')
    from aos_api.extension_runtime import runtime_connections
    import aos_api.main as main
    monkeypatch.setattr(runtime_connections,'runtime_worker_dsn',lambda:'isolated-test-dsn')
    calls=[]
    class Runner:
        def assert_configuration_ready(self):
            calls.append('configured')
        async def serve(self,stop,*,host_ready):
            calls.append(host_ready())
            await stop.wait()
    monkeypatch.setattr(main,'_build_content_execution_runner',lambda:Runner())
    async def exercise():
        stop=asyncio.Event()
        host=asyncio.create_task(asyncio.sleep(10))
        application=app(host)
        await _start_content_execution_worker(application,stop)
        assert application.state.content_execution_worker_status=='RUNNING'
        assert calls==['configured',True]
        assert len(application.state.runtime_background_tasks)==1
        stop.set()
        await application.state.content_execution_worker_task
        assert application.state.content_execution_worker_status=='STOPPED'
        host.cancel()
        try:await host
        except asyncio.CancelledError:pass
    asyncio.run(exercise())


def test_enabled_content_worker_rejects_missing_business_identity_before_task(monkeypatch):
    monkeypatch.setenv('AOS_ECOM_CONTENT_WORKER_ENABLED','true')
    from aos_api.extension_runtime import runtime_connections
    import aos_api.main as main
    monkeypatch.setattr(runtime_connections,'runtime_worker_dsn',lambda:'isolated-test-dsn')
    class Runner:
        def assert_configuration_ready(self):
            raise RuntimeError('ROUTE_WORKER_CURRENT_IDENTITY_REQUIRED')
    monkeypatch.setattr(main,'_build_content_execution_runner',lambda:Runner())
    async def exercise():
        host=asyncio.create_task(asyncio.sleep(10))
        application=app(host)
        with pytest.raises(RuntimeError,match='ROUTE_WORKER_CURRENT_IDENTITY_REQUIRED'):
            await _start_content_execution_worker(application,asyncio.Event())
        assert application.state.content_execution_worker_status=='FAILED_CLOSED'
        assert application.state.runtime_background_tasks==[]
        host.cancel()
        try:await host
        except asyncio.CancelledError:pass
    asyncio.run(exercise())
