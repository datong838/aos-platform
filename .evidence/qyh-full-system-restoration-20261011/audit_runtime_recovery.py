"""Current exact installation metadata; never a user authority or command."""
import json
from uuid import UUID
import release_transition as T
from audit_workshop_routes import readonly_factory, digest
from aos_api.asset_registry.installation_store import PostgresInstallationStore
from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
from aos_api.asset_registry.errors import AssetNotFoundError
from aos_api.extension_runtime.runtime_view import RuntimeViewReader, _derive_control_state
from aos_api.extension_runtime.runtime_resource_health import current_resources_live

IDS = ['407059df-6f1f-4927-acd7-8e388692838e',
       '89975129-7e0f-4860-ac56-7a031ebe4a1a',
       'ef5bc0c3-1dbe-4659-b839-2350f70232bf']


def read():
    store = PostgresInstallationStore(connect_factory=readonly_factory)
    result = []
    for iid in IDS:
        record = store.get_installation(org_id='org-org', project_id='dev-project', installation_id=iid)
        with readonly_factory() as conn:
            apply_asset_transaction_scope(conn, org_id='org-org', project_id='dev-project')
            binding_row = conn.execute('''SELECT generation,installation_revision,profile_ref,config_ref,
                execution_epoch,desired_state,observed_state,enabled,operation_fence,revision
                FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s
                ORDER BY (installation_revision=%s) DESC,(desired_state<>'uninstalled') DESC,
                revision DESC,generation DESC LIMIT 1''',('org-org','dev-project',UUID(iid),record.current_revision)).fetchone()
            operation_row = conn.execute('''SELECT operation_id,installation_id,kind,phase,status,revision,
                requested_by,approved_by,expected_installation_etag,expected_binding_revision,deadline,
                failure_code,created_at FROM extension_runtime_operation
                WHERE org_id=%s AND project_id=%s AND installation_id=%s
                ORDER BY (status NOT IN ('succeeded','failed','cancelled')) DESC,
                created_at DESC,operation_id DESC LIMIT 1''',('org-org','dev-project',UUID(iid))).fetchone()
            binding = RuntimeViewReader._binding_from_row(binding_row)
            operation = RuntimeViewReader._operation_from_row(conn,'org-org','dev-project',operation_row)
            state = str(getattr(record.state,'value',record.state))
            effective, actions, reasons = _derive_control_state(installation_state=state,
                installation_revision=record.current_revision,binding=binding,operation=operation)
            live = bool(binding and current_resources_live(conn,org_id='org-org',project_id='dev-project',
                installation_id=iid,generation=binding.generation))
            resource = conn.execute('''SELECT count(*) AS count,
                count(*) FILTER(WHERE observed_release IS TRUE) AS released,
                count(*) FILTER(WHERE expires_at>clock_timestamp()) AS unexpired
                FROM extension_runtime_resource_lease WHERE org_id=%s AND project_id=%s AND generation=%s''',
                ('org-org','dev-project',UUID(binding.generation))).fetchone() if binding else None
            result.append({'installationId':iid,'installationState':state,'currentRevision':record.current_revision,
                'effectiveStateBeforeLiveGate':effective,'descriptiveActionsOnly':list(actions),'reasons':list(reasons),
                'binding':None if not binding else {'generation':binding.generation,'revision':binding.revision,
                    'desiredState':binding.desiredState,'observedState':binding.observedState,
                    'enabled':binding.enabled,'operationFence':binding.operationFence,'configured':binding.configRef is not None},
                'operation':None if not operation else {'operationId':operation.operationId,'kind':operation.kind,
                    'status':operation.status,'phase':operation.phase,'failureCode':operation.failureCode},
                'currentResourcesLive':live,'resources':resource})
    denied = []
    for iid in IDS:
        try:
            store.get_installation(org_id='dev-org',project_id='dev-project',installation_id=iid)
        except AssetNotFoundError:
            denied.append(iid)
        else:
            raise RuntimeError('Canary unexpectedly read positive installation')
    return {'installations':result,'canaryRejected':denied}


if __name__ == '__main__':
    assert not (T.R/'runtime-recovery-state-audit.json').exists()
    T.H.preflight(T.R/'private/restored-identity.json')
    first, second = read(), read()
    assert digest(first) == digest(second), 'State changed: reconcile without replay'
    report={'outcome':'RESTORED_RUNTIME_RECOVERY_METADATA_READONLY','observed':first,
        'independentReadsStable':True,'databaseWrites':0,'userPrincipalAuthenticated':False,
        'actionsAuthorized':False,'apiStarted':False,'eightPagesAccepted':False}
    T.record('runtime-recovery-state-audit.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
