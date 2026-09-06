"""The API process assembles runtime control but starts no runtime worker."""
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
