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
BUNDLE_ROOT=ROOT.parent/'.aos-recovery-20260915/state/niushop-1.23-current-package/registry/signed-bundles-niushop-1.23-current'
TRUST_ROOTS=ROOT.parent/'.aos-recovery-20260910/state/a0v-canonical-ecommerce-first-install/signing/trust-roots.json'
CURRENT_CREATE=ROOT.parent/'.aos-recovery-20260915/state/current-ecommerce-package/install/e/create-result.json'
CUTOVER_RESUME=ROOT.parent/'.aos-recovery-20260915/state/niushop-1.23-current-package/business/p02-e-first-chain-r2/cutover-resume-result.json'
NIUSHOP_VERSION='1.23.0'
AUTHORITY_WINDOW_MINUTES=15


def require_cutover_resume(create_receipt,binding,result,row,*,expected_outcome="CURRENT_E_CUTOVER_RESUMED"):
    from aos_api.asset_registry.canonical_json import canonical_sha256
    receipt=result.get('receipt',{}) if type(result) is dict else {}
    authority=row.get('authority_data',{}) if type(row) is dict else {}
    if (result.get('outcome')!=expected_outcome
            or receipt.get('phase')!='resume' or receipt.get('status')!='resumed'
            or str(row.get('receipt_id'))!=receipt.get('receiptId')
            or row.get('content_hash')!=receipt.get('contentHash')
            or canonical_sha256(authority)!=row.get('content_hash')
            or row.get('status')!='resumed'
            or str(row.get('cutover_operation_id'))!=receipt.get('cutoverOperationId')
            or str(row.get('target_installation_id'))!=create_receipt.get('installationId')
            or str(row.get('target_generation'))!=str(binding.get('generation'))
            or row.get('target_execution_epoch')!=binding.get('execution_epoch')
            or row.get('target_runtime_revision')+2!=binding.get('revision')
            or authority.get('targetRuntimeRevision')!=binding.get('revision')
            or authority.get('status')!='resumed' or authority.get('claimPaused') is not False):
        raise ValueError('exact cutover resume Receipt required')
    return True


def require_current_head(create_receipt,head,binding,cutover_resumed=False):
    if (create_receipt.get('installationId')!=str(head.get('installation_id'))
            or create_receipt.get('installationState')!='approved'
            or head.get('state')!='active' or head.get('etag_version')!=5
            or head.get('overlay_revision')!='a0v-canonical-ecommerce-v1'):
        raise ValueError('exact current installation E required')
    if (binding.get('revision') not in ({4,6} if cutover_resumed else {4})
            or binding.get('revision')==6 and not cutover_resumed
            or binding.get('execution_epoch')!=3
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
        binding=bindings[0];binding_dict=dict(binding);cutover_resumed=False
        if binding_dict['revision']==6:
            if (not CUTOVER_RESUME.is_file() or CUTOVER_RESUME.stat().st_mode & 0o777 != 0o600):
                raise ValueError('private cutover resume result required')
            resume_result=json.loads(CUTOVER_RESUME.read_text(encoding='utf-8'))
            resume_receipt=resume_result.get('receipt',{})
            from aos_api.ecommerce_growth_registration_connection import registration_connection
            from aos_api.ecommerce_growth_cutover_connection import scoped_cutover_connection
            with scoped_cutover_connection(registration_connection)(scope) as control_conn:
                resume_row=control_conn.execute('''SELECT o.cutover_operation_id,o.status,o.target_installation_id,
                    o.target_generation,o.target_execution_epoch,o.target_runtime_revision,
                    r.receipt_id,r.content_hash,r.authority_data
                    FROM extension_dispatch_cutover_operation o
                    JOIN extension_dispatch_cutover_receipt r USING(org_id,project_id,cutover_operation_id)
                    WHERE o.org_id=%s AND o.project_id=%s AND r.phase='resume' AND r.receipt_id=%s''',
                    (*scope.key,resume_receipt.get('receiptId'))).fetchall()
            if len(resume_row)!=1:raise ValueError('one cutover resume Receipt required')
            cutover_resumed=require_cutover_resume(create_receipt,binding_dict,resume_result,dict(resume_row[0]))
        current_ref=require_current_head(create_receipt,dict(head),binding_dict,cutover_resumed)
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
            rowLimit=1000,timeoutSeconds=30,maxSourceCalls=1,notBefore=now,
            expiresAt=now+timedelta(minutes=AUTHORITY_WINDOW_MINUTES),**refs)
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
