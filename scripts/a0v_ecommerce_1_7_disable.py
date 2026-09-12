"""Conservative exact-target recovery of the configured local instance after host loss."""
import argparse
import json
import os
from pathlib import Path
from a0v_ecommerce_1_7_configure import setup, configuration_target


def disable_target(recovery=False, *, sleep_recovery=False):
    installation,configuration,key,command=configuration_target(recovery,sleep_recovery=sleep_recovery)
    return installation,configuration.with_name(command+'-disable-command.json'),key+'-disable-after-config-host-loss-v1'


def run(recovery=False, *, sleep_recovery=False):
    installation_id,path,key=disable_target(recovery,sleep_recovery=sleep_recovery)
    connect,activation,_,configuration=setup()
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.asset_registry.control_policy import DISABLE_RUNTIME_OPERATION
    from aos_api.extension_runtime.current_permission import CurrentControlPermission
    from aos_api.extension_runtime.disable_service import RuntimeDisableService
    scope=dict(org_id='org-org',project_id='dev-project')
    with connect() as conn:
        with conn.transaction():
            apply_asset_transaction_scope(conn,**scope)
            row=conn.execute('SELECT i.etag_version,b.generation,b.revision FROM bundle_installation i JOIN extension_runtime_binding b ON b.org_id=i.org_id AND b.project_id=i.project_id AND b.installation_id=i.installation_id WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s',(*scope.values(),installation_id)).fetchone()
    if not row:raise ValueError('KNOWN_BINDING_REQUIRED')
    if path.exists():
        frozen=json.loads(path.read_text())
    else:
        frozen=dict(installationId=installation_id,etag=row['etag_version'],target=dict(generation=str(row['generation']),bindingRevision=row['revision']))
        with path.open('x') as handle:
            os.chmod(path,0o600);handle.write(json.dumps(frozen,indent=2)+'\n');handle.flush();os.fsync(handle.fileno())
    if frozen['installationId']!=installation_id or frozen['target']['generation']!=str(row['generation']):raise ValueError('RECOVERY_TARGET_DRIFT')
    service=RuntimeDisableService(installation_store=configuration._store,installation_reader=configuration._reader,check_current_permission=CurrentControlPermission(operation=DISABLE_RUNTIME_OPERATION))
    receipt=service.request(installation_id=installation_id,**scope,actor=activation.ACTOR,roles=activation.ROLES,markings=activation.MARKINGS,idempotency_key=key,if_match='"'+str(frozen['etag'])+'"',target=frozen['target'])
    return dict(command=frozen,receipt=receipt.response_json,replayed=receipt.replayed)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');parser.add_argument('--output',type=Path,required=True)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--after-config-recovery',action='store_true')
    group.add_argument('--after-sleep-recovery',action='store_true')
    args=parser.parse_args()
    if not args.apply:raise ValueError('EXPLICIT_DISABLE_REQUIRED')
    result=run(recovery=args.after_config_recovery,sleep_recovery=args.after_sleep_recovery);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,default=str,indent=2)+'\n');print(json.dumps(result,default=str,indent=2))
