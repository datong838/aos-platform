"""Prepare an immutable SKU snapshot successor; no source access or publication."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
import yaml

from prepare_niushop_product_candidate import ROOT, builder, evaluate_shop, evaluate_product

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.5.0')
TARGET=Path('platform.ecommerce.niushop/1.6.0')
BASE_HASH='sha256:e25d7e781db3b03b72cf8443167d9536b2b1e9aad01aa385e4cd96d0ad4edfec'
MAPPING=Path('content/mappings/p03-product-sku.yaml')


def sku_mapping(original):
    value=deepcopy(original)
    if (value.get('pipeline_id'),value.get('source_table'),value.get('target_ot'),value.get('primary_key'))!=('P03','ns_goods_sku','ProductSku','sku_id'):
        raise ValueError('exact SKU mapping predecessor required')
    if value.get('validation')!={'non_negative':['price','market_price','cost_price','stock']}:
        raise ValueError('SKU validation predecessor drifted')
    if value.get('links')!=[{'name':'hasSku','from':'Product','to':'ProductSku','source_field':'goods_id'}]:
        raise ValueError('SKU relationship predecessor drifted')
    value['site_filter']='site_id=1'
    value['incremental_strategy']='snapshot'
    for name in ('incremental_cursor','soft_delete','links'):value.pop(name)
    value['validation']['required']=['sku_id','site_id','goods_id','sku_name','create_time']
    for field in value['field_mappings']:
        if field['source']=='sku_no':field['target']='barcode'
    value['snapshot_materialization']=dict(schema_version='aos.snapshot-materialization/v2',platform='niushop',
        shop_key='site_id',source_timezone='+08:00',property_defaults={'currency':'CNY'},
        source_updated_at={'primary':'modify_time','fallback':'create_time'},
        tombstone={'field':'is_delete','live_value':0,'deleted_value':1},
        status={'field':'goods_state','property_target':'status','values':{'0':'INACTIVE','1':'ACTIVE'}})
    value['notes']=[
        'Full-site SKU object snapshot, including off-shelf and explicitly deleted rows.',
        'Retains goods_id as productId; hasSku relation materialization and orphan checks remain pending.',
        'No claim that redundant SKU goods_state matches the parent Product state.',
        'Physical absence is not deletion; source timestamps never advance just because observation repeats.',
    ]
    return value


def evaluate_sku(mapping,root):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    schema=json.loads((root/'content/schemas/niushop-schema-fingerprint.json').read_text())
    masking=yaml.safe_load((root/'content/mappings/_pii-exclusion.yaml').read_text())
    spec=derive_mapping_read_spec(mapping,schema,masking)
    plan=compile_snapshot_mapping(mapping,spec)
    at=datetime(2026,9,14,tzinfo=timezone.utc)
    raw={f['source']:(1 if f['type']=='int' else Decimal('19.90') if f['type']=='decimal'
        else int(at.timestamp())-60 if f['type']=='timestamp' else 'synthetic') for f in mapping['field_mappings']}
    raw.update(sku_id=101,goods_id=201,site_id=1,goods_state=1,is_delete=0)
    output=materialize_snapshot([raw],plan,observed_at=at)
    scope=SyncScope(org_id='org-org',workspace_id='dev-project',platform=plan.platform,
                   shop_or_marketplace_id=plan.shop_id,stream='P03-product-sku-qyh')
    objects,links=_normalize_rows(output,scope)
    if (len(objects)!=1 or links or objects[0].properties['productId']!=201
            or objects[0].properties['barcode']!=raw['sku_no']
            or objects[0].properties['status']!='ACTIVE' or objects[0].properties['price']!='19.90'):
        raise ValueError('SKU canonical evaluation failed')
    if materialize_snapshot([raw],plan,observed_at=at+timedelta(hours=1))!=output:
        raise ValueError('observation fabricated SKU source change')
    for changes,deleted,status in [({'goods_state':0},False,'INACTIVE'),({'is_delete':1},True,'DELETED')]:
        item=materialize_snapshot([raw|changes],plan,observed_at=at)[0]
        if item['is_deleted']!=deleted or item['status_raw']!=status:raise ValueError('SKU state evaluation failed')
    checks=['canonical-sku-object','parent-key-retained','stable-source-time','off-shelf-preserved','explicit-tombstone']
    for name,rows in [('negative-stock',[raw|{'stock':Decimal('-1')}]),('extra-column',[raw|{'private_extra':'synthetic'}]),
        ('wrong-shop',[raw|{'site_id':2}]),('duplicate-key',[raw,dict(raw)]),('unknown-state',[raw|{'goods_state':9}]),
        ('missing-time',[raw|{'create_time':0,'modify_time':0}])]:
        try:materialize_snapshot(rows,plan,observed_at=at)
        except ValueError:checks.append(name+'-rejected')
        else:raise ValueError('SKU negative evaluation failed')
    return dict(status='passed',failed=0,scope='synthetic-sku-object-snapshot-only',
                relationshipMaterialized=False,columnCount=len(spec.columns),checks=checks)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    mapping=sku_mapping(yaml.safe_load((source/MAPPING).read_text()))
    evaluate_sku(mapping,source)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json'
    evidence.write_text(json.dumps(dict(status='pending',failed=0,scope='static-sku-snapshot-only'))+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.5.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.6.0\n',1))
    (target/MAPPING).write_text(yaml.safe_dump(mapping,allow_unicode=True,sort_keys=False))
    evaluation=dict(status='passed',failed=0,scope='static-shop-product-sku-objects-only',
        shop=evaluate_shop(target),product=evaluate_product(yaml.safe_load((target/'content/mappings/p02-product.yaml').read_text()),target),
        sku=evaluate_sku(yaml.safe_load((target/MAPPING).read_text()),target),
        mappingHash='sha256:'+hashlib.sha256((target/MAPPING).read_bytes()).hexdigest())
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed during preparation')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    if changed!=['bundle.yaml',str(MAPPING),'evidence/bundle-evals.json']:raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_SKU_SNAPSHOT_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,
        targetTreeHash=helper._tree_hash(target),changedFiles=changed,evaluation=evaluation,published=False,installed=False)


if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
