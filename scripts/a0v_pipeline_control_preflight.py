"""Current pipeline checks with existing runtime identity; never approve or execute."""
import argparse
import json
import os
from pathlib import Path
import sys
from datetime import timedelta, datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/aos-api'))
os.environ['AOS_DOTENV_DISABLED']='1'


def run():
    from a0v_ecommerce_runtime_host import DEFAULT_CREDENTIALS, _safe_error_chain
    bundle=ROOT.parent/'.aos-recovery-20260912/state/ecommerce-1.7-registry/signed-bundles-v7'
    trust=ROOT.parent/'.aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install/signing/trust-roots.json'
    os.environ['AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE']=str(DEFAULT_CREDENTIALS)
    os.environ['AOS_BUNDLE_ROOT']=str(bundle)
    os.environ['AOS_BUNDLE_TRUST_ROOTS_FILE']=str(trust)
    os.environ['AOS_EXTENSION_RUNTIME_HOST_ENABLED']='0'
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    from aos_api.ec_ingress_journal import _digest
    from aos_api.tenant_scope import TenantScope
    result=dict(observedAt=datetime.now(timezone.utc).isoformat(),currentChecksPassed=False,
        approvalsWritten=0,sourceRowsRead=0,businessWrites=0,executionGranted=False)
    try:
        scope=TenantScope('org-org','dev-project')
        plane=build_runtime_control_plane()
        service=plane.pipeline_control_factory.build(scope)
        prior=json.loads((ROOT/'.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/source-selection-installed-assets-preflight.json').read_text())
        installation=CurrentInstallationRef.model_validate(prior['installationRef'])
        if installation.installation_id!='a0fd8e25-cb6f-49e5-aa77-7faddae12099':raise ValueError('unexpected preflight installation')
        with consumer_connection(runtime_worker_connection,dict(org_id=scope.org_id,project_id=scope.project_id)) as conn:
            baseline=plane.installation_store.load_active_baseline_in_transaction(conn,org_id=scope.org_id,project_id=scope.project_id,requested_ref=installation)
            selected=[item for item in baseline.lock.payload.resolved if item.id=='platform.ecommerce.niushop']
            if len(selected)!=1:raise ValueError('ambiguous source package')
            selected=selected[0]
            binding=conn.execute('''SELECT generation,execution_epoch,config_ref FROM extension_runtime_binding
                WHERE org_id=%s AND project_id=%s AND installation_id=%s AND installation_revision=%s''',
                (*scope.key,installation.installation_id,installation.revision)).fetchall()
            if len(binding)!=1:raise ValueError('ambiguous runtime binding')
            binding=binding[0]
            graph=conn.execute('''SELECT payload,revision FROM phase5_pipeline_graph
                WHERE org_id=%s AND project_id=%s AND pipeline_id='P01-shop-qyh' ''',scope.key).fetchone()
            source=SourceConfigurationRevisionStore(HostTransaction(conn),scope).read_current('niushop-qyh')
            now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            body=dict(orgId=scope.org_id,projectId=scope.project_id,pipelineId='P01-shop-qyh',
                graphRevision=graph['revision'],graphHash=_digest(graph['payload']),installationRef=prior['installationRef'],
                generation=str(binding['generation']),executionEpoch=binding['execution_epoch'],configurationRef=binding['config_ref'],
                packageRef=dict(publisher=selected.publisher,id=selected.id,version=selected.version,contentHash=selected.content_hash),
                sourceId='niushop-qyh',sourceConfigurationRef=source.ref.model_dump(mode='json',by_alias=True),
                rowLimit=100,timeoutSeconds=30,maxSourceCalls=1,notBefore=now,expiresAt=now+timedelta(minutes=15))
            for name,kind,asset in zip(('mappingRef','schemaRef','maskingPolicyRef'),('Mapping','SchemaFingerprint','MaskingPolicy'),prior['artifacts']):
                body[name]=dict(resourceType=kind,resourceId=asset['path'],revision=selected.version,contentHash=asset['sha256'])
            draft=PipelineSourceSelectionDraft.model_validate(body)
            result['draft']=draft.model_dump(mode='json',by_alias=True)
            result['checkedActor']='a0v-ecommerce-growth-1.4-runtime-owner'
            result['spec']=service.selections._guarded(conn,draft,result['checkedActor'],
                lambda spec:dict(table=spec.table,columnCount=len(spec.columns),objectType=spec.object_type))
            result['currentChecksPassed']=True
    except Exception as error:
        result['errorChain']=_safe_error_chain(error)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run()
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:value for key,value in result.items() if key not in {'draft'}},ensure_ascii=False))
