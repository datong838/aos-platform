from __future__ import annotations

import asyncio
import types

import pytest

from aos_api import main


@pytest.mark.parametrize("value", [None, "1", "true", "TRUE", "yes", "on"])
def test_qyh_cron_worker_enabled_by_default_and_true_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str | None,
) -> None:
    if value is None:
        monkeypatch.delenv("AOS_QYH_CRON_ENABLED", raising=False)
    else:
        monkeypatch.setenv("AOS_QYH_CRON_ENABLED", value)

    assert main._qyh_cron_worker_enabled() is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off"])
def test_qyh_cron_worker_can_be_explicitly_disabled(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("AOS_QYH_CRON_ENABLED", value)

    assert main._qyh_cron_worker_enabled() is False


def test_lifespan_does_not_create_cron_task_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "run_migrations",
        lambda: types.SimpleNamespace(value="managed"),
    )
    monkeypatch.setenv("AOS_QYH_CRON_ENABLED", "false")
    monkeypatch.setenv("AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED", "false")

    def fail_create_task(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("disabled browser acceptance must not create a cron task")

    monkeypatch.setattr(main.asyncio, "create_task", fail_create_task)

    async def probe() -> None:
        async with main.lifespan(main.app):
            pass

    asyncio.run(probe())
