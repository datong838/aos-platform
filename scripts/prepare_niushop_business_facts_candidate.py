"""Immutable public business-content candidate; no source call or installation."""
from datetime import datetime,timezone,timedelta
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_fact_quality_candidate import ROOT,builder,POLICY,QUALITY,COHORT,FIELDS,evaluate_fields

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.20.0')
TARGET=Path('platform.ecommerce.niushop/1.21.0')
BASE_HASH='sha256:0a5d0b369f701e5aee68d5b3692fc0b6a89b1d89d195ccd4b549f7388d5a423b'
BUSINESS=Path('content/policies/business-facts.v1.json')


def business_document(fields):
    records={
        'Shop':['name','status','currency','timezone'],
        'Product':['title','status','price','stock','currency','createdAt'],
        'ProductSku':['name','status','price','stock','currency'],
        'Category':['name','status','level'],
        'OrderLine':['goodsName','quantity','unitPrice','lineAmount','refundStatus','currency'],
        'Weapp':['name','status'],'SystemConfig':['key','status','isUse'],
    }
    groups={'Order':['orderStatus','payStatus'],'Shipment':['status','deliveryType'],
        'CustomerLite':['memberLevel','status'],'ProductReview':['status','score','isAudit'],'Payment':['status','payStatus']}
    return dict(schemaVersion='aos.snapshot-business-facts/v1',fieldPolicyHash=fields.content_hash,purposeCode=fields.purpose_code,
        facts=[dict(objectType=ot,mode='records' if ot in records else 'group-counts',fields=(records|groups)[ot]) for ot,_ in fields.facts])


def evaluate_business(document,relation,cohort,quality,fields):
    from aos_api.pipeline_snapshot_business_facts import compile_business_fact_policy,build_business_facts
    policy=compile_business_fact_policy(document,field_policy=fields)
    forbidden={'orderNo','outTradeNo','orderId','productId','memberId','value','content','phone','mobile'}
    if any(forbidden&set(names) for _,_,names in policy.facts):raise ValueError('private or unneeded identity export')
    end=datetime(2026,9,14,tzinfo=timezone.utc);start=end-timedelta(days=30)
    rows={ot:[dict(ot=ot,source_pk='1',is_deleted=False,properties={})] for ot in relation.object_types}
    for ot,definitions in fields.facts:
        for field in definitions:
            rows[ot][0]['properties'][field.property_name]=(field.values[0] if field.kind=='enum' else
                start.isoformat() if field.kind=='timestamp' else 'public fixture' if field.kind=='nonblank-string' else 1)
    for rule in relation.rules:
        rows[rule.row_type][0]['properties'][rule.reference_property]=',1,' if rule.encoding=='wrapped-csv-positive-id' else 1
    for values in rows.values():values[0]['properties']['secret']='never-export'
    def measure():return build_business_facts(rows,relation,cohort,quality,fields,policy,window_start=start,window_end=end,observed_at=end)
    result=measure()
    if result!=measure() or len(result['facts'])!=12 or 'never-export' in str(result):raise ValueError('business content drift or leak')
    if result['facts']['Product']['records'][0]['values']['title']!='public fixture':raise ValueError('actual content missing')
    if result['facts']['Order']['groups']['orderStatus']['known']!=[dict(value=-1,count=1)]:raise ValueError('raw order status grouping differs')
    rows['Order'][0]['properties']['createdAt']=None
    if measure()['facts']['Order']['groups']['orderStatus']['unknown']!=[dict(value=-1,count=1)]:raise ValueError('unknown window lost')
    rows['Product'][0]['properties']['title']=''
    if measure()['facts']['Product']['records'][0]['values']['title'] is not None:raise ValueError('bad public value exposed')
    return dict(status='passed',businessPolicyHash=policy.content_hash,checks=['twelve-fact-content','explicit-fields-only',
        'actual-product-title','raw-status-not-sales','unknown-window-retained','invalid-value-null','deterministic'],
        formalBusinessEvidence=False,realTenantAcceptance=False)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source tree differs')
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
    from aos_api.pipeline_snapshot_relationship_quality import compile_relationship_quality_policy
    from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy
    from aos_api.pipeline_snapshot_fact_quality import compile_fact_quality_policy
    relation=compile_relationship_policy(json.loads((source/POLICY).read_text()))
    quality=compile_relationship_quality_policy(json.loads((source/QUALITY).read_text()),relationship_policy=relation)
    cohort=compile_business_cohort_policy(json.loads((source/COHORT).read_text()),relationship_policy=relation)
    field_doc=json.loads((source/FIELDS).read_text())
    fields=compile_fact_quality_policy(field_doc,relationship_policy=relation,cohort_policy=cohort,quality_policy=quality)
    document=business_document(fields)
    report=dict(status='passed',failed=0,scope='static-business-content-policy',realFulfillment=False,
        fields=evaluate_fields(field_doc,relation,cohort,quality,source),business=evaluate_business(document,relation,cohort,quality,fields),
        inheritedObjectMappings=dict(sourceTreeHash=BASE_HASH,unchanged=True,objectEvaluationsRerun=False))
    manifest=(source/'bundle.yaml').read_text()
    if ('content/policies/' not in yaml.safe_load(manifest)['spec']['exports']['policies']
        or manifest.count('  version: 1.20.0\n')!=1):raise ValueError('original export or version differs')
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (target/'bundle.yaml').write_text(manifest.replace('  version: 1.20.0\n','  version: 1.21.0\n',1))
    (target/BUSINESS).write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    (target/'evidence/bundle-evals.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    added=sorted(str(p.relative_to(target)) for p in target.rglob('*') if p.is_file() and not (source/p.relative_to(target)).exists())
    if helper._tree_hash(source)!=BASE_HASH or changed!=['bundle.yaml','evidence/bundle-evals.json'] or added!=[str(BUSINESS)]:
        raise ValueError('unexpected candidate changes')
    return dict(outcome='NIUSHOP_BUSINESS_FACTS_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,targetTreeHash=helper._tree_hash(target),
        changedFiles=changed,addedFiles=added,evaluation=report,published=False,installed=False)


if __name__=='__main__':
    import logging
    logging.disable(logging.CRITICAL)
    print(json.dumps(prepare(),ensure_ascii=False,indent=2))
