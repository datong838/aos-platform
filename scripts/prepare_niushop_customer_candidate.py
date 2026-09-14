"""Prepare a privacy-minimized CustomerLite snapshot successor, without source access or publication."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_shipment_candidate import ROOT,builder,evaluate_shop,evaluate_product,evaluate_sku,evaluate_category,evaluate_order,evaluate_orderline,evaluate_shipment

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.10.0')
TARGET=Path('platform.ecommerce.niushop/1.11.0')
BASE_HASH='sha256:d17d81fefde3e8159c1c18b8a361f6bdac128350c1623b9181540d06d57558cb'
MAPPING=Path('content/mappings/p08-customer-lite.yaml')


def customer_mapping(original):
    value=deepcopy(original)
    if (value.get('pipeline_id'),value.get('source_table'),value.get('target_ot'),value.get('primary_key'))!=('P08','ns_member','CustomerLite','member_id'):
        raise ValueError('exact CustomerLite mapping predecessor required')
    if value.get('customer_lite_schema_version')!=2:raise ValueError('CustomerLite public version drifted')
    for name in ('links','incremental_cursor','derived_metrics'):value.pop(name)
    value['incremental_strategy']='snapshot'
    value['validation']={'required':['member_id','site_id','reg_time','status','is_delete']}
    value['field_mappings']=[{'source':source,'target':target,'type':kind} for source,target,kind in [
        ('member_id','id','int'),('member_level','memberLevel','int'),('reg_time','createdAt','timestamp'),
        ('status','sourceStatus','int'),('site_id','siteId','int'),('is_delete','isDelete','int')]]
    if not {f['source'] for f in value['field_mappings']}<=set(value['public_source_allowlist']):
        raise ValueError('CustomerLite source allowlist drifted')
    value['snapshot_materialization']=dict(schema_version='aos.snapshot-materialization/v3',platform='niushop',
        shop_key='site_id',source_timezone='+08:00',time_basis='observation',
        deletion_basis={'field':'is_delete','live_value':0,'deleted_value':1},property_defaults={},
        status=dict(field='status',property_target='status',values={'1':'ACTIVE'}),
        public_projection={'schema_version':2,'properties':['memberLevel','status','createdAt']})
    value['notes']=[
        'Public schema v2 business properties plus mandatory explicit observation provenance only.',
        'Only currently verified source status 1 is accepted; unknown account states require an explicit successor policy.',
        'Registration time is actual reg_time; no inferred creation or modification time.',
        'Source selected columns remain within the existing CustomerLite allowlist; identity resolver is not invoked.',
        'Order relationship and order_count/last_order_days derived receipts remain pending.',
    ]
    return value


def evaluate_customer(mapping,root):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    from aos_api.ec_source_adapter import _PUBLIC_FIELDS_BY_TABLE
    schema=json.loads((root/'content/schemas/niushop-schema-fingerprint.json').read_text())
    masking=yaml.safe_load((root/'content/mappings/_pii-exclusion.yaml').read_text())
    spec=derive_mapping_read_spec(mapping,schema,masking);plan=compile_snapshot_mapping(mapping,spec)
    if not set(spec.columns)<=_PUBLIC_FIELDS_BY_TABLE['ns_member']:raise ValueError('CustomerLite public source mismatch')
    at=datetime(2026,9,14,tzinfo=timezone.utc)
    raw=dict(member_id=101,member_level=1,reg_time=int(at.timestamp())-3600,status=1,site_id=1,is_delete=0)
    scope=SyncScope(org_id='org-org',workspace_id='dev-project',platform='niushop',shop_or_marketplace_id='1',stream='P08-customer-lite-qyh')
    output=materialize_snapshot([raw],plan,observed_at=at)
    objects,links=_normalize_rows(output,scope);props=objects[0].properties
    allowed={'memberLevel','status','createdAt','updatedAt','observedAt','sourceUpdatedAtBasis','sourceModificationTimeKnown',
        'createdAtSourceTimezone','updatedAtSourceTimezone','observedAtSourceTimezone'}
    if (len(objects)!=1 or links or objects[0].schema_version!=2 or set(props)!=allowed
            or props['sourceModificationTimeKnown'] is not False):raise ValueError('CustomerLite public evaluation failed')
    later=materialize_snapshot([raw],plan,observed_at=at+timedelta(hours=1))[0]
    if later['properties']['createdAt']!=output[0]['properties']['createdAt']:raise ValueError('fabricated registration time')
    deleted=materialize_snapshot([raw|{'is_delete':1}],plan,observed_at=at)[0]
    if not deleted['is_deleted'] or deleted['properties']['status']!='DELETED':raise ValueError('CustomerLite delete failed')
    checks=['canonical-customer-v2','minimal-public-properties','registration-time-preserved','explicit-delete','source-allowlist']
    for name,bad in [('wrong-shop',raw|{'site_id':2}),('unknown-status',raw|{'status':99}),('unknown-delete',raw|{'is_delete':2}),
        ('mobile',raw|{'mobile':'synthetic'}),('openid',raw|{'weapp_openid':'synthetic'}),('zero-registration',raw|{'reg_time':0})]:
        try:_normalize_rows(materialize_snapshot([bad],plan,observed_at=at),scope)
        except ValueError:checks.append(name+'-rejected')
        else:raise ValueError('CustomerLite negative evaluation failed: '+name)
    return dict(status='passed',failed=0,scope='synthetic-customer-object-snapshot-only',relationshipMaterialized=False,
        publicSchemaVersion=2,columnCount=len(spec.columns),checks=checks)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    mapping=customer_mapping(yaml.safe_load((source/MAPPING).read_text()))
    evaluate_customer(mapping,source)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json'
    evidence.write_text(json.dumps(dict(status='pending',failed=0,scope='static-customer-snapshot-only'))+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.10.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.11.0\n',1))
    (target/MAPPING).write_text(yaml.safe_dump(mapping,allow_unicode=True,sort_keys=False))
    evaluation=dict(status='passed',failed=0,scope='static-eight-object-snapshots-only',
        shop=evaluate_shop(target),product=evaluate_product(yaml.safe_load((target/'content/mappings/p02-product.yaml').read_text()),target),
        sku=evaluate_sku(yaml.safe_load((target/'content/mappings/p03-product-sku.yaml').read_text()),target),
        category=evaluate_category(yaml.safe_load((target/'content/mappings/p04-category.yaml').read_text()),target),
        order=evaluate_order(yaml.safe_load((target/'content/mappings/p05-order.yaml').read_text()),target),
        orderline=evaluate_orderline(yaml.safe_load((target/'content/mappings/p06-order-line.yaml').read_text()),target),
        shipment=evaluate_shipment(yaml.safe_load((target/'content/mappings/p07-shipment.yaml').read_text()),target),
        customer=evaluate_customer(yaml.safe_load((target/MAPPING).read_text()),target),
        mappingHash='sha256:'+hashlib.sha256((target/MAPPING).read_bytes()).hexdigest())
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed during preparation')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    if changed!=['bundle.yaml',str(MAPPING),'evidence/bundle-evals.json']:raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_CUSTOMER_SNAPSHOT_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,
        targetTreeHash=helper._tree_hash(target),changedFiles=changed,evaluation=evaluation,published=False,installed=False)


if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
