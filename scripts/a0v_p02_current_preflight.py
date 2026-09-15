"""Read-only Product graph/draft preparation from the current signed package."""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
PIPELINE='P02-product-qyh'
ACTOR='a0v-ecommerce-growth-1.4-runtime-owner'
BUNDLE_ROOT=ROOT.parent/'.aos-recovery-20260915/state/current-ecommerce-package/registry/signed-bundles-current-ecommerce'
TRUST_ROOTS=ROOT.parent/'.aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install/signing/trust-roots.json'
CURRENT_CREATE=ROOT.parent/'.aos-recovery-20260915/state/current-ecommerce-package/install/d/create-result.json'
NIUSHOP_VERSION='1.22.0'


def require_current_head(create_receipt,head,binding):
    if (create_receipt.get('installationId')!=str(head.get('installation_id'))
            or create_receipt.get('installationState')!='approved'
            or head.get('state')!='active' or head.get('etag_version')!=5
            or head.get('overlay_revision')!='a0v-canonical-ecommerce-v1'):
        raise ValueError('exact current installation D required')
    if (binding.get('revision')!=4 or binding.get('execution_epoch')!=3
            or binding.get('enabled') is not True or binding.get('operation_fence') is not False
            or binding.get('desired_state')!='enabled' or binding.get('observed_state')!='ready'
            or not binding.get('config_ref')):
        raise ValueError('exact current ready binding required')
    return dict(installationId=str(head['installation_id']),revision=5,
        lockHash=head['lock_hash'],overlayRevision=head['overlay_revision'])


def build_graph(mapping):
    from copy import deepcopy
    source=dict(source_id='niushop-qyh',table=mapping['source_table'],source_table=mapping['source_table'],
        pk=mapping['primary_key'],primary_key=mapping['primary_key'],site_filter=mapping['site_filter'],
        incremental_strategy='snapshot',initial=False,unique_key_pattern=mapping['unique_key_pattern'])
    configs=(source,dict(expression='row',field_mappings=deepcopy(mapping['field_mappings']),target_ot=mapping['target_ot']),
        dict(target_ot=mapping['target_ot'],write_mode='SNAPSHOT',unique_key_pattern=mapping['unique_key_pattern']))
    kinds=('source','transform','sink')
    nodes=[dict(id=PIPELINE+'-'+kind,name=kind,node_type=kind,position_x=60+260*i,position_y=60,config=config)
        for i,(kind,config) in enumerate(zip(kinds,configs))]
    return dict(pipeline_id=PIPELINE,write_mode='SNAPSHOT',pipeline_type='ETL',name='栖月汇-商品',nodes=nodes,
        edges=[dict(id=PIPELINE+'-edge-'+str(i),source_node_id=nodes[i]['id'],target_node_id=nodes[i+1]['id']) for i in range(2)])


def run(action):
    if action not in ('graph','preflight'):raise ValueError('read-only preparation action required')
    from a0v_ecommerce_runtime_host import DEFAULT_CREDENTIALS, _configure_environment
    _configure_environment(DEFAULT_CREDENTIALS,bundle_root=BUNDLE_ROOT,trust_roots_file=TRUST_ROOTS)
    os.environ['AOS_EXTENSION_RUNTIME_HOST_ENABLED']='0'
    from aos_api.asset_registry.control_wiring import build_runtime_control_plane
    from aos_api.asset_registry.composition_contracts import CurrentInstallationRef
    from aos_api.asset_registry.manifest_loader import _UniqueKeySafeLoader
    from aos_api.extension_runtime.consumer_connection import consumer_connection
    from aos_api.extension_runtime.runtime_connections import runtime_worker_connection
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.source_configuration_revision import SourceConfigurationRevisionStore
    from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_source_selection_owner import verify_graph_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping
    from aos_api.ec_ingress_journal import _digest
    from aos_api.tenant_scope import TenantScope
    import yaml
    scope=TenantScope('org-org','dev-project');plane=build_runtime_control_plane();service=plane.pipeline_control_factory.build(scope)
    result=dict(observedAt=datetime.now(timezone.utc).isoformat(),sourceRowsRead=0,approvalsWritten=0,businessWrites=0)
    with consumer_connection(runtime_worker_connection,dict(org_id=scope.org_id,project_id=scope.project_id)) as conn:
        create_receipt=json.loads(CURRENT_CREATE.read_text(encoding='utf-8'))
        head=conn.execute('''SELECT i.installation_id,i.etag_version,r.state,r.lock_hash,r.overlay_revision
            FROM bundle_installation i JOIN bundle_installation_revision r ON r.installation_pk=i.installation_pk
            AND r.org_id=i.org_id AND r.project_id=i.project_id AND r.revision=i.current_revision
            WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',
            (*scope.key,create_receipt['installationId'])).fetchone()
        bindings=conn.execute('''SELECT generation,revision,execution_epoch,enabled,operation_fence,
            desired_state,observed_state,config_ref FROM extension_runtime_binding
            WHERE org_id=%s AND project_id=%s AND installation_id=%s AND installation_revision=5''',
            (*scope.key,create_receipt['installationId'])).fetchall()
        if head is None or len(bindings)!=1:raise ValueError('one current installation binding required')
        binding=bindings[0];current_ref=require_current_head(create_receipt,dict(head),dict(binding))
        baseline=plane.installation_store.load_active_baseline_in_transaction(conn,org_id=scope.org_id,project_id=scope.project_id,
            requested_ref=CurrentInstallationRef.model_validate(current_ref))
        selected=[p for p in baseline.lock.payload.resolved if p.id=='platform.ecommerce.niushop']
        if len(selected)!=1 or selected[0].version!=NIUSHOP_VERSION:raise ValueError('exact current Niushop required')
        selected=selected[0];docs=[];refs={}
        for name,kind,path in (
            ('mappingRef','Mapping','content/mappings/p02-product.yaml'),
            ('schemaRef','SchemaFingerprint','content/schemas/niushop-schema-fingerprint.json'),
            ('maskingPolicyRef','MaskingPolicy','content/mappings/_pii-exclusion.yaml')):
            raw=service.selections._artifacts.read_artifact(selected,path,256*1024)
            docs.append(json.loads(raw) if path.endswith('.json') else yaml.load(raw,Loader=_UniqueKeySafeLoader))
            refs[name]=dict(resourceType=kind,resourceId=path,revision=selected.version,contentHash='sha256:'+hashlib.sha256(raw).hexdigest())
        spec=derive_mapping_read_spec(*docs);compiled=compile_snapshot_mapping(docs[0],spec)
        graph=build_graph(docs[0]);verify_graph_read_spec(graph,docs[0],spec,source_id='niushop-qyh')
        result.update(spec=dict(table=spec.table,columnCount=len(spec.columns),objectType=spec.object_type),artifactRefs=refs)
        if action=='graph':result.update(outcome='SIGNED_PRODUCT_GRAPH_PREPARED',graph=graph);return result
        graphrow=conn.execute('SELECT payload,revision FROM phase5_pipeline_graph WHERE org_id=%s AND project_id=%s AND pipeline_id=%s',(*scope.key,PIPELINE)).fetchone()
        if not graphrow:raise ValueError('formal Product graph not registered')
        source=SourceConfigurationRevisionStore(HostTransaction(conn),scope).read_current('niushop-qyh')
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        body=dict(orgId=scope.org_id,projectId=scope.project_id,pipelineId=PIPELINE,graphRevision=graphrow['revision'],
            graphHash=_digest(graphrow['payload']),installationRef=current_ref,generation=str(binding['generation']),
            executionEpoch=binding['execution_epoch'],configurationRef=binding['config_ref'],
            packageRef=dict(publisher=selected.publisher,id=selected.id,version=selected.version,contentHash=selected.content_hash),
            sourceId='niushop-qyh',sourceConfigurationRef=source.ref.model_dump(mode='json',by_alias=True),
            rowLimit=1000,timeoutSeconds=30,maxSourceCalls=1,notBefore=now,expiresAt=now+timedelta(minutes=15),**refs)
        draft=PipelineSourceSelectionDraft.model_validate(body)
        service.selections._guarded(conn,draft,ACTOR,lambda value:True,snapshot=True)
        runtime_binding={**dict(binding),'generation':str(binding['generation'])}
        result.update(outcome='PRODUCT_CURRENT_PREFLIGHT_GREEN',checkedActor=ACTOR,
            currentInstallationRef=current_ref,runtimeBinding=runtime_binding,
            draft=draft.model_dump(mode='json',by_alias=True))
    return result


if __name__=='__main__':
    os.environ['AOS_DOTENV_DISABLED']='1';sys.path.insert(0,str(ROOT/'services/aos-api'))
    parser=argparse.ArgumentParser();parser.add_argument('--action',choices=('graph','preflight'),required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('immutable output exists')
    result=run(args.action);args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('draft','graph')},ensure_ascii=False))
