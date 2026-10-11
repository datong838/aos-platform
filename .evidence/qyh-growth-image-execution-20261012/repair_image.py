"""Locked offline dependency repair in a disposable image, never a live install."""
import json
import shutil
import subprocess
import tomllib
import urllib.request
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parents[2]
D=Path(__file__).resolve().parent
CONTEXT='colima-aos-extension'
NAME='qyh-growth-image-repaired-20261012'
assert not (D/'repaired-build.json').exists(), 'read back unknown result before retry'
lock=ROOT/'services/aos-api/uv.lock'
lock_hash=sha256(lock.read_bytes()).hexdigest()
packages={p['name']:p for p in tomllib.loads(lock.read_text())['package']}
needed={'pydantic','pydantic-core','annotated-types','typing-extensions','typing-inspection'}
assert {dep['name'] for n in needed for dep in packages[n].get('dependencies',[])} <= needed
work=D/'repaired-build'
if not work.exists():
    shutil.copytree(D/'build-ecommerce_growth',work,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
wheels=work/'wheelhouse';wheels.mkdir(exist_ok=True)
selected=[]
for name in sorted(needed):
    package=packages[name]
    choices=[w for w in package['wheels'] if w['url'].endswith('-py3-none-any.whl') or ('-cp311-cp311-musllinux_' in w['url'] and w['url'].endswith('_aarch64.whl'))]
    assert len(choices)==1, (name,len(choices))
    wheel=choices[0];url=wheel['url'];parsed=urlparse(url)
    assert parsed.scheme=='https' and parsed.netloc=='files.pythonhosted.org'
    path=wheels/Path(parsed.path).name
    if not path.exists():
        with urllib.request.urlopen(url,timeout=30) as response:
            raw=response.read(16*1024*1024+1)
        assert len(raw)<=16*1024*1024 and 'sha256:'+sha256(raw).hexdigest()==wheel['hash']
        path.write_bytes(raw)
    assert 'sha256:'+sha256(path.read_bytes()).hexdigest()==wheel['hash']
    selected.append({'name':name,'version':package['version'],'file':path.name,'hash':wheel['hash']})
requirements=''.join(f"{p['name']}=={p['version']} --hash={p['hash']}\n" for p in selected)
(work/'runtime-requirements.txt').write_text(requirements)
raw=(D/'build-ecommerce_growth/Dockerfile').read_text()
raw=raw.replace('USER 65534:65534\n','COPY wheelhouse /aos/wheelhouse\nCOPY runtime-requirements.txt /aos/runtime-requirements.txt\nRUN python -m pip install --no-index --no-deps --require-hashes --find-links=/aos/wheelhouse -r /aos/runtime-requirements.txt\nUSER 65534:65534\n')
(work/'Dockerfile').write_text(raw)
cmd=['docker','--context',CONTEXT]
r=subprocess.run(cmd+['build','--network=none','--pull=false','-q',str(work)],capture_output=True,text=True,timeout=120)
(D/'repaired-build.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
image=r.stdout.strip();assert image.startswith('sha256:')
assert sha256(lock.read_bytes()).hexdigest()==lock_hash
(D/'repaired-build.json').write_text(json.dumps({'imageId':image,'sourceLockHash':lock_hash,'wheels':selected,'scope':'isolated diagnostic image only'},indent=2)+'\n')
program='''
import sys,importlib,pkgutil
sys.path.insert(0,'/aos/bundle/backend')
import ecommerce_growth
from ecommerce_growth.ecommerce_analyst_stage_eval_report import EvalGatePolicyRef
for kind in ('MediaGatePolicyRevision','EvalContractRevision'):
 assert EvalGatePolicyRef(resourceType=kind,resourceId='policy',revision=1,contentHash='a'*64)
for kind,revision in (('BudgetRevision',1),('EvalContractRevision',True)):
 try: EvalGatePolicyRef(resourceType=kind,resourceId='policy',revision=revision,contentHash='a'*64)
 except ValueError: pass
 else: raise AssertionError('invalid exact ref admitted')
from types import SimpleNamespace
from ecommerce_growth.content_capability_runtime import execute_content_capability
try: execute_content_capability(object(),dispatch_ref=SimpleNamespace(operation_id='ecommerce_growth_content_generate',handler_kind='extension'),request=SimpleNamespace(source_kind='accepted-stage-v1'))
except ValueError as exc: assert 'Host is not wired' in str(exc)
else: raise AssertionError('unwired Host admitted')
modules=list(pkgutil.iter_modules(ecommerce_growth.__path__))
for item in modules: importlib.import_module('ecommerce_growth.'+item.name)
assert not any(x.startswith('aos_api') for x in sys.modules)
print('original Growth modules imported:',len(modules),'policy types and negative gates PASS; Host guard PASS')
'''
r=subprocess.run(cmd+['create','--name',NAME,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--memory=512m','--cpus=1','--pids-limit=64',image,'python','-I','-c',program],capture_output=True,text=True,timeout=30)
assert r.returncode==0,r.stderr
(D/'repaired-container-id.txt').write_text(r.stdout)
r=subprocess.run(cmd+['start','-a',NAME],capture_output=True,text=True,timeout=60)
(D/'repaired-runtime.log').write_text(r.stdout+r.stderr)
i=json.loads(subprocess.check_output(cmd+['inspect',NAME],text=True))[0]
assert not i['State']['Running'] and not i['Mounts'] and i['HostConfig']['ReadonlyRootfs'] and i['HostConfig']['NetworkMode']=='none'
(D/'repaired-result.json').write_text(json.dumps({'imageId':image,'container':NAME,'state':i['State']['Status'],'exitCode':i['State']['ExitCode'],'diagnosticPassed':r.returncode==0 and i['State']['ExitCode']==0,'mountCount':0,'readonlyRootfs':True,'network':'none','formalRuntimeReady':False},indent=2)+'\n')
assert r.returncode==0 and i['State']['ExitCode']==0,r.stderr
print(r.stdout)
