"""Static business cohort successor; no source read, signing or installation."""
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_relationship_candidate import ROOT, builder, POLICY, evaluate_relationships
from prepare_niushop_relationship_quality_candidate import QUALITY, evaluate_quality

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.18.0')
TARGET=Path('platform.ecommerce.niushop/1.19.0')
BASE_HASH='sha256:5f3c6c00002c184429ceaaeca626f62107e7a4ae54d64b3a34c57a6d70b9b4db'
COHORT=Path('content/policies/business-cohort.v1.json')


def cohort_policy(relationship):
    rules=[]
    for ot in relationship.object_types:
        rule=dict(objectType=ot,basis='snapshot',statusFilter=None)
        if ot=='Product':rule['statusFilter']=dict(property='status',known=['ACTIVE','INACTIVE'],accepted=['ACTIVE'])
        if ot=='Order':rule.update(basis='own-time',timeProperty='createdAt')
        if ot in ('OrderLine','Shipment','Payment'):
            rule.update(basis='parent-time',parentType='Order',referenceProperty='orderId',timeProperty='createdAt')
        rules.append(rule)
    return dict(schemaVersion='aos.snapshot-business-cohort/v1',relationshipPolicyHash=relationship.content_hash,
        purposeCode='initial_store_analysis',windowBoundary='start-inclusive-end-exclusive',rules=rules)


def evaluate_cohort(document, relationship, root):
    from aos_api.pipeline_snapshot_business_cohort import compile_business_cohort_policy,select_business_cohort
    policy=compile_business_cohort_policy(document,relationship_policy=relationship)
    mappings={d['target_ot']:d for path in (root/'content/mappings').glob('p*.yaml') for d in [yaml.safe_load(path.read_text())]}
    def public_fields(ot):
        mapping=mappings[ot];config=mapping.get('snapshot_materialization',{})
        projection=config.get('public_projection')
        if projection:return set(projection['properties'])
        result={f['target'] for f in mapping['field_mappings']}|set(config.get('property_defaults',{}))
        if config.get('status'):result.add(config['status']['property_target'])
        return result
    for rule in policy.rules:
        if rule.status_filter and rule.status_filter.property_name not in public_fields(rule.object_type):
            raise ValueError('cohort status property not publicly mapped')
        if rule.time_property and rule.time_property not in public_fields(rule.parent_type or rule.object_type):
            raise ValueError('cohort time property not publicly mapped')
        if rule.reference_property and rule.reference_property not in public_fields(rule.object_type):
            raise ValueError('cohort reference not publicly mapped')
    end=datetime(2026,9,14,tzinfo=timezone.utc);start=end-timedelta(days=30)
    rows={ot:[dict(ot=ot,source_pk='1',is_deleted=False,properties={})] for ot in relationship.object_types}
    for rule in relationship.rules:
        rows[rule.row_type][0]['properties'][rule.reference_property]=',1,' if rule.encoding=='wrapped-csv-positive-id' else 1
    rows['Order'][0]['properties']['createdAt']=(end-timedelta(days=1)).isoformat()
    rows['Product'][0]['properties']['status']='ACTIVE'
    def select():return select_business_cohort(rows,relationship,policy,window_start=start,window_end=end,observed_at=end)
    first=select()
    if len(first.cohorts)!=12 or any(c.included_keys!=('1',) for c in first.cohorts.values()):
        raise ValueError('complete current business cohort required')
    order_types=('Order','OrderLine','Shipment','Payment')
    rows['Order'][0]['properties']['createdAt']=(start-timedelta(seconds=1)).isoformat()
    old=select()
    if any(old.cohorts[ot].eligible_count!=0 for ot in order_types):raise ValueError('historical order scope drifted')
    rows['Order'][0]['properties']['createdAt']=None
    unknown=select()
    if any(unknown.cohorts[ot].eligible_count!=1 or len(unknown.cohorts[ot].unknown)!=1 for ot in order_types):
        raise ValueError('unknown business time disappeared')
    rows['Order']=[]
    missing=select()
    if any(missing.cohorts[ot].eligible_count!=1 or len(missing.cohorts[ot].unknown)!=1 for ot in order_types[1:]):
        raise ValueError('missing order disappeared from child denominator')
    rows['Product'][0]['properties']['status']='INACTIVE'
    inactive=select()
    if inactive.cohorts['Product'].excluded!=(('1','status-outside'),):raise ValueError('off-shelf population hidden')
    return dict(status='passed',cohortPolicyHash=policy.content_hash,
        checks=['public-output-fields','twelve-declared-types','historical-order-scope','unknown-time-retained',
            'missing-parent-retained','off-shelf-separated'],formalQuality=False,historicalSnapshotClaim=False)


def prepare():
    source,target=CANDIDATES/SOURCE,CANDIDATES/TARGET
    if target.exists():raise ValueError('immutable candidate target already exists')
    helper=builder()
    if helper._tree_hash(source)!=BASE_HASH:raise ValueError('immutable source tree differs')
    sys.path.insert(0,str(ROOT/'services/aos-api'))
    from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
    original=json.loads((source/POLICY).read_text());relationship=compile_relationship_policy(original)
    document=cohort_policy(relationship)
    report=dict(status='passed',failed=0,scope='static-business-cohort-policy',realFulfillment=False,
        relationships=evaluate_relationships(original,source),
        quality=evaluate_quality(json.loads((source/QUALITY).read_text()),relationship),
        cohort=evaluate_cohort(document,relationship,source),
        inheritedObjectMappings=dict(sourceTreeHash=BASE_HASH,unchanged=True,objectEvaluationsRerun=False))
    manifest=(source/'bundle.yaml').read_text()
    if ('content/policies/' not in yaml.safe_load(manifest)['spec']['exports']['policies']
        or manifest.count('  version: 1.18.0\n')!=1):raise ValueError('original export or version differs')
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (target/'bundle.yaml').write_text(manifest.replace('  version: 1.18.0\n','  version: 1.19.0\n',1))
    (target/COHORT).write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    (target/'evidence/bundle-evals.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    added=sorted(str(p.relative_to(target)) for p in target.rglob('*') if p.is_file() and not (source/p.relative_to(target)).exists())
    if helper._tree_hash(source)!=BASE_HASH or changed!=['bundle.yaml','evidence/bundle-evals.json'] or added!=[str(COHORT)]:
        raise ValueError('unexpected candidate change')
    return dict(outcome='NIUSHOP_BUSINESS_COHORT_POLICY_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,
        targetTreeHash=helper._tree_hash(target),changedFiles=changed,addedFiles=added,evaluation=report,published=False,installed=False)


if __name__=='__main__':
    import logging
    logging.disable(logging.CRITICAL)
    print(json.dumps(prepare(),ensure_ascii=False,indent=2))
