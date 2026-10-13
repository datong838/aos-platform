"""Signed installed-asset viewing, separate from business/runtime admission."""
from __future__ import annotations
from uuid import UUID

from aos_api.ecommerce_workshop_catalog import EcommerceWorkshopCatalog
from aos_api.ecommerce_workshop_contracts import (
    WorkshopDependencyState, WorkshopDependencyType, WorkshopReadiness,
    WorkshopReadinessBlocker,
)


class _SelectedInstalledSource:
    def __init__(self, source, *, installation_id: str, org_id: str, project_id: str):
        if str(UUID(installation_id)) != installation_id:
            raise ValueError('Canonical installation UUID required')
        if not org_id.strip() or not project_id.strip():
            raise ValueError('Explicit tenant required')
        self.source = source
        self.installation_id = installation_id
        self.org_id = org_id
        self.project_id = project_id

    def read_active_bundles(self, *, org_id, project_id, markings):
        if (org_id, project_id) != (self.org_id, self.project_id):
            return ()
        # This remains candidate discovery. It grants no runtime/UI session.
        rows = self.source.read_runtime_candidate_bundles(
            org_id=org_id, project_id=project_id, markings=markings)
        return tuple(row for row in rows if row.installation_id == self.installation_id)


class InstalledReadonlyWorkshopCatalog(EcommerceWorkshopCatalog):
    """Reuse exact lock/signature/artifact/permission projection; always disabled."""
    def __init__(self, *, source, loader, installation_id, org_id, project_id, clock=None):
        selected = _SelectedInstalledSource(source, installation_id=installation_id,
            org_id=org_id, project_id=project_id)
        super().__init__(source=selected, loader=loader, clock=clock)

    def _project_modules(self, **kwargs):
        modules, cutoff = super()._project_modules(**kwargs)
        for module in modules:
            module.readiness = WorkshopReadiness.DISABLED
            module.blockers.append(WorkshopReadinessBlocker(
                dependencyType=WorkshopDependencyType.INSTALLATION,
                dependencyId=module.installation_ref.installation_id,
                state=WorkshopDependencyState.UNKNOWN,
                reasonCode='INSTALLED_ASSET_READONLY', recoverable=True,
                requiredAction='已安装页面可只读查看；业务执行仍须完成正式运行准入。'))
        return modules, cutoff


class _EmptySource:
    def read_active_bundles(self, **kwargs):
        return ()


def build_installed_readonly_catalog():
    """Explicit server configuration; absent configuration discovers nothing."""
    import json
    import os
    from pathlib import Path
    from aos_api.asset_registry.control_wiring import _allowlist_roots, _configured_trust_roots
    from aos_api.asset_registry.errors import RegistryIntegrityCorruptError
    from aos_api.asset_registry.manifest_loader import ManifestLoader
    from aos_api.asset_registry.workshop_catalog_source import PostgresWorkshopCatalogSource
    from aos_api.db import connect_read_only

    raw = os.getenv('AOS_INSTALLED_READONLY_CATALOG')
    if not raw:
        return EcommerceWorkshopCatalog(source=_EmptySource(), loader=None)
    try:
        config = json.loads(raw)
        if not isinstance(config, dict) or set(config) != {'installationId', 'orgId', 'projectId'}:
            raise ValueError('Explicit bounded configuration required')
        if not all(isinstance(value, str) and value.strip() == value and value for value in config.values()):
            raise ValueError('Canonical configuration required')
        if not os.getenv('AOS_LOCAL_MANAGEMENT_OIDC_CONFIG') or not os.getenv('AOS_BUNDLE_ROOT'):
            raise ValueError('Management identity and signed source required')
        trust = _configured_trust_roots()
        if trust is None:
            raise ValueError('Explicit trust roots required')
        return InstalledReadonlyWorkshopCatalog(
            source=PostgresWorkshopCatalogSource(lambda: connect_read_only(inherit_scope=False)),
            loader=ManifestLoader(_allowlist_roots(repository_root=Path(__file__).resolve().parents[3]), trust_roots=trust),
            installation_id=config['installationId'], org_id=config['orgId'], project_id=config['projectId'])
    except (ValueError, TypeError, KeyError):
        raise RegistryIntegrityCorruptError() from None
