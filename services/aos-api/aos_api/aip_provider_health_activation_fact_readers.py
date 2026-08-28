"""Canonical sanitized fact readers for Provider Health activation audit."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Callable, Mapping

from aos_api.aip_provider_health_action import (
    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
)
from aos_api.aip_provider_health_activation_audit import ActivationFactSlice
from aos_api.aip_provider_health_activation_change_packet import CANONICAL_TENANT
from aos_api.aip_provider_health_maintenance_startup import (
    AUTHORITY_MODE_ENV,
    CANONICAL_AUTHORITY_MODE,
    CANONICAL_PLUGIN_ID,
    CANONICAL_SERVICE_SUBJECT,
    MAINTENANCE_ENABLED_ENV,
    SERVICE_ORG_ENV,
    SERVICE_PROJECT_ENV,
    SERVICE_SUBJECT_ENV,
)


CANONICAL_ENVIRONMENT = {
    MAINTENANCE_ENABLED_ENV: "true",
    AUTHORITY_MODE_ENV: CANONICAL_AUTHORITY_MODE,
    SERVICE_SUBJECT_ENV: CANONICAL_SERVICE_SUBJECT,
    SERVICE_ORG_ENV: "org-org",
    SERVICE_PROJECT_ENV: "dev-project",
}
CANONICAL_PROVIDER_REVISIONS = {
    "agnes-text-qyh-dev": 7,
    "agnes-image-qyh-dev": 2,
    "agnes-video-qyh-dev": 1,
}


@dataclass(frozen=True, slots=True)
class FactOwnerSnapshot:
    tenant: str
    observed_at: datetime

    def __post_init__(self) -> None:
        if self.tenant != CANONICAL_TENANT:
            raise ValueError("fact owner tenant is not canonical")
        if self.observed_at.tzinfo is None:
            raise ValueError("fact owner observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class DeploymentFactSnapshot(FactOwnerSnapshot):
    deployed_revision: str | None


@dataclass(frozen=True, slots=True)
class EnvironmentFactSnapshot(FactOwnerSnapshot):
    values: Mapping[str, str]

    def __post_init__(self) -> None:
        FactOwnerSnapshot.__post_init__(self)
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


@dataclass(frozen=True, slots=True)
class PluginFactSnapshot(FactOwnerSnapshot):
    plugin_id: str | None
    installed: bool
    action_type_id: str | None
    action_type_revision_hash: str | None


@dataclass(frozen=True, slots=True)
class AuthorityFactSnapshot(FactOwnerSnapshot):
    proposal_exact: bool
    approval_exact: bool
    lease_exact: bool
    receipt_authority_exact: bool
    lease_expires_at: datetime | None

    def __post_init__(self) -> None:
        FactOwnerSnapshot.__post_init__(self)
        if self.lease_expires_at is not None and self.lease_expires_at.tzinfo is None:
            raise ValueError("lease_expires_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class HealthObservationSnapshot:
    provider_id: str
    provider_revision: int
    healthy: bool
    expires_at: datetime

    def __post_init__(self) -> None:
        if self.expires_at.tzinfo is None:
            raise ValueError("health expires_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class HealthFactSnapshot(FactOwnerSnapshot):
    cutoff: datetime
    observations: tuple[HealthObservationSnapshot, ...]

    def __post_init__(self) -> None:
        FactOwnerSnapshot.__post_init__(self)
        if self.cutoff.tzinfo is None:
            raise ValueError("health cutoff must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SourceReadinessFactSnapshot(FactOwnerSnapshot):
    ready_count: int
    required_count: int
    fresh_until: datetime | None
    cutoff: datetime

    def __post_init__(self) -> None:
        FactOwnerSnapshot.__post_init__(self)
        if not 0 <= self.ready_count <= self.required_count:
            raise ValueError("SourceReadiness count is outside required range")
        if self.cutoff.tzinfo is None:
            raise ValueError("SourceReadiness cutoff must be timezone-aware")
        if self.fresh_until is not None and self.fresh_until.tzinfo is None:
            raise ValueError("SourceReadiness fresh_until must be timezone-aware")


@dataclass(frozen=True, slots=True)
class BindingFactSnapshot(FactOwnerSnapshot):
    exact: bool
    operational: bool
    expires_at: datetime | None
    cutoff: datetime | None

    def __post_init__(self) -> None:
        FactOwnerSnapshot.__post_init__(self)
        for name in ("expires_at", "cutoff"):
            value = getattr(self, name)
            if value is not None and value.tzinfo is None:
                raise ValueError(f"Binding {name} must be timezone-aware")


OwnerReader = Callable[[str, datetime], FactOwnerSnapshot]


@dataclass(frozen=True, slots=True)
class ActivationFactOwnerReaders:
    deployment: OwnerReader
    environment: OwnerReader
    plugin: OwnerReader
    authority: OwnerReader
    health: OwnerReader
    source_readiness: OwnerReader
    binding: OwnerReader


def _ensure_snapshot(
    snapshot: FactOwnerSnapshot,
    expected_type: type[FactOwnerSnapshot],
    tenant: str,
    evaluated_at: datetime,
) -> None:
    if not isinstance(snapshot, expected_type):
        raise TypeError("fact owner snapshot type mismatch")
    if snapshot.tenant != tenant:
        raise ValueError("fact owner tenant mismatch")
    if snapshot.observed_at > evaluated_at:
        raise ValueError("fact owner cutoff is in the future")


def build_canonical_activation_fact_readers(
    *,
    expected_deployed_revision: str,
    expected_action_type_revision_hash: str,
    owners: ActivationFactOwnerReaders,
) -> dict[str, Callable[[str, datetime], ActivationFactSlice]]:
    """Build reader-only adapters; returned functions cannot mutate or execute."""
    if not expected_deployed_revision.strip():
        raise ValueError("expected_deployed_revision must be non-empty")
    if not expected_action_type_revision_hash.strip():
        raise ValueError("expected_action_type_revision_hash must be non-empty")

    def deployment(tenant: str, at: datetime) -> ActivationFactSlice:
        item = owners.deployment(tenant, at)
        _ensure_snapshot(item, DeploymentFactSnapshot, tenant, at)
        assert isinstance(item, DeploymentFactSnapshot)
        return ActivationFactSlice(
            "deployment",
            tenant,
            item.observed_at,
            {
                "expected_deployed_revision": expected_deployed_revision,
                "deployed_revision": item.deployed_revision,
            },
        )

    def environment(tenant: str, at: datetime) -> ActivationFactSlice:
        item = owners.environment(tenant, at)
        _ensure_snapshot(item, EnvironmentFactSnapshot, tenant, at)
        assert isinstance(item, EnvironmentFactSnapshot)
        exact = dict(item.values) == CANONICAL_ENVIRONMENT
        return ActivationFactSlice(
            "environment",
            tenant,
            item.observed_at,
            {"canonical_environment_exact": exact},
        )

    def plugin(tenant: str, at: datetime) -> ActivationFactSlice:
        item = owners.plugin(tenant, at)
        _ensure_snapshot(item, PluginFactSnapshot, tenant, at)
        assert isinstance(item, PluginFactSnapshot)
        plugin_exact = (
            item.plugin_id == CANONICAL_PLUGIN_ID
            and item.action_type_id == PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
        )
        return ActivationFactSlice(
            "plugin",
            tenant,
            item.observed_at,
            {
                "plugin_installed": plugin_exact and item.installed,
                "action_type_exact": (
                    plugin_exact
                    and item.action_type_revision_hash
                    == expected_action_type_revision_hash
                ),
            },
        )

    def authority(tenant: str, at: datetime) -> ActivationFactSlice:
        item = owners.authority(tenant, at)
        _ensure_snapshot(item, AuthorityFactSnapshot, tenant, at)
        assert isinstance(item, AuthorityFactSnapshot)
        return ActivationFactSlice(
            "authority",
            tenant,
            item.observed_at,
            {
                "proposal_exact": item.proposal_exact,
                "approval_exact": item.approval_exact,
                "lease_exact": item.lease_exact,
                "receipt_authority_exact": item.receipt_authority_exact,
                "lease_expires_at": item.lease_expires_at,
            },
        )

    def health(tenant: str, at: datetime) -> ActivationFactSlice:
        item = owners.health(tenant, at)
        _ensure_snapshot(item, HealthFactSnapshot, tenant, at)
        assert isinstance(item, HealthFactSnapshot)
        if item.cutoff.tzinfo is None or item.cutoff > at:
            raise ValueError("health cutoff is invalid")
        by_ref = {
            (observation.provider_id, observation.provider_revision): observation
            for observation in item.observations
        }
        if len(by_ref) != len(item.observations):
            raise ValueError("health observations are not unique")
        expected_refs = set(CANONICAL_PROVIDER_REVISIONS.items())
        if set(by_ref) != expected_refs:
            raise ValueError("health observations are not the canonical set")
        healthy = [
            observation
            for observation in by_ref.values()
            if observation.healthy and observation.expires_at > at
        ]
        expires_at = min(
            (observation.expires_at for observation in by_ref.values()),
            default=None,
        )
        return ActivationFactSlice(
            "health",
            tenant,
            item.observed_at,
            {
                "healthy_probe_count": len(healthy),
                "required_probe_count": 3,
                "health_expires_at": expires_at,
                "health_cutoff": item.cutoff,
            },
        )

    def source_readiness(tenant: str, at: datetime) -> ActivationFactSlice:
        item = owners.source_readiness(tenant, at)
        _ensure_snapshot(item, SourceReadinessFactSnapshot, tenant, at)
        assert isinstance(item, SourceReadinessFactSnapshot)
        if item.required_count != 12:
            raise ValueError("SourceReadiness denominator is not canonical")
        if item.cutoff.tzinfo is None or item.cutoff > at:
            raise ValueError("SourceReadiness cutoff is invalid")
        return ActivationFactSlice(
            "source_readiness",
            tenant,
            item.observed_at,
            {
                "source_ready_count": item.ready_count,
                "source_required_count": item.required_count,
                "source_readiness_fresh_until": item.fresh_until,
                "source_readiness_cutoff": item.cutoff,
            },
        )

    def binding(tenant: str, at: datetime) -> ActivationFactSlice:
        item = owners.binding(tenant, at)
        _ensure_snapshot(item, BindingFactSnapshot, tenant, at)
        assert isinstance(item, BindingFactSnapshot)
        if item.cutoff is not None and (
            item.cutoff.tzinfo is None or item.cutoff > at
        ):
            raise ValueError("Binding cutoff is invalid")
        return ActivationFactSlice(
            "binding",
            tenant,
            item.observed_at,
            {
                "binding_exact": item.exact,
                "binding_operational": item.operational,
                "binding_expires_at": item.expires_at,
                "binding_cutoff": item.cutoff,
            },
        )

    return {
        "deployment": deployment,
        "environment": environment,
        "plugin": plugin,
        "authority": authority,
        "health": health,
        "source_readiness": source_readiness,
        "binding": binding,
    }


__all__ = [
    "ActivationFactOwnerReaders",
    "AuthorityFactSnapshot",
    "BindingFactSnapshot",
    "CANONICAL_ENVIRONMENT",
    "CANONICAL_PROVIDER_REVISIONS",
    "DeploymentFactSnapshot",
    "EnvironmentFactSnapshot",
    "FactOwnerSnapshot",
    "HealthFactSnapshot",
    "HealthObservationSnapshot",
    "PluginFactSnapshot",
    "SourceReadinessFactSnapshot",
    "build_canonical_activation_fact_readers",
]
