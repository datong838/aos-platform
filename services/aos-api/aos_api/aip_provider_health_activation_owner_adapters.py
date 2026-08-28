"""Production read-only owner adapters for Provider Health activation facts."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Iterable, Mapping

from aos_api.aip_action_store import AipActionNotFound, AipActionStore
from aos_api.aip_model_runtime_store import AipModelRuntimeStore
from aos_api.aip_provider_health_action import (
    PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID,
)
from aos_api.aip_provider_health_activation_fact_readers import (
    ActivationFactOwnerReaders,
    AuthorityFactSnapshot,
    BindingFactSnapshot,
    CANONICAL_ENVIRONMENT,
    CANONICAL_PROVIDER_REVISIONS,
    DeploymentFactSnapshot,
    EnvironmentFactSnapshot,
    HealthFactSnapshot,
    HealthObservationSnapshot,
    OwnerReader,
    PluginFactSnapshot,
    SourceReadinessFactSnapshot,
    build_canonical_activation_fact_readers,
)
from aos_api.aip_provider_health_maintenance_startup import (
    CANONICAL_PLUGIN_ID,
    CANONICAL_SCOPE,
    _default_plugin_catalog,
)
from aos_api.source_readiness import build_source_readiness_service


DEPLOYED_REVISION_ENV = "AOS_DEPLOYED_REVISION"
Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _value(item: Any) -> Any:
    return getattr(item, "value", item)


@dataclass(frozen=True, slots=True)
class ProductionActivationFactReaderBundle:
    collected_at: datetime
    readers: Mapping[str, Callable[..., Any]]


def build_production_activation_fact_readers(
    *,
    expected_deployed_revision: str,
    expected_action_type_revision_hash: str,
    authority_reader: OwnerReader,
    binding_reader: OwnerReader,
    environ: Mapping[str, str] | None = None,
    clock: Clock = _utc_now,
    plugin_catalog_reader: Callable[[], Mapping[str, Any]] | None = None,
    action_type_reader: Callable[[Any, str], Mapping[str, Any]] | None = None,
    health_reader: Callable[[Any], Iterable[Any]] | None = None,
    source_readiness_reader: Callable[[str, str], Any] | None = None,
) -> ProductionActivationFactReaderBundle:
    """Read each owner once and return cached, immutable audit readers."""
    if authority_reader is None or binding_reader is None:
        raise ValueError("Action authority and Binding readers are required")
    env = environ if environ is not None else os.environ
    plugin_catalog = plugin_catalog_reader or _default_plugin_catalog
    action_snapshot = action_type_reader or AipActionStore().action_type_snapshot
    list_health = health_reader or AipModelRuntimeStore().list_latest_provider_health
    source_readiness = source_readiness_reader or (
        lambda org_id, project_id: build_source_readiness_service().read(
            org_id=org_id, project_id=project_id
        )
    )

    started_at = clock()
    tenant = f"{CANONICAL_SCOPE.org_id}/{CANONICAL_SCOPE.project_id}"
    snapshots: dict[str, Any] = {}
    failed_sources: set[str] = set()

    def capture(source_id: str, collect: Callable[[], Any]) -> None:
        try:
            snapshots[source_id] = collect()
        except Exception:  # owner boundaries never expose provider/store details
            failed_sources.add(source_id)

    capture(
        "deployment",
        lambda: DeploymentFactSnapshot(
            tenant=tenant,
            observed_at=started_at,
            deployed_revision=env.get(DEPLOYED_REVISION_ENV),
        ),
    )
    capture(
        "environment",
        lambda: EnvironmentFactSnapshot(
            tenant=tenant,
            observed_at=started_at,
            values={key: env[key] for key in CANONICAL_ENVIRONMENT if key in env},
        ),
    )

    def collect_plugin() -> PluginFactSnapshot:
        catalog = plugin_catalog()
        matches = [
            item
            for item in catalog.get("items", [])
            if item.get("id") == CANONICAL_PLUGIN_ID
        ]
        if len(matches) > 1:
            raise ValueError("canonical plugin catalog is ambiguous")
        plugin_item = matches[0] if matches else None
        try:
            action_type = action_snapshot(
                CANONICAL_SCOPE, PROVIDER_HEALTH_PROBE_ACTION_TYPE_ID
            )
        except AipActionNotFound:
            action_type = None
        return PluginFactSnapshot(
            tenant=tenant,
            observed_at=started_at,
            plugin_id=plugin_item.get("id") if plugin_item else None,
            installed=bool(plugin_item and plugin_item.get("installed")),
            action_type_id=(
                plugin_item.get("actionTypeId") if plugin_item else None
            ),
            action_type_revision_hash=(
                action_type.get("revisionHash") if action_type else None
            ),
        )

    def collect_health() -> HealthFactSnapshot:
        observations = []
        for item in list_health(CANONICAL_SCOPE):
            provider_id = item.provider.asset_id
            provider_revision = item.provider.revision
            if CANONICAL_PROVIDER_REVISIONS.get(provider_id) != provider_revision:
                continue
            observations.append(
                HealthObservationSnapshot(
                    provider_id=provider_id,
                    provider_revision=provider_revision,
                    healthy=_value(item.status) == "healthy",
                    expires_at=item.expires_at,
                )
            )
        return HealthFactSnapshot(
            tenant=tenant,
            observed_at=started_at,
            cutoff=started_at,
            observations=tuple(observations),
        )

    def collect_source_readiness() -> SourceReadinessFactSnapshot:
        envelope = source_readiness(
            CANONICAL_SCOPE.org_id, CANONICAL_SCOPE.project_id
        )
        sources = tuple(envelope.sources)
        freshness = [item.freshness_expires_at for item in sources]
        return SourceReadinessFactSnapshot(
            tenant=tenant,
            observed_at=envelope.checked_at,
            ready_count=sum(_value(item.status) == "ready" for item in sources),
            required_count=len(sources),
            fresh_until=(
                min(freshness) if freshness and all(freshness) else None
            ),
            cutoff=envelope.cutoff_at,
        )

    capture("plugin", collect_plugin)
    capture("authority", lambda: authority_reader(tenant, started_at))
    capture("health", collect_health)
    capture("source_readiness", collect_source_readiness)
    capture("binding", lambda: binding_reader(tenant, started_at))
    collected_at = clock()

    def cached(source_id: str) -> OwnerReader:
        def read(requested_tenant: str, evaluated_at: datetime) -> Any:
            if source_id in failed_sources:
                raise RuntimeError("production owner read failed")
            return snapshots[source_id]

        return read

    owners = ActivationFactOwnerReaders(
        **{
            source_id: cached(source_id)
            for source_id in ActivationFactOwnerReaders.__annotations__
        }
    )
    readers = build_canonical_activation_fact_readers(
        expected_deployed_revision=expected_deployed_revision,
        expected_action_type_revision_hash=expected_action_type_revision_hash,
        owners=owners,
    )
    return ProductionActivationFactReaderBundle(
        collected_at=collected_at,
        readers=readers,
    )


__all__ = [
    "DEPLOYED_REVISION_ENV",
    "ProductionActivationFactReaderBundle",
    "build_production_activation_fact_readers",
    "AuthorityFactSnapshot",
    "BindingFactSnapshot",
]
