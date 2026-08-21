"""W1 catalog tests over immutable Module artifacts and active exact locks."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.composition_contracts import (
    CompositionLockPayload,
    CompositionRequest,
    StoredCompositionLock,
)
from aos_api.asset_registry.errors import AssetNotFoundError, RegistryIntegrityCorruptError
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.ecommerce_workshop_catalog import (
    ActiveWorkshopBundle,
    EcommerceWorkshopCatalog,
    PersistedBundleVersion,
    PostgresWorkshopCatalogSource,
    _filter_effective_rows_by_markings,
    build_ecommerce_workshop_catalog,
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
        self.rollback_count = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def rollback(self):
        self.rollback_count += 1
        self.calls.append(("ROLLBACK", None))

    def execute(self, statement, params=None):
        normalized = " ".join(statement.split())
        self.calls.append((normalized, params))
        if normalized == "SHOW search_path":
            return _QueryResult(one={"search_path": '"tenant_fixture", public'})
        if "to_regclass('bundle_installation')" in normalized:
            return _QueryResult(
                one={
                    "installation": "bundle_installation",
                    "lock": "bundle_composition_lock",
                    "registry": "asset_bundle_version",
                }
            )
        if "SELECT current_user AS current_user" in normalized:
            return _QueryResult(one={"current_user": "aos_runtime"})
        if "current_setting('aos.org_id'" in normalized:
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


def _lock(
    persisted: PersistedBundleVersion,
    *,
    current_installation_ref: dict[str, object] | None = None,
    target_markings: Collection[str] = (),
) -> StoredCompositionLock:
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
    empty_permissions = {
        "roles": [],
        "markings": [],
        "dataScopes": [],
        "actionTypes": [],
    }
    target_permissions = {
        **empty_permissions,
        "markings": sorted(target_markings),
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
                "baseline": empty_permissions,
                "target": target_permissions,
                "added": target_permissions,
                "removed": empty_permissions,
                "unchanged": empty_permissions,
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
            "currentInstallationRef": current_installation_ref,
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


def _active_row(
    lock: StoredCompositionLock,
    *,
    installation_id: str,
    overlay_revision: str,
) -> dict[str, object]:
    return {
        "installation_id": installation_id,
        "active_revision": 5,
        "overlay_revision": overlay_revision,
        "revision_lock_hash": lock.lock_hash,
        "composition_id": lock.composition_id,
        "lock_revision": lock.revision,
        "lock_payload": lock.payload.model_dump(mode="json", by_alias=True),
        "lock_hash": lock.lock_hash,
        "permission_diff_json": lock.payload.permission_diff.model_dump(
            mode="json", by_alias=True
        ),
        "permission_diff_hash": lock.permission_diff_hash,
        "migration_plan_json": lock.payload.migration_plan.model_dump(
            mode="json", by_alias=True
        ),
        "migration_plan_hash": lock.migration_plan_hash,
        "contribution_diff_json": lock.payload.contribution_diff.model_dump(
            mode="json", by_alias=True
        ),
        "contribution_diff_hash": lock.contribution_diff_hash,
        "created_at": lock.created_at,
    }


def _catalog(source):
    return EcommerceWorkshopCatalog(
        source=source,
        loader=ManifestLoader({"catalog": REPOSITORY_ROOT / "bundles"}),
        clock=lambda: NOW,
    )


def test_catalog_builder_allowlists_current_and_historical_fixed_source_aliases() -> None:
    catalog = build_ecommerce_workshop_catalog(repository_root=REPOSITORY_ROOT)
    for alias in ("catalog", "d3-catalog"):
        loaded = catalog._loader.load(  # noqa: SLF001 - construction contract
            f"bundle://{alias}/solutions/ecommerce-growth"
        )
        assert loaded.manifest.metadata.id == "solution.ecommerce.growth"


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

    assert conn.rollback_count == 1
    assert conn.calls[0][0] == "SHOW search_path"
    assert conn.calls[1][0] == "ROLLBACK"
    assert conn.calls[2][0] == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    assert conn.calls[3] == (
        "SELECT set_config('search_path', %s, true)",
        ('"tenant_fixture", public',),
    )
    scope_query = next(call for call in conn.calls if "current_setting(" in call[0])
    assert "current_setting('aos.org_id'" in scope_query[0]
    assert "current_setting('aos.project_id'" in scope_query[0]
    assert "app.current_" not in scope_query[0]
    active_query = next(call for call in conn.calls if "FROM bundle_installation i" in call[0])
    assert "WHERE i.org_id=%s AND i.project_id=%s" in active_query[0]
    assert "permission_diff_json->'target'->'markings'" not in active_query[0]
    assert active_query[1] == ("org-org", "dev-project")


def test_asset_scope_is_idempotent_when_request_connection_already_uses_runtime_role() -> None:
    conn = _ReadOnlyConnection()
    with patch("aos_api.asset_registry.tenant_transaction.psycopg.Connection", _ReadOnlyConnection):
        apply_asset_transaction_scope(conn, org_id="org-org", project_id="dev-project")

    statements = [call[0] for call in conn.calls]
    assert statements[0] == "SELECT current_user AS current_user"
    assert not any("SET LOCAL ROLE" in statement for statement in statements)
    assert any("set_config('aos.org_id'" in statement for statement in statements)


def test_replacement_graph_is_resolved_before_marking_visibility() -> None:
    persisted = _persisted(_loaded_growth())
    parent_overlay = "overlay-parent"
    parent = _lock(persisted, target_markings=("public",))
    child = _lock(
        persisted,
        current_installation_ref={
            "installationId": INSTALLATION_ID,
            "revision": 5,
            "lockHash": parent.lock_hash,
            "overlayRevision": parent_overlay,
        },
        target_markings=("restricted",),
    )
    rows = (
        _active_row(
            parent,
            installation_id=INSTALLATION_ID,
            overlay_revision=parent_overlay,
        ),
        _active_row(
            child,
            installation_id="33333333-3333-4333-8333-333333333333",
            overlay_revision="overlay-child",
        ),
    )

    assert _filter_effective_rows_by_markings(rows, {"public"}) == ()
    visible = _filter_effective_rows_by_markings(
        rows, {"public", "restricted"}
    )
    assert len(visible) == 1
    assert visible[0][0]["installation_id"] == (
        "33333333-3333-4333-8333-333333333333"
    )


def test_postgres_source_fails_closed_when_bound_scope_cannot_be_verified() -> None:
    conn = _ReadOnlyConnection(org_id="dev-org")
    source = PostgresWorkshopCatalogSource(connect_factory=lambda: conn)

    with pytest.raises(RegistryIntegrityCorruptError):
        source.read_active_bundles(
            org_id="org-org",
            project_id="dev-project",
            markings=["public"],
        )
