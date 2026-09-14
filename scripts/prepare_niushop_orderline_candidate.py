"""Prepare a complete-state OrderLine snapshot successor, without source access or publication."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_order_candidate import ROOT,builder,evaluate_shop,evaluate_product,evaluate_sku,evaluate_category,evaluate_order

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.8.0')
TARGET=Path('platform.ecommerce.niushop/1.9.0')
BASE_HASH='sha256:d0f2a557e0749a4bc753e18954a2dce368f632d7be8bd3247cece69d04e0c575'
MAPPING=Path('content/mappings/p06-order-line.yaml')


def orderline_mapping(original):
    value=deepcopy(original)
    if (value.get('pipeline_id'),value.get('source_table'),value.get('target_ot'),value.get('primary_key'))!=('P06','ns_order_goods','OrderLine','order_goods_id'):
        raise ValueError('exact OrderLine mapping predecessor required')
    if value.get('validation')!={'non_negative':['num','goods_money','cost_money'],'enum':{'refund_status':[-3,0,3]}}:
        raise ValueError('OrderLine validation predecessor drifted')
    expected=[{'name':'contains','from':'Order','to':'OrderLine','source_field':'order_id'},
        {'name':'forProduct','from':'OrderLine','to':'Product','source_field':'goods_id'},
        {'name':'forSku','from':'OrderLine','to':'ProductSku','source_field':'sku_id'}]
    if value.get('links')!=expected:raise ValueError('OrderLine relationships predecessor drifted')
    value.pop('links');value.pop('incremental_cursor')
    value['validation'].pop('enum')
    value['validation']['required']=['order_goods_id','order_id','site_id','sku_id']
    targets={'price':'unitPrice','goods_money':'lineAmount'}
    for field in value['field_mappings']:
        if field['source'] in targets:field['target']=targets[field['source']]
    value['snapshot_materialization']=dict(schema_version='aos.snapshot-materialization/v3',platform='niushop',
        shop_key='site_id',source_timezone='+08:00',property_defaults={'currency':'CNY'},time_basis='observation',
        deletion_basis='row-presence-only',status=dict(field='refund_status',property_target='status',
            values={'-3':'ACTIVE','0':'ACTIVE','3':'ACTIVE'}))
    value['notes']=[
        'Complete-site OrderLine observation snapshot; source zero creation/refund timestamps remain unknown.',
        'Business windows require verified parent Order creation time through actual relationship materialization.',
        'lineAmount is declared source goods_money, not an inferred net revenue or paid amount.',
        'Refund states are preserved independently from record presence; absence does not imply deletion.',
        'Order/Product/SKU relationships and parent deletion semantics remain pending.',
    ]
    return value


def evaluate_orderline(mapping,root):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    schema=json.loads((root/'content/schemas/niushop-schema-fingerprint.json').read_text())
    masking=yaml.safe_load((root/'content/mappings/_pii-exclusion.yaml').read_text())
    spec=derive_mapping_read_spec(mapping,schema,masking);plan=compile_snapshot_mapping(mapping,spec)
    at=datetime(2026,9,14,tzinfo=timezone.utc)
    raw={f['source']:(1 if f['type']=='int' else Decimal('19.90') if f['type']=='decimal'
        else 0 if f['type']=='timestamp' else 'synthetic') for f in mapping['field_mappings']}
    raw.update(order_goods_id=101,site_id=1,refund_status=0)
    scope=SyncScope(org_id='org-org',workspace_id='dev-project',platform='niushop',shop_or_marketplace_id='1',stream='P06-order-line-qyh')
    for refund in (-3,0,3):
        output=materialize_snapshot([raw|{'refund_status':refund}],plan,observed_at=at)
        objects,links=_normalize_rows(output,scope)
        props=objects[0].properties
        if (len(objects)!=1 or links or props['lineAmount']!='19.90' or props['unitPrice']!='19.90'
                or props.get('createTime') is not None or props.get('refundActionTime') is not None
                or 'createdAt' in props or props['sourceModificationTimeKnown'] is not False
                or props['refundStatus']!=refund):raise ValueError('OrderLine canonical evaluation failed')
    later=materialize_snapshot([raw],plan,observed_at=at+timedelta(hours=1))[0]
    if later['properties'].get('createTime') is not None:raise ValueError('fabricated OrderLine creation time')
    checks=['canonical-orderline-object','all-declared-refund-states','zero-source-time-unknown','observation-time-marked']
    for name,bad in [('negative-money',raw|{'goods_money':Decimal('-1')}),('wrong-shop',raw|{'site_id':2}),
        ('unknown-refund',raw|{'refund_status':99}),('refund-address',raw|{'refund_address':'synthetic'})]:
        try:materialize_snapshot([bad],plan,observed_at=at)
        except ValueError:checks.append(name+'-rejected')
        else:raise ValueError('OrderLine negative evaluation failed')
    return dict(status='passed',failed=0,scope='synthetic-orderline-object-snapshot-only',relationshipMaterialized=False,
        businessWindowResolved=False,columnCount=len(spec.columns),checks=checks)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    mapping=orderline_mapping(yaml.safe_load((source/MAPPING).read_text()))
    evaluate_orderline(mapping,source)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json'
    evidence.write_text(json.dumps(dict(status='pending',failed=0,scope='static-orderline-snapshot-only'))+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.8.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.9.0\n',1))
    (target/MAPPING).write_text(yaml.safe_dump(mapping,allow_unicode=True,sort_keys=False))
    evaluation=dict(status='passed',failed=0,scope='static-six-object-snapshots-only',
        shop=evaluate_shop(target),product=evaluate_product(yaml.safe_load((target/'content/mappings/p02-product.yaml').read_text()),target),
        sku=evaluate_sku(yaml.safe_load((target/'content/mappings/p03-product-sku.yaml').read_text()),target),
        category=evaluate_category(yaml.safe_load((target/'content/mappings/p04-category.yaml').read_text()),target),
        order=evaluate_order(yaml.safe_load((target/'content/mappings/p05-order.yaml').read_text()),target),
        orderline=evaluate_orderline(yaml.safe_load((target/MAPPING).read_text()),target),
        mappingHash='sha256:'+hashlib.sha256((target/MAPPING).read_bytes()).hexdigest())
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed during preparation')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    if changed!=['bundle.yaml',str(MAPPING),'evidence/bundle-evals.json']:raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_ORDERLINE_SNAPSHOT_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,
        targetTreeHash=helper._tree_hash(target),changedFiles=changed,evaluation=evaluation,published=False,installed=False)


if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
