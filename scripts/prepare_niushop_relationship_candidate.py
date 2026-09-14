"""Export exact Niushop relationship policy in a new immutable adapter candidate."""
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_order_relation_candidate import ROOT,builder,evaluate_shop,evaluate_product,evaluate_sku,evaluate_category,evaluate_order_relations,evaluate_orderline,evaluate_shipment,evaluate_customer,evaluate_extended,evaluate_payment_key,MAPPINGS,SCHEMA,MASKING

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.15.0')
TARGET=Path('platform.ecommerce.niushop/1.16.0')
BASE_HASH='sha256:b09e20811f08b3d40e155406dd293d2642779acb6caed9ec8272f8337655779c'
POLICY=Path('content/policies/snapshot-relationships.v1.json')


def relationship_policy():
    types=['Shop','Product','ProductSku','Category','Order','OrderLine','Shipment','CustomerLite','Weapp','SystemConfig','ProductReview','Payment']
    values=[
      ('ProductSku.ofProduct','ProductSku','Product','productId','row-to-parent',False),
      ('Product.inCategory','Product','Category','categoryId','row-to-parent',True),
      ('Shop.sellsProduct','Product','Shop','shopId','parent-to-row',False),
      ('Order.lines','OrderLine','Order','orderId','parent-to-row',False),
      ('OrderLine.ofProduct','OrderLine','Product','productId','row-to-parent',False),
      ('OrderLine.ofSku','OrderLine','ProductSku','skuId','row-to-parent',True),
      ('Order.fulfilledBy','Shipment','Order','orderId','parent-to-row',False),
      ('Order.placedByLite','Order','CustomerLite','memberId','row-to-parent',False),
      ('Shop.hasWeapp','Weapp','Shop','siteId','parent-to-row',False),
      ('Product.hasReview','ProductReview','Product','productId','parent-to-row',False),
      ('ProductReview.ofSku','ProductReview','ProductSku','skuId','row-to-parent',True),
      ('ProductReview.byMember','ProductReview','CustomerLite','memberId','row-to-parent',False),
      ('Order.hasPayment','Payment','Order','orderId','parent-to-row',False),
      ('Order.fromWeapp','Order','Weapp','weappId','row-to-parent',True),
    ]
    return dict(schemaVersion='aos.snapshot-relationships/v1',objectTypes=types,rules=[dict(linkType=name,rowType=row,parentType=parent,
        referenceProperty=field,direction=direction,encoding='wrapped-csv-positive-id' if name=='Product.inCategory' else 'positive-id',allowUnset=unset)
        for name,row,parent,field,direction,unset in values])


def evaluate_relationships(document,root):
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_snapshot_relationships import compile_relationship_policy,assess_snapshot_relationships
    from aos_api.ec_ot_writer import _normalize_rows
    from aos_api.ecom_core_models import CORE_LINK_TYPES,SyncScope
    policy=compile_relationship_policy(document)
    mappings={d['target_ot']:d for path in (root/'content/mappings').glob('p*.yaml') for d in [yaml.safe_load(path.read_text())]}
    rows={ot:[dict(ot=ot,source_pk='1',is_deleted=False,properties={})] for ot in policy.object_types}
    for rule in policy.rules:
        mapping=mappings[rule.row_type];projection=mapping['snapshot_materialization'].get('public_projection')
        fields=set(projection['properties']) if projection else {f['target'] for f in mapping['field_mappings']}
        if rule.reference_property not in fields:raise ValueError('relationship field absent from current public output')
        endpoints=(rule.row_type,rule.parent_type) if rule.direction=='row-to-parent' else (rule.parent_type,rule.row_type)
        if CORE_LINK_TYPES.get(rule.link_type)!=endpoints:raise ValueError('relationship direction differs from canonical registry')
        rows[rule.row_type][0]['properties'][rule.reference_property]=',1,' if rule.encoding=='wrapped-csv-positive-id' else 1
    result=assess_snapshot_relationships(rows,policy,observed_at=datetime(2026,9,14,tzinfo=timezone.utc))
    objects,links=_normalize_rows(list(result.candidate_links),SyncScope(org_id='org-org',workspace_id='dev-project',platform='niushop',shop_or_marketplace_id='1',stream='relationship-candidate'))
    if objects or len(links)!=14:raise ValueError('all fourteen canonical relationships required')
    rows['CustomerLite']=[]
    missing=assess_snapshot_relationships(rows,policy,observed_at=datetime(2026,9,14,tzinfo=timezone.utc))
    if missing.counts['Order.placedByLite']['missingParent']!=1:raise ValueError('missing customer was hidden')
    rows['Product'][0]['is_deleted']=True
    deleted=assess_snapshot_relationships(rows,policy,observed_at=datetime(2026,9,14,tzinfo=timezone.utc))
    if deleted.counts['ProductSku.ofProduct']['deletedEndpoint']!=1:raise ValueError('soft deleted product was hidden')
    return dict(status='passed',candidateLinks=len(links),policyHash=policy.content_hash,relationshipWritten=False,checks=['current-public-fields','core-directions','canonical-links','missing-customer-visible','soft-delete-visible'])


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable candidate baseline differs')
    policy=relationship_policy();evaluate_relationships(policy,source)
    manifest_body=yaml.safe_load((source/'bundle.yaml').read_text())
    if 'content/policies/' not in manifest_body['spec']['exports']['policies']:raise ValueError('policy export missing')
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    evidence=target/'evidence/bundle-evals.json';evidence.write_text(json.dumps({'status':'pending'})+'\n')
    manifest=target/'bundle.yaml';text=manifest.read_text();marker='  version: 1.15.0\n'
    if text.count(marker)!=1:raise ValueError('candidate version declaration differs')
    manifest.write_text(text.replace(marker,'  version: 1.16.0\n',1));(target/POLICY).write_text(json.dumps(policy,ensure_ascii=False,indent=2)+'\n')
    schema=json.loads((target/SCHEMA).read_text());masking=yaml.safe_load((target/MASKING).read_text())
    evaluation=dict(status='passed',failed=0,scope='static-twelve-objects-and-fourteen-relationship-rules',realFulfillment=False,shop=evaluate_shop(target),relationships=evaluate_relationships(policy,target))
    for name,filename,fn in [('product','p02-product.yaml',evaluate_product),('sku','p03-product-sku.yaml',evaluate_sku),('category','p04-category.yaml',evaluate_category),
        ('order','p05-order.yaml',evaluate_order_relations),('orderline','p06-order-line.yaml',evaluate_orderline),('shipment','p07-shipment.yaml',evaluate_shipment),('customer','p08-customer-lite.yaml',evaluate_customer),('payment','p12-payment.yaml',evaluate_payment_key)]:
        evaluation[name]=fn(yaml.safe_load((target/'content/mappings'/filename).read_text()),target)
    for path in MAPPINGS:evaluation[path.stem]=evaluate_extended(yaml.safe_load((target/path).read_text()),schema,masking)
    evidence.write_text(json.dumps(evaluation,sort_keys=True,separators=(',',':'))+'\n')
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source changed')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    additions=sorted(str(p.relative_to(target)) for p in target.rglob('*') if p.is_file() and not (source/p.relative_to(target)).exists())
    if changed!=['bundle.yaml','evidence/bundle-evals.json'] or additions!=[str(POLICY)]:raise ValueError('unexpected successor changes')
    return dict(outcome='NIUSHOP_RELATIONSHIP_POLICY_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,targetTreeHash=helper._tree_hash(target),changedFiles=changed,addedFiles=additions,evaluation=evaluation,published=False,installed=False)

if __name__=='__main__':print(json.dumps(prepare(),ensure_ascii=False,indent=2))
