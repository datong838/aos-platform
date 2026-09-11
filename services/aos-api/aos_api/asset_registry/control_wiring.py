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
    disable_service: Any = None
    view_reader: Any = None
    disable_dependent: Any = None
    live_job_directory: Any = None


class _LazyRuntimeViewReader:
    """Resolve the read projection on first request, not during app import."""

    def __init__(self) -> None:
        self._reader: Any = None

    def _resolve(self) -> Any:
        if self._reader is None:
            from aos_api.extension_runtime.runtime_view import RuntimeViewReader

            self._reader = RuntimeViewReader(
                installation_reader=_build_read_only_installation_service(),
                ui_session_resolver=_build_runtime_ui_session_resolver(),
            )
        return self._reader

    def get_installation(self, **kwargs: Any) -> Any:
        return self._resolve().get_installation(**kwargs)

    def get_operation(self, **kwargs: Any) -> Any:
        return self._resolve().get_operation(**kwargs)


def build_production_runtime_host_selection(*, control_plane: RuntimeControlPlane):
    """Build but do not start the explicitly enabled persistent runtime host."""
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.oci_driver import CleanupOnlyOciDriver, OciDriver
    from aos_api.extension_runtime.production_runtime import (
        RuntimeWorkerDependencies,
        select_production_runtime_host,
    )
    from aos_api.extension_runtime.runtime_connections import (
        runtime_directory_connection,
        runtime_web_identity_connection,
        runtime_worker_connection,
    )

    enabled = os.getenv("AOS_EXTENSION_RUNTIME_HOST_ENABLED", "").strip() == "1"
    runtime_dsn = os.getenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "").strip()
    directory_dsn = os.getenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "").strip()
    oci_context = os.getenv("AOS_EXTENSION_OCI_CONTEXT", "").strip()
    dependencies = None
    if (
        enabled
        and type(control_plane) is RuntimeControlPlane
        and runtime_dsn
        and directory_dsn
        and oci_context
    ):
        try:
            dependencies = RuntimeWorkerDependencies(
                installation_store=control_plane.installation_store,
                configuration_authorize=control_plane.configuration_authorize,
                disable_permission=CurrentControlPermission(
                    operation=DISABLE_RUNTIME_OPERATION
                ),
                drain_reader=GenerationDrainReader(),
                cleanup_driver=CleanupOnlyOciDriver(OciDriver(context=oci_context)),
                disable_dependent=control_plane.disable_dependent,
            )
        except (TypeError, ValueError):
            dependencies = None
    return select_production_runtime_host(
        enabled=enabled,
        directory_connect=runtime_directory_connection,
        runtime_connect=runtime_worker_connection,
        web_connect=runtime_web_identity_connection,
        dependencies=dependencies,
    )


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
    from aos_api.extension_runtime.runtime_uninstall import RuntimeUninstallGuard

    return InstallationService(
        store=PostgresInstallationStore(),
        composition_store=PostgresCompositionStore(),
        revalidator=InstallationRevalidator(
            release_policy=ReleasePolicy(trust_roots=_configured_trust_roots())
        ),
        runtime_uninstall_guard=RuntimeUninstallGuard(),
    )


def _build_read_only_installation_service() -> InstallationControl:
    """Build the Installation projection with an actually read-only connection."""

    from aos_api.asset_registry.composition_store import PostgresCompositionStore
    from aos_api.asset_registry.installation_revalidation import InstallationRevalidator
    from aos_api.asset_registry.installation_service import InstallationService
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.db import connect_read_only

    return InstallationService(
        store=PostgresInstallationStore(connect_factory=connect_read_only),
        composition_store=PostgresCompositionStore(),
        revalidator=InstallationRevalidator(
            release_policy=ReleasePolicy(trust_roots=_configured_trust_roots())
        ),
    )


def _build_runtime_ui_session_resolver():
    """Build the fail-closed signed frontend projection from server-owned inputs."""

    from aos_api.db import connect_read_only
    from aos_api.extension_runtime.ui_resources import ProductionUiSessionResolver
    from aos_api.asset_registry.release_policy import ReleasePolicy

    loader = ManifestLoader(
        _allowlist_roots(repository_root=_REPOSITORY_ROOT),
        trust_roots=_configured_trust_roots(),
    )
    return ProductionUiSessionResolver(
        connect_factory=connect_read_only,
        release_policy=ReleasePolicy(trust_roots=_configured_trust_roots()),
        loader=loader,
        resource_origin=os.getenv("AOS_EXTENSION_UI_RESOURCE_ORIGIN"),
    )


def build_runtime_lifecycle_service():
    """Wire preparation commands, without exposing routes or starting workers."""
    return build_runtime_control_plane().lifecycle_service


def build_runtime_view_reader():
    """Build the read-only runtime projection without enabling command services."""
    return _LazyRuntimeViewReader()


def build_runtime_control_plane(*, disable_dependent: Any = None) -> RuntimeControlPlane:
    """Assemble current runtime controls without connecting or starting workers."""
    from aos_api.aip_runtime_configuration_sources import (
        build_current_configuration_authorization,
    )
    from aos_api.asset_registry.composition_store import PostgresCompositionStore
    from aos_api.asset_registry.installation_revalidation import (
        InstallationRevalidator,
    )
    from aos_api.asset_registry.installation_service import InstallationService
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.extension_runtime.configuration_service import (
        RuntimeConfigurationService,
    )
    from aos_api.extension_runtime.configuration_authorization import (
        CurrentConfigurationPermission,
    )
    from aos_api.extension_runtime.lifecycle_service import RuntimeLifecycleService
    from aos_api.extension_runtime.disable_service import RuntimeDisableService
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.runtime_view import RuntimeViewReader
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.extension_runtime.release_revalidation import (
        RuntimeReleaseRevalidator,
    )
    from aos_api.extension_runtime.runtime_uninstall import RuntimeUninstallGuard
    from aos_api.extension_runtime.live_job_directory import LivePreparedJobDirectory

    store = PostgresInstallationStore()
    policy = ReleasePolicy(trust_roots=_configured_trust_roots())
    planning = RuntimeReleaseRevalidator(release_policy=policy)
    installation = InstallationService(
        store=store,
        composition_store=PostgresCompositionStore(),
        revalidator=InstallationRevalidator(release_policy=policy),
        planning_revalidator=planning,
        runtime_uninstall_guard=RuntimeUninstallGuard(),
    )

    disable = RuntimeDisableService(
        installation_store=store,
        installation_reader=installation,
        check_current_permission=CurrentControlPermission(
            operation=DISABLE_RUNTIME_OPERATION
        ),
        dependent=disable_dependent,
    )
    authorize = build_current_configuration_authorization(
        permission=CurrentConfigurationPermission(installation_store=store)
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
        disable_service=disable,
        view_reader=RuntimeViewReader(
            installation_reader=_build_read_only_installation_service(),
            ui_session_resolver=_build_runtime_ui_session_resolver(),
        ),
        configuration_authorize=authorize,
        disable_dependent=disable_dependent,
        live_job_directory=LivePreparedJobDirectory(),
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
