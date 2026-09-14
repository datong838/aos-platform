"""Prepare a privacy-minimized Shipment snapshot successor, without source access or publication."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_orderline_candidate import ROOT,builder,evaluate_shop,evaluate_product,evaluate_sku,evaluate_category,evaluate_order,evaluate_orderline

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.9.0')
TARGET=Path('platform.ecommerce.niushop/1.10.0')
BASE_HASH='sha256:b52f6a76334528d7c8cde06e802252e6934dd4ead29c35219f976d3f55413e01'
MAPPING=Path('content/mappings/p07-shipment.yaml')


def shipment_mapping(original):
    value=deepcopy(original)
    if (value.get('pipeline_id'),value.get('source_table'),value.get('target_ot'),value.get('primary_key'))!=('P07','ns_express_delivery_package','Shipment','id'):
        raise ValueError('exact Shipment mapping predecessor required')
    if 'validation' in value:raise ValueError('Shipment validation predecessor drifted')
    if value.get('links')!=[{'name':'ships','from':'Shipment','to':'Order','source_field':'order_id'}]:
        raise ValueError('Shipment relationship predecessor drifted')
    value.pop('links');value.pop('incremental_cursor')
    value['validation']={'required':['id','site_id','order_id','delivery_time']}
    dropped={'delivery_no','member_name','trace'}
    value['field_mappings']=[f for f in value['field_mappings'] if f['source'] not in dropped]
    value['pii_exclusion']=sorted(set(value['pii_exclusion'])|dropped)
    targets={'express_company_name':'carrier','delivery_time':'shippedAt'}
    for field in value['field_mappings']:
        if field['source'] in targets:field['target']=targets[field['source']]
    value['snapshot_materialization']=dict(schema_version='aos.snapshot-materialization/v3',platform='niushop',
        shop_key='site_id',source_timezone='+08:00',time_basis='observation',deletion_basis='row-presence-only',
        property_defaults={'trackingNo':'[REDACTED]','trackingNoRedacted':True,'trackingNoSourceRead':False},
        status=dict(field='site_id',property_target='status',values={'1':'ACTIVE'}))
    value['notes']=[
        'Tracking number is fully redacted and never selected; no source number availability or tracking capability is claimed.',
        'Member name and free-form trace are excluded from source selection.',
        'shippedAt is source delivery_time; observation time never substitutes for missing shipment time.',
        'ACTIVE denotes presence in the selected site, not a delivery lifecycle state; deliveryType remains a source field.',
        'Parent Order relationship and completeness validation remain pending.',
    ]
    return value


def evaluate_shipment(mapping,root):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    schema=json.loads((root/'content/schemas/niushop-schema-fingerprint.json').read_text())
    masking=yaml.safe_load((root/'content/mappings/_pii-exclusion.yaml').read_text())
    spec=derive_mapping_read_spec(mapping,schema,masking);plan=compile_snapshot_mapping(mapping,spec)
    if {'delivery_no','member_name','trace'}&set(spec.columns):raise ValueError('Shipment privacy exclusion failed')
    at=datetime(2026,9,14,tzinfo=timezone.utc)
    raw={f['source']:(1 if f['type']=='int' else int(at.timestamp())-3600 if f['type']=='timestamp' else 'synthetic') for f in mapping['field_mappings']}
    scope=SyncScope(org_id='org-org',workspace_id='dev-project',platform='niushop',shop_or_marketplace_id='1',stream='P07-shipment-qyh')
    output=materialize_snapshot([raw],plan,observed_at=at)
    objects,links=_normalize_rows(output,scope);props=objects[0].properties
    if (len(objects)!=1 or links or props['trackingNo']!='[REDACTED]' or props['trackingNoRedacted'] is not True
            or props['trackingNoSourceRead'] is not False or props['sourceModificationTimeKnown'] is not False):
        raise ValueError('Shipment canonical evaluation failed')
    later=materialize_snapshot([raw],plan,observed_at=at+timedelta(hours=1))[0]
    if later['properties']['shippedAt']!=output[0]['properties']['shippedAt']:raise ValueError('fabricated shipment time')
    checks=['canonical-shipment-object','full-source-redaction','source-shipment-time-preserved','observation-time-marked']
    for name,bad in [('wrong-shop',raw|{'site_id':2}),('tracking-number',raw|{'delivery_no':'synthetic'}),
        ('member-name',raw|{'member_name':'synthetic'}),('trace',raw|{'trace':'synthetic'}),('zero-shipment-time',raw|{'delivery_time':0})]:
        try:_normalize_rows(materialize_snapshot([bad],plan,observed_at=at),scope)
        except ValueError:checks.append(name+'-rejected')
        else:raise ValueError('Shipment negative evaluation failed: '+name)
    return dict(status='passed',failed=0,scope='synthetic-shipment-object-snapshot-only',relationshipMaterialized=False,
        trackingCapability=False,columnCount=len(spec.columns),checks=checks)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    mapping=shipment_mapping(yaml.safe_load((source/MAPPING).read_text()))
    evaluate_shipment(mapping,source)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json'
    evidence.write_text(json.dumps(dict(status='pending',failed=0,scope='static-shipment-snapshot-only'))+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.9.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.10.0\n',1))
    (target/MAPPING).write_text(yaml.safe_dump(mapping,allow_unicode=True,sort_keys=False))
    evaluation=dict(status='passed',failed=0,scope='static-seven-object-snapshots-only',
        shop=evaluate_shop(target),product=evaluate_product(yaml.safe_load((target/'content/mappings/p02-product.yaml').read_text()),target),
        sku=evaluate_sku(yaml.safe_load((target/'content/mappings/p03-product-sku.yaml').read_text()),target),
        category=evaluate_category(yaml.safe_load((target/'content/mappings/p04-category.yaml').read_text()),target),
        order=evaluate_order(yaml.safe_load((target/'content/mappings/p05-order.yaml').read_text()),target),
        orderline=evaluate_orderline(yaml.safe_load((target/'content/mappings/p06-order-line.yaml').read_text()),target),
        shipment=evaluate_shipment(yaml.safe_load((target/MAPPING).read_text()),target),
        mappingHash='sha256:'+hashlib.sha256((target/MAPPING).read_bytes()).hexdigest())
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed during preparation')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    if changed!=['bundle.yaml',str(MAPPING),'evidence/bundle-evals.json']:raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_SHIPMENT_SNAPSHOT_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,
        targetTreeHash=helper._tree_hash(target),changedFiles=changed,evaluation=evaluation,published=False,installed=False)


if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
