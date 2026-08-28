"""Fail-closed startup preflight for canonical Provider Health maintenance."""
from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from aos_api.aip_action_store import AipActionStore, AipActionStoreError
from aos_api.aip_provider_health_action import PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
from aos_api.aip_provider_health_action_authority import (
    provider_health_action_type_snapshot,
)
from aos_api.auth import Principal
from aos_api.tenant_scope import TenantScope

MAINTENANCE_ENABLED_ENV = "AOS_AIP_TEXT_HEALTH_MAINTENANCE_ENABLED"
AUTHORITY_MODE_ENV = "AOS_AIP_TEXT_HEALTH_CANONICAL_AUTHORITY_MODE"
SERVICE_SUBJECT_ENV = "AOS_AIP_TEXT_HEALTH_SERVICE_SUBJECT"
SERVICE_ORG_ENV = "AOS_AIP_TEXT_HEALTH_SERVICE_ORG_ID"
SERVICE_PROJECT_ENV = "AOS_AIP_TEXT_HEALTH_SERVICE_PROJECT_ID"

CANONICAL_AUTHORITY_MODE = "action-lease-v1"
CANONICAL_SERVICE_SUBJECT = "service:aip-provider-health-maintenance"
CANONICAL_SCOPE = TenantScope("org-org", "dev-project")
CANONICAL_SERVICE_ROLES = ["aip_executor"]
CANONICAL_SERVICE_MARKINGS = ["public", "restricted"]
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class ProviderHealthStartupPreflightError(RuntimeError):
    """Stable startup failure that contains no credential or Provider detail."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ProviderHealthStartupPreflight:
    status: str
    enabled: bool
    ready: bool
    authority_mode: str | None = None
    principal: Principal | None = None
    action_type_snapshot: dict[str, Any] | None = None


def _legacy_maintenance_enabled(environ: Mapping[str, str]) -> bool:
    return environ.get(MAINTENANCE_ENABLED_ENV, "false").strip().lower() in (
        _TRUE_VALUES
    )


def preflight_provider_health_maintenance_startup(
    *,
    environ: Mapping[str, str] | None = None,
    action_store: AipActionStore | None = None,
) -> ProviderHealthStartupPreflight:
    """Validate wiring prerequisites without constructing or starting a runtime."""
    env = os.environ if environ is None else environ
    if not _legacy_maintenance_enabled(env):
        return ProviderHealthStartupPreflight(
            status="PROVIDER_HEALTH_MAINTENANCE_STARTUP_INACTIVE",
            enabled=False,
            ready=False,
        )

    authority_mode = env.get(AUTHORITY_MODE_ENV)
    if authority_mode != CANONICAL_AUTHORITY_MODE:
        raise ProviderHealthStartupPreflightError(
            "CANONICAL_ACTION_LEASE_AUTHORITY_MODE_REQUIRED"
        )
    if env.get(SERVICE_SUBJECT_ENV) != CANONICAL_SERVICE_SUBJECT:
        raise ProviderHealthStartupPreflightError(
            "EXACT_PROVIDER_HEALTH_SERVICE_SUBJECT_REQUIRED"
        )
    if (
        env.get(SERVICE_ORG_ENV) != CANONICAL_SCOPE.org_id
        or env.get(SERVICE_PROJECT_ENV) != CANONICAL_SCOPE.project_id
    ):
        raise ProviderHealthStartupPreflightError(
            "EXACT_PROVIDER_HEALTH_SERVICE_TENANT_REQUIRED"
        )

    principal = Principal(
        subject=CANONICAL_SERVICE_SUBJECT,
        org_id=CANONICAL_SCOPE.org_id,
        project_id=CANONICAL_SCOPE.project_id,
        roles=list(CANONICAL_SERVICE_ROLES),
        markings=list(CANONICAL_SERVICE_MARKINGS),
        token_kind="service",
    )
    store = action_store or AipActionStore()
    expected = provider_health_action_type_snapshot()
    try:
        installed = store.action_type_snapshot(
            CANONICAL_SCOPE,
            PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
        )
    except AipActionStoreError as exc:
        raise ProviderHealthStartupPreflightError(
            "PROVIDER_HEALTH_ACTION_TYPE_NOT_INSTALLED"
        ) from exc
    if installed != expected:
        raise ProviderHealthStartupPreflightError(
            "PROVIDER_HEALTH_ACTION_TYPE_REVISION_DRIFTED"
        )
    return ProviderHealthStartupPreflight(
        status="PROVIDER_HEALTH_MAINTENANCE_STARTUP_PREFLIGHT_GREEN",
        enabled=True,
        ready=True,
        authority_mode=authority_mode,
        principal=principal,
        action_type_snapshot=installed,
    )


__all__ = [
    "AUTHORITY_MODE_ENV",
    "CANONICAL_AUTHORITY_MODE",
    "CANONICAL_SCOPE",
    "CANONICAL_SERVICE_MARKINGS",
    "CANONICAL_SERVICE_ROLES",
    "CANONICAL_SERVICE_SUBJECT",
    "MAINTENANCE_ENABLED_ENV",
    "ProviderHealthStartupPreflight",
    "ProviderHealthStartupPreflightError",
    "SERVICE_ORG_ENV",
    "SERVICE_PROJECT_ENV",
    "SERVICE_SUBJECT_ENV",
    "preflight_provider_health_maintenance_startup",
]
