"""Fail-closed production selector for the persistent extension runtime host."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import inspect

from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.workshop_catalog_source import PostgresWorkshopCatalogSource
from aos_api.ecommerce_growth_lifecycle import EcommerceGrowthDisableDependent
from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalog
from .ui_read_consumer import RuntimeUiReadConsumer
from .ui_read_preflight import runtime_ui_read_ready

from .configuration_authorization import CurrentFourSourceConfigurationAuthorization
from .configuration_consumer import ConfigurationConsumer
from .configuration_stage_consumer import ConfigurationStageConsumer
from .configuration_stage_preflight import configuration_stage_ready
from .current_permission import CurrentControlPermission
from .disable_consumer import RuntimeDisableConsumer
from .generation_attempts import (
    ExpiredSignedReadAttemptRecovery,
    GenerationDrainReader,
)
from .oci_driver import CleanupOnlyOciDriver
from .production_preparation import ProductionPreparationDependencies
from .resource_recovery import ExpiredResourceRecovery
from .runtime_directory import PostgresRuntimeTenantDirectory
from .runtime_host import RuntimeHost, RuntimeTenantAssignment
from .runtime_identity import (
    RuntimeDatabaseIdentity,
    probe_runtime_database_identity,
    require_isolated_runtime_identities,
)

_PROTECTED_RELATIONS = (
    "bundle_installation",
    "extension_runtime_binding",
    "extension_runtime_execution_attempt",
    "extension_runtime_host_assignment",
    "extension_runtime_operation",
    "extension_runtime_outbox",
)


@dataclass(frozen=True, slots=True)
class RuntimeWorkerDependencies:
    installation_store: PostgresInstallationStore
    configuration_authorize: CurrentFourSourceConfigurationAuthorization
    disable_permission: CurrentControlPermission
    drain_reader: GenerationDrainReader
    cleanup_driver: CleanupOnlyOciDriver
    disable_dependent: EcommerceGrowthDisableDependent
    preparation: ProductionPreparationDependencies
    ui_read_catalog: RuntimeWorkshopCatalog | None = None
    ui_read_markings: tuple[str, ...] = ()
    configuration_stage_enabled: bool = False

    def __post_init__(self) -> None:
        if type(self.configuration_stage_enabled) is not bool:
            raise TypeError("exact configuration staging flag required")
        if type(self.installation_store) is not PostgresInstallationStore:
            raise TypeError("production runtime requires the PostgreSQL installation store")
        if (
            type(self.configuration_authorize)
            is not CurrentFourSourceConfigurationAuthorization
        ):
            raise TypeError("production runtime requires current four-source authority")
        if (
            type(self.disable_permission) is not CurrentControlPermission
            or self.disable_permission.operation != DISABLE_RUNTIME_OPERATION
        ):
            raise TypeError("production runtime requires current disable permission")
        if type(self.drain_reader) is not GenerationDrainReader:
            raise TypeError("production runtime requires the persistent generation drain reader")
        if type(self.cleanup_driver) is not CleanupOnlyOciDriver:
            raise TypeError("production runtime requires the cleanup-only OCI facade")
        if type(self.disable_dependent) is not EcommerceGrowthDisableDependent:
            raise TypeError("production runtime requires ecommerce disable lifecycle authority")
        if type(self.preparation) is not ProductionPreparationDependencies:
            raise TypeError("production runtime requires exact preparation dependencies")
        if (
            self.preparation.installation_store is not self.installation_store
            or self.preparation.configuration_authorize
            is not self.configuration_authorize
            or self.preparation.driver.context != self.cleanup_driver.context
        ):
            raise TypeError("production runtime dependency graph is inconsistent")

        if self.ui_read_catalog is not None and (type(self.ui_read_catalog) is not RuntimeWorkshopCatalog
                or self.ui_read_catalog._loader is not self.preparation.loader
                or type(self.ui_read_catalog._source) is not PostgresWorkshopCatalogSource
                or not callable(getattr(self.ui_read_catalog._view_reader,'get_installation',None))):
            raise TypeError('UI catalog must share the preparation loader')
        if (type(self.ui_read_markings) is not tuple or len(self.ui_read_markings)>500
                or any(type(x) is not str or not x or x!=x.strip() or not x.isprintable() for x in self.ui_read_markings)
                or len(set(self.ui_read_markings))!=len(self.ui_read_markings)
                or (self.ui_read_catalog is None and self.ui_read_markings)):
            raise ValueError('exact configured UI read markings required')


@dataclass(frozen=True, slots=True)
class RuntimeHostSelection:
    host: RuntimeHost | None
    status: str
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ("ACTIVE", "INACTIVE"):
            raise ValueError("invalid runtime host selection status")
        if self.status == "ACTIVE":
            if type(self.host) is not RuntimeHost or self.error_code is not None:
                raise ValueError("active runtime host selection is incomplete")
        elif self.host is not None or type(self.error_code) is not str or not self.error_code:
            raise ValueError("inactive runtime host selection requires a fixed error code")


def _inactive(code: str) -> RuntimeHostSelection:
    return RuntimeHostSelection(host=None, status="INACTIVE", error_code=code)


def _directory_identity(identity: RuntimeDatabaseIdentity) -> None:
    if type(identity) is not RuntimeDatabaseIdentity:
        raise TypeError("exact directory database identity required")
    if (
        not identity.directory_member
        or identity.runtime_member
        or identity.privileged
        or identity.owns_protected_relation
    ):
        raise RuntimeError("directory database principal is not isolated")


def select_production_runtime_host(
    *,
    enabled: bool,
    directory_connect,
    runtime_connect,
    web_connect,
    dependencies: RuntimeWorkerDependencies | None,
) -> RuntimeHostSelection:
    """Return ACTIVE only after every pure and database identity gate passes."""
    if enabled is not True:
        return _inactive("DISABLED")
    if type(dependencies) is not RuntimeWorkerDependencies:
        return _inactive("MISSING_DEPENDENCIES")
    connectors = (directory_connect, runtime_connect, web_connect)
    if any(not callable(value) or inspect.iscoroutinefunction(value) for value in connectors):
        return _inactive("MISSING_DEPENDENCIES")
    if dependencies.preparation.connect is not runtime_connect:
        return _inactive("MISMATCHED_RUNTIME_CONNECTOR")

    directory_identity: RuntimeDatabaseIdentity | None = None

    @contextmanager
    def checked_directory_connection():
        nonlocal directory_identity
        with directory_connect() as conn:
            identity = probe_runtime_database_identity(
                conn, protected_relations=_PROTECTED_RELATIONS
            )
            _directory_identity(identity)
            directory_identity = identity
            yield conn

    def build_assignment(*, scope, assignment_revision):
        if type(assignment_revision) is not int or assignment_revision < 1:
            raise TypeError("exact assignment revision required")
        recovery = ExpiredResourceRecovery(
            connect=runtime_connect, driver=dependencies.cleanup_driver
        )
        configure = ConfigurationConsumer(
            connect=runtime_connect,
            authorize=dependencies.configuration_authorize,
            check_drained=dependencies.drain_reader,
        )
        disable = RuntimeDisableConsumer(
            connect=runtime_connect,
            installation_store=dependencies.installation_store,
            check_current_permission=dependencies.disable_permission,
            check_drained=dependencies.drain_reader,
            dependent=dependencies.disable_dependent,
        )
        consumers=(configure,disable)
        if dependencies.configuration_stage_enabled:
            consumers += (ConfigurationStageConsumer(connect=runtime_connect, authorize=dependencies.configuration_authorize),)
        if dependencies.ui_read_catalog is not None:
            consumers+=(RuntimeUiReadConsumer(scope=scope,connect=runtime_connect,catalog=dependencies.ui_read_catalog,
                installation_store=dependencies.installation_store,live_directory=dependencies.preparation.live_directory,
                markings=dependencies.ui_read_markings),)
        return RuntimeTenantAssignment(
            scope=scope,
            recovery=recovery,
            attempt_recovery=ExpiredSignedReadAttemptRecovery(connect=runtime_connect),
            lifecycle=dependencies.preparation.build_scheduler(scope),
            consumers=consumers,
        )

    directory = PostgresRuntimeTenantDirectory(
        connect=checked_directory_connection, build_assignment=build_assignment
    )
    try:
        descriptors = directory.read_descriptors()
    except Exception:
        return _inactive("DIRECTORY_PREFLIGHT_FAILED")
    if not descriptors:
        return _inactive("DIRECTORY_EMPTY")
    if directory_identity is None:
        return _inactive("DIRECTORY_PREFLIGHT_FAILED")

    try:
        with runtime_connect() as conn:
            runtime_identity = probe_runtime_database_identity(
                conn, protected_relations=_PROTECTED_RELATIONS
            )
            if dependencies.configuration_stage_enabled:
                try:
                    if not configuration_stage_ready(conn):return _inactive('CONFIGURATION_STAGE_PREFLIGHT_FAILED')
                except Exception:return _inactive('CONFIGURATION_STAGE_PREFLIGHT_FAILED')
            if dependencies.ui_read_catalog is not None:
                try:
                    if not runtime_ui_read_ready(conn):return _inactive('UI_READ_PREFLIGHT_FAILED')
                except Exception:return _inactive('UI_READ_PREFLIGHT_FAILED')
        with web_connect() as conn:
            web_identity = probe_runtime_database_identity(
                conn, protected_relations=_PROTECTED_RELATIONS
            )
        require_isolated_runtime_identities(
            directory=directory_identity,
            runtime=runtime_identity,
            web=web_identity,
        )
    except Exception:
        return _inactive("IDENTITY_PREFLIGHT_FAILED")
    try:
        directory.materialize(descriptors)
    except Exception:
        return _inactive("ASSIGNMENT_FACTORY_FAILED")
    return RuntimeHostSelection(host=RuntimeHost(assignments=directory), status="ACTIVE")
