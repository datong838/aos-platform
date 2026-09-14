"""Prepare a complete-state Order snapshot successor, without source access or publication."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_category_candidate import ROOT,builder,evaluate_shop,evaluate_product,evaluate_sku,evaluate_category

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.7.0')
TARGET=Path('platform.ecommerce.niushop/1.8.0')
BASE_HASH='sha256:5641f4890a2198fd92d6eefc4e68400d90ce7030c8e8e8059a657c09de4ba069'
MAPPING=Path('content/mappings/p05-order.yaml')


def order_mapping(original):
    value=deepcopy(original)
    if (value.get('pipeline_id'),value.get('source_table'),value.get('target_ot'),value.get('primary_key'))!=('P05','ns_order','Order','order_id'):
        raise ValueError('exact Order mapping predecessor required')
    if value.get('validation')!={'non_negative':['goods_money','delivery_money','order_money','pay_money']}:
        raise ValueError('Order validation predecessor drifted')
    if value.get('links')!=[{'name':'placedByLite','from':'Order','to':'CustomerLite','source_field':'member_id'}]:
        raise ValueError('Order relationship predecessor drifted')
    for key in ('links','incremental_cursor','soft_delete'):value.pop(key)
    value['site_filter']='site_id=1';value['incremental_strategy']='snapshot'
    value['validation']['required']=['order_id','site_id','create_time']
    value['field_mappings']=[f for f in value['field_mappings'] if f['source']!='name']
    targets={'site_id':'shopId','order_money':'totalAmount','create_time':'createdAt'}
    for field in value['field_mappings']:
        if field['source'] in targets:field['target']=targets[field['source']]
    if 'name' not in value['pii_exclusion']:value['pii_exclusion'].append('name')
    value['snapshot_materialization']=dict(schema_version='aos.snapshot-materialization/v3',platform='niushop',
        shop_key='site_id',source_timezone='+08:00',property_defaults={'currency':'CNY'},time_basis='observation',
        deletion_basis={'field':'is_delete','live_value':0,'deleted_value':1},
        status=dict(field='is_delete',property_target='status',values={'0':'ACTIVE','1':'ACTIVE'}))
    value['notes']=[
        'Full-site Order object snapshot preserves closed/refunded states and explicit source tombstones.',
        'Record status derives from is_delete; order_status and payment/delivery/refund states remain separate source fields.',
        'createdAt is source create_time; updatedAt is explicitly an observation version, not a source modification timestamp.',
        'Receiver name is not required by the business portrait and is excluded with contact/address fields.',
        'placedByLite relationship materialization remains pending; memberId is retained as the source association key.',
    ]
    return value


def evaluate_order(mapping,root):
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
        else int(at.timestamp())-3600 if f['type']=='timestamp' else 'synthetic') for f in mapping['field_mappings']}
    raw.update(order_id=101,site_id=1,order_status=-1,is_delete=0)
    output=materialize_snapshot([raw],plan,observed_at=at)
    objects,links=_normalize_rows(output,SyncScope(org_id='org-org',workspace_id='dev-project',
        platform='niushop',shop_or_marketplace_id='1',stream='P05-order-qyh'))
    if (len(objects)!=1 or links or objects[0].properties['orderStatus']!=-1
            or objects[0].properties['totalAmount']!='19.90' or objects[0].properties['status']!='ACTIVE'
            or objects[0].properties['sourceModificationTimeKnown'] is not False):
        raise ValueError('Order canonical evaluation failed')
    later=materialize_snapshot([raw],plan,observed_at=at+timedelta(hours=1))[0]
    if later['properties']['createdAt']!=output[0]['properties']['createdAt']:
        raise ValueError('observation fabricated Order creation time')
    deleted=materialize_snapshot([raw|{'is_delete':1}],plan,observed_at=at)[0]
    if deleted['is_deleted'] is not True or deleted['status_raw']!='DELETED':raise ValueError('Order delete evaluation failed')
    checks=['canonical-order-object','closed-order-retained','source-created-time-preserved','explicit-tombstone','observation-time-marked']
    for name,bad in [('negative-money',raw|{'order_money':Decimal('-1')}),('wrong-shop',raw|{'site_id':2}),
        ('unknown-delete',raw|{'is_delete':2}),('receiver-name',raw|{'name':'synthetic'}),('contact',raw|{'mobile':'synthetic'})]:
        try:materialize_snapshot([bad],plan,observed_at=at)
        except ValueError:checks.append(name+'-rejected')
        else:raise ValueError('Order negative evaluation failed')
    return dict(status='passed',failed=0,scope='synthetic-order-object-snapshot-only',relationshipMaterialized=False,
                columnCount=len(spec.columns),checks=checks)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    mapping=order_mapping(yaml.safe_load((source/MAPPING).read_text()))
    evaluate_order(mapping,source)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json'
    evidence.write_text(json.dumps(dict(status='pending',failed=0,scope='static-order-snapshot-only'))+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.7.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.8.0\n',1))
    (target/MAPPING).write_text(yaml.safe_dump(mapping,allow_unicode=True,sort_keys=False))
    evaluation=dict(status='passed',failed=0,scope='static-five-object-snapshots-only',
        shop=evaluate_shop(target),product=evaluate_product(yaml.safe_load((target/'content/mappings/p02-product.yaml').read_text()),target),
        sku=evaluate_sku(yaml.safe_load((target/'content/mappings/p03-product-sku.yaml').read_text()),target),
        category=evaluate_category(yaml.safe_load((target/'content/mappings/p04-category.yaml').read_text()),target),
        order=evaluate_order(yaml.safe_load((target/MAPPING).read_text()),target),
        mappingHash='sha256:'+hashlib.sha256((target/MAPPING).read_bytes()).hexdigest())
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed during preparation')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    if changed!=['bundle.yaml',str(MAPPING),'evidence/bundle-evals.json']:raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_ORDER_SNAPSHOT_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,
        targetTreeHash=helper._tree_hash(target),changedFiles=changed,evaluation=evaluation,published=False,installed=False)


if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
