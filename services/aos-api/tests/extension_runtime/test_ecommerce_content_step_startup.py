import asyncio
from types import SimpleNamespace

import pytest

from aos_api.main import _start_content_generation_step_worker


def _app():
    return SimpleNamespace(state=SimpleNamespace(
        extension_runtime_host_task=None,
        extension_runtime_host_status="DISABLED",
        runtime_background_tasks=[],
    ))


def test_generation_step_worker_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AOS_ECOM_CONTENT_STEP_WORKER_ENABLED", raising=False)
    application = _app()
    asyncio.run(_start_content_generation_step_worker(application, asyncio.Event()))
    assert application.state.content_generation_step_worker_status == "DISABLED"
    assert application.state.runtime_background_tasks == []


def test_generation_step_worker_requires_active_runtime_host(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_CONTENT_STEP_WORKER_ENABLED", "true")
    application = _app()
    with pytest.raises(RuntimeError, match="active Runtime Host"):
        asyncio.run(_start_content_generation_step_worker(application, asyncio.Event()))
    assert application.state.content_generation_step_worker_status == "FAILED_CLOSED"


def test_generation_step_worker_is_managed_and_stops_with_host(monkeypatch):
    monkeypatch.setenv("AOS_ECOM_CONTENT_STEP_WORKER_ENABLED", "true")
    from aos_api.extension_runtime import runtime_connections
    import aos_api.main as main
    monkeypatch.setattr(runtime_connections, "runtime_worker_dsn",
                        lambda: "isolated-test-dsn")
    calls = []

    class Owner:
        async def serve(self, stop, *, host_ready):
            calls.append(host_ready())
            await stop.wait()

    monkeypatch.setattr(main, "_build_content_generation_step_owner", lambda: Owner())

    async def exercise():
        stop = asyncio.Event()
        host = asyncio.create_task(asyncio.sleep(10))
        application = _app()
        application.state.extension_runtime_host_task = host
        application.state.extension_runtime_host_status = "ACTIVE"
        await _start_content_generation_step_worker(application, stop)
        assert application.state.content_generation_step_worker_status == "RUNNING"
        assert calls == [True]
        stop.set()
        await application.state.content_generation_step_worker_task
        assert application.state.content_generation_step_worker_status == "STOPPED"
        host.cancel()
        try:
            await host
        except asyncio.CancelledError:
            pass

    asyncio.run(exercise())
