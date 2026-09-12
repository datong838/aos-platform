"""Prepare an immutable Product snapshot successor; no source access or publish."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import yaml

from prepare_niushop_snapshot_candidate import builder, evaluate as evaluate_shop

ROOT=Path(__file__).resolve().parents[1]
os.environ['AOS_DOTENV_DISABLED']='1'
CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.4.0')
TARGET=Path('platform.ecommerce.niushop/1.5.0')
BASE_HASH='sha256:e819116f16f2c0e057fbbbbbcfba05e614ddafb2f312566c24dc07cb15244709'
MAPPING=Path('content/mappings/p02-product.yaml')


def product_mapping(original):
    value=deepcopy(original)
    if (value.get('pipeline_id'),value.get('source_table'),value.get('target_ot'),value.get('primary_key'))!=('P02','ns_goods','Product','goods_id'):
        raise ValueError('exact Product mapping predecessor required')
    if value.get('validation')!={'non_negative':['price','market_price','cost_price']}:
        raise ValueError('Product validation predecessor drifted')
    value['site_filter']='site_id=1'
    value['incremental_strategy']='snapshot'
    value.pop('incremental_cursor')
    value.pop('soft_delete')
    value['validation']['required']=['goods_id','site_id','goods_name','category_id','create_time']
    targets={'goods_name':'title','site_id':'shopId','create_time':'createdAt'}
    for field in value['field_mappings']:
        if field['source'] in targets:field['target']=targets[field['source']]
    value['snapshot_materialization']=dict(schema_version='aos.snapshot-materialization/v2',platform='niushop',
        shop_key='site_id',source_timezone='+08:00',property_defaults={'currency':'CNY'},
        source_updated_at={'primary':'modify_time','fallback':'create_time'},
        tombstone={'field':'is_delete','live_value':0,'deleted_value':1},
        status={'field':'goods_state','property_target':'status','values':{'0':'INACTIVE','1':'ACTIVE'}})
    value['notes']=[
        'Candidate full site Product snapshot, including off-shelf and explicit deleted rows.',
        'No row count or current business-state assertion is made by this declaration.',
        'Unknown state, missing valid source time, negative declared money or truncated snapshot fails closed.',
        'Physical absence does not imply deletion; only explicit is_delete yields a tombstone.',
    ]
    return value


def evaluate_product(mapping,root):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    schema=json.loads((root/'content/schemas/niushop-schema-fingerprint.json').read_text())
    masking=yaml.safe_load((root/'content/mappings/_pii-exclusion.yaml').read_text())
    spec=derive_mapping_read_spec(mapping,schema,masking)
    plan=compile_snapshot_mapping(mapping,spec)
    at=datetime(2026,9,13,tzinfo=timezone.utc)
    raw={field['source']:(1 if field['type']=='int' else Decimal('19.90') if field['type']=='decimal'
        else int(at.timestamp())-60 if field['type']=='timestamp' else 'synthetic') for field in mapping['field_mappings']}
    raw.update(goods_id=101,site_id=1,goods_state=1,is_delete=0,category_id='1')
    output=materialize_snapshot([raw],plan,observed_at=at)
    scope=SyncScope(org_id='org-org',workspace_id='dev-project',platform=plan.platform,shop_or_marketplace_id=plan.shop_id,stream='P02-product-qyh')
    objects,links=_normalize_rows(output,scope)
    if (len(objects)!=1 or links or objects[0].properties['title']!='synthetic'
            or objects[0].properties['status']!='ACTIVE' or objects[0].properties['price']!='19.90'):
        raise ValueError('Product canonical evaluation failed')
    if materialize_snapshot([raw],plan,observed_at=at+timedelta(hours=1))!=output:
        raise ValueError('observation time fabricated source change')
    for changes,deleted,status in [({'goods_state':0},False,'INACTIVE'),({'is_delete':1},True,'DELETED')]:
        item=materialize_snapshot([raw|changes],plan,observed_at=at)[0]
        if item['is_deleted']!=deleted or item['status_raw']!=status:raise ValueError('Product state evaluation failed')
    checks=['schema-privacy-and-v2-compile','canonical-product-properties','stable-source-time','off-shelf-preserved','explicit-tombstone']
    for name,rows in [('negative-money',[raw|{'price':Decimal('-0.01')}]),('extra-column',[raw|{'private_extra':'synthetic'}]),
        ('wrong-shop',[raw|{'site_id':2}]),('duplicate-key',[raw,dict(raw)]),('unknown-state',[raw|{'goods_state':9}])]:
        try:materialize_snapshot(rows,plan,observed_at=at)
        except ValueError:checks.append(name+'-rejected')
        else:raise ValueError('Product negative evaluation failed')
    return dict(status='passed',failed=0,scope='synthetic-product-snapshot-only',columnCount=len(spec.columns),checks=checks)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    mapping=product_mapping(yaml.safe_load((source/MAPPING).read_text()))
    evaluate_product(mapping,source)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json'
    evidence.write_text(json.dumps(dict(status='pending',failed=0,scope='static-product-snapshot-only'))+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.4.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.5.0\n',1))
    (target/MAPPING).write_text(yaml.safe_dump(mapping,allow_unicode=True,sort_keys=False))
    evaluation=dict(status='passed',failed=0,scope='static-shop-and-product-snapshot-only',
        shop=evaluate_shop(target),product=evaluate_product(yaml.safe_load((target/MAPPING).read_text()),target),
        mappingHash='sha256:'+hashlib.sha256((target/MAPPING).read_bytes()).hexdigest())
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed during preparation')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    if changed!=['bundle.yaml',str(MAPPING),'evidence/bundle-evals.json']:raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_PRODUCT_SNAPSHOT_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,
        targetTreeHash=helper._tree_hash(target),changedFiles=changed,evaluation=evaluation,published=False,installed=False)


if __name__=='__main__':
    print(json.dumps(prepare(),ensure_ascii=False,indent=2))
