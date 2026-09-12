"""Conservative exact-target recovery of the configured, never-enabled instance."""
import argparse
import json
import os
from pathlib import Path
from a0v_ecommerce_1_7_configure import setup, INSTALLATION, RECOVERY


def run():
    connect,activation,_,configuration=setup()
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_service import RuntimeDisableService
    scope=dict(org_id='org-org',project_id='dev-project')
    path=RECOVERY/'state/ecommerce-1.7-disable-command.json'
    with connect() as conn:
        with conn.transaction():
            apply_asset_transaction_scope(conn,**scope)
            row=conn.execute('SELECT i.etag_version,b.generation,b.revision FROM bundle_installation i JOIN extension_runtime_binding b ON b.org_id=i.org_id AND b.project_id=i.project_id AND b.installation_id=i.installation_id WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s',(*scope.values(),INSTALLATION)).fetchone()
    if not row:raise ValueError('KNOWN_BINDING_REQUIRED')
    if path.exists():
        frozen=json.loads(path.read_text())
    else:
        frozen=dict(installationId=INSTALLATION,etag=row['etag_version'],target=dict(generation=str(row['generation']),bindingRevision=row['revision']))
        with path.open('x') as handle:
            os.chmod(path,0o600);handle.write(json.dumps(frozen,indent=2)+'\n');handle.flush();os.fsync(handle.fileno())
    if frozen['installationId']!=INSTALLATION or frozen['target']['generation']!=str(row['generation']):raise ValueError('RECOVERY_TARGET_DRIFT')
    service=RuntimeDisableService(installation_store=configuration._store,installation_reader=configuration._reader,check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION))
    receipt=service.request(installation_id=INSTALLATION,**scope,actor=activation.ACTOR,roles=activation.ROLES,markings=activation.MARKINGS,idempotency_key='a0v-ecommerce-1.7-disable-after-config-host-loss-v1',if_match='"'+str(frozen['etag'])+'"',target=frozen['target'])
    return dict(command=frozen,receipt=receipt.response_json,replayed=receipt.replayed)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if not args.apply:raise ValueError('EXPLICIT_DISABLE_REQUIRED')
    result=run();args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,default=str,indent=2)+'\n');print(json.dumps(result,default=str,indent=2))
