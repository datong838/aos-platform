"""Verify prepared source using original loaders; never builds or installs it."""
import importlib.util
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'services/aos-api/src'))
sys.path.insert(0, str(ROOT / 'packages/aos-extension-sdk/python'))
from prepare_ecommerce_growth_1_5_candidate import tree_hash
from build_ecommerce_runtime_candidates import _load_manifest, _runtime_registration, _manifest_api_registration, _schema_compatibility
from aos_api.asset_registry.manifest_loader import ManifestLoader

spec = importlib.util.spec_from_file_location('prepared_source', D / 'prepare.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
t = m.TARGET
assert tree_hash(m.BASE) == m.BASE_HASH
assert tree_hash(t) == json.loads((D / 'preparation.json').read_text())['treeHash']
assert ManifestLoader({'candidate': t.parent}).load('bundle://candidate/1.13.1').manifest.metadata.version == '1.13.1'
ops = _runtime_registration(t, 'ecommerce_growth')
assert ops == _manifest_api_registration(_load_manifest(t)) and len(ops) == 11
assert _schema_compatibility(t, 'solution.ecommerce.growth').startswith('sha256:')
for relative in ('bundle.signature.json', 'evidence/bundle-evals.json', 'evidence/sbom.json', 'artifacts/runtime-image-index.json', 'artifacts/python-dependencies.lock'):
    assert not (t / relative).exists()
for name, expected in m.BACKEND_DELTA.items():
    assert sha256((t / 'backend/ecommerce_growth' / name).read_bytes()).hexdigest() == expected
retained = json.loads((ROOT / '.evidence/qyh-analyst-eval-policy-contract-20261012/retained-package-hashes.json').read_text())
assert len(retained) == 1695
assert all(sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in retained.items())
try:
    m.prepare()
except ValueError as exc:
    assert 'already exists' in str(exc)
else:
    raise AssertionError('existing target was not rejected')
program = '''
import importlib,sys
class Deny:
 def find_spec(self,name,path=None,target=None):
  if name=='aos_api' or name.startswith('aos_api.'): raise AssertionError(name)
sys.meta_path.insert(0,Deny())
sys.path[:0]=sys.argv[1:]
from test_analyst_stage_eval_report_proof import values
import ecommerce_growth as runtime
package=tuple(importlib.import_module('ecommerce_growth.'+x) for x in ('ecommerce_analyst_authority_contracts','ecommerce_analyst_stage_decision','ecommerce_analyst_stage_eval_report'))
for kind in ('MediaGatePolicyRevision','EvalContractRevision'):
 module,proof,args=values(package)
 body=proof.model_dump(mode='json',by_alias=True)
 policy=dict(resourceType=kind,resourceId='policy',revision=1,contentHash='a'*64)
 body['gatePolicyRef']=policy
 response=runtime.handle('ecommerce_growth_review_advance',dict(kind='validate_eval_proof',proof=body,tenant=args['tenant'].model_dump(mode='json',by_alias=True),artifactRef=args['artifact_ref'].model_dump(mode='json',by_alias=True),stageAttemptRef=args['stage_attempt_ref'].model_dump(mode='json',by_alias=True),evalContractRef=args['eval_contract_ref'].model_dump(mode='json',by_alias=True),gatePolicyRef=policy,cutoffAt=args['cutoff_at'].isoformat(),now=args['now'].isoformat()),object())
 assert response['reportRef']['resourceId']=='report'
from types import SimpleNamespace
from ecommerce_growth.content_capability_runtime import execute_content_capability
try: execute_content_capability(request=SimpleNamespace(source_kind='accepted-stage-v1'),port=object(),dispatch_ref=SimpleNamespace(operation_id='ecommerce_growth_content_generate',handler_kind='extension'))
except ValueError as exc: assert 'Host is not wired' in str(exc)
else: raise AssertionError('Host guard removed')
assert not any(x.startswith('aos_api') for x in sys.modules)
print('candidate dispatch both policy types PASS; accepted-stage Host guard PASS; platform import denied PASS')
'''
result = subprocess.run([sys.executable, '-I', '-c', program, str(t / 'backend'), str(ROOT / 'packages/aos-extension-sdk/python'), str(ROOT / 'services/aos-api/tests/extension_runtime')], capture_output=True, text=True)
(D / 'isolated.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
print(json.dumps({'state':'SOURCE_PREPARED_UNBUILT_UNSIGNED','apiRegistrations':len(ops),'workshopSelfReferences':8,'retainedFilesUnchanged':len(retained),'sourceDeltaFiles':3,'isolatedCandidateChecks':'PASS','existingTargetRefusal':'PASS','runtimeReady':False,'formalLoginConnected':False,'independentPublisherConnected':False},ensure_ascii=False,indent=2))
