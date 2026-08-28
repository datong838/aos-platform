from __future__ import annotations

import asyncio
import types

import pytest

from aos_api import main
from aos_api.aip_provider_health_maintenance import (
    refresh_ecommerce_readiness_from_authorized_runtime,
    refresh_provider_health_from_authorized_runtime,
)
from aos_api.aip_provider_health_maintenance_startup import (
    ProviderHealthStartupPreflightError,
)


def test_main_build_passes_only_explicit_reviewed_refresh_callables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    sentinel = object()

    def fake_build(**kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        "aos_api.aip_provider_health_maintenance_startup."
        "build_provider_health_maintenance_startup",
        fake_build,
    )

    assert main._build_provider_health_startup() is sentinel
    assert captured == {
        "refresh_health": refresh_provider_health_from_authorized_runtime,
        "refresh_readiness": refresh_ecommerce_readiness_from_authorized_runtime,
    }


def test_main_selects_inactive_without_maintainer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "_build_provider_health_startup",
        lambda: types.SimpleNamespace(
            preflight=types.SimpleNamespace(
                status="PROVIDER_HEALTH_MAINTENANCE_STARTUP_INACTIVE"
            ),
            runtime=None,
        ),
    )

    selection = main._select_provider_health_maintenance()

    assert selection.maintainer is None
    assert selection.error_code is None
    assert selection.status == "PROVIDER_HEALTH_MAINTENANCE_STARTUP_INACTIVE"


def test_main_selects_factory_built_maintainer_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    maintainer = object()
    monkeypatch.setattr(
        main,
        "_build_provider_health_startup",
        lambda: types.SimpleNamespace(
            preflight=types.SimpleNamespace(status="GREEN"),
            runtime=types.SimpleNamespace(maintainer=maintainer),
        ),
    )

    selection = main._select_provider_health_maintenance()

    assert selection.maintainer is maintainer
    assert selection.error_code is None
    assert selection.status == "PROVIDER_HEALTH_MAINTENANCE_STARTUP_RUNTIME_GREEN"


def test_main_fails_closed_with_stable_preflight_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail() -> None:
        raise ProviderHealthStartupPreflightError(
            "CANONICAL_ACTION_LEASE_AUTHORITY_MODE_REQUIRED"
        )

    monkeypatch.setattr(main, "_build_provider_health_startup", fail)

    selection = main._select_provider_health_maintenance()

    assert selection.maintainer is None
    assert selection.status == "PROVIDER_HEALTH_MAINTENANCE_STARTUP_FAILED_CLOSED"
    assert selection.error_code == "CANONICAL_ACTION_LEASE_AUTHORITY_MODE_REQUIRED"


def test_lifespan_failed_preflight_does_not_create_provider_health_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "run_migrations",
        lambda: types.SimpleNamespace(value="managed"),
    )
    monkeypatch.setenv("AOS_QYH_CRON_ENABLED", "false")
    monkeypatch.setenv("AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED", "true")
    monkeypatch.delenv(
        "AOS_AIP_TEXT_HEALTH_CANONICAL_AUTHORITY_MODE", raising=False
    )

    def fail_create_task(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("failed preflight must not create a background task")

    monkeypatch.setattr(main.asyncio, "create_task", fail_create_task)

    async def probe() -> None:
        async with main.lifespan(main.app):
            pass

    asyncio.run(probe())
