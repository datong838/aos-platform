"""Prepare explicit source policies and three minimal snapshots; no source access."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_customer_candidate import ROOT,builder,evaluate_shop,evaluate_product,evaluate_sku,evaluate_category,evaluate_order,evaluate_orderline,evaluate_shipment,evaluate_customer

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.11.0')
TARGET=Path('platform.ecommerce.niushop/1.12.0')
BASE_HASH='sha256:f2bc7069f564af79dbef3feb14da9ba64a7b6fd767cef4a2879421caf71cb7f5'
SCHEMA=Path('content/schemas/niushop-schema-fingerprint.json')
MASKING=Path('content/mappings/_pii-exclusion.yaml')
MAPPINGS=tuple(Path('content/mappings')/name for name in ('p09-weapp.yaml','p10-system-config.yaml','p11-product-review.yaml'))
OBSERVATION=ROOT/'.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/full-store-source-structure-20260914.json'
OBSERVATION_HASH='6ef53e8f516137f95907c66caa919ed34190ef32606ef12af71f556fa7db2ca0'
BLOCKED={
    'ns_weapp':['appsecret','token','encodingaeskey'],
    'ns_config':['value','config_desc'],
    'ns_goods_evaluate':['member_name','member_headimg','content','images','videos','explain_first','again_content','again_images','again_explain'],
    'ns_pay':['pay_body','pay_detail','pay_addon','pay_voucher','pay_json','mch_info','return_url','event','mch_id','trade_no','pay_no'],
}


def extended_policy(schema,masking):
    raw=OBSERVATION.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=OBSERVATION_HASH:raise ValueError('source observation differs')
    observed=json.loads(raw)
    result,policy=deepcopy(schema),deepcopy(masking)
    if result.get('tableCount')!=8 or len(result.get('tables',[]))!=8:raise ValueError('schema predecessor differs')
    names={t['name'] for t in result['tables']}
    for t in observed['tables']:
        if t['pipelineId'] not in ('P09','P10','P11','P12'):continue
        if t['table'] in names or t['table'] in policy['tables']:raise ValueError('source policy already declared')
        result['tables'].append(dict(name=t['table'],pipelineId=t['pipelineId'],targetOt=t['objectType'],primaryKey=t['primaryKey'],
            rowCount=t['rowCount'],columns=t['columns'],observationRef='sha256:'+OBSERVATION_HASH,observedAt=observed['observedAt']))
        policy['tables'][t['table']]=dict(pii_direct=BLOCKED[t['table']],pii_quasi=[])
    if len(result['tables'])!=12:raise ValueError('source observation incomplete')
    result['tableCount']=12
    result['extensionObservation']={'sha256':OBSERVATION_HASH,'observedAt':observed['observedAt'],'scope':'P09-P12 metadata only; earlier entries retain historical provenance'}
    return result,policy


def extended_mapping(original):
    value=deepcopy(original);table=value['source_table'];kind=value['target_ot']
    specs={
        'ns_weapp':('P09','Weapp','weapp_id',{'weapp_id','site_id','weapp_name','appid','status'},'status',{'status':'sourceStatus'}),
        'ns_config':('P10','SystemConfig','id',{'id','site_id','weapp_id','app_module','config_key','is_use'},'is_use',{'app_module':'module','config_key':'key'}),
        'ns_goods_evaluate':('P11','ProductReview','evaluate_id',{'evaluate_id','site_id','order_id','order_goods_id','goods_id','sku_id','member_id','scores','is_show','is_audit','create_time'},'is_show',{'goods_id':'productId','scores':'score'}),
    }
    pipeline,ot,pk,selected,state,renames=specs[table]
    if (value['pipeline_id'],kind,value['primary_key'])!=(pipeline,ot,pk):raise ValueError('source mapping predecessor differs')
    value.pop('incremental_cursor');value['incremental_strategy']='snapshot'
    value['field_mappings']=[f for f in value['field_mappings'] if f['source'] in selected]
    if {f['source'] for f in value['field_mappings']}!=selected:raise ValueError('selected source field missing')
    for field in value['field_mappings']:
        if field['source'] in renames:field['target']=renames[field['source']]
    value['pii_exclusion']=sorted(set(value['pii_exclusion'])|set(BLOCKED[table]))
    value['validation']['required']=list(dict.fromkeys([pk,'site_id']+value['validation']['required']))
    value['snapshot_materialization']=dict(schema_version='aos.snapshot-materialization/v3',platform='niushop',shop_key='site_id',
        source_timezone='+08:00',property_defaults={},time_basis='observation',deletion_basis='row-presence-only',
        status={'field':state,'property_target':'status','values':{'1':'ACTIVE'} if table=='ns_weapp' else {'0':'INACTIVE','1':'ACTIVE'}})
    value['notes']=[
        'Explicit minimal snapshot with observation provenance; no source modification time claim.',
        'Configuration values, customer free text/media and secrets are excluded before source read.',
        'Configuration inventory is not configuration-value interpretation; review scores are not review-text diagnosis.',
        'Relationships and downstream data quality/Fulfillment remain pending.',
    ]
    return value


def evaluate_extended(mapping,schema,masking):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    spec=derive_mapping_read_spec(mapping,schema,masking);plan=compile_snapshot_mapping(mapping,spec)
    at=datetime(2026,9,14,tzinfo=timezone.utc)
    raw={f['source']:(1 if f['type']=='int' else int(at.timestamp())-3600 if f['type']=='timestamp' else 'synthetic') for f in mapping['field_mappings']}
    if 'scores' in raw:raw['scores']=5
    scope=SyncScope(org_id='org-org',workspace_id='dev-project',platform='niushop',shop_or_marketplace_id='1',stream=mapping['pipeline_id']+'-qyh')
    objects,links=_normalize_rows(materialize_snapshot([raw],plan,observed_at=at),scope)
    if len(objects)!=1 or links or objects[0].object_type!=spec.object_type:raise ValueError('canonical object evaluation failed')
    if set(spec.columns)&set(BLOCKED[spec.table]):raise ValueError('prohibited field selected')
    checks=['canonical-object','explicit-observation','source-exclusions']
    cases=[('wrong-shop',raw|{'site_id':2}),('unknown-state',raw|{plan.status_field:99})]
    cases.extend((field,raw|{field:'synthetic'}) for field in BLOCKED[spec.table])
    for name,bad in cases:
        try:materialize_snapshot([bad],plan,observed_at=at)
        except ValueError:checks.append(name+'-rejected')
        else:raise ValueError('negative evaluation failed')
    return dict(status='passed',failed=0,scope='synthetic-minimal-object-only',columnCount=len(spec.columns),checks=checks,relationshipMaterialized=False)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    schema,masking=extended_policy(json.loads((source/SCHEMA).read_text()),yaml.safe_load((source/MASKING).read_text()))
    mappings={path:extended_mapping(yaml.safe_load((source/path).read_text())) for path in MAPPINGS}
    for value in mappings.values():evaluate_extended(value,schema,masking)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json';evidence.write_text(json.dumps({'status':'pending'})+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.11.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.12.0\n',1))
    (target/SCHEMA).write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n')
    (target/MASKING).write_text(yaml.safe_dump(masking,allow_unicode=True,sort_keys=False))
    for path,value in mappings.items():(target/path).write_text(yaml.safe_dump(value,allow_unicode=True,sort_keys=False))
    evaluation=dict(status='passed',failed=0,scope='static-eleven-object-snapshots-only',paymentSnapshotComplete=False,shop=evaluate_shop(target))
    for name,filename,fn in [('product','p02-product.yaml',evaluate_product),('sku','p03-product-sku.yaml',evaluate_sku),
        ('category','p04-category.yaml',evaluate_category),('order','p05-order.yaml',evaluate_order),('orderline','p06-order-line.yaml',evaluate_orderline),
        ('shipment','p07-shipment.yaml',evaluate_shipment),('customer','p08-customer-lite.yaml',evaluate_customer)]:
        evaluation[name]=fn(yaml.safe_load((target/'content/mappings'/filename).read_text()),target)
    for path in MAPPINGS:evaluation[path.stem]=evaluate_extended(yaml.safe_load((target/path).read_text()),schema,masking)
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed during preparation')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    expected=sorted(['bundle.yaml',str(SCHEMA),str(MASKING),'evidence/bundle-evals.json']+[str(p) for p in MAPPINGS])
    if changed!=expected:raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_EXTENDED_SNAPSHOT_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,targetTreeHash=helper._tree_hash(target),changedFiles=changed,evaluation=evaluation,published=False,installed=False)


if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
