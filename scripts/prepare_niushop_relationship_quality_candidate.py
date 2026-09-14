"""Static purpose coverage policy candidate; no installation or readiness grant."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import yaml
from prepare_niushop_relationship_candidate import ROOT, builder, POLICY, evaluate_relationships

CANDIDATES = ROOT / 'bundles/candidates/ecommerce'
SOURCE = Path('platform.ecommerce.niushop/1.17.0')
TARGET = Path('platform.ecommerce.niushop/1.18.0')
BASE_HASH = 'sha256:9cb8cd7c54fee2dd1f9e490b0d9f6e735045002f4b5d3164d6c1cd7ce83f89d3'
QUALITY = Path('content/policies/relationship-quality.v1.json')


def quality_policy(relationship):
    disclosures = {'Order.placedByLite', 'ProductReview.byMember'}
    if not disclosures.issubset({r.link_type for r in relationship.rules}):
        raise ValueError('explicit customer relationship rules missing')
    return dict(schemaVersion='aos.snapshot-relationship-quality/v1',
        relationshipPolicyHash=relationship.content_hash,
        purposes=[dict(purposeCode=purpose, rules=[dict(linkType=r.link_type,
            requirement='disclose' if purpose == 'initial_store_analysis' and r.link_type in disclosures
            else 'required') for r in relationship.rules])
            for purpose in ('initial_store_analysis', 'customer_cohort_analysis')])


def evaluate_quality(document, relationship):
    from aos_api.pipeline_snapshot_relationship_quality import (
        compile_relationship_quality_policy, measure_relationship_quality,
    )
    policy = compile_relationship_quality_policy(document, relationship_policy=relationship)
    rows = {ot: [dict(ot=ot, source_pk='1', is_deleted=False, properties={})]
        for ot in relationship.object_types}
    for rule in relationship.rules:
        rows[rule.row_type][0]['properties'][rule.reference_property] = (
            ',1,' if rule.encoding == 'wrapped-csv-positive-id' else 1)
    def measure():
        return measure_relationship_quality(rows, relationship, policy,
            observed_at=datetime(2026, 9, 14, tzinfo=timezone.utc))
    complete = measure()
    if len(complete.counts) != 14 or any(c['completeRows'] != 1 for c in complete.counts.values()):
        raise ValueError('all fourteen complete row references required')
    rows['CustomerLite'] = []
    missing = measure()
    names = ('Order.placedByLite', 'ProductReview.byMember')
    if (missing.purposes['initial_store_analysis']['disclosedIncomplete'] != names
        or missing.purposes['initial_store_analysis']['requiredIncomplete']
        or missing.purposes['customer_cohort_analysis']['requiredIncomplete'] != names
        or any(missing.counts[n]['eligibleRows'] != 1 or missing.counts[n]['missingParentRows'] != 1 for n in names)):
        raise ValueError('customer gap classification or denominator differs')
    rows['CustomerLite'] = [dict(ot='CustomerLite', source_pk='1', is_deleted=True, properties={})]
    deleted = measure()
    if any(deleted.counts[n]['deletedParentRows'] != 1 for n in names):
        raise ValueError('deleted customer gap hidden')
    rows = {ot: [] for ot in relationship.object_types}
    empty = measure()
    if (len(empty.purposes['initial_store_analysis']['emptyRules']) != 14
        or any(c['eligibleRows'] or c['completeRows'] for c in empty.counts.values())):
        raise ValueError('empty cohort fabricated a population')
    return dict(status='passed', qualityPolicyHash=policy.content_hash,
        checks=['fourteen-complete-references', 'missing-customer-purpose-difference',
            'real-row-denominator-retained', 'deleted-customer-visible', 'empty-population-visible'],
        measurementScope='reference-coverage-only', readinessGranted=False)


def prepare():
    source, target = CANDIDATES / SOURCE, CANDIDATES / TARGET
    if target.exists():
        raise ValueError('immutable candidate target already exists')
    helper = builder()
    if helper._tree_hash(source) != BASE_HASH:
        raise ValueError('immutable source tree differs')
    sys.path.insert(0, str(ROOT / 'services/aos-api'))
    from aos_api.pipeline_snapshot_relationships import compile_relationship_policy
    original = json.loads((source / POLICY).read_text())
    relationship = compile_relationship_policy(original)
    document = quality_policy(relationship)
    evaluation = evaluate_quality(document, relationship)
    relation_eval = evaluate_relationships(original, source)
    manifest_text = (source / 'bundle.yaml').read_text()
    if ('content/policies/' not in yaml.safe_load(manifest_text)['spec']['exports']['policies']
        or manifest_text.count('  version: 1.17.0\n') != 1):
        raise ValueError('original candidate export or version differs')
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (target / 'bundle.yaml').write_text(manifest_text.replace('  version: 1.17.0\n', '  version: 1.18.0\n', 1))
    (target / QUALITY).write_text(json.dumps(document, ensure_ascii=False, indent=2) + '\n')
    report = dict(status='passed', failed=0, scope='static-purpose-relationship-quality',
        relationships=relation_eval, quality=evaluation, realFulfillment=False,
        inheritedObjectMappings=dict(sourceTreeHash=BASE_HASH, unchanged=True, objectEvaluationsRerun=False))
    (target / 'evidence/bundle-evals.json').write_text(json.dumps(report, sort_keys=True, separators=(',', ':'))+'\n')
    changed = sorted(str(p.relative_to(source)) for p in source.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'
        and p.read_bytes() != (target / p.relative_to(source)).read_bytes())
    added = sorted(str(p.relative_to(target)) for p in target.rglob('*')
        if p.is_file() and not (source / p.relative_to(target)).exists())
    if (helper._tree_hash(source) != BASE_HASH or changed != ['bundle.yaml', 'evidence/bundle-evals.json']
        or added != [str(QUALITY)]):
        raise ValueError('unexpected candidate changes')
    return dict(outcome='NIUSHOP_PURPOSE_RELATIONSHIP_QUALITY_CANDIDATE_PREPARED',
        sourceTreeHash=BASE_HASH, targetTreeHash=helper._tree_hash(target), changedFiles=changed,
        addedFiles=added, evaluation=report, published=False, installed=False)


if __name__ == '__main__':
    import logging
    logging.disable(logging.CRITICAL)
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))
