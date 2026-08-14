"""Tenant-scoped, rebuildable Workshop catalog over Registry/Installation truth."""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import psycopg
from pydantic import ValidationError

from aos_api.asset_registry.composition_contracts import StoredCompositionLock
from aos_api.asset_registry.contracts import (
    BundleManifest,
    LoadedBundle,
    WorkshopModuleContribution,
    contribution_sort_key,
)
from aos_api.asset_registry.errors import (
    AssetNotFoundError,
    AssetRegistryError,
    RegistryIntegrityCorruptError,
)
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import connect
from aos_api.ecommerce_workshop_contracts import (
    ECOMMERCE_WORKSHOP_SCHEMA_VERSION,
    EcommerceWorkshopModuleListResponse,
    EcommerceWorkshopModuleProjection,
    EcommerceWorkshopModuleReadinessResponse,
    WorkshopDependencyState,
    WorkshopDependencyType,
    WorkshopReadiness,
    WorkshopReadinessBlocker,
)
from aos_api.tenant_scope import ORG_GUC, PROJECT_GUC

ConnectFactory = Callable[[], AbstractContextManager[Any]]
Clock = Callable[[], datetime]
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_SUPPORTED_BUNDLE_STATUSES = frozenset({"published", "deprecated", "revoked"})


@dataclass(frozen=True, slots=True)
class PersistedBundleVersion:
    publisher: str
    bundle_id: str
    version: str
    status: str
    manifest: BundleManifest
    content_hash: str
    artifacts: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class ActiveWorkshopBundle:
    installation_id: str
    active_revision: int
    overlay_revision: str
    lock: StoredCompositionLock
    bundle: PersistedBundleVersion


class WorkshopCatalogSource(Protocol):
    def read_active_bundles(
        self,
        *,
        org_id: str,
        project_id: str,
        markings: Collection[str],
    ) -> tuple[ActiveWorkshopBundle, ...]: ...


class WorkshopBundleLoader(Protocol):
    def load(self, source_ref: str) -> LoadedBundle: ...


class PostgresWorkshopCatalogSource:
    """Read every effective active lock and exact Registry version atomically."""

    def __init__(self, connect_factory: ConnectFactory = connect) -> None:
        self._connect_factory = connect_factory

    def read_active_bundles(
        self,
        *,
        org_id: str,
        project_id: str,
        markings: Collection[str],
    ) -> tuple[ActiveWorkshopBundle, ...]:
        checked_org = _normalized_text(org_id, "org_id")
        checked_project = _normalized_text(project_id, "project_id")
        checked_markings = sorted(
            {_normalized_text(value, "marking") for value in markings}
        )
        try:
            with self._connect_factory() as conn:
                conn.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                apply_asset_transaction_scope(
                    conn, org_id=checked_org, project_id=checked_project
                )
                tables = conn.execute(
                    """
                    SELECT to_regclass('bundle_installation') AS installation,
                           to_regclass('bundle_composition_lock') AS lock,
                           to_regclass('asset_bundle_version') AS registry
                    """
                ).fetchone()
                if (
                    tables is None
                    or tables["installation"] is None
                    or tables["lock"] is None
                    or tables["registry"] is None
                ):
                    raise RegistryIntegrityCorruptError()
                scope = conn.execute(
                    f"""
                    SELECT current_setting('{ORG_GUC}', true) AS org_id,
                           current_setting('{PROJECT_GUC}', true) AS project_id
                    """
                ).fetchone()
                if scope is None or (
                    scope["org_id"],
                    scope["project_id"],
                ) != (checked_org, checked_project):
                    raise RegistryIntegrityCorruptError()
                rows = conn.execute(
                    """
                    SELECT i.installation_id, i.active_revision,
                           r.overlay_revision, r.lock_hash AS revision_lock_hash,
                           c.composition_id,
                           l.revision AS lock_revision, l.lock_payload,
                           l.lock_hash, l.permission_diff_json,
                           l.permission_diff_hash, l.migration_plan_json,
                           l.migration_plan_hash, l.contribution_diff_json,
                           l.contribution_diff_hash, l.created_at
                      FROM bundle_installation i
                      JOIN bundle_installation_revision r
                        ON r.org_id=i.org_id AND r.project_id=i.project_id
                       AND r.installation_pk=i.installation_pk
                       AND r.revision=i.active_revision
                      JOIN bundle_composition c
                        ON c.org_id=r.org_id AND c.project_id=r.project_id
                       AND c.composition_pk=r.composition_pk
                      JOIN bundle_composition_lock l
                        ON l.org_id=r.org_id AND l.project_id=r.project_id
                       AND l.composition_pk=r.composition_pk
                       AND l.revision=r.lock_revision
                     WHERE i.org_id=%s AND i.project_id=%s
                       AND i.active_revision IS NOT NULL
                       AND r.state='active'
                     ORDER BY i.installation_id ASC
                    """,
                    (checked_org, checked_project),
                ).fetchall()
                effective_rows = _filter_effective_rows_by_markings(
                    rows, set(checked_markings)
                )
                result: list[ActiveWorkshopBundle] = []
                versions: dict[tuple[str, str, str], PersistedBundleVersion] = {}
                for row, lock in effective_rows:
                    for resolved in lock.payload.resolved:
                        coordinate = (resolved.publisher, resolved.id, resolved.version)
                        version = versions.get(coordinate)
                        if version is None:
                            version = _load_registry_version(conn, coordinate=coordinate)
                            versions[coordinate] = version
                        if version.content_hash != resolved.content_hash:
                            raise RegistryIntegrityCorruptError()
                        result.append(
                            ActiveWorkshopBundle(
                                installation_id=str(row["installation_id"]),
                                active_revision=int(row["active_revision"]),
                                overlay_revision=str(row["overlay_revision"]),
                                lock=lock,
                                bundle=version,
                            )
                        )
                return tuple(result)
        except AssetRegistryError:
            raise
        except (psycopg.Error, KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RegistryIntegrityCorruptError() from exc


def _effective_active_rows(
    rows: Collection[Any],
) -> tuple[tuple[Any, StoredCompositionLock], ...]:
    """Validate the immutable replacement graph and return only active leaves."""

    indexed: dict[str, tuple[Any, StoredCompositionLock]] = {}
    for row in rows:
        installation_id = str(row["installation_id"])
        if installation_id in indexed:
            raise RegistryIntegrityCorruptError()
        lock = _lock_from_row(row)
        if str(row["revision_lock_hash"]) != lock.lock_hash:
            raise RegistryIntegrityCorruptError()
        indexed[installation_id] = (row, lock)

    parent_by_child: dict[str, str] = {}
    children_by_parent: dict[str, list[str]] = {}
    for child_id, (_, child_lock) in indexed.items():
        current_ref = child_lock.payload.current_installation_ref
        if current_ref is None:
            continue
        parent_id = current_ref.installation_id
        if parent_id == child_id:
            raise RegistryIntegrityCorruptError()
        parent = indexed.get(parent_id)
        if parent is None:
            raise RegistryIntegrityCorruptError()
        parent_row, parent_lock = parent
        if (
            current_ref.revision != int(parent_row["active_revision"])
            or current_ref.lock_hash != parent_lock.lock_hash
            or current_ref.overlay_revision != str(parent_row["overlay_revision"])
        ):
            raise RegistryIntegrityCorruptError()
        parent_by_child[child_id] = parent_id
        children_by_parent.setdefault(parent_id, []).append(child_id)

    if any(len(children) != 1 for children in children_by_parent.values()):
        raise RegistryIntegrityCorruptError()

    for start in parent_by_child:
        visited: set[str] = set()
        cursor: str | None = start
        while cursor is not None:
            if cursor in visited:
                raise RegistryIntegrityCorruptError()
            visited.add(cursor)
            cursor = parent_by_child.get(cursor)

    shadowed = set(children_by_parent)
    return tuple(
        indexed[installation_id]
        for installation_id in sorted(indexed)
        if installation_id not in shadowed
    )


def _filter_effective_rows_by_markings(
    rows: Collection[Any],
    principal_markings: Collection[str],
) -> tuple[tuple[Any, StoredCompositionLock], ...]:
    """Resolve replacement authority before applying leaf visibility."""

    checked_markings = set(principal_markings)
    return tuple(
        (row, lock)
        for row, lock in _effective_active_rows(rows)
        if set(lock.payload.permission_diff.target.markings).issubset(
            checked_markings
        )
    )


class EcommerceWorkshopCatalog:
    """Project immutable Module artifacts from active exact installation locks."""

    def __init__(
        self,
        *,
        source: WorkshopCatalogSource,
        loader: WorkshopBundleLoader,
        clock: Clock | None = None,
    ) -> None:
        self._source = source
        self._loader = loader
        self._clock = clock or (lambda: datetime.now(UTC))

    def list_modules(
        self,
        *,
        org_id: str,
        project_id: str,
        roles: Collection[str],
        markings: Collection[str],
    ) -> EcommerceWorkshopModuleListResponse:
        evaluated_at = self._aware_now()
        modules, data_cutoff = self._project_modules(
            org_id=org_id,
            project_id=project_id,
            roles=roles,
            markings=markings,
        )
        return EcommerceWorkshopModuleListResponse.model_validate(
            {
                "schemaVersion": ECOMMERCE_WORKSHOP_SCHEMA_VERSION,
                "tenant": {"orgId": org_id, "projectId": project_id},
                "evaluatedAt": evaluated_at,
                "dataCutoff": data_cutoff,
                "items": modules,
                "count": len(modules),
            }
        )

    def get_readiness(
        self,
        *,
        module_id: str,
        org_id: str,
        project_id: str,
        roles: Collection[str],
        markings: Collection[str],
    ) -> EcommerceWorkshopModuleReadinessResponse:
        checked_module_id = _normalized_text(module_id, "module_id")
        evaluated_at = self._aware_now()
        modules, data_cutoff = self._project_modules(
            org_id=org_id,
            project_id=project_id,
            roles=roles,
            markings=markings,
        )
        item = next((item for item in modules if item.module_id == checked_module_id), None)
        if item is None:
            raise AssetNotFoundError("Workshop module is not installed")
        return EcommerceWorkshopModuleReadinessResponse.model_validate(
            {
                "schemaVersion": ECOMMERCE_WORKSHOP_SCHEMA_VERSION,
                "tenant": {"orgId": org_id, "projectId": project_id},
                "evaluatedAt": evaluated_at,
                "dataCutoff": data_cutoff,
                "item": item,
            }
        )

    def _project_modules(
        self,
        *,
        org_id: str,
        project_id: str,
        roles: Collection[str],
        markings: Collection[str],
    ) -> tuple[list[EcommerceWorkshopModuleProjection], datetime | None]:
        active = self._source.read_active_bundles(
            org_id=org_id,
            project_id=project_id,
            markings=markings,
        )
        projections: list[EcommerceWorkshopModuleProjection] = []
        loaded_cache: dict[tuple[str, str, str], LoadedBundle] = {}
        principal_roles = set(roles)
        principal_markings = set(markings)
        for installed in active:
            bundle = installed.bundle
            resolved = next(
                (
                    item
                    for item in installed.lock.payload.resolved
                    if (item.publisher, item.id, item.version)
                    == (bundle.publisher, bundle.bundle_id, bundle.version)
                ),
                None,
            )
            if resolved is None or (
                resolved.content_hash != bundle.content_hash
                or resolved.contributions
                != sorted(
                    bundle.manifest.spec.contributions,
                    key=contribution_sort_key,
                )
                or resolved.permissions.model_dump(
                    mode="json", by_alias=True
                )
                != _sorted_permission_payload(bundle.manifest.spec.permissions)
                or resolved.capabilities.provides
                != sorted(bundle.manifest.spec.capabilities.provides)
                or resolved.capabilities.requires
                != sorted(bundle.manifest.spec.capabilities.requires)
            ):
                raise RegistryIntegrityCorruptError()
            if not any(
                str(item.get("relativePath", "")).startswith("content/workshops/")
                for item in bundle.artifacts
            ):
                continue
            coordinate = (bundle.publisher, bundle.bundle_id, bundle.version)
            loaded = loaded_cache.get(coordinate)
            if loaded is None:
                source_ref = _derive_source_ref(bundle.artifacts)
                loaded = self._loader.load(source_ref)
                _verify_loaded_bundle(loaded=loaded, persisted=bundle)
                loaded_cache[coordinate] = loaded
            for module in loaded.workshop_modules:
                required_roles = set(module.permissions.roles)
                required_markings = set(module.permissions.markings)
                if not required_roles.issubset(principal_roles):
                    continue
                if not required_markings.issubset(principal_markings):
                    continue
                projections.append(
                    _module_projection(
                        installed=installed,
                        loaded=loaded,
                        module=module,
                        persisted=bundle,
                    )
                )
        _require_unique_catalog(projections)
        data_cutoff = min(
            (item.lock.created_at for item in active),
            default=None,
        )
        return sorted(projections, key=lambda item: item.order), data_cutoff

    def _aware_now(self) -> datetime:
        value = self._clock()
        if not isinstance(value, datetime) or value.utcoffset() is None:
            raise RegistryIntegrityCorruptError()
        return value


def build_ecommerce_workshop_catalog(
    *, repository_root: Path = _REPOSITORY_ROOT
) -> EcommerceWorkshopCatalog:
    bundle_root = repository_root / "bundles"
    return EcommerceWorkshopCatalog(
        source=PostgresWorkshopCatalogSource(),
        loader=ManifestLoader(
            {
                "catalog": bundle_root,
                "d3-catalog": bundle_root,
            }
        ),
    )


def _lock_from_row(row: Any) -> StoredCompositionLock:
    return StoredCompositionLock.model_validate(
        {
            "compositionId": str(row["composition_id"]),
            "revision": int(row["lock_revision"]),
            "payload": row["lock_payload"],
            "lockHash": str(row["lock_hash"]),
            "permissionDiffHash": str(row["permission_diff_hash"]),
            "migrationPlanHash": str(row["migration_plan_hash"]),
            "contributionDiffHash": str(row["contribution_diff_hash"]),
            "createdAt": row["created_at"],
        }
    )


def _load_registry_version(
    conn: Any, *, coordinate: tuple[str, str, str]
) -> PersistedBundleVersion:
    publisher, bundle_id, version = coordinate
    rows = conn.execute(
        """
        SELECT b.publisher, b.bundle_id, v.version, v.status,
               v.manifest_json, v.content_hash
          FROM asset_bundle b
          JOIN asset_bundle_version v ON v.bundle_pk=b.bundle_pk
         WHERE b.publisher=%s AND b.bundle_id=%s AND v.version=%s
        """,
        coordinate,
    ).fetchall()
    if len(rows) != 1:
        raise RegistryIntegrityCorruptError()
    row = rows[0]
    if str(row["status"]) not in _SUPPORTED_BUNDLE_STATUSES:
        raise RegistryIntegrityCorruptError()
    manifest = BundleManifest.model_validate(row["manifest_json"])
    if (
        manifest.metadata.publisher,
        manifest.metadata.id,
        manifest.metadata.version,
    ) != coordinate:
        raise RegistryIntegrityCorruptError()
    artifacts = conn.execute(
        """
        SELECT a.relative_path, a.artifact_ref, a.digest, a.size, a.media_type
          FROM asset_bundle_artifact a
          JOIN asset_bundle_version v ON v.version_pk=a.version_pk
          JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk
         WHERE b.publisher=%s AND b.bundle_id=%s AND v.version=%s
         ORDER BY a.relative_path ASC
        """,
        coordinate,
    ).fetchall()
    return PersistedBundleVersion(
        publisher=publisher,
        bundle_id=bundle_id,
        version=version,
        status=str(row["status"]),
        manifest=manifest,
        content_hash=str(row["content_hash"]),
        artifacts=tuple(
            {
                "relativePath": str(item["relative_path"]),
                "artifactRef": str(item["artifact_ref"]),
                "digest": str(item["digest"]),
                "size": int(item["size"]),
                "mediaType": str(item["media_type"]),
            }
            for item in artifacts
        ),
    )


def _derive_source_ref(artifacts: Iterable[dict[str, object]]) -> str:
    source_refs: set[str] = set()
    has_workshop_artifact = False
    for artifact in artifacts:
        relative_path = artifact.get("relativePath")
        artifact_ref = artifact.get("artifactRef")
        if not isinstance(relative_path, str) or not isinstance(artifact_ref, str):
            raise RegistryIntegrityCorruptError()
        suffix = f"/{relative_path}"
        if not artifact_ref.endswith(suffix):
            raise RegistryIntegrityCorruptError()
        source_refs.add(artifact_ref[: -len(suffix)])
        has_workshop_artifact |= relative_path.startswith("content/workshops/")
    if len(source_refs) != 1 or not has_workshop_artifact:
        raise RegistryIntegrityCorruptError()
    return next(iter(source_refs))


def _verify_loaded_bundle(
    *, loaded: LoadedBundle, persisted: PersistedBundleVersion
) -> None:
    metadata = loaded.manifest.metadata
    if (
        metadata.publisher,
        metadata.id,
        metadata.version,
        loaded.content_hash,
    ) != (
        persisted.publisher,
        persisted.bundle_id,
        persisted.version,
        persisted.content_hash,
    ):
        raise RegistryIntegrityCorruptError()
    if loaded.manifest != persisted.manifest:
        raise RegistryIntegrityCorruptError()
    loaded_artifacts = tuple(
        item.model_dump(mode="json", by_alias=True, exclude_none=False)
        for item in loaded.artifacts
    )
    if loaded_artifacts != persisted.artifacts:
        raise RegistryIntegrityCorruptError()


def _module_projection(
    *,
    installed: ActiveWorkshopBundle,
    loaded: LoadedBundle,
    module: WorkshopModuleContribution,
    persisted: PersistedBundleVersion,
) -> EcommerceWorkshopModuleProjection:
    artifact_path = next(
        (
            item.relative_path
            for item in loaded.artifacts
            if item.relative_path.startswith("content/workshops/")
            and item.relative_path.endswith(".json")
            and _artifact_contains_module(loaded.source_ref, item.relative_path, module)
        ),
        None,
    )
    if artifact_path is None:
        raise RegistryIntegrityCorruptError()
    artifact = next(item for item in loaded.artifacts if item.relative_path == artifact_path)
    blockers = _initial_blockers(module=module, bundle_status=persisted.status)
    readiness = _readiness_from(blockers)
    return EcommerceWorkshopModuleProjection.model_validate(
        {
            "moduleId": module.module_id,
            "displayName": module.display_name,
            "menuLabel": module.menu_label,
            "route": module.route,
            "slot": module.slot,
            "order": module.order,
            "installationRef": {
                "installationId": installed.installation_id,
                "revision": installed.active_revision,
                "compositionId": installed.lock.composition_id,
                "lockRevision": installed.lock.revision,
                "lockHash": installed.lock.lock_hash,
                "overlayRevision": installed.overlay_revision,
            },
            "moduleRef": {
                "publisher": persisted.publisher,
                "bundleId": persisted.bundle_id,
                "version": persisted.version,
                "bundleContentHash": persisted.content_hash,
                "moduleArtifactRef": artifact.artifact_ref,
                "moduleArtifactHash": artifact.digest,
            },
            "readiness": readiness,
            "blockers": blockers,
            "permissions": module.permissions,
            "requiredObjects": module.required_objects,
            "requiredCapabilities": module.required_capabilities,
            "requiredAipFeatures": module.required_aip_features,
            "viewRefs": module.view_refs,
            "evalPackRefs": module.eval_pack_refs,
            "productionContractRefs": module.production_contract_refs,
            "responsibilityTemplateRefs": module.responsibility_template_refs,
            "impactCalculatorRefs": module.impact_calculator_refs,
            "legacyAssetRefs": module.legacy_asset_refs,
            "legacyRoutes": module.legacy_redirects,
            "minimumRuntimeVersion": module.minimum_runtime_version,
            "lastReceiptRef": None,
        }
    )


def _artifact_contains_module(
    source_ref: str, relative_path: str, module: WorkshopModuleContribution
) -> bool:
    expected = f"{source_ref}/{relative_path}"
    # ManifestLoader enforces canonical filename == moduleId for schematized assets.
    return expected.startswith(source_ref + "/") and Path(relative_path).stem == module.module_id


def _initial_blockers(
    *, module: WorkshopModuleContribution, bundle_status: str
) -> list[WorkshopReadinessBlocker]:
    if bundle_status in {"deprecated", "revoked"}:
        reason = "BUNDLE_REVOKED" if bundle_status == "revoked" else "BUNDLE_DEPRECATED"
        return [
            WorkshopReadinessBlocker.model_validate(
                {
                    "dependencyType": "registry",
                    "dependencyId": module.bundle_ref,
                    "state": "disabled",
                    "reasonCode": reason,
                    "recoverable": bundle_status == "deprecated",
                    "requiredAction": "安装经验证的替代 Bundle revision 后重新评估",
                    "ref": None,
                }
            )
        ]

    blockers: list[WorkshopReadinessBlocker] = []
    groups = (
        (
            WorkshopDependencyType.OBJECT,
            module.required_objects,
            "OBJECT_READINESS_UNVERIFIED",
            "接入 canonical 对象 readiness reader 后重新评估",
        ),
        (
            WorkshopDependencyType.CAPABILITY,
            module.required_capabilities,
            "CAPABILITY_BINDING_UNVERIFIED",
            "完成组织 CapabilityBinding 并由 canonical reader 回读",
        ),
        (
            WorkshopDependencyType.AIP_FEATURE,
            module.required_aip_features,
            "AIP_FEATURE_UNVERIFIED",
            "等待对应 AIP authority 集成并由 canonical reader 回读",
        ),
        (
            WorkshopDependencyType.DATA_SCOPE,
            module.permissions.data_scopes,
            "DATA_SCOPE_UNVERIFIED",
            "验证当前主体与数据源的 scope/freshness 后重新评估",
        ),
    )
    for dependency_type, dependency_ids, reason_code, required_action in groups:
        blockers.extend(
            WorkshopReadinessBlocker.model_validate(
                {
                    "dependencyType": dependency_type.value,
                    "dependencyId": dependency_id,
                    "state": WorkshopDependencyState.UNKNOWN.value,
                    "reasonCode": reason_code,
                    "recoverable": True,
                    "requiredAction": required_action,
                    "ref": None,
                }
            )
            for dependency_id in dependency_ids
        )
    if not blockers:
        return [
            WorkshopReadinessBlocker.model_validate(
                {
                    "dependencyType": "installation",
                    "dependencyId": module.module_id,
                    "state": "unknown",
                    "reasonCode": "DEPENDENCY_READERS_UNVERIFIED",
                    "recoverable": True,
                    "requiredAction": "接入 canonical dependency readers 后重新评估",
                    "ref": None,
                }
            )
        ]
    return blockers


def _readiness_from(blockers: Collection[WorkshopReadinessBlocker]) -> WorkshopReadiness:
    states = {item.state for item in blockers}
    if WorkshopDependencyState.DISABLED in states:
        return WorkshopReadiness.DISABLED
    if WorkshopDependencyState.BLOCKED in states:
        return WorkshopReadiness.BLOCKED
    if WorkshopDependencyState.UNKNOWN in states:
        return WorkshopReadiness.UNKNOWN
    if WorkshopDependencyState.DEGRADED in states:
        return WorkshopReadiness.DEGRADED
    return WorkshopReadiness.AVAILABLE


def _require_unique_catalog(
    projections: Collection[EcommerceWorkshopModuleProjection],
) -> None:
    for label, values in (
        ("module id", [item.module_id for item in projections]),
        ("route", [item.route for item in projections]),
        ("slot/order", [(item.slot, item.order) for item in projections]),
    ):
        if len(values) != len(set(values)):
            raise RegistryIntegrityCorruptError()


def _normalized_text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or "\x00" in value:
        raise ValueError(f"{label} must be normalized")
    return value


def _sorted_permission_payload(permissions: Any) -> dict[str, list[str]]:
    return {
        "roles": sorted(permissions.roles),
        "markings": sorted(permissions.markings),
        "dataScopes": sorted(permissions.data_scopes),
        "actionTypes": sorted(permissions.action_types),
    }
