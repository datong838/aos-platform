"""Immutable readiness policy candidate; no binding activation or installation."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_business_facts_candidate import (
    ROOT,builder,POLICY,QUALITY,COHORT,FIELDS,BUSINESS,evaluate_fields,evaluate_business,
)

CANDIDATES=ROOT/'bundles/candidates/ecommerce'
SOURCE=Path('platform.ecommerce.niushop/1.21.0')
TARGET=Path('platform.ecommerce.niushop/1.22.0')
BASE_HASH='sha256:33b35f7fb8dd145c4cd9700b71e396505ee1cd9cd669953a860c96304e5a2844'
READINESS=Path('content/policies/snapshot-readiness.v1.json')


def readiness_document(fields,quality):
    from aos_api.source_readiness_contracts import CANONICAL_QYH_SOURCES
    return dict(schemaVersion='aos.snapshot-readiness-policy/v1',fieldPolicyHash=fields.content_hash,
        relationshipQualityPolicyHash=quality.content_hash,purposeCode='initial_store_analysis',
        freshnessMode='requirement-oldest-observation',reconciliationMode='current-original-base-and-derived',
        queryBindingId='ecommerce.data_advisor.strategy.plan.r2',
        sources=[dict(pipelineId=s.pipeline_id,objectType=s.object_type) for s in CANONICAL_QYH_SOURCES])


def evaluate_readiness(document,fields,quality):
    from aos_api.pipeline_snapshot_readiness_policy import compile_snapshot_readiness_policy
    def compile(value):return compile_snapshot_readiness_policy(value,field_policy=fields,quality_policy=quality)
    policy=compile(document)
    if policy!=compile(document) or len(policy.sources)!=12:raise ValueError('complete stable readiness policy required')
    for fault in ('missing-source','freshness','reconciliation','untrusted-ready'):
        bad=deepcopy(document)
        if fault=='missing-source':bad['sources'].pop()
        if fault=='freshness':bad['freshnessMode']='query-time'
        if fault=='reconciliation':bad['reconciliationMode']='event-count'
        if fault=='untrusted-ready':bad['ready']=True
        try:compile(bad)
        except ValueError:continue
        raise ValueError('invalid policy was accepted: '+fault)
    return dict(status='passed',policyHash=policy.content_hash,checks=['complete-twelve','deterministic',
        'missing-source-refused','query-time-refused','event-count-refused','self-reported-ready-refused'],
        bindingCurrentlyValidated=False,formalReadiness=False,realTenantAcceptance=False)


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
    def read(path):return json.loads((source/path).read_text())
    relation=compile_relationship_policy(read(POLICY))
    quality=compile_relationship_quality_policy(read(QUALITY),relationship_policy=relation)
    cohort=compile_business_cohort_policy(read(COHORT),relationship_policy=relation)
    field_doc=read(FIELDS)
    fields=compile_fact_quality_policy(field_doc,relationship_policy=relation,cohort_policy=cohort,quality_policy=quality)
    document=readiness_document(fields,quality)
    report=dict(status='passed',failed=0,scope='static-snapshot-readiness-policy',realFulfillment=False,
        readiness=evaluate_readiness(document,fields,quality),
        fields=evaluate_fields(field_doc,relation,cohort,quality,source),
        business=evaluate_business(read(BUSINESS),relation,cohort,quality,fields),
        inheritedObjectMappings=dict(sourceTreeHash=BASE_HASH,unchanged=True,objectEvaluationsRerun=False))
    manifest=(source/'bundle.yaml').read_text()
    if ('content/policies/' not in yaml.safe_load(manifest)['spec']['exports']['policies']
        or manifest.count('  version: 1.21.0\n')!=1):raise ValueError('original export or version differs')
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (target/'bundle.yaml').write_text(manifest.replace('  version: 1.21.0\n','  version: 1.22.0\n',1))
    (target/READINESS).write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n')
    (target/'evidence/bundle-evals.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':'))+'\n')
    changed=sorted(str(p.relative_to(source)) for p in source.rglob('*') if p.is_file()
        and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.read_bytes()!=(target/p.relative_to(source)).read_bytes())
    added=sorted(str(p.relative_to(target)) for p in target.rglob('*') if p.is_file() and not (source/p.relative_to(target)).exists())
    if helper._tree_hash(source)!=BASE_HASH or changed!=['bundle.yaml','evidence/bundle-evals.json'] or added!=[str(READINESS)]:
        raise ValueError('unexpected candidate changes')
    return dict(outcome='NIUSHOP_SNAPSHOT_READINESS_CANDIDATE_PREPARED',sourceTreeHash=BASE_HASH,targetTreeHash=helper._tree_hash(target),
        changedFiles=changed,addedFiles=added,evaluation=report,published=False,installed=False)


if __name__=='__main__':
    import logging
    logging.disable(logging.CRITICAL)
    print(json.dumps(prepare(),ensure_ascii=False,indent=2))
