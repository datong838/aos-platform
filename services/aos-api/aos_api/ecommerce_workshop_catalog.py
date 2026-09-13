"""Tenant-scoped, rebuildable Workshop catalog over Registry/Installation truth."""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import psycopg

from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.asset_registry.contracts import (
    LoadedBundle,
    WorkshopModuleContribution,
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
    WorkshopDependencyRef,
    WorkshopDependencyType,
    WorkshopReadiness,
    WorkshopReadinessBlocker,
)
from aos_api.tenant_scope import TenantScope

from aos_api.asset_registry.workshop_catalog_source import (
    ActiveWorkshopBundle,
    PersistedBundleVersion,
    PostgresWorkshopCatalogSource,
    _derive_source_ref,
    _effective_active_rows,
    _filter_effective_rows_by_markings,
    _load_registry_version,
    _lock_from_row,
    _normalized_text,
    _sorted_permission_payload,
    _verify_installed_bundle,
    _verify_loaded_bundle,
)

ConnectFactory = Callable[[], AbstractContextManager[Any]]
Clock = Callable[[], datetime]
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


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


class WorkshopObjectAuthoritySource(Protocol):
    def read_object_refs(
        self, *, org_id: str, project_id: str
    ) -> dict[str, WorkshopDependencyRef]: ...


class WorkshopCapabilityAuthoritySource(Protocol):
    def read_capability_refs(
        self, *, org_id: str, project_id: str, evaluated_at: datetime
    ) -> dict[str, WorkshopDependencyRef]: ...


class WorkshopAipFeatureAuthoritySource(Protocol):
    def read_feature_refs(
        self, *, org_id: str, project_id: str, evaluated_at: datetime
    ) -> dict[str, WorkshopDependencyRef]: ...


class PostgresWorkshopObjectAuthoritySource:
    """Read published ObjectTypes through the active tenant composition boundary."""

    def read_object_refs(
        self, *, org_id: str, project_id: str
    ) -> dict[str, WorkshopDependencyRef]:
        from aos_api.ontology_compose import filter_object_type_rows

        scope = TenantScope(
            _normalized_text(org_id, "org_id"),
            _normalized_text(project_id, "project_id"),
        )
        try:
            with connect(scope) as conn:
                rows = conn.execute(
                    "SELECT id, name, description, published, properties "
                    "FROM meta_object_type ORDER BY id"
                ).fetchall()
                visible, composition = filter_object_type_rows(conn, scope, list(rows))
            if composition is None:
                return {}
            revision = str(composition["composed_schema_etag"])
            return {
                str(row["id"]): WorkshopDependencyRef.model_validate(
                    {
                        "resourceType": "ObjectTypeComposition",
                        "resourceId": str(row["id"]),
                        "revision": revision,
                        "contentHash": canonical_sha256(
                            {
                                "composition": composition,
                                "objectType": dict(row),
                            }
                        ),
                        "authority": (
                            "postgres:integration_instance+bundle_composition_lock+"
                            "ontology_overlay+meta_object_type"
                        ),
                    }
                )
                for row in visible
                if bool(row.get("published"))
            }
        except (psycopg.Error, KeyError, RuntimeError, TypeError, ValueError):
            return {}


class PostgresWorkshopCapabilityAuthoritySource:
    """Resolve fresh active AIP CapabilityBindings without exposing secret refs."""

    def read_capability_refs(
        self, *, org_id: str, project_id: str, evaluated_at: datetime
    ) -> dict[str, WorkshopDependencyRef]:
        from aos_api.aip_capability_binding_service import AipCapabilityBindingService

        scope = TenantScope(
            _normalized_text(org_id, "org_id"),
            _normalized_text(project_id, "project_id"),
        )
        try:
            bindings = AipCapabilityBindingService().list_bindings(scope, limit=200)
        except Exception:
            return {}
        return _fresh_capability_refs(bindings, evaluated_at=evaluated_at)


class PostgresWorkshopAipFeatureAuthoritySource:
    """Read tenant-bound AIP feature activations; missing schema remains unknown."""

    def read_feature_refs(
        self, *, org_id: str, project_id: str, evaluated_at: datetime
    ) -> dict[str, WorkshopDependencyRef]:
        scope = TenantScope(
            _normalized_text(org_id, "org_id"),
            _normalized_text(project_id, "project_id"),
        )
        try:
            with connect(scope) as conn:
                table = conn.execute(
                    "SELECT to_regclass('aip_feature_activation') AS feature"
                ).fetchone()
                if table is None or table["feature"] is None:
                    return {}
                rows = conn.execute(
                    "SELECT feature_id, revision, content_hash, activated_at, expires_at "
                    "FROM aip_feature_activation "
                    "WHERE org_id=%s AND project_id=%s AND status='active' "
                    "AND (expires_at IS NULL OR expires_at>%s) "
                    "ORDER BY feature_id, revision DESC",
                    (*scope.key, evaluated_at),
                ).fetchall()
            result: dict[str, WorkshopDependencyRef] = {}
            for row in rows:
                feature_id = str(row["feature_id"])
                if feature_id in result:
                    continue
                result[feature_id] = WorkshopDependencyRef.model_validate(
                    {
                        "resourceType": "AipFeatureActivationRevision",
                        "resourceId": feature_id,
                        "revision": str(row["revision"]),
                        "contentHash": str(row["content_hash"]),
                        "authority": "postgres:aip_feature_activation",
                    }
                )
            return result
        except (psycopg.Error, KeyError, TypeError, ValueError):
            return {}


class EcommerceWorkshopCatalog:
    """Project immutable Module artifacts from active exact installation locks."""

    def __init__(
        self,
        *,
        source: WorkshopCatalogSource,
        loader: WorkshopBundleLoader,
        object_source: WorkshopObjectAuthoritySource | None = None,
        capability_source: WorkshopCapabilityAuthoritySource | None = None,
        aip_feature_source: WorkshopAipFeatureAuthoritySource | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._source = source
        self._loader = loader
        self._object_source = object_source
        self._capability_source = capability_source
        self._aip_feature_source = aip_feature_source
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
            evaluated_at=evaluated_at,
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
            evaluated_at=evaluated_at,
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
        evaluated_at: datetime,
    ) -> tuple[list[EcommerceWorkshopModuleProjection], datetime | None]:
        active = self._source.read_active_bundles(
            org_id=org_id,
            project_id=project_id,
            markings=markings,
        )
        object_refs = (
            self._object_source.read_object_refs(
                org_id=org_id,
                project_id=project_id,
            )
            if self._object_source is not None
            else {}
        )
        capability_refs = (
            self._capability_source.read_capability_refs(
                org_id=org_id,
                project_id=project_id,
                evaluated_at=evaluated_at,
            )
            if self._capability_source is not None
            else {}
        )
        aip_feature_refs = (
            self._aip_feature_source.read_feature_refs(
                org_id=org_id,
                project_id=project_id,
                evaluated_at=evaluated_at,
            )
            if self._aip_feature_source is not None
            else {}
        )
        projections: list[EcommerceWorkshopModuleProjection] = []
        loaded_cache: dict[tuple[str, str, str], LoadedBundle] = {}
        principal_roles = set(roles)
        principal_markings = set(markings)
        for installed in active:
            bundle = installed.bundle
            _verify_installed_bundle(installed)
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
                        object_refs=object_refs,
                        capability_refs=capability_refs,
                        aip_feature_refs=aip_feature_refs,
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
        object_source=PostgresWorkshopObjectAuthoritySource(),
        capability_source=PostgresWorkshopCapabilityAuthoritySource(),
        aip_feature_source=PostgresWorkshopAipFeatureAuthoritySource(),
    )


def _module_projection(
    *,
    installed: ActiveWorkshopBundle,
    loaded: LoadedBundle,
    module: WorkshopModuleContribution,
    persisted: PersistedBundleVersion,
    object_refs: dict[str, WorkshopDependencyRef],
    capability_refs: dict[str, WorkshopDependencyRef],
    aip_feature_refs: dict[str, WorkshopDependencyRef],
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
    blockers, dependency_refs = _initial_dependencies(
        module=module,
        bundle_status=persisted.status,
        granted_data_scopes=installed.lock.payload.permission_diff.target.data_scopes,
        installation_revision=installed.active_revision,
        lock_revision=installed.lock.revision,
        lock_hash=installed.lock.lock_hash,
        object_refs=object_refs,
        capability_refs=capability_refs,
        aip_feature_refs=aip_feature_refs,
    )
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
            "dependencyRefs": dependency_refs,
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


def _initial_dependencies(
    *,
    module: WorkshopModuleContribution,
    bundle_status: str,
    granted_data_scopes: Collection[str] = (),
    installation_revision: int,
    lock_revision: int,
    lock_hash: str,
    object_refs: dict[str, WorkshopDependencyRef],
    capability_refs: dict[str, WorkshopDependencyRef],
    aip_feature_refs: dict[str, WorkshopDependencyRef],
) -> tuple[list[WorkshopReadinessBlocker], list[WorkshopDependencyRef]]:
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
        ], []

    blockers: list[WorkshopReadinessBlocker] = []
    dependency_refs: list[WorkshopDependencyRef] = [
        object_refs[dependency_id]
        for dependency_id in module.required_objects
        if dependency_id in object_refs
    ]
    dependency_refs.extend(
        capability_refs[dependency_id]
        for dependency_id in module.required_capabilities
        if dependency_id in capability_refs
    )
    dependency_refs.extend(
        aip_feature_refs[dependency_id]
        for dependency_id in module.required_aip_features
        if dependency_id in aip_feature_refs
    )
    blockers.extend(
        WorkshopReadinessBlocker.model_validate(
            {
                "dependencyType": WorkshopDependencyType.CAPABILITY.value,
                "dependencyId": dependency_id,
                "state": WorkshopDependencyState.UNKNOWN.value,
                "reasonCode": "CAPABILITY_BINDING_UNVERIFIED",
                "recoverable": True,
                "requiredAction": "完成组织 CapabilityBinding 并由 canonical reader 回读",
                "ref": None,
            }
        )
        for dependency_id in module.required_capabilities
        if dependency_id not in capability_refs
    )
    blockers.extend(
        WorkshopReadinessBlocker.model_validate(
            {
                "dependencyType": WorkshopDependencyType.AIP_FEATURE.value,
                "dependencyId": dependency_id,
                "state": WorkshopDependencyState.UNKNOWN.value,
                "reasonCode": "AIP_FEATURE_UNVERIFIED",
                "recoverable": True,
                "requiredAction": "由同租户 active AIP FeatureActivation exact ref 闭合后重新评估",
                "ref": None,
            }
        )
        for dependency_id in module.required_aip_features
        if dependency_id not in aip_feature_refs
    )
    blockers.extend(
        WorkshopReadinessBlocker.model_validate(
            {
                "dependencyType": WorkshopDependencyType.OBJECT.value,
                "dependencyId": dependency_id,
                "state": WorkshopDependencyState.UNKNOWN.value,
                "reasonCode": "OBJECT_READINESS_UNVERIFIED",
                "recoverable": True,
                "requiredAction": "由当前租户 canonical ObjectType composition 提供 exact 定义后重新评估",
                "ref": None,
            }
        )
        for dependency_id in module.required_objects
        if dependency_id not in object_refs
    )
    granted_scope_set = set(granted_data_scopes)
    dependency_refs.extend(
        WorkshopDependencyRef.model_validate(
            {
                "resourceType": "DataScopeGrant",
                "resourceId": dependency_id,
                "revision": f"installation:{installation_revision}/lock:{lock_revision}",
                "contentHash": lock_hash,
                "authority": "postgres:bundle_composition_lock",
            }
        )
        for dependency_id in module.permissions.data_scopes
        if dependency_id in granted_scope_set
    )
    blockers.extend(
        WorkshopReadinessBlocker.model_validate(
            {
                "dependencyType": WorkshopDependencyType.DATA_SCOPE.value,
                "dependencyId": dependency_id,
                "state": WorkshopDependencyState.BLOCKED.value,
                "reasonCode": "DATA_SCOPE_NOT_GRANTED",
                "recoverable": True,
                "requiredAction": "由当前生效 CompositionLock 明确授予该数据范围后重新评估",
                "ref": None,
            }
        )
        for dependency_id in module.permissions.data_scopes
        if dependency_id not in granted_scope_set
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
        ], dependency_refs
    return blockers, dependency_refs


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


def _fresh_capability_refs(
    bindings: Collection[Any], *, evaluated_at: datetime
) -> dict[str, WorkshopDependencyRef]:
    candidates: dict[str, list[Any]] = {}
    for binding in bindings:
        usable = binding.operational_readiness.value == "available" or (
            binding.operational_readiness.value == "degraded"
            and binding.dependencies.allow_degraded
        )
        if (
            binding.status != "active"
            or binding.health.value not in {"healthy", "degraded"}
            or not usable
            or binding.dependency_snapshot_hash is None
            or binding.readiness_expires_at is None
            or binding.readiness_expires_at <= evaluated_at
        ):
            continue
        candidates.setdefault(binding.capability.asset_id, []).append(binding)

    result: dict[str, WorkshopDependencyRef] = {}
    for capability_id, options in candidates.items():
        binding = max(
            options,
            key=lambda item: (
                item.updated_at,
                item.capability.revision,
                item.version,
                item.binding_id,
            ),
        )
        result[capability_id] = WorkshopDependencyRef.model_validate(
            {
                "resourceType": "CapabilityBindingRevision",
                "resourceId": capability_id,
                "revision": f"{binding.binding_id}:{binding.version}",
                "contentHash": canonical_sha256(
                    {
                        "bindingId": binding.binding_id,
                        "bindingVersion": binding.version,
                        "capability": binding.capability.model_dump(
                            mode="json", by_alias=True
                        ),
                        "health": binding.health.value,
                        "operationalReadiness": binding.operational_readiness.value,
                        "dependencySnapshotHash": binding.dependency_snapshot_hash,
                        "readinessExpiresAt": binding.readiness_expires_at.isoformat(),
                        "status": binding.status,
                    }
                ),
                "authority": "postgres:aip_capability_binding+aip_capability_revision",
            }
        )
    return result


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
