"""Prepare explicit Order association keys; never reads source or publishes."""
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_payment_key_candidate import evaluate_payment_key
from prepare_niushop_extended_candidate import ROOT,builder,evaluate_shop,evaluate_product,evaluate_sku,evaluate_category,evaluate_order,evaluate_orderline,evaluate_shipment,evaluate_customer,evaluate_extended,MAPPINGS,SCHEMA,MASKING

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.14.0')
TARGET=Path('platform.ecommerce.niushop/1.15.0')
BASE_HASH='sha256:9cb6cd266571dfbe7725e3411229f307025beec6ea93380a995529aa610d4b76'
MAPPING=Path('content/mappings/p05-order.yaml')
STRUCTURE=ROOT/'.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/full-store-source-structure-20260914.json'
STRUCTURE_HASH='6ef53e8f516137f95907c66caa919ed34190ef32606ef12af71f556fa7db2ca0'


def order_relation_mapping(original):
    value=deepcopy(original)
    if value.get('target_ot')!='Order' or value.get('source_table')!='ns_order' or value.get('site_filter')!='site_id=1':
        raise ValueError('exact Order predecessor required')
    if any(f['source'] in {'weapp_id','out_trade_no'} for f in value['field_mappings']):raise ValueError('Order keys already declared')
    raw=STRUCTURE.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=STRUCTURE_HASH:raise ValueError('structure evidence differs')
    columns={c['column_name']:c for t in json.loads(raw)['tables'] if t['table']=='ns_order' for c in t['columns']}
    if any(columns.get(k,{}).get('column_type')!=v or columns[k]['is_nullable']!='NO' for k,v in [('weapp_id','int(11)'),('out_trade_no','varchar(50)')]):
        raise ValueError('observed Order columns differ')
    value['field_mappings'] += [dict(source='weapp_id',target='weappId',type='int'),dict(source='out_trade_no',target='outTradeNo',type='string')]
    value['validation']['non_negative'].append('weapp_id')
    value['pii_exclusion'].append('weapp_openid')
    value['notes'] += ['Order association columns observed in source structure sha256:'+STRUCTURE_HASH,
        'weappId zero means unset; outTradeNo is the current order trade, not every historical payment trade.',
        'No relationship is inferred from orderFrom; weapp_openid is never selected.']
    return value


def evaluate_order_relations(mapping,root):
    result=evaluate_order(mapping,root)
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot
    schema=json.loads((root/SCHEMA).read_text());mask=yaml.safe_load((root/MASKING).read_text())
    spec=derive_mapping_read_spec(mapping,schema,mask);plan=compile_snapshot_mapping(mapping,spec)
    at=datetime(2026,9,14,tzinfo=timezone.utc)
    raw={f['source']:(1 if f['type']=='int' else int(at.timestamp()) if f['type']=='timestamp' else Decimal('1') if f['type']=='decimal' else 'synthetic') for f in mapping['field_mappings']}
    raw.update(is_delete=0,weapp_id=0,out_trade_no='synthetic-trade')
    output=materialize_snapshot([raw],plan,observed_at=at)[0]
    if output['properties']['weappId']!=0 or output['properties']['outTradeNo']!='synthetic-trade':raise ValueError('Order association keys changed')
    for bad in [raw|{'weapp_id':-1},raw|{'weapp_openid':'synthetic-private'},raw|{'site_id':2}]:
        try:materialize_snapshot([bad],plan,observed_at=at)
        except ValueError:pass
        else:raise ValueError('Order association negative failed')
    result['checks']+=['weapp-zero-preserved','current-trade-preserved','negative-weapp-rejected','openid-rejected']
    return result


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    mapping=order_relation_mapping(yaml.safe_load((source/MAPPING).read_text()))
    evaluate_order_relations(mapping,source)
    masking=yaml.safe_load((source/MASKING).read_text());masking['tables']['ns_order']['pii_direct'].append('weapp_openid')
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json';evidence.write_text(json.dumps({'status':'pending'})+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.14.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.15.0\n',1))
    (target/MAPPING).write_text(yaml.safe_dump(mapping,allow_unicode=True,sort_keys=False))
    (target/MASKING).write_text(yaml.safe_dump(masking,allow_unicode=True,sort_keys=False))
    schema=json.loads((target/SCHEMA).read_text())
    evaluation=dict(status='passed',failed=0,scope='static-twelve-object-snapshots-only',realFulfillment=False,shop=evaluate_shop(target))
    for name,filename,fn in [('product','p02-product.yaml',evaluate_product),('sku','p03-product-sku.yaml',evaluate_sku),('category','p04-category.yaml',evaluate_category),
        ('order','p05-order.yaml',evaluate_order_relations),('orderline','p06-order-line.yaml',evaluate_orderline),('shipment','p07-shipment.yaml',evaluate_shipment),('customer','p08-customer-lite.yaml',evaluate_customer),('payment','p12-payment.yaml',evaluate_payment_key)]:
        evaluation[name]=fn(yaml.safe_load((target/'content/mappings'/filename).read_text()),target)
    for path in MAPPINGS:evaluation[path.stem]=evaluate_extended(yaml.safe_load((target/path).read_text()),schema,masking)
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    if changed!=sorted(['bundle.yaml',str(MAPPING),str(MASKING),'evidence/bundle-evals.json']):raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_ORDER_RELATION_KEYS_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,targetTreeHash=helper._tree_hash(target),changedFiles=changed,evaluation=evaluation,published=False,installed=False)

if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
