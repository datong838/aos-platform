from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from aos_api.aip_provider_health_maintenance import (
    AipTextProviderHealthMaintainer,
    maintenance_interval_seconds,
)


NOW = datetime(2026, 8, 23, 7, 0, tzinfo=UTC)


def health(*, minutes: int) -> SimpleNamespace:
    return SimpleNamespace(
        status="healthy",
        expires_at=NOW + timedelta(minutes=minutes),
        provider=SimpleNamespace(
            asset_id="agnes-text-qyh-dev",
            revision=7,
        ),
    )


class Store:
    def __init__(self, items):
        self.items = items

    def list_latest_provider_health(self, _scope):
        return self.items


def test_fresh_health_is_read_only_noop() -> None:
    called = []
    maintainer = AipTextProviderHealthMaintainer(
        store=Store([health(minutes=10)]),
        refresh_health=lambda: called.append("health"),
        refresh_readiness=lambda **_: called.append("readiness"),
        clock=lambda: NOW,
    )
    result = maintainer.run_once()
    assert result["status"] == "TEXT_PROVIDER_HEALTH_MAINTENANCE_NOOP"
    assert result["remainingSeconds"] == 600
    assert called == []


def test_due_health_refreshes_once_then_refreshes_bindings() -> None:
    called = []

    def refresh_health():
        called.append("health")
        return {
            "status": "PROVIDER_HEALTH_REFRESH_GREEN",
            "observationId": "health-2",
            "expiresAt": NOW + timedelta(minutes=15),
            "providerCalls": 3,
        }

    def refresh_readiness(**_):
        called.append("readiness")
        return {
            "status": "R12_ECOMMERCE_RUNTIME_READINESS_REFRESH_GREEN",
            "completedRoles": ["a", "b", "c", "d", "e", "f"],
        }

    result = AipTextProviderHealthMaintainer(
        store=Store([health(minutes=5)]),
        refresh_health=refresh_health,
        refresh_readiness=refresh_readiness,
        clock=lambda: NOW,
    ).run_once()
    assert result["status"] == "TEXT_PROVIDER_HEALTH_MAINTENANCE_GREEN"
    assert result["providerCalls"] == 3
    assert called == ["health", "readiness"]


def test_provider_failure_is_closed_without_readiness_or_retry() -> None:
    called = []

    def blocked():
        called.append("health")
        raise RuntimeError("sensitive upstream detail")

    result = AipTextProviderHealthMaintainer(
        store=Store([]),
        refresh_health=blocked,
        refresh_readiness=lambda **_: called.append("readiness"),
        clock=lambda: NOW,
    ).run_once()
    assert result == {
        "status": "TEXT_PROVIDER_HEALTH_MAINTENANCE_BLOCKED",
        "stage": "provider_health",
        "errorType": "RuntimeError",
        "errorCode": "RuntimeError",
        "healthObservationWritten": False,
        "automaticRetry": False,
    }
    assert called == ["health"]


def test_readiness_failure_is_retried_without_another_provider_cycle() -> None:
    health_calls = []
    readiness_calls = []

    def refresh_health():
        health_calls.append(1)
        return {
            "status": "PROVIDER_HEALTH_REFRESH_GREEN",
            "observationId": "health-3",
            "expiresAt": NOW + timedelta(minutes=15),
            "providerCalls": 3,
        }

    def refresh_readiness(**_):
        readiness_calls.append(1)
        if len(readiness_calls) == 1:
            raise RuntimeError("db unavailable")
        return {
            "status": "R12_ECOMMERCE_RUNTIME_READINESS_REFRESH_GREEN",
            "completedRoles": ["a", "b", "c", "d", "e", "f"],
        }

    store = Store([health(minutes=5)])
    maintainer = AipTextProviderHealthMaintainer(
        store=store,
        refresh_health=refresh_health,
        refresh_readiness=refresh_readiness,
        clock=lambda: NOW,
    )
    first = maintainer.run_once()
    store.items = [health(minutes=14)]
    second = maintainer.run_once()
    assert first["stage"] == "binding_readiness"
    assert second["status"] == "TEXT_PROVIDER_HEALTH_MAINTENANCE_GREEN"
    assert health_calls == [1]
    assert readiness_calls == [1, 1]


def test_interval_is_bounded(monkeypatch) -> None:
    monkeypatch.setenv(
        "AOS_AIP_TEXT_HEALTH_MAINTENANCE_INTERVAL_SECONDS", "1"
    )
    assert maintenance_interval_seconds() == 60
    monkeypatch.setenv(
        "AOS_AIP_TEXT_HEALTH_MAINTENANCE_INTERVAL_SECONDS", "9999"
    )
    assert maintenance_interval_seconds() == 900
