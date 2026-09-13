"""Runtime-only Workshop resource catalog; never a business execution grant."""
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from aos_api.asset_registry.contracts import WorkshopModuleContribution
from aos_api.asset_registry.errors import RegistryIntegrityCorruptError
from aos_api.asset_registry.workshop_catalog_source import (
    _derive_source_ref, _verify_loaded_bundle, _verify_installed_bundle,
)
from aos_api.extension_runtime.runtime_view import RuntimeUiSessionView
from aos_api.tenant_scope import TenantScope


class RuntimeWorkshopTenant(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)
    orgId: str
    projectId: str


class RuntimeWorkshopModuleRef(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)
    publisher: str
    bundleId: str
    version: str
    bundleContentHash: str
    moduleArtifactRef: str
    moduleArtifactHash: str


class RuntimeWorkshopEntry(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)
    module: WorkshopModuleContribution
    moduleRef: RuntimeWorkshopModuleRef
    installationId: str
    installationRevision: int = Field(ge=1)
    generation: str
    executionEpoch: int = Field(ge=1)
    bindingRevision: int = Field(ge=1)
    ui: RuntimeUiSessionView
    resourceOnly: Literal[True] = True


class RuntimeWorkshopCatalogResponse(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True)
    schemaVersion: Literal['aos.runtime-workshop-catalog/v1'] = 'aos.runtime-workshop-catalog/v1'
    tenant: RuntimeWorkshopTenant
    evaluatedAt: datetime
    dataCutoff: datetime | None
    items: list[RuntimeWorkshopEntry]
    count: int = Field(ge=0)


class RuntimeWorkshopCatalog:
    def __init__(self, *, source, loader, view_reader):
        self._source = source
        self._loader = loader
        self._view_reader = view_reader

    def list_modules(self, *, org_id, project_id, roles, markings):
        scope = TenantScope(org_id, project_id)
        candidates = self._source.read_runtime_candidate_bundles(org_id=scope.org_id,
            project_id=scope.project_id, markings=markings)
        items = []
        seen_ids, seen_routes = set(), set()
        for installed in candidates:
            bundle = installed.bundle
            _verify_installed_bundle(installed)
            if not any(str(artifact.get('relativePath','')).startswith('content/workshops/') for artifact in bundle.artifacts):
                continue
            loaded = self._loader.load(_derive_source_ref(bundle.artifacts))
            _verify_loaded_bundle(loaded=loaded, persisted=bundle)
            for module in loaded.workshop_modules:
                if module.module_id in seen_ids or module.route in seen_routes:
                    raise RegistryIntegrityCorruptError()
                seen_ids.add(module.module_id)
                seen_routes.add(module.route)
                if (not set(module.permissions.roles).issubset(roles) or not set(module.permissions.markings).issubset(markings)
                        or not set(module.permissions.data_scopes).issubset(installed.lock.payload.permission_diff.target.data_scopes)):
                    continue
                view = self._view_reader.get_installation(installation_id=installed.installation_id,
                    org_id=scope.org_id, project_id=scope.project_id, roles=list(roles), markings=list(markings), requested_route=module.route)
                if (view.installationId != installed.installation_id or view.installationRevision != installed.active_revision
                        or view.effectiveState != 'ready' or view.binding is None or view.ui is None
                        or view.binding.installationRevision != installed.active_revision
                        or view.binding.enabled is not True or view.binding.operationFence is not False
                        or view.ui.initialRoute != module.route or module.route not in view.ui.routeClaims):
                    continue
                artifacts = [a for a in loaded.artifacts if a.relative_path == f'content/workshops/{module.module_id}.json']
                if len(artifacts) != 1:
                    raise RegistryIntegrityCorruptError()
                artifact = artifacts[0]
                items.append(RuntimeWorkshopEntry(module=module, installationId=view.installationId,
                    installationRevision=view.installationRevision, generation=view.binding.generation,
                    executionEpoch=view.binding.executionEpoch, bindingRevision=view.binding.revision, ui=view.ui,
                    moduleRef=RuntimeWorkshopModuleRef(publisher=bundle.publisher,bundleId=bundle.bundle_id,
                        version=bundle.version,bundleContentHash=bundle.content_hash,
                        moduleArtifactRef=artifact.artifact_ref,moduleArtifactHash=artifact.digest)))
        items.sort(key=lambda item:(item.module.order,item.module.module_id))
        return RuntimeWorkshopCatalogResponse(tenant=RuntimeWorkshopTenant(orgId=scope.org_id,projectId=scope.project_id),
            evaluatedAt=datetime.now(timezone.utc),dataCutoff=min((c.lock.created_at for c in candidates),default=None),
            items=items,count=len(items))


def build_runtime_workshop_catalog(*, source, loader, view_reader):
    return RuntimeWorkshopCatalog(source=source, loader=loader, view_reader=view_reader)
