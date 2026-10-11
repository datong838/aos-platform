"""Finite original-builder image diagnostic; no publishing or production calls."""
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
D=Path(__file__).resolve().parent
SOURCE=ROOT/'.evidence/qyh-growth-source-candidate-20261012/candidate/solution.ecommerce.growth/1.13.1'
NAME='qyh-growth-image-execution-20261012'
CONTEXT='colima-aos-extension'
sys.path.insert(0,str(ROOT/'scripts'))
from build_ecommerce_runtime_candidates import _require_isolated_engine,_build_image,_tree_hash,SDK_ROOT
expected='sha256:'+json.loads((SOURCE.parents[2]/'preparation.json').read_text())['treeHash']
assert _tree_hash(SOURCE)==expected
assert not (D/'build-result.json').exists(), 'reconcile existing build before any retry'
engine=_require_isolated_engine(CONTEXT)
image,archive=_build_image(context=CONTEXT,bundle=SOURCE,package='ecommerce_growth',work=D)
build={'imageId':image,'archiveHash':sha256(archive.read_bytes()).hexdigest(),'base':engine,'sdkHash':_tree_hash(SDK_ROOT),'sourceHash':expected}
(D/'build-result.json').write_text(json.dumps(build,indent=2)+'\n')
program="import sys;sys.path.insert(0,'/aos/bundle/backend');import ecommerce_growth;assert len(ecommerce_growth.register(object())['contributions'])>0;print('original registration PASS',flush=True);from ecommerce_growth.ecommerce_analyst_stage_eval_report import EvalGatePolicyRef;assert EvalGatePolicyRef(resourceType='EvalContractRevision',resourceId='policy',revision=1,contentHash='a'*64);print('original StageEvalProof policy import PASS',flush=True)"
cmd=['docker','--context',CONTEXT]
r=subprocess.run(cmd+['create','--name',NAME,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=512m','--cpus=1','--pids-limit=64',image,'python','-I','-c',program],capture_output=True,text=True,timeout=30)
assert r.returncode==0,r.stderr
(D/'container-id.txt').write_text(r.stdout)
r=subprocess.run(cmd+['start','-a',NAME],capture_output=True,text=True,timeout=60)
(D/'runtime.log').write_text(r.stdout+r.stderr)
i=json.loads(subprocess.check_output(cmd+['inspect',NAME],text=True))[0]
assert not i['Mounts'] and not i['State']['Running']
assert i['HostConfig']['ReadonlyRootfs'] and i['HostConfig']['NetworkMode']=='none'
assert _tree_hash(SOURCE)==expected
retained=json.loads((ROOT/'.evidence/qyh-analyst-eval-policy-contract-20261012/retained-package-hashes.json').read_text())
assert all(sha256((ROOT/k).read_bytes()).hexdigest()==v for k,v in retained.items())
result={**build,'container':NAME,'state':i['State']['Status'],'exitCode':i['State']['ExitCode'],'diagnosticPassed':r.returncode==0 and i['State']['ExitCode']==0,'mountCount':len(i['Mounts']),'readonlyRootfs':True,'network':'none','retainedFilesUnchanged':len(retained),'formalRuntimeReady':False}
(D/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
