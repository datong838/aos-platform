"""Exact four-source configuration for the known local ecommerce successor."""
import argparse
import json
import os
from pathlib import Path
from a0v_ecommerce_1_7_first_install import load, ROOT, RECOVERY, TRUST_STATE

INSTALLATION='e42e042b-1fe7-4cfa-bb83-469ff256081d'
STATE=RECOVERY/'state/ecommerce-1.7-configuration.json'
BUNDLE_ROOT=RECOVERY/'state/ecommerce-1.7-registry/signed-bundles-v7'


def setup():
    host=load('a0v_ecommerce_runtime_host')
    credentials=host._load_credentials(host.DEFAULT_CREDENTIALS)
    host._configure_environment(credentials,bundle_root=BUNDLE_ROOT,trust_roots_file=TRUST_STATE/'signing/trust-roots.json')
    import sys
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    activation=load('a0v_ecommerce_growth_1_4_activate')
    connect=runtime_worker_connection
    store,lifecycle=activation._services(connect,TRUST_STATE/'signing/trust-roots.json')
    from aos_api.extension_runtime.configuration_authorization import CurrentConfigurationPermission
    from aos_api.aip_runtime_configuration_sources import build_current_configuration_authorization
    from aos_api.extension_runtime.configuration_service import RuntimeConfigurationService
    authorize=build_current_configuration_authorization(permission=CurrentConfigurationPermission(installation_store=store))
    service=RuntimeConfigurationService(installation_store=store,installation_reader=lifecycle._reader,revalidator=lifecycle._revalidator,authorize=authorize)
    return connect,activation,authorize,service


def run(action):
    connect,activation,authorize,service=setup()
    from aos_api.asset_registry.tenant_transaction import apply_asset_transaction_scope
    from aos_api.extension_runtime.configuration_contracts import ConfigurationDocument,ConfigurationSourceRef,ConfigureTarget
    from aos_api.extension_runtime.configuration_store import append_configuration
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    from aos_api.aip_model_governance_policy_store import AipModelGovernancePolicyStore
    from aos_api.tenant_scope import TenantScope
    scope=TenantScope('org-org','dev-project')
    # Read metadata through the same verified isolated endpoint; Owner readers
    # below revalidate every exact ref on the admitted runtime transaction.
    from a0v_formal_text_model_renewal import database_connect
    metadata=database_connect('aos_meta_head')
    models=AipModelRuntimeStore(metadata)
    policy=models.get_policy(scope,'a0v-ecommerce-runtime-policy-v1')
    budget_policy=AipModelGovernancePolicyStore(metadata).get_budget(scope,policy.budget_policy_ref.asset_id,policy.budget_policy_ref.revision)
    with metadata(scope) as conn:
        plans=conn.execute("SELECT r.plan_id,r.revision,r.content_hash FROM aip_responsibility_plan_head h JOIN aip_responsibility_plan_revision r USING(org_id,project_id,plan_id) WHERE h.org_id=%s AND h.project_id=%s AND r.revision=h.current_revision AND r.profile='ecommerce.business-investigation.readonly' AND r.lifecycle='frozen'",scope.key).fetchall()
    if len(plans)!=1:raise ValueError('EXACT_FROZEN_INVESTIGATION_PLAN_REQUIRED')
    plan=plans[0]
    def ref(authority,id,revision,hash):return ConfigurationSourceRef(authority=authority,id=id,revision=revision,hash=hash if hash.startswith('sha256:') else 'sha256:'+hash)
    document=ConfigurationDocument(roleRefs=(ref('aip.responsibility_plan_revision',plan['plan_id'],plan['revision'],plan['content_hash']),),
        dataRefs=(ref('aip.data_classification_policy_revision',policy.data_classification_policy_ref.asset_id,policy.data_classification_policy_ref.revision,policy.data_classification_policy_ref.content_hash),),
        budgetRef=ref('aip.budget_revision',budget_policy.budget_revision_ref.asset_id,budget_policy.budget_revision_ref.revision,budget_policy.budget_revision_ref.content_hash),
        policyRef=ref('aip.runtime_policy_revision',policy.policy_id,policy.revision,policy.content_hash))
    with connect() as conn:
        with conn.transaction():
            apply_asset_transaction_scope(conn,org_id=scope.org_id,project_id=scope.project_id)
            installation=conn.execute('SELECT r.state,i.etag_version FROM bundle_installation i JOIN bundle_installation_revision r ON r.org_id=i.org_id AND r.project_id=i.project_id AND r.installation_pk=i.installation_pk AND r.revision=i.current_revision WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s',(*scope.key,INSTALLATION)).fetchone()
            binding=conn.execute('SELECT generation,revision,desired_state,observed_state,enabled,operation_fence,config_ref FROM extension_runtime_binding WHERE org_id=%s AND project_id=%s AND installation_id=%s',(*scope.key,INSTALLATION)).fetchone()
            if not installation or installation['state']!='active' or not binding:raise ValueError('KNOWN_ACTIVE_INSTALLATION_REQUIRED')
            target={'org_id':scope.org_id,'project_id':scope.project_id,'installation_id':INSTALLATION,'generation':str(binding['generation'])}
            authorize(conn,**target,actor=activation.ACTOR,configuration=document)
            result={'action':action,'installationId':INSTALLATION,'installation':dict(installation),'binding':dict(binding),'configuration':document.model_dump(mode='json'),'authorized':True}
            if action=='stage':
                frozen=json.loads(STATE.read_text()) if STATE.exists() else {'installationEtag':installation['etag_version'],'bindingRevision':binding['revision'],'generation':str(binding['generation']),'configuration':document.model_dump(mode='json')}
                if frozen['generation']!=str(binding['generation']) or frozen['configuration']!=document.model_dump(mode='json'):raise ValueError('CONFIGURATION_INPUT_DRIFT')
                staged=append_configuration(conn,**target,expected_installation_etag=frozen['installationEtag'],expected_binding_revision=frozen['bindingRevision'],
                    actor=activation.ACTOR,idempotency_key='a0v-ecommerce-1.7-config-stage-v1',configuration=document,authorize=authorize)
                frozen['configRef']=staged.model_dump(mode='json');result['staged']=frozen
    if action=='stage':
        STATE.parent.mkdir(parents=True,exist_ok=True);temporary=STATE.with_suffix('.tmp');temporary.write_text(json.dumps(result['staged'],indent=2)+'\n');os.chmod(temporary,0o600);temporary.replace(STATE)
    elif action in {'configure','enable'}:
        frozen=json.loads(STATE.read_text())
        if frozen['generation']!=str(binding['generation']):raise ValueError('CONFIGURATION_GENERATION_DRIFT')
        command_path=STATE.with_name('ecommerce-1.7-'+action+'-command.json')
        if command_path.exists():
            command=json.loads(command_path.read_text())
        else:
            command={'generation':frozen['generation'],'bindingRevision':binding['revision'],'configRef':frozen['configRef'],'etag':installation['etag_version']}
            with command_path.open('x') as handle:
                os.chmod(command_path,0o600);handle.write(json.dumps(command,indent=2)+'\n');handle.flush();os.fsync(handle.fileno())
        if command['generation']!=frozen['generation'] or command['configRef']!=frozen['configRef']:raise ValueError('FROZEN_CONFIGURATION_COMMAND_DRIFT')
        command_target=ConfigureTarget(generation=command['generation'],bindingRevision=command['bindingRevision'],configRef=command['configRef'])
        receipt=service.request(installation_id=INSTALLATION,kind=action,org_id=scope.org_id,project_id=scope.project_id,
            actor=activation.ACTOR,roles=activation.ROLES,markings=activation.MARKINGS,idempotency_key='a0v-ecommerce-1.7-'+action+'-v1',
            if_match='"'+str(command['etag'])+'"',target=command_target)
        result['receipt']=receipt.response_json
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--action',choices=['preflight','stage','configure','enable'],required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run(args.action)
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,default=str,indent=2)+'\n')
    print(json.dumps(result,default=str,indent=2))
