"""Control-specific signed qualification; stopping does not read the source."""
from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
from aos_api.ecommerce_product_event_qualified_owner import ProductEventQualifiedOwner
from aos_api.extension_runtime.lifecycle_store import _require_transaction
from aos_api.extension_runtime.runtime_gate import _reject_deferred
from aos_api.tenant_scope import TenantScope

CONTROL_CONTRACT_PATH='content/schemas/product-event-control.contract.v1.json'
CONTROL_CONTRACT={
    'schemaVersion':'aos.ecommerce.product-event-control-contract/v1',
    'operationId':'ecommerce_growth_event_control',
    'commandSchema':'aos.ecommerce.product-event-control-command/v1',
    'receiptType':'EventPolicyControlReceipt',
    'tenantAuthority':'trusted-host-scope',
    'enableApproval':'current-independent-action-approval',
    'disableAuthority':'current-tenant-controller',
    'sourceRequiredForDisable':False,
}


class ProductEventControlQualifiedOwner:
    def __init__(self,*,selections,installation_store,artifacts,release_policy):
        self._release=ProductEventQualifiedOwner(selections=selections,installation_store=installation_store,
            artifacts=artifacts,release_policy=release_policy)
        self._source=selections
        self._artifacts=artifacts

    def _check_scope(self,conn,scope,execute):
        _require_transaction(conn)
        if type(scope) is not TenantScope or scope!=self._artifacts.scope or not callable(execute):
            raise PermissionError('current control qualification scope required')

    def _qualify(self,conn,scope,current):
        self._release._qualify_contract(conn,scope,current,CONTROL_CONTRACT_PATH,CONTROL_CONTRACT)

    def run_current_snapshot(self,conn,*,scope,ref,actor,execute):
        self._check_scope(conn,scope,execute)
        conn.execute('SELECT pg_advisory_xact_lock(228,1)')
        def current(draft,mapping):
            installed=CurrentInstallationRef.model_validate(draft.installation_ref.model_dump(by_alias=True))
            self._qualify(conn,scope,installed)
            result=execute(draft,mapping)
            _reject_deferred(result)
            self._qualify(conn,scope,installed)
            return result
        return self._source.run_current_snapshot(conn,scope=scope,ref=ref,actor=actor,execute=current)

    def run_without_source(self,conn,*,scope,dispatch,execute):
        self._check_scope(conn,scope,execute)
        identity=conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id").fetchone()
        if identity is None or (identity['role'],identity['org_id'],identity['project_id'])!=('aos_runtime',*scope.key):
            raise PermissionError('current control runtime scope required')
        if dispatch.operation_id!='ecommerce_growth_event_control':
            raise ValueError('current control operation required')
        conn.execute('SELECT pg_advisory_xact_lock(228,1)')
        def check():
            row=conn.execute('''SELECT i.installation_id,i.active_revision AS revision,i.etag_version,
                ir.lock_hash,ir.overlay_revision,r.generation,r.execution_epoch
                FROM bundle_installation i JOIN bundle_installation_revision ir
                  ON (ir.org_id,ir.project_id,ir.installation_pk,ir.revision)=
                     (i.org_id,i.project_id,i.installation_pk,i.active_revision)
                JOIN extension_runtime_binding r
                  ON (r.org_id,r.project_id,r.installation_id,r.installation_revision)=
                     (i.org_id,i.project_id,i.installation_id,i.active_revision)
                WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s AND r.generation=%s''',
                (*scope.key,dispatch.installation_id,dispatch.generation)).fetchone()
            if (row is None or str(row['installation_id'])!=str(dispatch.installation_id)
                    or str(row['generation'])!=str(dispatch.generation)
                    or type(dispatch.execution_epoch) is not int or row['execution_epoch']!=dispatch.execution_epoch):
                raise ValueError('current control installation or generation drifted')
            current=CurrentInstallationRef(installationId=str(row['installation_id']),revision=row['revision'],
                lockHash=row['lock_hash'],overlayRevision=row['overlay_revision'])
            self._qualify(conn,scope,current)
            return current,row['etag_version']
        before=check()
        result=execute()
        _reject_deferred(result)
        if check()!=before:
            raise ValueError('control installation changed during callback')
        return result
