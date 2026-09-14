"""Prepare ordinary-order payments only; no source access or publication."""
from copy import deepcopy
from datetime import datetime,timezone
from decimal import Decimal
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_extended_candidate import ROOT,builder,evaluate_shop,evaluate_product,evaluate_sku,evaluate_category,evaluate_order,evaluate_orderline,evaluate_shipment,evaluate_customer,evaluate_extended,MAPPINGS,SCHEMA,MASKING

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.12.0')
TARGET=Path('platform.ecommerce.niushop/1.13.0')
BASE_HASH='sha256:7d0eaeb6c99da59f8e9f08f78607da60320f97bdaab881184c4f7e6a47fd9587'
MAPPING=Path('content/mappings/p12-payment.yaml')


def payment_policy(original):
    value=deepcopy(original);rule=value['tables']['ns_pay']
    if 'event' not in rule['pii_direct'] or 'conditional_only' in rule:raise ValueError('payment policy predecessor differs')
    rule['pii_direct'].remove('event');rule['conditional_only']={'event':'OrderPayNotify'}
    return value


def payment_mapping(original):
    value=deepcopy(original)
    if (value.get('pipeline_id'),value.get('source_table'),value.get('target_ot'),value.get('primary_key'))!=('P12','ns_pay','Payment','id'):
        raise ValueError('exact Payment mapping predecessor required')
    value.pop('incremental_cursor');value['incremental_strategy']='snapshot'
    value['site_filter']="site_id=1 AND event='OrderPayNotify'"
    value['validation']={'required':['id','site_id','relate_id','out_trade_no','event'],'non_negative':['pay_money']}
    names={'id','site_id','out_trade_no','pay_type','pay_money','pay_status','member_id','relate_id','is_delete','create_time','pay_time','event'}
    seen=set();fields=[]
    for field in value['field_mappings']:
        if field['source'] in names and field['source'] not in seen:
            fields.append(field);seen.add(field['source'])
    if seen!=names:raise ValueError('payment source columns differ')
    for field in fields:
        if field['source']=='relate_id':field['target']='orderId'
    value['field_mappings']=fields
    value['snapshot_materialization']=dict(schema_version='aos.snapshot-materialization/v3',platform='niushop',shop_key='site_id',
        source_timezone='+08:00',property_defaults={'currency':'CNY'},time_basis='observation',
        deletion_basis={'field':'is_delete','live_value':0,'deleted_value':1},
        status={'field':'pay_status','property_target':'status','values':{str(i):'ACTIVE' for i in (-2,-1,0,1,2)}},
        public_projection={'schema_version':1,'properties':['orderId','outTradeNo','payType','payMoney','payStatus','memberId','createTime','payTime','currency','status']})
    value['notes']=[
        'Only site 1 OrderPayNotify payments; member-card payment IDs belong to another order namespace and are excluded.',
        'relate_id is ordinary order_id in this event namespace; actual parent relationship validation remains required.',
        'Closed historical retries remain included; current order trade number alone is not payment identity.',
        'Source payment times remain source fields, including unknown zero time; updatedAt is observation only.',
        'No pay-duration metric, parent relation Receipt or payment effect is produced.',
    ]
    return value


def evaluate_payment(mapping,root,masking=None):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_source_selection import derive_mapping_read_spec
    from aos_api.pipeline_snapshot_materialization import compile_snapshot_mapping,materialize_snapshot
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import SyncScope
    schema=json.loads((root/SCHEMA).read_text())
    masking=masking if masking is not None else yaml.safe_load((root/MASKING).read_text())
    spec=derive_mapping_read_spec(mapping,schema,masking);plan=compile_snapshot_mapping(mapping,spec)
    at=datetime(2026,9,14,tzinfo=timezone.utc)
    raw=dict(id=101,site_id=1,out_trade_no='synthetic-trade',pay_type='synthetic',pay_money=Decimal('19.90'),pay_status=0,
        member_id=1,relate_id=1,is_delete=0,create_time=int(at.timestamp())-3600,pay_time=0,event='OrderPayNotify')
    scope=SyncScope(org_id='org-org',workspace_id='dev-project',platform='niushop',shop_or_marketplace_id='1',stream='P12-payment-qyh')
    for state in (-2,-1,0,1,2):
        output=materialize_snapshot([raw|{'pay_status':state}],plan,observed_at=at)
        objects,links=_normalize_rows(output,scope);props=objects[0].properties
        if (len(objects)!=1 or links or props['payStatus']!=state or props['payMoney']!='19.90'
                or props.get('payTime') is not None or 'event' in props or 'pay_duration_min' in props
                or props['sourceModificationTimeKnown'] is not False):raise ValueError('Payment canonical evaluation failed')
    removed=materialize_snapshot([raw|{'is_delete':1}],plan,observed_at=at)[0]
    if not removed['is_deleted'] or removed['properties']['status']!='DELETED':raise ValueError('Payment deletion failed')
    checks=['canonical-payment','all-source-payment-states','unknown-payment-time-preserved','explicit-delete','ordinary-order-scope']
    for name,bad in [('other-business',raw|{'event':'SuperCardOrderPayNotify'}),('wrong-shop',raw|{'site_id':2}),
        ('unknown-status',raw|{'pay_status':99}),('unknown-delete',raw|{'is_delete':2}),('negative-money',raw|{'pay_money':Decimal('-1')}),
        ('secret',raw|{'pay_json':'synthetic'})]:
        try:materialize_snapshot([bad],plan,observed_at=at)
        except ValueError:checks.append(name+'-rejected')
        else:raise ValueError('Payment negative evaluation failed')
    return dict(status='passed',failed=0,scope='synthetic-ordinary-order-payment-only',columnCount=len(spec.columns),checks=checks,relationshipMaterialized=False)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    mapping=payment_mapping(yaml.safe_load((source/MAPPING).read_text()));masking=payment_policy(yaml.safe_load((source/MASKING).read_text()))
    evaluate_payment(mapping,source,masking)
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json';evidence.write_text(json.dumps({'status':'pending'})+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.12.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.13.0\n',1))
    (target/MASKING).write_text(yaml.safe_dump(masking,allow_unicode=True,sort_keys=False))
    (target/MAPPING).write_text(yaml.safe_dump(mapping,allow_unicode=True,sort_keys=False))
    schema=json.loads((target/SCHEMA).read_text())
    evaluation=dict(status='passed',failed=0,scope='static-twelve-object-snapshots-only',realFulfillment=False,shop=evaluate_shop(target))
    for name,filename,fn in [('product','p02-product.yaml',evaluate_product),('sku','p03-product-sku.yaml',evaluate_sku),
        ('category','p04-category.yaml',evaluate_category),('order','p05-order.yaml',evaluate_order),('orderline','p06-order-line.yaml',evaluate_orderline),
        ('shipment','p07-shipment.yaml',evaluate_shipment),('customer','p08-customer-lite.yaml',evaluate_customer)]:
        evaluation[name]=fn(yaml.safe_load((target/'content/mappings'/filename).read_text()),target)
    for path in MAPPINGS:evaluation[path.stem]=evaluate_extended(yaml.safe_load((target/path).read_text()),schema,masking)
    evaluation['payment']=evaluate_payment(yaml.safe_load((target/MAPPING).read_text()),target)
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed during preparation')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    if changed!=sorted(['bundle.yaml',str(MAPPING),str(MASKING),'evidence/bundle-evals.json']):raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_PAYMENT_SNAPSHOT_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,targetTreeHash=helper._tree_hash(target),changedFiles=changed,evaluation=evaluation,published=False,installed=False)


if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
