"""W1 catalog tests over immutable Module artifacts and active exact locks."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CompositionRequest,
    StoredCompositionLock,
)
from aos_api.asset_registry.errors import AssetNotFoundError, RegistryIntegrityCorruptError
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.ecommerce_workshop_catalog import (
    ActiveWorkshopBundle,
    EcommerceWorkshopCatalog,
    PersistedBundleVersion,
    PostgresWorkshopCatalogSource,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
SHA_A = "sha256:" + "a" * 64
SHA_B = "sha256:" + "b" * 64
SHA_C = "sha256:" + "c" * 64
INSTALLATION_ID = "11111111-1111-4111-8111-111111111111"
COMPOSITION_ID = "22222222-2222-4222-8222-222222222222"
NOW = datetime(2026, 8, 14, tzinfo=UTC)


class FakeSource:
    def __init__(self, by_tenant):
        self.by_tenant = by_tenant
        self.calls = []

    def read_active_bundles(self, **kwargs):
        self.calls.append(kwargs)
        return self.by_tenant.get((kwargs["org_id"], kwargs["project_id"]), ())


class _QueryResult:
    def __init__(self, *, one=None, many=()):
        self._one = one
        self._many = many

    def fetchone(self):
        return self._one

    def fetchall(self):
        return list(self._many)


class _ReadOnlyConnection:
    def __init__(self, *, org_id="org-org", project_id="dev-project"):
        self.org_id = org_id
        self.project_id = project_id
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.calls.append((normalized, params))
        if "to_regclass('bundle_installation')" in normalized:
            return _QueryResult(
                one={
                    "installation": "bundle_installation",
                    "lock": "bundle_composition_lock",
                    "registry": "asset_bundle_version",
                }
            )
        if "current_setting('app.current_org_id'" in normalized:
            return _QueryResult(
                one={"org_id": self.org_id, "project_id": self.project_id}
            )
        if "FROM bundle_installation i" in normalized:
            return _QueryResult(many=())
        return _QueryResult()


def _loaded_growth():
    return ManifestLoader({"catalog": REPOSITORY_ROOT / "bundles"}).load(
        "bundle://catalog/solutions/ecommerce-growth"
    )


def _persisted(loaded, *, content_hash: str | None = None):
    metadata = loaded.manifest.metadata
    return PersistedBundleVersion(
        publisher=metadata.publisher,
        bundle_id=metadata.id,
        version=metadata.version,
        status="published",
        manifest=loaded.manifest,
        content_hash=content_hash or loaded.content_hash,
        artifacts=tuple(
            item.model_dump(mode="json", by_alias=True, exclude_none=False)
            for item in loaded.artifacts
        ),
    )


def _lock(persisted: PersistedBundleVersion) -> StoredCompositionLock:
    request = CompositionRequest.model_validate(
        {
            "requested": [
                {
                    "publisher": persisted.publisher,
                    "id": persisted.bundle_id,
                    "version": persisted.version,
                }
            ],
            "platformApiVersion": "1.7.0",
            "platformRelease": "aos-platform/1.7.0",
            "environment": "dev",
        }
    )
    permissions = {
        "roles": [],
        "markings": [],
        "dataScopes": [],
        "actionTypes": [],
    }
    bindings = [
        {
            "publisher": persisted.publisher,
            "id": persisted.bundle_id,
            "version": persisted.version,
            "claim": claim.model_dump(mode="json", by_alias=True),
        }
        for claim in persisted.manifest.spec.contributions
    ]
    payload = CompositionLockPayload.model_validate(
        {
            "lockSchemaVersion": "aos.dev/composition-lock/v1alpha1",
            "resolverVersion": "aos-resolver/1.0.0",
            "request": request.lock_request(),
            "registrySnapshotHash": SHA_A,
            "resolved": [
                {
                    "publisher": persisted.publisher,
                    "id": persisted.bundle_id,
                    "version": persisted.version,
                    "kind": "SolutionPack",
                    "contentHash": persisted.content_hash,
                    "signatureFingerprint": SHA_B,
                    "releaseEvidenceRevision": SHA_C,
                    "dependencies": [],
                    "optionalDependencies": [],
                    "conflicts": [],
                    "capabilities": persisted.manifest.spec.capabilities.model_dump(
                        mode="json", by_alias=True
                    ),
                    "permissions": persisted.manifest.spec.permissions.model_dump(
                        mode="json", by_alias=True
                    ),
                    "migration": {
                        "planRef": None,
                        "downgradePolicy": "retain-canonical",
                    },
                    "contributions": persisted.manifest.spec.contributions,
                    "selectionReason": "requested",
                }
            ],
            "edges": [],
            "capabilityProviders": [],
            "permissionDiff": {
                "baseline": permissions,
                "target": permissions,
                "added": permissions,
                "removed": permissions,
                "unchanged": permissions,
            },
            "migrationPlan": {
                "baseline": [],
                "target": [],
                "added": [],
                "removed": [],
                "changed": [],
            },
            "contributionDiff": {
                "baseline": [],
                "target": bindings,
                "added": bindings,
                "removed": [],
                "unchanged": [],
            },
            "currentInstallationRef": None,
        }
    )
    return StoredCompositionLock.model_validate(
        {
            "compositionId": COMPOSITION_ID,
            "revision": 1,
            "payload": payload,
            "lockHash": canonical_sha256(payload.hash_payload_dump()),
            "permissionDiffHash": canonical_sha256(
                payload.permission_diff.model_dump(mode="json", by_alias=True)
            ),
            "migrationPlanHash": canonical_sha256(
                payload.migration_plan.model_dump(mode="json", by_alias=True)
            ),
            "contributionDiffHash": canonical_sha256(
                payload.contribution_diff.model_dump(mode="json", by_alias=True)
            ),
            "createdAt": NOW,
        }
    )


def _active(persisted, *, installation_id=INSTALLATION_ID):
    return ActiveWorkshopBundle(
        installation_id=installation_id,
        active_revision=5,
        overlay_revision="overlay-5",
        lock=_lock(persisted),
        bundle=persisted,
    )


def _catalog(source):
    return EcommerceWorkshopCatalog(
        source=source,
        loader=ManifestLoader({"catalog": REPOSITORY_ROOT / "bundles"}),
        clock=lambda: NOW,
    )


def test_catalog_projects_only_active_tenant_modules_and_exact_refs() -> None:
    loaded = _loaded_growth()
    persisted = _persisted(loaded)
    source = FakeSource({("org-org", "dev-project"): (_active(persisted),)})
    catalog = _catalog(source)

    response = catalog.list_modules(
        org_id="org-org",
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )

    assert response.count == 7
    assert [item.order for item in response.items] == sorted(
        item.order for item in response.items
    )
    assert all(item.readiness.value == "unknown" for item in response.items)
    assert all(item.blockers for item in response.items)
    assert all(item.installation_ref.lock_hash == _lock(persisted).lock_hash for item in response.items)
    assert all(item.module_ref.bundle_content_hash == loaded.content_hash for item in response.items)
    assert all(item.last_receipt_ref is None for item in response.items)
    assert source.calls[0]["markings"] == ["public"]

    canary = catalog.list_modules(
        org_id="dev-org",
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )
    assert canary.count == 0
    assert canary.items == []


def test_catalog_get_readiness_and_not_installed_are_explicit() -> None:
    persisted = _persisted(_loaded_growth())
    catalog = _catalog(FakeSource({("org-org", "dev-project"): (_active(persisted),)}))

    result = catalog.get_readiness(
        module_id="ecommerce.media-studio",
        org_id="org-org",
        project_id="dev-project",
        roles=["operator"],
        markings=["public"],
    )
    assert result.item.module_id == "ecommerce.media-studio"
    assert {item.reason_code for item in result.item.blockers} >= {
        "AIP_FEATURE_UNVERIFIED",
        "CAPABILITY_BINDING_UNVERIFIED",
        "OBJECT_READINESS_UNVERIFIED",
    }

    with pytest.raises(AssetNotFoundError, match="not installed"):
        catalog.get_readiness(
            module_id="ecommerce.operations",
            org_id="org-org",
            project_id="dev-project",
            roles=["operator"],
            markings=["public"],
        )


def test_catalog_fails_closed_on_content_hash_drift_or_duplicate_active_modules() -> None:
    loaded = _loaded_growth()
    drifted = _persisted(loaded, content_hash=SHA_A)
    with pytest.raises(RegistryIntegrityCorruptError):
        _catalog(FakeSource({("org-org", "dev-project"): (_active(drifted),)})).list_modules(
            org_id="org-org",
            project_id="dev-project",
            roles=["operator"],
            markings=["public"],
        )

    persisted = _persisted(loaded)
    duplicate = replace(
        _active(persisted),
        installation_id="33333333-3333-4333-8333-333333333333",
    )
    with pytest.raises(RegistryIntegrityCorruptError):
        _catalog(
            FakeSource(
                {("org-org", "dev-project"): (_active(persisted), duplicate)}
            )
        ).list_modules(
            org_id="org-org",
            project_id="dev-project",
            roles=["operator"],
            markings=["public"],
        )


def test_postgres_source_uses_repeatable_read_and_explicit_tenant_predicates() -> None:
    conn = _ReadOnlyConnection()
    source = PostgresWorkshopCatalogSource(connect_factory=lambda: conn)

    assert source.read_active_bundles(
        org_id="org-org",
        project_id="dev-project",
        markings=["restricted", "public", "public"],
    ) == ()

    assert conn.calls[0][0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    active_query = next(call for call in conn.calls if "FROM bundle_installation i" in call[0])
    assert "WHERE i.org_id=%s AND i.project_id=%s" in active_query[0]
    assert active_query[1][0:2] == ("org-org", "dev-project")
    assert active_query[1][2].obj == ["public", "restricted"]


def test_postgres_source_fails_closed_when_bound_scope_cannot_be_verified() -> None:
    conn = _ReadOnlyConnection(org_id="dev-org")
    source = PostgresWorkshopCatalogSource(connect_factory=lambda: conn)

    with pytest.raises(RegistryIntegrityCorruptError):
        source.read_active_bundles(
            org_id="org-org",
            project_id="dev-project",
            markings=["public"],
        )
