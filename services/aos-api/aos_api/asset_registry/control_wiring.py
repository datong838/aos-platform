"""Production wiring shared by Registry and the M2-B control plane."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aos_api.asset_registry.control_protocols import (
    CompositionControl,
    InstallationControl,
)
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.registry_service import RegistryService
from aos_api.asset_registry.registry_store import PostgresRegistryStore
from aos_api.asset_registry.signature import (
    TRUST_ROOTS_ENV,
    FileTrustRootProvider,
    TrustRoot,
    TrustRootConfigurationError,
    TrustRootProvider,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RegistryStoreFactory = Callable[[], Any]
ManifestLoaderFactory = Callable[..., Any]


@dataclass(frozen=True, slots=True)
class RuntimeControlPlane:
    """Process-owned control services; construction starts no runtime work."""

    installation_store: Any
    installation_reader: Any
    revalidator: Any
    lifecycle_service: Any
    configuration_service: Any
    configuration_authorize: Any


class _UnavailableTrustRootProvider:
    """Deferred fail-closed provider that keeps read-only Registry APIs alive."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    def get_trust_root(self, *, publisher: str, key_id: str) -> TrustRoot | None:
        raise TrustRootConfigurationError(
            "trust-root configuration is unavailable"
        ) from self._error


def build_asset_registry_service(
    *,
    repository_root: Path = _REPOSITORY_ROOT,
    registry_store_factory: RegistryStoreFactory = PostgresRegistryStore,
    manifest_loader_factory: ManifestLoaderFactory = ManifestLoader,
) -> RegistryService:
    """Build the canonical Registry service from server-controlled roots."""

    trust_roots = _configured_trust_roots()
    loader = manifest_loader_factory(
        _allowlist_roots(repository_root=repository_root),
        trust_roots=trust_roots,
    )
    return RegistryService(
        store=registry_store_factory(),
        loader=loader,
        trust_roots=trust_roots,
    )


def build_composition_service() -> CompositionControl:
    """Lazily assemble the M2-B Composition service after B1 is installed."""

    from aos_api.asset_registry.composition_service import CompositionService
    from aos_api.asset_registry.composition_store import PostgresCompositionStore
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.registry_snapshot import RegistrySnapshotReader
    from aos_api.asset_registry.release_policy import ReleasePolicy

    installation_store = PostgresInstallationStore()
    return CompositionService(
        snapshot_reader=RegistrySnapshotReader(
            release_policy=ReleasePolicy(trust_roots=_configured_trust_roots())
        ),
        composition_store=PostgresCompositionStore(),
        command_store=installation_store,
        baseline_reader=installation_store,
    )


def build_installation_service() -> InstallationControl:
    """Lazily assemble the M2-B Installation service after B1 is installed."""

    from aos_api.asset_registry.composition_store import PostgresCompositionStore
    from aos_api.asset_registry.installation_revalidation import (
        InstallationRevalidator,
    )
    from aos_api.asset_registry.installation_service import InstallationService
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.release_policy import ReleasePolicy

    return InstallationService(
        store=PostgresInstallationStore(),
        composition_store=PostgresCompositionStore(),
        revalidator=InstallationRevalidator(
            release_policy=ReleasePolicy(trust_roots=_configured_trust_roots())
        ),
    )


def build_runtime_lifecycle_service():
    """Wire preparation commands, without exposing routes or starting workers."""
    return build_runtime_control_plane().lifecycle_service


def build_runtime_control_plane() -> RuntimeControlPlane:
    """Assemble current runtime controls without connecting or starting workers."""
    from aos_api.aip_runtime_configuration_sources import (
        build_current_configuration_authorization,
    )
    from aos_api.asset_registry.composition_store import PostgresCompositionStore
    from aos_api.asset_registry.control_policy import CONFIGURE_RUNTIME_OPERATION
    from aos_api.asset_registry.installation_revalidation import (
        InstallationRevalidator,
    )
    from aos_api.asset_registry.installation_service import InstallationService
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.extension_runtime.configuration_service import (
        RuntimeConfigurationService,
    )
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.lifecycle_service import RuntimeLifecycleService
    from aos_api.extension_runtime.release_revalidation import (
        RuntimeReleaseRevalidator,
    )

    store = PostgresInstallationStore()
    policy = ReleasePolicy(trust_roots=_configured_trust_roots())
    planning = RuntimeReleaseRevalidator(release_policy=policy)
    installation = InstallationService(
        store=store,
        composition_store=PostgresCompositionStore(),
        revalidator=InstallationRevalidator(release_policy=policy),
        planning_revalidator=planning,
    )

    def current_configuration_permission(
        conn,
        *,
        org_id,
        project_id,
        installation_id,
        actor,
        **_,
    ):
        row = conn.execute(
            """SELECT etag_version FROM bundle_installation
               WHERE org_id=%s AND project_id=%s AND installation_id=%s
               FOR UPDATE""",
            (org_id, project_id, installation_id),
        ).fetchone()
        if row is None:
            raise LookupError("configuration installation not found")
        etag = row["etag_version"] if isinstance(row, dict) else row[0]
        locked = store.lock_for_transition_in_transaction(
            conn,
            org_id=org_id,
            project_id=project_id,
            installation_id=installation_id,
            expected_etag_version=etag,
        )
        return CurrentControlPermission(operation=CONFIGURE_RUNTIME_OPERATION)(
            conn=conn, locked=locked, actor=actor
        )

    authorize = build_current_configuration_authorization(
        permission=current_configuration_permission
    )
    lifecycle = RuntimeLifecycleService(
        installation_store=store,
        installation_reader=installation,
        revalidator=planning,
    )
    configuration = RuntimeConfigurationService(
        installation_store=store,
        installation_reader=installation,
        revalidator=planning,
        authorize=authorize,
    )
    return RuntimeControlPlane(
        installation_store=store,
        installation_reader=installation,
        revalidator=planning,
        lifecycle_service=lifecycle,
        configuration_service=configuration,
        configuration_authorize=authorize,
    )


def build_integration_case_service():
    """Assemble the M4 Integration Case service from PostgreSQL truth sources."""

    from aos_api.asset_registry.integration_projection import (
        IntegrationExpiryProjector,
    )
    from aos_api.asset_registry.integration_reader import (
        PostgresIntegrationCaseReader,
        PrincipalMarkingResolver,
    )
    from aos_api.asset_registry.integration_service import IntegrationCaseService
    from aos_api.asset_registry.integration_store import PostgresIntegrationStore

    return IntegrationCaseService(
        store=PostgresIntegrationStore(),
        reader=PostgresIntegrationCaseReader(),
        marking_resolver=PrincipalMarkingResolver(),
        expiry_projector=IntegrationExpiryProjector(),
    )


def _allowlist_roots(*, repository_root: Path) -> dict[str, Path]:
    roots: dict[str, Path] = {}
    catalog_root = repository_root / "bundles"
    if catalog_root.is_dir():
        roots["catalog"] = catalog_root
    configured_root = os.getenv("AOS_BUNDLE_ROOT")
    if configured_root:
        roots["server"] = Path(configured_root)
    return roots


def _configured_trust_roots() -> TrustRootProvider | None:
    if not os.getenv(TRUST_ROOTS_ENV):
        return None
    try:
        return FileTrustRootProvider.from_environment()
    except (TrustRootConfigurationError, TypeError, ValueError) as exc:
        return _UnavailableTrustRootProvider(exc)
