"""Prepare fresh owned tmpfs PG and committed public source, no customer reads."""
from pathlib import Path
import hashlib,json,subprocess,tarfile,io,time
P=Path(__file__).resolve().parent
REPO=P.parents[1]
OWNER='01a13484-f019-7d82-94ce-812396db9124'
D=['docker','--context','colima-aos-extension']
name='qyh-budget-renewal-b-native-20261014-r4-pg'
def run(args):return subprocess.check_output(D+args,text=True).strip()
intent=P/'native-b-fixture-intent-r4.json'
assert not intent.exists(),'existing attempt: reconcile same CID'
image=json.loads(run(['image','inspect','postgres:16-alpine']))[0]['Id']
assert image.startswith('sha256:7e7dbab8d3b4')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
assert head=='c5c06bd8110d611f30fb7a643160bcc4f76d6182'
freeze=P/'native-b-public-r4-latest';freeze.mkdir()
raw=subprocess.check_output(['git','archive',head,'services/aos-api','scripts/a0v_qyh_restored_http.py','scripts/a0v_current_preview_http.py'],cwd=REPO)
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:archive.extractall(freeze,filter='data')
files=['services/aos-api/aos_api/aip_budget_policy_renewal_'+n for n in ('connection.py','service.py','process.py','schema.json')]
files+=['services/aos-api/tests/aip/test_budget_policy_renewal_'+n for n in ('connection.py','service.py','process.py')]
for f in files:(freeze/f).write_bytes((REPO/f).read_bytes())
manifest={'head':head,'candidateFiles':{f:hashlib.sha256((freeze/f).read_bytes()).hexdigest() for f in files},'protectedDirtyCopied':False,'originalVolumeTouched':False}
(freeze/'freeze-manifest.json').write_text(json.dumps(manifest,indent=2))
with intent.open('x') as f:json.dump({'name':name,'owner':OWNER,'image':image,'tmpfsOnly':True,'publicFreeze':str(freeze),'originalVolumeTouched':False},f)
cid=run(['run','-d','--name',name,'--label','aos.owner='+OWNER,'--mount','type=tmpfs,destination=/var/lib/postgresql/data','-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust','-p','127.0.0.1::5432',image])
with (P/'native-b-fixture-created-r4.json').open('x') as f:json.dump({'cid':cid,'owner':OWNER},f)
for _ in range(50):
    if subprocess.run(D+['exec',cid,'pg_isready','-U','aos_app'],capture_output=True).returncode==0:break
    time.sleep(.2)
else:raise RuntimeError('readiness unknown; reconcile same CID')
info=json.loads(run(['inspect',cid]))[0]
assert info['State']['Running'] and info['Config']['Labels']['aos.owner']==OWNER
assert len(info['Mounts'])==1 and info['Mounts'][0]['Type']=='tmpfs'
bindings=info['NetworkSettings']['Ports']['5432/tcp'];assert len(bindings)==1 and bindings[0]['HostIp']=='127.0.0.1'
with (P/'native-b-fixture-ready-r4.json').open('x') as f:json.dump({'cid':cid,'owner':OWNER,'port':int(bindings[0]['HostPort']),'tmpfsOnly':True,'originalVolumeTouched':False},f)
print(json.dumps({'fixtureReady':True,'publicFreezeOnly':True,'port':int(bindings[0]['HostPort'])}))
