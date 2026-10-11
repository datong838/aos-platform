"""Independent readback of full candidate build, preserving current system."""
import importlib.util
import json
import subprocess
from hashlib import sha256
from pathlib import Path
from datetime import datetime,UTC
ROOT=Path(__file__).resolve().parents[2]
D=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('profile',D/'build_profile.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p);b=p.load_builder()
r=json.loads((D/'build-result.json').read_text());assert r['outcome']=='BUILD_GREEN' and r['moduleCount']==8 and r['operationCount']==15
assert r['outputTreeHash']==b._tree_hash(p.OUTPUT) and r['contentHashes']==b._content_hashes(p.OUTPUT)
assert r['effects']==dict(registryPublishCount=0,installationMutationCount=0,providerInvocationCount=0,externalPublicationCount=0)
rows=[]
for relative,bid,version,package in p.CASES:
    root=p.OUTPUT/relative
    if package is None:
        assert r['contentHashes'][bid]=='sha256:ca0f6e74bcb428efd78c868285cd9fbed136919d4676b46aee9e181e8eec33ec'
        continue
    assert (root/'artifacts/python-dependencies.lock').read_bytes()==b._dependency_lock(root)
    actual=b._sha256((root/'artifacts/python-dependencies.lock').read_bytes())
    index=json.loads((root/'artifacts/runtime-image-index.json').read_text())['images'][0]
    image=r['images'][bid.replace('.','-')]
    assert index['dependencyLockHash']==r['dependencyLockHashes'][bid]==actual
    assert index['imageDigest']==image['imageDigest'] and index['configDigest']==image['configDigest']
    config=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','image','inspect',image['configDigest']],text=True))[0]
    assert config['Id']==image['configDigest'] and config['Config']['User']=='65534:65534' and not config['Config'].get('Volumes')
    assert image['imageDigest'] in {v.rsplit('@',1)[-1] for v in config['RepoDigests']}
    sbom={i['name']:i for i in json.loads((root/'evidence/sbom.json').read_text())['components']}
    deps=b._runtime_dependencies(root)
    assert all(sbom[v['name']]['version']==v['version'] and sbom[v['name']]['hashes']==[{'alg':'SHA-256','content':v['hash'][7:]}] for v in deps)
    evaluation=json.loads((root/'evidence/bundle-evals.json').read_text());assert evaluation['scope']=='source-preflight-only' and evaluation['runtimeReadiness']=='blocked'
    assert not (root/'bundle.signature.json').exists()
    rows.append({'id':bid,'version':version,'imageDigest':image['imageDigest'],'configDigest':image['configDigest'],'dependencyCount':len(deps),'sourceEvalScope':evaluation['scope'],'signed':False})
assert len(rows)==3
inputs=json.loads((D/'inputs.json').read_text())
public=ROOT/'.evidence/qyh-full-system-restoration-20261011/selected-public-bundles'
assert all(b._tree_hash(public/i['id']/i['baseVersion'])==i['baseHash'] for i in inputs['bases'])
retained=json.loads((ROOT/'.evidence/qyh-analyst-eval-policy-contract-20261012/retained-package-hashes.json').read_text());assert all(sha256((ROOT/name).read_bytes()).hexdigest()==v for name,v in retained.items())
containers=[json.loads(line) for line in subprocess.check_output(['docker','--context','colima-aos-extension','container','ls','-a','--format','json'],text=True).splitlines()]
helper=[]
for row in containers:
    if not row['Names'].startswith('a0v-candidate-registry-'): continue
    info=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',row['ID']],text=True))[0]
    if datetime.fromisoformat(info['Created'].replace('Z','+00:00')).timestamp() < (D/'inputs.json').stat().st_mtime: continue
    ports=info['HostConfig'].get('PortBindings') or {}
    if any(v.get('HostPort')=='18438' for vals in ports.values() for v in vals or []):
        assert not info['State']['Running'];helper.append({'name':row['Names'],'state':info['State']['Status']})
assert len(helper)==1
probes=[]
for row in containers:
    if not row['Names'].startswith('a0v-runtime-import-'): continue
    info=json.loads(subprocess.check_output(['docker','--context','colima-aos-extension','inspect',row['ID']],text=True))[0]
    if datetime.fromisoformat(info['Created'].replace('Z','+00:00')).timestamp() < (D/'inputs.json').stat().st_mtime: continue
    if info['Config']['Image'] not in {r['images'][bid.replace('.','-')]['configDigest'] for _,bid,_,package in p.CASES if package}: continue
    assert not info['State']['Running'] and info['State']['ExitCode']==0 and not info['Mounts'] and info['HostConfig']['ReadonlyRootfs'] and info['HostConfig']['NetworkMode']=='none'
    probes.append({'name':row['Names'],'imageId':info['Image'],'exitCode':0,'mounts':0,'network':'none'})
assert len(probes)>=3
result={'outcome':'FULL_UNSIGNED_CANDIDATE_BUILD_READBACK_PASS','versions':rows,'operationsPackageRetainedExact':True,'eightModules':8,'runtimeOperations':15,'runtimeProbes':probes,'localRegistryHelper':helper,'retained1695Exact':True,'oldFourSignedRootsExact':True,'formalPublishingAuthority':False,'currentInstallationChanged':False,'formalRuntimeReady':False,'builderHash':sha256((ROOT/'scripts/build_ecommerce_runtime_candidates.py').read_bytes()).hexdigest()}
(D/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print('full4 build independent byte/SBOM/lock/OCI readback PASS;3 terminal isolated imports;helper stopped;old roots1695 unchanged')
