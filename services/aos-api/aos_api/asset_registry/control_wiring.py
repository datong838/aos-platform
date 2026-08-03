"""Production wiring shared by Registry and the M2-B control plane."""

from __future__ import annotations

import os
from collections.abc import Callable
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
