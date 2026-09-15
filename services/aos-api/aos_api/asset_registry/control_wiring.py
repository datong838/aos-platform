"""Production wiring shared by Registry and the M2-B control plane."""

from __future__ import annotations

import os
import json
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
    pipeline_control_factory: Any = None
    first_dispatch_registration_service: Any = None
    ecommerce_growth_cutover_service: Any = None
    ecommerce_growth_cutover_control: Any = None
    workshop_catalog: Any = None


class _LazyRuntimeWorkshopCatalog:
    """Read-only catalog dependencies are resolved only when requested."""

    def __init__(self, *, view_reader):
        self._view_reader = view_reader
        self._catalog = None

    def resolve_catalog(self):
        if self._catalog is None:
            from aos_api.asset_registry.workshop_catalog_source import PostgresWorkshopCatalogSource
            from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalog

            self._catalog = RuntimeWorkshopCatalog(
                source=PostgresWorkshopCatalogSource(),
                loader=ManifestLoader(
                    _allowlist_roots(repository_root=_REPOSITORY_ROOT),
                    trust_roots=_configured_trust_roots(),
                ),
                view_reader=self._view_reader,
            )
        return self._catalog

    def list_modules(self, **kwargs):
        return self.resolve_catalog().list_modules(**kwargs)


def build_runtime_workshop_catalog_reader(*, view_reader):
    return _LazyRuntimeWorkshopCatalog(view_reader=view_reader)


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

    def list_configurations(self, **kwargs: Any) -> Any:
        return self._resolve().list_configurations(**kwargs)

    def list_configuration_sources(self, **kwargs: Any) -> Any:
        return self._resolve().list_configuration_sources(**kwargs)

    def get_operation(self, **kwargs: Any) -> Any:
        return self._resolve().get_operation(**kwargs)


def build_production_runtime_host_selection(*, control_plane: RuntimeControlPlane):
    """Build but do not start the explicitly enabled persistent runtime host."""
    from aos_api.asset_registry.control_policy import (
        APPLY_INSTALLATION_OPERATION,
        DISABLE_RUNTIME_OPERATION,
        ENABLE_RUNTIME_OPERATION,
        VERIFY_INSTALLATION_OPERATION,
    )
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.generation_attempts import GenerationDrainReader
    from aos_api.extension_runtime.oci_driver import CleanupOnlyOciDriver, OciDriver
    from aos_api.extension_runtime.production_preparation import (
        ProductionPreparationDependencies,
    )
    from aos_api.extension_runtime.production_runtime import (
        RuntimeWorkerDependencies,
        select_production_runtime_host,
    )
    from aos_api.extension_runtime.release_revalidation import RuntimeReleaseRevalidator
    from aos_api.extension_runtime.runtime_connections import (
        runtime_directory_connection,
        runtime_web_identity_connection,
        runtime_worker_connection,
    )

    enabled = os.getenv("AOS_EXTENSION_RUNTIME_HOST_ENABLED", "").strip() == "1"
    runtime_dsn = os.getenv("AOS_EXTENSION_RUNTIME_DATABASE_URL", "").strip()
    directory_dsn = os.getenv("AOS_EXTENSION_DIRECTORY_DATABASE_URL", "").strip()
    credential_reference = os.getenv("AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE", "").strip()
    oci_context = os.getenv("AOS_EXTENSION_OCI_CONTEXT", "").strip()
    runtime_platform = os.getenv("AOS_EXTENSION_RUNTIME_PLATFORM", "").strip()
    dependencies = None
    if (
        enabled
        and type(control_plane) is RuntimeControlPlane
        and (credential_reference or (runtime_dsn and directory_dsn))
        and oci_context
        and runtime_platform
    ):
        try:
            trust_roots = _configured_trust_roots()
            policy = ReleasePolicy(trust_roots=trust_roots)
            loader = ManifestLoader(
                _allowlist_roots(repository_root=_REPOSITORY_ROOT),
                trust_roots=trust_roots,
            )
            driver = OciDriver(context=oci_context)
            preparation = ProductionPreparationDependencies(
                connect=runtime_worker_connection,
                installation_store=control_plane.installation_store,
                revalidator=RuntimeReleaseRevalidator(release_policy=policy),
                policy=policy,
                loader=loader,
                apply_permission=CurrentControlPermission(
                    operation=APPLY_INSTALLATION_OPERATION
                ),
                verification_permission=CurrentControlPermission(
                    operation=VERIFY_INSTALLATION_OPERATION
                ),
                enable_permission=CurrentControlPermission(
                    operation=ENABLE_RUNTIME_OPERATION
                ),
                configuration_authorize=control_plane.configuration_authorize,
                driver=driver,
                platform=runtime_platform,
                live_directory=control_plane.live_job_directory,
            )
            ui_catalog=None
            ui_markings=()
            if os.getenv('AOS_EXTENSION_RUNTIME_UI_READ_ENABLED','').strip()=='1':
                from aos_api.asset_registry.workshop_catalog_source import PostgresWorkshopCatalogSource
                from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalog
                if not callable(getattr(control_plane.view_reader,'get_installation',None)):
                    raise ValueError('current runtime UI view reader required')
                raw_markings=json.loads(os.getenv('AOS_EXTENSION_UI_READ_MARKINGS_JSON','[]'))
                if type(raw_markings) is not list:raise ValueError('UI markings must be a JSON list')
                ui_markings=tuple(raw_markings)
                ui_catalog=RuntimeWorkshopCatalog(source=PostgresWorkshopCatalogSource(),loader=loader,
                                                   view_reader=control_plane.view_reader)
            stage_flag = os.getenv('AOS_EXTENSION_RUNTIME_CONFIGURATION_STAGE_ENABLED','0').strip()
            if stage_flag not in {'0','1'}:
                raise ValueError('exact configuration staging flag required')
            dependencies = RuntimeWorkerDependencies(
                installation_store=control_plane.installation_store,
                configuration_authorize=control_plane.configuration_authorize,
                disable_permission=CurrentControlPermission(
                    operation=DISABLE_RUNTIME_OPERATION
                ),
                drain_reader=GenerationDrainReader(),
                cleanup_driver=CleanupOnlyOciDriver(driver),
                disable_dependent=control_plane.disable_dependent,
                preparation=preparation,
                ui_read_catalog=ui_catalog,
                ui_read_markings=ui_markings,
                configuration_stage_enabled=stage_flag == '1',
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


def build_runtime_ui_resource_reader():
    """Read published static frontend code without inheriting tenant scope."""
    from aos_api.db import connect_read_only
    from aos_api.asset_registry.release_policy import ReleasePolicy
    from aos_api.extension_runtime.ui_resource_reader import PublishedUiResourceReader

    roots = _configured_trust_roots()
    return PublishedUiResourceReader(
        connect_factory=lambda: connect_read_only(inherit_scope=False),
        release_policy=ReleasePolicy(trust_roots=roots),
        loader=ManifestLoader(_allowlist_roots(repository_root=_REPOSITORY_ROOT), trust_roots=roots),
    )


def build_runtime_lifecycle_service():
    """Wire preparation commands, without exposing routes or starting workers."""
    return build_runtime_control_plane().lifecycle_service


def build_runtime_view_reader():
    """Build the read-only runtime projection without enabling command services."""
    return _LazyRuntimeViewReader()


def build_runtime_control_plane(*, disable_dependent: Any = None, registration_connect: Any = None) -> RuntimeControlPlane:
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
    from aos_api.pipeline_control_service import PipelineControlServiceFactory

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
    registration = None
    cutover = None
    cutover_control = None
    if registration_connect is not None:
        from aos_api.ecommerce_growth_registration import FirstDispatchRegistrationService
        registration = FirstDispatchRegistrationService(
            connect=registration_connect, installation_store=store,
            configuration_authorize=authorize, release_policy=policy,
        )
        from aos_api.ecommerce_growth_cutover import EcommerceGrowthCutoverStore
        from aos_api.ecommerce_growth_cutover_connection import scoped_cutover_connection
        cutover = EcommerceGrowthCutoverStore(
            scoped_cutover_connection(registration_connect), registration_service=registration,
        )
        from aos_api.ecommerce_growth_cutover_control import EcommerceGrowthCutoverControl
        cutover_control = EcommerceGrowthCutoverControl(cutover)
    view_reader = RuntimeViewReader(
        installation_reader=_build_read_only_installation_service(),
        ui_session_resolver=_build_runtime_ui_session_resolver(),
    )
    return RuntimeControlPlane(
        workshop_catalog=build_runtime_workshop_catalog_reader(view_reader=view_reader),
        first_dispatch_registration_service=registration,
        ecommerce_growth_cutover_service=cutover,
        ecommerce_growth_cutover_control=cutover_control,
        installation_store=store,
        installation_reader=installation,
        revalidator=planning,
        lifecycle_service=lifecycle,
        configuration_service=configuration,
        disable_service=disable,
        view_reader=view_reader,
        configuration_authorize=authorize,
        disable_dependent=disable_dependent,
        live_job_directory=LivePreparedJobDirectory(),
        pipeline_control_factory=PipelineControlServiceFactory(
            event_dispatch_connect=registration_connect,
            installation_store=store,
            policy=policy,
            allowlist_roots=_allowlist_roots(repository_root=_REPOSITORY_ROOT),
        ),
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
        server_root = Path(configured_root)
        roots["server"] = server_root
        # Canonical ecommerce releases created by the first-install executor
        # persist this alias in their immutable artifact references.
        roots["a0v-canonical"] = server_root
    return roots


def _configured_trust_roots() -> TrustRootProvider | None:
    if not os.getenv(TRUST_ROOTS_ENV):
        return None
    try:
        return FileTrustRootProvider.from_environment()
    except (TrustRootConfigurationError, TypeError, ValueError) as exc:
        return _UnavailableTrustRootProvider(exc)
