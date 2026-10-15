"""Fresh original-scope API-only readonly switch, no PG/Web/Chrome signal."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,signal,subprocess,sys,time
E=Path(__file__).resolve().parent;R=E.parents[1];F=R/'.evidence/qyh-full-system-restoration-20261011';HEAD='4e038063368cc41fe17aec7b9f6148fa66bd7192';OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';OLD=80779;WEB=89803
OLD_SOURCE=F/'private/api-source-246d8305332c143bd281cc6aedb013649b81f7d6';REPORT=F/'price-disposition-api-20261015.json';CID='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c'
def read(p):return json.loads(p.read_text())
def cmd(*args):return subprocess.check_output(args,cwd=R,text=True,timeout=30).strip()
def save(n,v):
 with (E/n).open('x') as f:json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno())
def listeners(port):return sorted({int(x) for x in cmd('lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN').split()})
def cwd(pid):return next(x[1:] for x in cmd('lsof','-a','-p',str(pid),'-d','cwd','-Fn').splitlines() if x.startswith('n'))
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as gate
sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard

def legal(folder,request,result,consume):
 req=read(folder/request);env=read(folder/result);transport=read((folder/result).with_suffix('.transport.json'));assert gate.consumption_record(req,env,transport,env['runner_sha256'])==read(folder/consume) and env['result']['verdict']=='PASS'
def base():
 assert cmd('git','rev-parse','HEAD')==HEAD and cmd('git','branch','--show-current')=='m1'
 m=R.parent/'docs/palantier/AOS项目开发上下文/memory';lease=read(m/'receipts/tasks'/(E.name+'.json'));assert lease in read(m/'leases.json')['leases'] and lease['owner']==OWNER and lease['base_revision']==read(m/'authority.json')['project_revision']=='AOS-002034' and datetime.datetime.fromisoformat(lease['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
 source=guard.require_api_source_candidate(REPORT);assert read(REPORT)['head']==HEAD
 legal(R/'.evidence/qyh-price-disposition-read-admission-r2-20261015','route-quality-request-r2.json','route-quality-result-r2.json','route-quality-consumption-r2.json')
 legal(R/'.evidence/qyh-price-disposition-bounded-reader-20261015','code-review-request-r2.json','code-review-result-r2.json','code-review-consumption-r2.json')
 hashes=read(R/'.evidence/qyh-price-disposition-bounded-reader-20261015/source-verification-r1.json')['sourceAfter'];assert all(hashlib.sha256((source/f).read_bytes()).hexdigest()==sha for f,sha in hashes.items())
 pg=json.loads(cmd('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0];assert pg['Id']==CID and pg['State']['Running'] and len(pg['Mounts'])==1 and pg['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011' and pg['State']['StartedAt']=='2026-10-14T20:36:36.408087963Z'
 assert cmd('ps','-p',str(WEB),'-o','command=')==str(Path('/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node'))+' '+str(R/'.evidence/qyh-restoration-readonly-continuation-r6-20261015/price-visual-web-server.mjs')
 assert listeners(18434)==[WEB] and cwd(WEB)==str(R) and not cmd('git','diff','f036e46c643308651b415179e6e991870dbc26ab','HEAD','--','apps/web')
 return source,pg

def old():
 assert listeners(18080)==[OLD] and cwd(OLD)==str(OLD_SOURCE)
 assert cmd('ps','-p',str(OLD),'-o','command=')==str(R/'services/aos-api/.venv/bin/python')+' -m uvicorn a0v_qyh_restored_http:management_app --factory --host 127.0.0.1 --port 18080 --workers 1 --no-access-log --log-level warning'

def quality():
 req=read(E/'api-controller-review-request-r3.json');assert req['task_id']==E.name and req['owner']==OWNER;gate.validate_request(R,req)
 legal(E,'api-controller-review-request-r3.json','api-controller-review-result-r3.json','api-controller-review-consumption-r3.json')
 assert 'CONTROLLER_SHA '+hashlib.sha256(Path(__file__).read_bytes()).hexdigest() in (E/'api-controller-review-package-r3.txt').read_text()
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['preflight','api'],required=True);a=parser.parse_args();source,pg=base();old()
if a.phase=='preflight':
 before=read(R/'.evidence/qyh-restoration-successor-latest-restart-20261013/price-disposition-before-20261015.json');assert before['containerId']==CID and before['pgStartedAt']==pg['State']['StartedAt'] and before['native']['schema']=='a0v_161' and before['native']['enabledBindings']==0 and len(before['fingerprints'])==650
 native=guard.preflight(F/'private/restored-identity.json',management_readonly=True)
 save('api-preflight-r3.json',dict(nativeManagementReadonly=native,head=HEAD,apiPid=OLD,apiCwd=str(OLD_SOURCE),webPid=WEB,pgStartedAt=pg['State']['StartedAt'],sourceGuard=True,ownedCodeHashesVerified=True,serviceEffects=False));sys.exit(0)
quality();assert not (E/'api-switch-intent-r1.json').exists() and not (E/'api-started-r1.json').exists(),'known intent: reconcile no replay'
assert read(E/'api-preflight-r3.json')['head']==HEAD
save('api-switch-intent-r1.json',dict(head=HEAD,oldPid=OLD,oldCwd=str(OLD_SOURCE),source=str(source),pgWebChromeTouched=False))
os.kill(OLD,signal.SIGTERM)
for _ in range(100):
 result=subprocess.run(['lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN'],capture_output=True,text=True)
 if not result.stdout.strip():break
 time.sleep(.2)
else:raise RuntimeError('stop unresolved; reconcile no resend')
save('api-old-stop-r1.json',dict(oldPid=OLD,portFree=True))
args=[str(R/'services/aos-api/.venv/bin/python'),str(R/'scripts/a0v_qyh_restored_http.py'),'--api-identity-file',str(F/'private/restored-identity.json'),'--serve-management-readonly','--bundle-root',str(F/'selected-public-bundles'),'--trust-roots-file',str(F/'restoration-public-trust-roots.json'),'--source-candidate',str(REPORT),'--management-oidc-config','/Users/ddt/.aos-local-identities/qyh-20261013/aos-management-oidc.json','--installed-readonly-installation','ab2fd72f-d81c-400d-bbbc-e1589a159d6b']
with (E/'price-disposition-live-api-r1.log').open('x') as log:proc=subprocess.Popen(args,cwd=R,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
save('api-started-r1.json',dict(pid=proc.pid,head=HEAD,source=str(source),spawnedOnly=True));print(dict(apiPid=proc.pid,spawnedOnly=True))
