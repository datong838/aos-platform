"""Fail-closed maintenance for the real tenant's text Provider health.

The maintainer owns no new authority.  It reuses the approved R2 three-probe
writer and the reviewed R12 binding-readiness refresh.  It never logs or
returns prompts, responses, headers, or Secret payloads.
"""
from __future__ import annotations

import importlib
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope("org-org", "dev-project")
PROVIDER_ID = "agnes-text-qyh-dev"
PROVIDER_REVISION = 7
DEFAULT_INTERVAL_SECONDS = 300
REFRESH_BEFORE_EXPIRY = timedelta(minutes=6)
_SCRIPT_DIR = Path(__file__).resolve().parents[3] / "scripts" / "aip"


def maintenance_enabled() -> bool:
    return os.getenv(
        "AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}


def maintenance_interval_seconds() -> int:
    raw = os.getenv(
        "AOS_AIP_TEXT_HEALTH_MAINTENANCE_INTERVAL_SECONDS",
        str(DEFAULT_INTERVAL_SECONDS),
    )
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_INTERVAL_SECONDS
    return min(900, max(60, value))


def _script_callable(module_name: str, function_name: str) -> Callable[..., Any]:
    script_dir = str(_SCRIPT_DIR)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    return getattr(importlib.import_module(module_name), function_name)


def _default_health_refresh() -> dict[str, Any]:
    return _script_callable("refresh_r2_provider_health", "refresh")()


def _default_readiness_refresh(*, now: datetime) -> dict[str, Any]:
    return _script_callable(
        "refresh_r12_ecommerce_runtime_readiness", "apply"
    )(now=now)


def _safe_error(exc: Exception) -> dict[str, str]:
    code = getattr(exc, "code", type(exc).__name__)
    return {"errorType": type(exc).__name__, "errorCode": str(code)}


def _deny_provider_refresh(_now: datetime) -> bool:
    """Default runtime boundary: an enabled loop is not call authorization."""
    return False


class AipTextProviderHealthMaintainer:
    """Execute at most one approved health cycle per scheduler tick."""

    def __init__(
        self,
        *,
        store: AipModelRuntimeStore | None = None,
        refresh_health: Callable[[], dict[str, Any]] | None = None,
        refresh_readiness: Callable[..., dict[str, Any]] | None = None,
        authorize_provider_refresh: Callable[[datetime], bool] | None = None,
        execute_authorized_refresh: (
            Callable[[datetime], dict[str, Any]] | None
        ) = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if (
            execute_authorized_refresh is not None
            and authorize_provider_refresh is not None
        ):
            raise ValueError(
                "canonical Action consumer and legacy authorizer are mutually exclusive"
            )
        self._store = store or AipModelRuntimeStore()
        self._refresh_health = refresh_health or _default_health_refresh
        self._refresh_readiness = refresh_readiness or _default_readiness_refresh
        self._authorize_provider_refresh = (
            authorize_provider_refresh or _deny_provider_refresh
        )
        self._execute_authorized_refresh = execute_authorized_refresh
        self._clock = clock or (lambda: datetime.now(UTC))
        self._readiness_pending = False

    def _latest_exact_health(self) -> Any | None:
        for item in self._store.list_latest_provider_health(SCOPE):
            if (
                item.provider.asset_id == PROVIDER_ID
                and item.provider.revision == PROVIDER_REVISION
            ):
                return item
        return None

    def run_once(self) -> dict[str, Any]:
        now = self._clock()
        latest = self._latest_exact_health()
        remaining = (
            latest.expires_at - now
            if latest is not None and latest.status == "healthy"
            else timedelta(0)
        )
        if not self._readiness_pending and remaining > REFRESH_BEFORE_EXPIRY:
            return {
                "status": "TEXT_PROVIDER_HEALTH_MAINTENANCE_NOOP",
                "remainingSeconds": int(remaining.total_seconds()),
                "providerCalls": 0,
                "secretPayloadReadsReported": 0,
            }

        health_result: dict[str, Any] | None = None
        if remaining <= REFRESH_BEFORE_EXPIRY:
            if self._execute_authorized_refresh is not None:
                try:
                    health_result = self._execute_authorized_refresh(now)
                except Exception as exc:
                    self._readiness_pending = False
                    return {
                        "status": "TEXT_PROVIDER_HEALTH_MAINTENANCE_BLOCKED",
                        "stage": "action_authority",
                        **_safe_error(exc),
                        "providerCalls": 0,
                        "healthObservationWritten": False,
                        "automaticRetry": False,
                    }
            else:
                try:
                    authorized = self._authorize_provider_refresh(now)
                except Exception as exc:
                    return {
                        "status": "TEXT_PROVIDER_HEALTH_MAINTENANCE_BLOCKED",
                        "stage": "authorization",
                        **_safe_error(exc),
                        "providerCalls": 0,
                        "healthObservationWritten": False,
                        "automaticRetry": False,
                    }
                if authorized is not True:
                    return {
                        "status": "TEXT_PROVIDER_HEALTH_MAINTENANCE_BLOCKED",
                        "stage": "authorization",
                        "errorType": "ProviderHealthAuthorizationUnavailable",
                        "errorCode": "EXACT_APPROVAL_LEASE_REQUIRED",
                        "providerCalls": 0,
                        "healthObservationWritten": False,
                        "automaticRetry": False,
                    }
                try:
                    health_result = self._refresh_health()
                except Exception as exc:
                    self._readiness_pending = False
                    return {
                        "status": "TEXT_PROVIDER_HEALTH_MAINTENANCE_BLOCKED",
                        "stage": "provider_health",
                        **_safe_error(exc),
                        "healthObservationWritten": False,
                        "automaticRetry": False,
                    }
            if health_result.get("status") != "PROVIDER_HEALTH_REFRESH_GREEN":
                self._readiness_pending = False
                return {
                    "status": "TEXT_PROVIDER_HEALTH_MAINTENANCE_BLOCKED",
                    "stage": "provider_health",
                    "errorType": "UnexpectedHealthStatus",
                    "errorCode": str(health_result.get("status") or "missing"),
                    "healthObservationWritten": False,
                    "automaticRetry": False,
                }
            self._readiness_pending = True

        try:
            readiness_result = self._refresh_readiness(now=self._clock())
        except Exception as exc:
            return {
                "status": "TEXT_PROVIDER_HEALTH_MAINTENANCE_BLOCKED",
                "stage": "binding_readiness",
                **_safe_error(exc),
                "healthObservationWritten": health_result is not None,
                "automaticRetry": False,
            }
        if (
            readiness_result.get("status")
            != "R12_ECOMMERCE_RUNTIME_READINESS_REFRESH_GREEN"
        ):
            return {
                "status": "TEXT_PROVIDER_HEALTH_MAINTENANCE_BLOCKED",
                "stage": "binding_readiness",
                "errorType": "UnexpectedReadinessStatus",
                "errorCode": str(readiness_result.get("status") or "missing"),
                "healthObservationWritten": health_result is not None,
                "automaticRetry": False,
            }
        self._readiness_pending = False
        return {
            "status": "TEXT_PROVIDER_HEALTH_MAINTENANCE_GREEN",
            "observationId": (
                health_result.get("observationId") if health_result else None
            ),
            "expiresAt": health_result.get("expiresAt") if health_result else None,
            "completedRoles": readiness_result.get("completedRoles") or [],
            "providerCalls": int((health_result or {}).get("providerCalls") or 0),
            "agentRunsCreated": 0,
            "secretPayloadReadsReported": 0,
        }
