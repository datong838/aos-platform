"""Static opt-in successor; no runtime permission, signing, installation or deletion."""
import json
from pathlib import Path
import shutil
import yaml
from prepare_niushop_relationship_candidate import ROOT, builder, POLICY, evaluate_relationships

CANDIDATES = ROOT / 'bundles/candidates/ecommerce'
SOURCE = Path('platform.ecommerce.niushop/1.16.0')
TARGET = Path('platform.ecommerce.niushop/1.17.0')
BASE_HASH = 'sha256:be89c813a9185c05a4c923016977f8ac09df387c78c059ef10bfc800083e9c93'


def prepare():
    source, target = CANDIDATES / SOURCE, CANDIDATES / TARGET
    if target.exists():
        raise ValueError('immutable candidate target already exists')
    helper = builder()
    if helper._tree_hash(source) != BASE_HASH:
        raise ValueError('immutable source tree differs')
    policy = json.loads((source / POLICY).read_text())
    if policy['schemaVersion'] != 'aos.snapshot-relationships/v1':
        raise ValueError('original non-retirement policy required')
    policy.update(schemaVersion='aos.snapshot-relationships/v2', retirement={
        'mode':'present-rows-only', 'requireCompleteReferences':True,
        'rejectNewerThanObservation':True, 'allowMissingRowDeletion':False})
    evaluation = evaluate_relationships(policy, source)
    manifest_body = yaml.safe_load((source / 'bundle.yaml').read_text())
    if 'content/policies/' not in manifest_body['spec']['exports']['policies']:
        raise ValueError('original policy export required')
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    manifest = target / 'bundle.yaml'
    text = manifest.read_text()
    marker = '  version: 1.16.0\n'
    if text.count(marker) != 1:
        raise ValueError('original candidate version differs')
    manifest.write_text(text.replace(marker, '  version: 1.17.0\n', 1))
    (target / POLICY).write_text(json.dumps(policy, ensure_ascii=False, indent=2) + '\n')
    report = dict(status='passed', failed=0, scope='static-retirement-policy-and-fourteen-canonical-links',
        relationships=evaluation, realFulfillment=False, retirementExecuted=False,
        inheritedObjectMappings=dict(sourceTreeHash=BASE_HASH, unchanged=True, objectEvaluationsRerun=False))
    (target / 'evidence/bundle-evals.json').write_text(json.dumps(report, sort_keys=True, separators=(',', ':'))+'\n')
    if helper._tree_hash(source) != BASE_HASH:
        raise ValueError('immutable source changed')
    changed = sorted(str(p.relative_to(source)) for p in source.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'
        and p.read_bytes() != (target / p.relative_to(source)).read_bytes())
    additions = [p for p in target.rglob('*') if p.is_file() and not (source / p.relative_to(target)).exists()]
    if changed != ['bundle.yaml', str(POLICY), 'evidence/bundle-evals.json'] or additions:
        raise ValueError('unexpected candidate changes')
    return dict(outcome='NIUSHOP_PRESENT_ROW_RETIREMENT_POLICY_CANDIDATE_PREPARED',
        sourceTreeHash=BASE_HASH, targetTreeHash=helper._tree_hash(target), changedFiles=changed,
        evaluation=report, published=False, installed=False)


if __name__ == '__main__':
    import logging
    logging.disable(logging.CRITICAL)
    print(json.dumps(prepare(), ensure_ascii=False, indent=2))
