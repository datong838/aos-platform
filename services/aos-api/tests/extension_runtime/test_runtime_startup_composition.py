"""The API process starts only a fully selected, explicitly enabled runtime host."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from aos_api import main


def _quiet_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "run_migrations", lambda: SimpleNamespace(value="managed"))
    monkeypatch.setattr(main, "_prebuild_jdbc_ssh_tunnels", lambda: None)
    monkeypatch.setattr(
        main,
        "_select_provider_health_maintenance",
        lambda: main._ProviderHealthLoopSelection(maintainer=None, status="INACTIVE"),
    )
    monkeypatch.setenv("AOS_QYH_CRON_ENABLED", "false")
    monkeypatch.setenv("AOS_AIP_LOGIC_AUTOMATION_ENABLED", "false")
    import aos_api.asset_registry.control_wiring as wiring

    monkeypatch.setattr(
        wiring,
        "build_production_runtime_host_selection",
        lambda *, control_plane: SimpleNamespace(
            host=None, status="INACTIVE", error_code="DISABLED"
        ),
    )


def test_lifespan_installs_and_clears_runtime_control_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_startup(monkeypatch)
    sentinel = object()
    import aos_api.asset_registry.control_wiring as wiring

    monkeypatch.setattr(wiring, "build_runtime_control_plane", lambda: sentinel)

    async def probe() -> None:
        async with main.lifespan(main.app):
            assert main.app.state.extension_runtime_control_plane is sentinel
        assert main.app.state.extension_runtime_control_plane is None

    asyncio.run(probe())


def test_lifespan_fails_closed_when_runtime_control_cannot_be_assembled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_startup(monkeypatch)
    import aos_api.asset_registry.control_wiring as wiring

    def fail():
        raise RuntimeError("runtime-control-assembly-failed")

    monkeypatch.setattr(wiring, "build_runtime_control_plane", fail)

    async def probe() -> None:
        with pytest.raises(RuntimeError, match="runtime-control-assembly-failed"):
            async with main.lifespan(main.app):
                raise AssertionError("failed assembly must not enter lifespan")
        assert main.app.state.extension_runtime_control_plane is None

    asyncio.run(probe())


def test_lifespan_body_failure_still_clears_runtime_control_plane(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_startup(monkeypatch)
    sentinel = object()
    import aos_api.asset_registry.control_wiring as wiring

    monkeypatch.setattr(wiring, "build_runtime_control_plane", lambda: sentinel)

    async def probe() -> None:
        with pytest.raises(RuntimeError, match="request-failed"):
            async with main.lifespan(main.app):
                assert main.app.state.extension_runtime_control_plane is sentinel
                raise RuntimeError("request-failed")
        assert main.app.state.extension_runtime_control_plane is None
        assert main.app.state.runtime_background_tasks == []
        assert main.app.state.runtime_stop_events == ()

    asyncio.run(probe())


def test_lifespan_startup_failure_cancels_an_already_created_background_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_startup(monkeypatch)
    sentinel = object()
    import aos_api.asset_registry.control_wiring as wiring

    monkeypatch.setattr(wiring, "build_runtime_control_plane", lambda: sentinel)
    monkeypatch.setattr(main, "_qyh_cron_worker_enabled", lambda: True)

    def fail_after_cron_started():
        raise RuntimeError("startup-after-cron-failed")

    monkeypatch.setattr(main, "_select_provider_health_maintenance", fail_after_cron_started)
    created: list[asyncio.Task[None]] = []
    create_task = asyncio.create_task

    def capture_task(coroutine, *, name: str):
        task = create_task(coroutine, name=name)
        created.append(task)
        return task

    monkeypatch.setattr(main.asyncio, "create_task", capture_task)

    async def probe() -> None:
        with pytest.raises(RuntimeError, match="startup-after-cron-failed"):
            async with main.lifespan(main.app):
                raise AssertionError("failed startup must not enter lifespan")
        assert len(created) == 1
        assert created[0].cancelled()
        assert main.app.state.extension_runtime_control_plane is None
        assert main.app.state.runtime_background_tasks == []
        assert main.app.state.runtime_stop_events == ()

    asyncio.run(probe())


def test_inactive_runtime_host_selection_creates_no_background_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_startup(monkeypatch)
    sentinel = object()
    import aos_api.asset_registry.control_wiring as wiring

    monkeypatch.setattr(wiring, "build_runtime_control_plane", lambda: sentinel)
    seen: list[object] = []

    def select(*, control_plane):
        seen.append(control_plane)
        return SimpleNamespace(
            host=None, status="INACTIVE", error_code="DIRECTORY_EMPTY"
        )

    monkeypatch.setattr(wiring, "build_production_runtime_host_selection", select)

    async def probe() -> None:
        async with main.lifespan(main.app):
            assert seen == [sentinel]
            assert main.app.state.extension_runtime_host_status == "INACTIVE"
            assert main.app.state.extension_runtime_host_error_code == "DIRECTORY_EMPTY"
            assert main.app.state.extension_runtime_host_task is None
            assert main.app.state.runtime_background_tasks == []
        assert main.app.state.extension_runtime_host_status == "STOPPED"

    asyncio.run(probe())


def test_active_runtime_host_is_unique_and_stops_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_startup(monkeypatch)
    import aos_api.asset_registry.control_wiring as wiring

    monkeypatch.setattr(wiring, "build_runtime_control_plane", object)
    entered = asyncio.Event()
    stopped = asyncio.Event()

    class Host:
        async def serve(self, stop_event: asyncio.Event) -> None:
            entered.set()
            await stop_event.wait()
            stopped.set()

    host = Host()
    monkeypatch.setattr(
        wiring,
        "build_production_runtime_host_selection",
        lambda *, control_plane: SimpleNamespace(
            host=host, status="ACTIVE", error_code=None
        ),
    )

    async def probe() -> None:
        async with main.lifespan(main.app):
            await entered.wait()
            tasks = main.app.state.runtime_background_tasks
            assert len(tasks) == 1
            assert tasks[0] is main.app.state.extension_runtime_host_task
            assert tasks[0].get_name() == "extension-runtime-host"
            assert main.app.state.extension_runtime_host_status == "ACTIVE"
        assert stopped.is_set()
        assert main.app.state.extension_runtime_host_task is None
        assert main.app.state.runtime_background_tasks == []
        assert main.app.state.extension_runtime_host_status == "STOPPED"

    asyncio.run(probe())


def test_runtime_host_immediate_failure_fails_startup_and_is_observed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_startup(monkeypatch)
    import aos_api.asset_registry.control_wiring as wiring

    monkeypatch.setattr(wiring, "build_runtime_control_plane", object)

    class Host:
        async def serve(self, stop_event: asyncio.Event) -> None:
            raise RuntimeError("worker-detail-must-not-become-status")

    monkeypatch.setattr(
        wiring,
        "build_production_runtime_host_selection",
        lambda *, control_plane: SimpleNamespace(
            host=Host(), status="ACTIVE", error_code=None
        ),
    )

    async def probe() -> None:
        with pytest.raises(
            RuntimeError, match="extension runtime host failed during startup"
        ):
            async with main.lifespan(main.app):
                raise AssertionError("failed host must not enter lifespan")
        assert main.app.state.extension_runtime_host_status == "FAILED_CLOSED"
        assert main.app.state.extension_runtime_host_error_code == "HOST_TASK_FAILED"
        assert main.app.state.extension_runtime_host_task is None
        assert main.app.state.runtime_background_tasks == []

    asyncio.run(probe())


def test_runtime_host_failure_after_startup_marks_health_failed_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_startup(monkeypatch)
    import aos_api.asset_registry.control_wiring as wiring

    monkeypatch.setattr(wiring, "build_runtime_control_plane", object)
    release = asyncio.Event()

    class Host:
        async def serve(self, stop_event: asyncio.Event) -> None:
            await release.wait()
            raise RuntimeError("late-worker-detail")

    monkeypatch.setattr(
        wiring,
        "build_production_runtime_host_selection",
        lambda *, control_plane: SimpleNamespace(
            host=Host(), status="ACTIVE", error_code=None
        ),
    )

    async def probe() -> None:
        async with main.lifespan(main.app):
            release.set()
            task = main.app.state.extension_runtime_host_task
            with pytest.raises(RuntimeError, match="late-worker-detail"):
                await task
            await asyncio.sleep(0)
            assert main.app.state.extension_runtime_host_status == "FAILED_CLOSED"
            assert main.app.state.extension_runtime_host_error_code == "HOST_TASK_FAILED"
        assert main.app.state.extension_runtime_host_status == "FAILED_CLOSED"

    asyncio.run(probe())


def test_active_runtime_host_stops_when_lifespan_body_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_startup(monkeypatch)
    import aos_api.asset_registry.control_wiring as wiring

    monkeypatch.setattr(wiring, "build_runtime_control_plane", object)
    stopped = asyncio.Event()

    class Host:
        async def serve(self, stop_event: asyncio.Event) -> None:
            await stop_event.wait()
            stopped.set()

    monkeypatch.setattr(
        wiring,
        "build_production_runtime_host_selection",
        lambda *, control_plane: SimpleNamespace(
            host=Host(), status="ACTIVE", error_code=None
        ),
    )

    async def probe() -> None:
        with pytest.raises(RuntimeError, match="request-body-failed"):
            async with main.lifespan(main.app):
                raise RuntimeError("request-body-failed")
        assert stopped.is_set()
        assert main.app.state.extension_runtime_control_plane is None
        assert main.app.state.runtime_background_tasks == []
        assert main.app.state.runtime_stop_events == ()

    asyncio.run(probe())


def test_selector_failure_uses_the_same_cleanup_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _quiet_startup(monkeypatch)
    import aos_api.asset_registry.control_wiring as wiring

    monkeypatch.setattr(wiring, "build_runtime_control_plane", object)

    def fail(*, control_plane):
        raise RuntimeError("selector-failed")

    monkeypatch.setattr(wiring, "build_production_runtime_host_selection", fail)

    async def probe() -> None:
        with pytest.raises(RuntimeError, match="selector-failed"):
            async with main.lifespan(main.app):
                raise AssertionError("selector failure must not enter lifespan")
        assert main.app.state.extension_runtime_control_plane is None
        assert main.app.state.extension_runtime_host_selection is None
        assert main.app.state.runtime_background_tasks == []
        assert main.app.state.runtime_stop_events == ()

    asyncio.run(probe())


def test_shutdown_timeout_cancels_and_awaits_runtime_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "_EXTENSION_RUNTIME_SHUTDOWN_TIMEOUT_SECONDS", 0)
    cancelled = asyncio.Event()

    async def host_task() -> None:
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async def probe() -> None:
        task = asyncio.create_task(host_task(), name="extension-runtime-host")
        await asyncio.sleep(0)
        main.app.state.runtime_stop_events = (asyncio.Event(),)
        main.app.state.runtime_background_tasks = [task]
        main.app.state.extension_runtime_host_task = task
        main.app.state.extension_runtime_host_status = "ACTIVE"
        main.app.state.extension_runtime_control_plane = object()
        main.app.state.runtime_shutdown_task = None
        await main._shutdown_application_runtime(main.app)
        assert cancelled.is_set()
        assert task.cancelled()
        assert main.app.state.runtime_background_tasks == []
        assert main.app.state.extension_runtime_control_plane is None

    asyncio.run(probe())


def test_cancelled_shutdown_caller_waits_for_host_cleanup_then_propagates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release = asyncio.Event()
    host_stopped = asyncio.Event()
    jdbc_stopped = []

    async def host_task() -> None:
        await release.wait()
        host_stopped.set()

    monkeypatch.setattr(
        "aos_api.jdbc_connector_runtime.jdbc_runtime_shutdown",
        lambda: jdbc_stopped.append(True),
    )

    async def probe() -> None:
        task = asyncio.create_task(host_task(), name="extension-runtime-host")
        stop = asyncio.Event()
        main.app.state.runtime_stop_events = (stop,)
        main.app.state.runtime_background_tasks = [task]
        main.app.state.extension_runtime_host_task = task
        main.app.state.extension_runtime_host_status = "ACTIVE"
        main.app.state.extension_runtime_control_plane = object()
        main.app.state.runtime_shutdown_task = None
        caller = asyncio.create_task(main._shutdown_application_runtime(main.app))
        for _ in range(20):
            if stop.is_set():
                break
            await asyncio.sleep(0)
        assert stop.is_set()
        caller.cancel()
        await asyncio.sleep(0)
        assert not caller.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await caller
        assert host_stopped.is_set()
        assert task.done()
        assert jdbc_stopped == [True]
        assert main.app.state.runtime_background_tasks == []
        assert main.app.state.runtime_stop_events == ()
        assert main.app.state.runtime_shutdown_task is None

    asyncio.run(probe())
