"""Shared read-only Registry/Installation Workshop candidates and integrity checks."""
from __future__ import annotations
from collections.abc import Callable, Collection, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from functools import partial
from typing import Any
import psycopg
from pydantic import ValidationError
from aos_api.asset_registry.composition_contracts import StoredCompositionLock
from aos_api.asset_registry.contracts import BundleManifest, LoadedBundle, contribution_sort_key
from aos_api.asset_registry.errors import AssetRegistryError, RegistryIntegrityCorruptError
from aos_api.asset_registry.legacy_runtime_boundary import legacy_content_predicate
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.db import connect
from aos_api.tenant_scope import ORG_GUC, PROJECT_GUC

ConnectFactory = Callable[[], AbstractContextManager[Any]]
_SUPPORTED_BUNDLE_STATUSES = frozenset({'published', 'deprecated', 'revoked'})

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


class PostgresWorkshopCatalogSource:
    """Read every effective active lock and exact Registry version atomically."""

    def __init__(self, connect_factory: ConnectFactory | None = None) -> None:
        self._connect_factory = connect_factory or partial(connect, inherit_scope=False)

    def read_active_bundles(
        self,
        *,
        org_id: str,
        project_id: str,
        markings: Collection[str],
    ) -> tuple[ActiveWorkshopBundle, ...]:
        return self._read_candidate_bundles(org_id=org_id, project_id=project_id,
                                           markings=markings, runtime_only=False)

    def read_runtime_candidate_bundles(
        self, *, org_id: str, project_id: str, markings: Collection[str],
    ) -> tuple[ActiveWorkshopBundle, ...]:
        """Candidates only; callers must still validate current runtime and signed UI."""
        return self._read_candidate_bundles(org_id=org_id, project_id=project_id,
                                           markings=markings, runtime_only=True)

    def _read_candidate_bundles(
        self, *, org_id: str, project_id: str, markings: Collection[str], runtime_only: bool,
    ) -> tuple[ActiveWorkshopBundle, ...]:
        checked_org = _normalized_text(org_id, "org_id")
        checked_project = _normalized_text(project_id, "project_id")
        checked_markings = sorted(
            {_normalized_text(value, "marking") for value in markings}
        )
        try:
            with self._connect_factory() as conn:
                # A connection factory may establish an isolated schema in the
                # transaction that connect() already opened. Preserve only its
                # effective search_path: tenant GUCs must be rebound below.
                search_path_row = conn.execute("SHOW search_path").fetchone()
                if search_path_row is None or not str(
                    search_path_row["search_path"]
                ).strip():
                    raise RegistryIntegrityCorruptError()
                search_path = str(search_path_row["search_path"])
                conn.rollback()
                conn.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
                )
                conn.execute(
                    "SELECT set_config('search_path', %s, true)",
                    (search_path,),
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
                    f"""
                    SELECT {legacy_content_predicate('l')} AS legacy_eligible,
                           i.installation_id, i.active_revision,
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
                    # Preserve replacement graph selection before exclusion.
                    if row['legacy_eligible'] is not (False if runtime_only else True):
                        continue
                    installation_bundles: list[ActiveWorkshopBundle] = []
                    for resolved in lock.payload.resolved:
                        coordinate = (resolved.publisher, resolved.id, resolved.version)
                        version = versions.get(coordinate)
                        if version is None:
                            version = _load_registry_version(conn, coordinate=coordinate)
                            versions[coordinate] = version
                        if version.content_hash != resolved.content_hash:
                            raise RegistryIntegrityCorruptError()
                        installation_bundles.append(
                            ActiveWorkshopBundle(
                                installation_id=str(row["installation_id"]),
                                active_revision=int(row["active_revision"]),
                                overlay_revision=str(row["overlay_revision"]),
                                lock=lock,
                                bundle=version,
                            )
                        )
                    if not runtime_only or any(item.bundle.manifest.spec.runtime is not None for item in installation_bundles):
                        result.extend(installation_bundles)
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


def _verify_installed_bundle(installed: ActiveWorkshopBundle) -> None:
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
