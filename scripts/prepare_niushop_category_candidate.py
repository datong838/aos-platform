"""Prepare a Category observation/hierarchy successor without publishing or reading sources."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_sku_candidate import ROOT,builder,evaluate_shop,evaluate_product,evaluate_sku

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.6.0')
TARGET=Path('platform.ecommerce.niushop/1.7.0')
BASE_HASH='sha256:891b9312ecd040d19388e624fc40d636f08e2c567e56487650283a38aab6b0c6'
MAPPING=Path('content/mappings/p04-category.yaml')


def category_mapping(original):
    value=deepcopy(original)
    if (value.get('pipeline_id'),value.get('source_table'),value.get('target_ot'),value.get('primary_key'))!=('P04','ns_goods_category','Category','category_id'):
        raise ValueError('exact Category mapping predecessor required')
    if value.get('validation')!={'custom':'pid=0 为根；检测分类环与孤儿父级'}:
        raise ValueError('Category validation predecessor drifted')
    if value.get('links')!=[{'name':'inCategory','from':'Product','to':'Category','source_field':'category_id'}]:
        raise ValueError('Category relationship predecessor drifted')
    for key in ('links','incremental_cursor'):value.pop(key)
    value['validation']={'required':['category_id','site_id','category_name'],
                         'hierarchy':{'parent_field':'pid','root_value':0}}
    for field in value['field_mappings']:
        if field['source']=='pid':field['target']='parentCategoryId'
    value['snapshot_materialization']=dict(schema_version='aos.snapshot-materialization/v3',platform='niushop',
        shop_key='site_id',source_timezone='+08:00',property_defaults={},time_basis='observation',
        deletion_basis='row-presence-only',status=dict(field='is_show',property_target='status',values={'0':'INACTIVE','1':'ACTIVE'}))
    value['notes']=[
        'Category has no source modification timestamp; explicit observation metadata is not historical source time.',
        'Complete snapshot hierarchy rejects missing parents and cycles; physical absence is never a delete instruction.',
        'Product.inCategory relationship materialization remains pending; category source fields are retained.',
        'Unknown visibility states fail closed. No current source population claim is made.',
    ]
    return value


def evaluate_category(mapping,root):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    schema=json.loads((root/'content/schemas/niushop-schema-fingerprint.json').read_text())
    masking=yaml.safe_load((root/'content/mappings/_pii-exclusion.yaml').read_text())
    spec=derive_mapping_read_spec(mapping,schema,masking);plan=compile_snapshot_mapping(mapping,spec)
    at=datetime(2026,9,14,tzinfo=timezone.utc)
    raw={f['source']:(1 if f['type']=='int' else 'synthetic') for f in mapping['field_mappings']}
    rows=[raw|{'category_id':2,'pid':1},raw|{'category_id':1,'pid':0}]
    output=materialize_snapshot(rows,plan,observed_at=at)
    objects,links=_normalize_rows(output,SyncScope(org_id='org-org',workspace_id='dev-project',
        platform='niushop',shop_or_marketplace_id='1',stream='P04-category-qyh'))
    if (len(objects)!=2 or links or objects[0].properties['parentCategoryId']!=1
            or objects[0].properties['sourceModificationTimeKnown'] is not False
            or objects[0].properties['sourceUpdatedAtBasis']!='observation'):
        raise ValueError('Category canonical evaluation failed')
    checks=['canonical-category-object','explicit-observation-time','shuffled-complete-hierarchy']
    for name,bad in [('orphan',[raw|{'category_id':1,'pid':9}]),('cycle',[raw|{'category_id':1,'pid':1}]),
        ('wrong-shop',[raw|{'site_id':2,'pid':0}]),('unknown-state',[raw|{'is_show':9,'pid':0}])]:
        try:materialize_snapshot(bad,plan,observed_at=at)
        except ValueError:checks.append(name+'-rejected')
        else:raise ValueError('Category negative evaluation failed')
    return dict(status='passed',failed=0,scope='synthetic-category-object-snapshot-only',
                relationshipMaterialized=False,columnCount=len(spec.columns),checks=checks)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    mapping=category_mapping(yaml.safe_load((source/MAPPING).read_text()))
    evaluate_category(mapping,source)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json'
    evidence.write_text(json.dumps(dict(status='pending',failed=0,scope='static-category-snapshot-only'))+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.6.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.7.0\n',1))
    (target/MAPPING).write_text(yaml.safe_dump(mapping,allow_unicode=True,sort_keys=False))
    evaluation=dict(status='passed',failed=0,scope='static-shop-product-sku-category-objects-only',
        shop=evaluate_shop(target),product=evaluate_product(yaml.safe_load((target/'content/mappings/p02-product.yaml').read_text()),target),
        sku=evaluate_sku(yaml.safe_load((target/'content/mappings/p03-product-sku.yaml').read_text()),target),
        category=evaluate_category(yaml.safe_load((target/MAPPING).read_text()),target),
        mappingHash='sha256:'+hashlib.sha256((target/MAPPING).read_bytes()).hexdigest())
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed during preparation')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    if changed!=['bundle.yaml',str(MAPPING),'evidence/bundle-evals.json']:raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_CATEGORY_SNAPSHOT_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,
        targetTreeHash=helper._tree_hash(target),changedFiles=changed,evaluation=evaluation,published=False,installed=False)


if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
