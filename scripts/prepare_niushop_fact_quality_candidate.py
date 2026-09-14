"""Immutable static field-count policy candidate; no source access or installation."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_business_cohort_candidate import ROOT, builder, POLICY, QUALITY, COHORT, evaluate_cohort
from prepare_niushop_relationship_candidate import evaluate_relationships
from prepare_niushop_relationship_quality_candidate import evaluate_quality

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.19.0')
TARGET=Path('platform.ecommerce.niushop/1.20.0')
BASE_HASH='sha256:dd15e696a3962610e88bf2fef3cb1f843d97d3760be8aeafe0a8e035ba49957f'
FIELDS=Path('content/policies/fact-quality.v1.json')


def field(name,kind,values=None):
    return dict(property=name,kind=kind,**({'values':values} if values is not None else {}))


def fact_document(cohort, quality):
    def text(name):return field(name,'nonblank-string')
    def integer(name):return field(name,'nonnegative-integer')
    def number(name):return field(name,'nonnegative-number')
    def positive(name):return field(name,'positive-integer')
    def key(name):return field(name,'positive-id')
    def time(name):return field(name,'timestamp')
    def enum(name,*values):return field(name,'enum',list(values))
    status=enum('status','ACTIVE','INACTIVE'); active=enum('status','ACTIVE'); currency=enum('currency','CNY')
    facts={
        'Shop':[text('name'),enum('status','active'),currency,enum('timezone','+08:00')],
        'Product':[text('title'),status,number('price'),integer('stock'),currency,time('createdAt')],
        'ProductSku':[text('name'),key('productId'),status,number('price'),integer('stock'),currency],
        'Category':[text('name'),status,integer('level')],
        'Order':[text('orderNo'),active,enum('orderStatus',-1,0,1,2,10),integer('payStatus'),
            number('totalAmount'),number('payMoney'),positive('goodsNum'),currency,time('createdAt')],
        'OrderLine':[text('goodsName'),active,positive('quantity'),number('unitPrice'),number('lineAmount'),
            enum('refundStatus',-3,0,3),currency],
        'Shipment':[key('orderId'),active,integer('deliveryType'),time('shippedAt')],
        'CustomerLite':[integer('memberLevel'),active,time('createdAt')],
        'Weapp':[text('name'),active],
        'SystemConfig':[text('key'),status,enum('isUse',0,1)],
        'ProductReview':[key('productId'),status,integer('score'),enum('isAudit',0,1)],
        'Payment':[key('orderId'),active,text('outTradeNo'),number('payMoney'),enum('payStatus',-2,-1,0,1,2),currency,time('createTime')],
    }
    return dict(schemaVersion='aos.snapshot-fact-quality/v1',cohortPolicyHash=cohort.content_hash,
        relationshipQualityPolicyHash=quality.content_hash,purposeCode='initial_store_analysis',
        facts=[dict(objectType=ot,fields=deepcopy(rules)) for ot,rules in facts.items()])


def evaluate_fields(document,relationship,cohort,quality,source):
    from aos_api.pipeline_snapshot_fact_quality import compile_fact_quality_policy,measure_fact_quality
    policy=compile_fact_quality_policy(document,relationship_policy=relationship,cohort_policy=cohort,quality_policy=quality)
    mappings={d['target_ot']:d for path in (source/'content/mappings').glob('p*.yaml') for d in [yaml.safe_load(path.read_text())]}
    for ot,fields in policy.facts:
        mapping=mappings[ot]; config=mapping.get('snapshot_materialization',{})
        projection=config.get('public_projection')
        available=set(projection['properties']) if projection else {f['target'] for f in mapping['field_mappings']}|set(config.get('property_defaults',{}))
        if not projection and config.get('status'):available.add(config['status']['property_target'])
        if not {f.property_name for f in fields}<=available:raise ValueError('required field not publicly mapped')
    end=datetime(2026,9,14,tzinfo=timezone.utc);start=end-timedelta(days=30)
    rows={ot:[dict(ot=ot,source_pk='1',is_deleted=False,properties={})] for ot in relationship.object_types}
    for ot,fields in policy.facts:
        for f in fields:
            value=f.values[0] if f.kind=='enum' else start.isoformat() if f.kind=='timestamp' else 'fixture' if f.kind=='nonblank-string' else 1
            rows[ot][0]['properties'][f.property_name]=value
    for rule in relationship.rules:
        rows[rule.row_type][0]['properties'][rule.reference_property]=',1,' if rule.encoding=='wrapped-csv-positive-id' else 1
    def measure():return measure_fact_quality(rows,relationship,cohort,quality,policy,window_start=start,window_end=end,observed_at=end)
    full=measure()
    if len(full['facts'])!=12 or any(v['counts']['validCount']!=1 for v in full['facts'].values()):
        raise ValueError('complete field fixture not jointly valid')
    rows['Product'][0]['properties']['title']=''
    if measure()['facts']['Product']['counts']['validCount']!=0:raise ValueError('missing title accepted')
    rows['OrderLine'][0]['properties']['quantity']=0
    if measure()['facts']['OrderLine']['counts']['validCount']!=0:raise ValueError('zero quantity accepted')
    rows['CustomerLite']=[]
    if measure()['facts']['Order']['counts']['validCount']!=1:raise ValueError('disclosure incorrectly became mandatory')
    rows['OrderLine'][0]['properties']['quantity']=1
    rows['OrderLine'][0]['properties']['orderId']=99
    count=measure()['facts']['OrderLine']
    if count['counts']['eligibleCount']!=1 or count['counts']['validCount']!=0 or count['unknownRows']!=1:
        raise ValueError('missing parent left denominator')
    for ot in rows:rows[ot]=[]
    if any(v['counts']['eligibleCount'] or v['counts']['validCount'] for v in measure()['facts'].values()):
        raise ValueError('empty facts became valid')
    return dict(status='passed',fieldPolicyHash=policy.content_hash,checks=[
        'public-fields-only','twelve-joint-facts','missing-title','positive-quantity','disclosure-preserved',
        'unknown-parent-denominator','empty-facts-zero'],formalQualityEvidence=False,businessOutcome=False)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source tree differs')
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
    from aos_api.pipeline_snapshot_relationship_quality import compile_relationship_quality_policy
    from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy
    rel_doc=json.loads((source/POLICY).read_text());relationship=compile_relationship_policy(rel_doc)
    quality_doc=json.loads((source/QUALITY).read_text());quality=compile_relationship_quality_policy(quality_doc,relationship_policy=relationship)
    cohort_doc=json.loads((source/COHORT).read_text());cohort=compile_business_cohort_policy(cohort_doc,relationship_policy=relationship)
    document=fact_document(cohort,quality)
    report=dict(status='passed',failed=0,scope='static-fact-field-quality-policy',realFulfillment=False,
        relationships=evaluate_relationships(rel_doc,source),quality=evaluate_quality(quality_doc,relationship),
        cohort=evaluate_cohort(cohort_doc,relationship,source),fields=evaluate_fields(document,relationship,cohort,quality,source),
        inheritedObjectMappings=dict(sourceTreeHash=BASE_HASH,unchanged=True,objectEvaluationsRerun=False))
    manifest=(source/'bundle.yaml').read_text()
    if ('content/policies/' not in yaml.safe_load(manifest)['spec']['exports']['policies']
        or manifest.count('  version: 1.19.0\n')!=1):raise ValueError('original export or version differs')
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (target/'bundle.yaml').write_text(manifest.replace('  version: 1.19.0\n','  version: 1.20.0\n',1))
    (target/FIELDS).write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    (target/'evidence/bundle-evals.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    added=sorted(str(p.relative_to(target)) for p in target.rglob('*') if p.is_file() and not (source/p.relative_to(target)).exists())
    if helper._tree_hash(source)!=BASE_HASH or changed!=['bundle.yaml','evidence/bundle-evals.json'] or added!=[str(FIELDS)]:
        raise ValueError('unexpected candidate change')
    return dict(outcome='NIUSHOP_FACT_QUALITY_POLICY_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,
        targetTreeHash=helper._tree_hash(target),changedFiles=changed,addedFiles=added,evaluation=report,published=False,installed=False)


if __name__=='__main__':
    import logging
    logging.disable(logging.CRITICAL)
    print(json.dumps(prepare(),ensure_ascii=False,indent=2))
