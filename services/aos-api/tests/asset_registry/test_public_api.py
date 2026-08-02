from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import aos_api
import aos_api.asset_registry as public_api
from aos_api import db
from aos_api.asset_registry import (
    BundleLoader,
    CompositionLockPayload,
    CompositionRequest,
    ManifestLoader,
    PostgresRegistryStore,
    RegistryService,
    RegistrySnapshot,
    RegistryStore,
    ResolvedBundle,
    SemVerError,
    StoredCompositionLock,
    TrustRoot,
    TrustRootProvider,
    canonical_json,
    canonical_sha256,
    parse_range,
    parse_version,
    satisfies,
    select_highest,
    verify_ed25519,
)
from aos_api.asset_registry.registry_service import (
    BundleLoader as ServiceBundleLoader,
)
from aos_api.asset_registry.registry_service import (
    RegistryService as ServiceRegistryService,
)
from aos_api.asset_registry.registry_store import (
    PostgresRegistryStore as StorePostgresRegistryStore,
)
from aos_api.asset_registry.registry_store import RegistryStore as StoreRegistryStore

API_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = API_ROOT / "aos_api/asset_registry"

EXPECTED_PUBLIC_API = [
    "BUNDLE_API_VERSION",
    "BUNDLE_ID_PATTERN",
    "CAPABILITY_PATTERN",
    "ERROR_HTTP_STATUS",
    "SHA256_PATTERN",
    "ApprovalStaleError",
    "AssetNotFoundError",
    "AssetRegistryError",
    "AssetRegistryErrorCode",
    "BundleArtifact",
    "BundleCapabilities",
    "BundleConflict",
    "BundleDependency",
    "BundleEvidence",
    "BundleEvidenceStatus",
    "BundleEvidenceType",
    "BundleExports",
    "BundleKind",
    "BundleLoader",
    "BundleManifest",
    "BundleMetadata",
    "BundleMigrations",
    "BundlePermissions",
    "BundleSignature",
    "BundleSpec",
    "BundleVersionImmutableError",
    "BundleVersionStatus",
    "CompositionLockPayload",
    "CompositionRequest",
    "DependencyConflictError",
    "DependencyCycleError",
    "DowngradePolicy",
    "DutySeparationRequiredError",
    "IdempotencyConflictError",
    "LoadedBundle",
    "ManifestInvalidError",
    "ManifestLoader",
    "PostgresRegistryStore",
    "PreflightFailedError",
    "RegistryService",
    "RegistrySnapshot",
    "RegistryStore",
    "ResolvedBundle",
    "RevisionConflictError",
    "RollbackBlockedError",
    "SemVerError",
    "SignatureInvalidError",
    "StoredCompositionLock",
    "TrustRoot",
    "TrustRootProvider",
    "TrustRootUnavailableError",
    "VerificationFailedError",
    "VersionInvalidError",
    "canonical_json",
    "canonical_sha256",
    "parse_range",
    "parse_version",
    "satisfies",
    "select_highest",
    "verify_ed25519",
]


def test_public_api_is_explicit_complete_and_has_no_duplicates() -> None:
    assert public_api.__all__ == EXPECTED_PUBLIC_API
    assert len(public_api.__all__) == len(set(public_api.__all__))
    assert all(getattr(public_api, name) is not None for name in public_api.__all__)


def test_new_public_symbols_resolve_to_their_owned_implementations() -> None:
    assert BundleLoader is ServiceBundleLoader
    for composition_contract in (
        CompositionRequest,
        RegistrySnapshot,
        ResolvedBundle,
        CompositionLockPayload,
        StoredCompositionLock,
    ):
        assert composition_contract.__module__.endswith(".composition_contracts")
    assert RegistryService is ServiceRegistryService
    assert RegistryStore is StoreRegistryStore
    assert PostgresRegistryStore is StorePostgresRegistryStore
    assert ManifestLoader.__module__.endswith(".manifest_loader")
    assert SemVerError.__module__.endswith(".semver")
    assert TrustRoot.__module__.endswith(".signature")
    assert TrustRootProvider.__module__.endswith(".signature")
    assert canonical_json.__module__.endswith(".canonical_json")
    assert canonical_sha256.__module__.endswith(".canonical_json")
    assert parse_range.__module__.endswith(".semver")
    assert parse_version.__module__.endswith(".semver")
    assert satisfies.__module__.endswith(".semver")
    assert select_highest.__module__.endswith(".semver")
    assert verify_ed25519.__module__.endswith(".signature")


def test_internal_helpers_and_non_contract_constants_are_not_exported() -> None:
    forbidden = {
        "CanonicalJsonError",
        "CREATE_ROLES",
        "ED25519_ALGORITHM",
        "JsonRecord",
        "MAX_SEMVER_INPUT_LENGTH",
        "LOCK_SCHEMA_VERSION",
        "REQUIRED_RELEASE_EVIDENCE",
        "InstallationRecord",
        "RegistrySnapshotCandidate",
        "RequestedBundle",
        "contracts",
        "errors",
        "manifest_loader",
        "registry_service",
        "registry_store",
        "semver",
        "signature",
        "_VersionRecord",
        "_validate_json_value",
    }

    assert forbidden.isdisjoint(public_api.__all__)
    assert all(not name.startswith("_") for name in public_api.__all__)


def test_general_asset_registry_package_has_no_domain_specific_terms() -> None:
    forbidden = ("ecom" + "merce", "niu" + "shop")

    for path in PACKAGE_ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8").lower()
        assert all(term not in content for term in forbidden), path


def test_fresh_public_import_does_not_access_database_or_bundle_files(
    monkeypatch,
) -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []

    def deny(operation: str):
        def blocked(*args: Any, **_kwargs: Any) -> Any:
            calls.append((operation, args))
            raise AssertionError(f"import attempted {operation}")

        return blocked

    monkeypatch.setattr(db, "connect", deny("database connection"))
    for method in (
        "glob",
        "iterdir",
        "open",
        "read_bytes",
        "read_text",
        "resolve",
        "rglob",
    ):
        monkeypatch.setattr(Path, method, deny(f"Path.{method}"))

    prefix = "aos_api.asset_registry"
    preserved = {
        name: module
        for name, module in sys.modules.items()
        if name == prefix or name.startswith(f"{prefix}.")
    }
    for name in preserved:
        sys.modules.pop(name, None)
    try:
        imported = importlib.import_module(prefix)
        assert imported.__all__ == EXPECTED_PUBLIC_API
        assert calls == []
    finally:
        for name in list(sys.modules):
            if name == prefix or name.startswith(f"{prefix}."):
                sys.modules.pop(name, None)
        sys.modules.update(preserved)
        aos_api.asset_registry = preserved[prefix]
