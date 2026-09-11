"""Exact, side-effect-free composition of one tenant's live preparation scheduler."""
from __future__ import annotations

from dataclasses import dataclass
import inspect
from typing import Callable, Literal

from aos_api.asset_registry.control_policy import (
    APPLY_INSTALLATION_OPERATION,
    ENABLE_RUNTIME_OPERATION,
    VERIFY_INSTALLATION_OPERATION,
)
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.tenant_scope import TenantScope

from .configuration_authorization import CurrentFourSourceConfigurationAuthorization
from .current_permission import CurrentControlPermission
from .live_installation_scheduler import LiveInstallationScheduler
from .live_job_directory import LivePreparedJobDirectory
from .oci_driver import OciDriver
from .pending_preparation_directory import (
    LiveInstallationOwnerFactory,
    PostgresPendingPreparationDirectory,
)
from .preparation_worker import PreparationWorker
from .release_revalidation import RuntimeReleaseRevalidator
from .runtime_release_artifacts import CurrentRuntimeReleaseArtifacts
from .schema_conditions import CurrentSchemaConditions

RuntimePlatform = Literal["linux/arm64", "linux/amd64"]


def _reject_unbound_artifact(_path: str, _limit: int) -> bytes:
    """Prevent accidental use of the legacy reader without selected-release identity."""
    raise RuntimeError("selected runtime release is required for artifact access")


@dataclass(frozen=True, slots=True)
class ProductionPreparationDependencies:
    """Server-owned dependencies for tenant-scoped preparation workers."""

    connect: Callable
    installation_store: PostgresInstallationStore
    revalidator: RuntimeReleaseRevalidator
    policy: ReleasePolicy
    loader: ManifestLoader
    apply_permission: CurrentControlPermission
    verification_permission: CurrentControlPermission
    enable_permission: CurrentControlPermission
    configuration_authorize: CurrentFourSourceConfigurationAuthorization
    driver: OciDriver
    platform: RuntimePlatform
    live_directory: LivePreparedJobDirectory

    def __post_init__(self) -> None:
        if not callable(self.connect) or inspect.iscoroutinefunction(self.connect):
            raise TypeError("production preparation requires a synchronous runtime connector")
        exact_types = (
            (self.installation_store, PostgresInstallationStore),
            (self.revalidator, RuntimeReleaseRevalidator),
            (self.policy, ReleasePolicy),
            (self.loader, ManifestLoader),
            (self.configuration_authorize, CurrentFourSourceConfigurationAuthorization),
            (self.driver, OciDriver),
            (self.live_directory, LivePreparedJobDirectory),
        )
        if any(type(value) is not expected for value, expected in exact_types):
            raise TypeError("exact production preparation dependencies required")
        if (
            self.revalidator._release_policy is not self.policy
            or self.loader.trust_roots is not self.policy._trust_roots
            or self.configuration_authorize._permission._store
            is not self.installation_store
        ):
            raise TypeError("production preparation dependency graph is inconsistent")
        permissions = (
            (self.apply_permission, APPLY_INSTALLATION_OPERATION),
            (self.verification_permission, VERIFY_INSTALLATION_OPERATION),
            (self.enable_permission, ENABLE_RUNTIME_OPERATION),
        )
        if any(
            type(permission) is not CurrentControlPermission
            or permission.operation != operation
            for permission, operation in permissions
        ):
            raise TypeError("exact current preparation permissions required")
        if self.platform not in ("linux/arm64", "linux/amd64"):
            raise ValueError("explicit supported runtime platform required")

    def build_scheduler(self, scope: TenantScope) -> LiveInstallationScheduler:
        if type(scope) is not TenantScope:
            raise TypeError("exact tenant scope required")
        artifacts = CurrentRuntimeReleaseArtifacts(
            connect=self.connect,
            scope=scope,
            loader=self.loader,
        )
        conditions = CurrentSchemaConditions(
            load_record=artifacts.load_record,
            read_artifact=artifacts.read_artifact,
            policy=self.policy,
        )
        worker = PreparationWorker(
            connect=self.connect,
            driver=self.driver,
            installation_store=self.installation_store,
            revalidator=self.revalidator,
            check_current_permission=self.apply_permission,
            check_verification_permission=self.verification_permission,
            check_enable_permission=self.enable_permission,
            load_record=artifacts.load_record,
            read_artifact=_reject_unbound_artifact,
            read_member_artifact=artifacts.read_artifact,
            policy=self.policy,
            platform=self.platform,
            check_current_conditions=conditions,
            configuration_authorize=self.configuration_authorize,
        )
        directory = PostgresPendingPreparationDirectory(
            connect=self.connect,
            scope=scope,
        )
        factory = LiveInstallationOwnerFactory(
            connect=self.connect,
            scope=scope,
            worker=worker,
            live_directory=self.live_directory,
        )
        return LiveInstallationScheduler(directory=directory, factory=factory)
