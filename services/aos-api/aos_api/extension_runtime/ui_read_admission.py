"""Current signed-resource admission; a delivery is never execution authority."""
from aos_api.ecommerce_runtime_workshop_catalog import RuntimeWorkshopCatalog
from aos_api.extension_runtime.lifecycle_store import RuntimeConflict
from aos_api.extension_runtime.ui_read_api_database import read_api_ui_principal, enqueue_api_ui_read
from aos_api.extension_runtime.ui_read_contracts import UiReadRequest
from aos_api.extension_runtime.ui_read_store import UiReadDelivery
from aos_api.tenant_scope import TenantScope


class RuntimeUiReadAdmission:
    def __init__(self, *, catalog: RuntimeWorkshopCatalog):
        if type(catalog) is not RuntimeWorkshopCatalog:
            raise TypeError('current signed runtime catalog required')
        self._catalog = catalog

    def enqueue(self, *, conn, scope: TenantScope, subject: str,
                required_markings: tuple[str, ...], idempotency_key: str,
                request: UiReadRequest) -> UiReadDelivery:
        if type(request) is not UiReadRequest:
            raise RuntimeConflict('fixed UI read request required')
        principal = read_api_ui_principal(conn=conn, scope=scope, subject=subject,
                                              required_markings=required_markings)
        catalog = self._catalog.list_modules(org_id=scope.org_id, project_id=scope.project_id,
                                            roles=principal.roles, markings=principal.markings)
        if ((catalog.tenant.orgId, catalog.tenant.projectId) != scope.key
                or catalog.count != len(catalog.items)):
            raise RuntimeConflict('current UI catalog scope differs')
        matches = [entry for entry in catalog.items if entry.module.module_id == request.moduleId]
        if len(matches) != 1:
            raise RuntimeConflict('current signed UI module unavailable')
        entry = matches[0]
        target = request.target
        if (entry.module.route != target.route or entry.ui.initialRoute != target.route
                or target.route not in entry.ui.routeClaims
                or request.operationId not in entry.ui.readOperationClaims
                or not set(entry.module.permissions.roles).issubset(principal.roles)
                or not set(entry.module.permissions.markings).issubset(principal.markings)
                or entry.installationId != target.installationId
                or entry.installationRevision != target.installationRevision
                or entry.generation != target.generation
                or entry.executionEpoch != target.executionEpoch
                or entry.bindingRevision != target.bindingRevision
                or entry.ui.resourceHash != target.resourceHash):
            raise RuntimeConflict('current signed UI read declaration differs')
        return enqueue_api_ui_read(conn=conn, scope=scope, subject=subject,
                               idempotency_key=idempotency_key, request=request)
