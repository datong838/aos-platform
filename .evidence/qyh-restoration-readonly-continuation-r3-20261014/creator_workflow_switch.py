"""Fresh reviewed phases; no replay of an existing phase intent."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,signal,subprocess,sys,time
sys.dont_write_bytecode=True
E=Path(__file__).resolve().parent;R=E.parents[1];F=R/'.evidence/qyh-full-system-restoration-20261011'
HEAD='ce1f8258c863a2dae3baddadb1b5d2fa9557ea3d';OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';NODE='/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node'
OLDAPI=25389;OLDWEB=78346;OLDAPISOURCE=F/'private/api-source-f005a195265f4590d9214a810a24fbec0d15ab32'
REPORT=F/'creator-workflow-api-20261014.json'
def read(p):return json.loads(p.read_text())
def command(*a):return subprocess.check_output(list(a),cwd=R,text=True).strip()
def listeners(port):
 r=subprocess.run(['lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True,text=True);return sorted({int(p) for p in r.stdout.split()})
def cwd(pid):return next(x[1:] for x in command('lsof','-a','-p',str(pid),'-d','cwd','-Fn').splitlines() if x.startswith('n'))
def save(name,data):
 with (E/name).open('x') as f:json.dump(data,f,indent=2);f.flush();os.fsync(f.fileno())
def base():
 assert command('git','rev-parse','HEAD')==HEAD and command('git','branch','--show-current')=='m1'
 m=R.parent/'docs/palantier/AOS项目开发上下文/memory';leases=[x for x in read(m/'leases.json')['leases'] if x['task_id']==E.name]
 assert len(leases)==1 and leases[0]['owner']==OWNER and leases[0]['base_revision']==read(m/'authority.json')['project_revision']=='AOS-002030'
 assert datetime.datetime.fromisoformat(leases[0]['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
 for name,v in [('qyh-creator-workflow-read-admission-20261014','r1'),('qyh-creator-workflow-read-failure-ui-20261014','r1'),('qyh-creator-workflow-read-failure-ui-20261014','r2')]:
  q=R/'.evidence'/name;r=read(q/f'code-review-result-{v}.json');c=read(q/f'code-review-consumption-{v}.json')
  assert r['result']['verdict']=='PASS' and c['status']=='CONSUMED_MATERIAL_REVIEW' and c['result_sha256']==hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()
 sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
 source=guard.require_api_source_candidate(REPORT.resolve());assert read(REPORT)['head']==HEAD
 q=R/'.evidence/qyh-creator-workflow-read-admission-20261014';material=(q/'code-review-package-r1.txt').read_text();hashes=json.loads(material.split('CURRENT full source hashes ')[1])
 assert all(hashlib.sha256((source/f).read_bytes()).hexdigest()==h for f,h in hashes.items())
 web=read(E/'creator-workflow-web-source.json');w=Path(web['source']);assert web['head']==HEAD and web['port']==18434 and web['apiTarget']=='http://127.0.0.1:18080'
 observed={str(p.relative_to(w)):hashlib.sha256(p.read_bytes()).hexdigest() for p in w.rglob('*') if p.is_file()};assert observed==web['manifest']
 u=read(R/'.evidence/qyh-creator-workflow-read-failure-ui-20261014/complete-code-review-manifest.json');assert all(hashlib.sha256((w/f).read_bytes()).hexdigest()==h for f,h in u['sourceHashes'].items())
 return source,web,leases[0]
def oldweb():
 assert listeners(18434)==[OLDWEB] and cwd(OLDWEB)==str(R)
 assert command('ps','-p',str(OLDWEB),'-o','command=')==str(NODE)+' '+str(R/'.evidence/qyh-restoration-successor-latest-restart-20261013/daily-20261014-r2/web-server.mjs')
 old=read(R/'.evidence/qyh-restoration-successor-latest-restart-20261013/daily-20261014-r2/web-source.json');assert old['head']=='6c9b65777eec4ab0688fa50a318e40b0a9b05d9b'
def reviewed_controller():
 r=read(E/'switch-review-result-r3.json');c=read(E/'switch-review-consumption-r3.json');assert r['result']['verdict']=='PASS' and c['status']=='CONSUMED_MATERIAL_REVIEW' and c['result_sha256']==hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest()
 frozen=(E/'switch-review-package-r3.txt').read_text();assert 'CONTROLLER_SOURCE_SHA256 '+hashlib.sha256(Path(__file__).read_bytes()).hexdigest() in frozen
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['preflight','api','web'],required=True);a=parser.parse_args()
source,web,lease=base()
if a.phase=='preflight':
 assert listeners(18080)==[OLDAPI] and cwd(OLDAPI)==str(OLDAPISOURCE);oldweb()
 save('switch-preflight-r1.json',dict(head=HEAD,lease=lease,apiPid=OLDAPI,apiCwd=str(OLDAPISOURCE),webPid=OLDWEB,webCwd=str(R),sourceGuard=True,webManifestVerified=True,allProductHashesVerified=True,signal=False,pgChromeTouched=False))
elif a.phase=='api':
 reviewed_controller();assert not (E/'api-switch-intent-r1.json').exists() and not (E/'api-started-r1.json').exists(),'existing phase:reconcile only'
 assert listeners(18080)==[OLDAPI] and cwd(OLDAPI)==str(OLDAPISOURCE);oldweb()
 save('api-switch-intent-r1.json',dict(oldPid=OLDAPI,oldCwd=str(OLDAPISOURCE),head=HEAD,source=str(source),pgWebChromeTouched=False))
 os.kill(OLDAPI,signal.SIGTERM)
 for _ in range(100):
  if not listeners(18080):break
  time.sleep(.2)
 assert not listeners(18080),'stop unresolved:never signal again'
 save('api-old-stop-r1.json',dict(oldPid=OLDAPI,portFree=True))
 args=[str(R/'services/aos-api/.venv/bin/python'),str(R/'scripts/a0v_qyh_restored_http.py'),'--api-identity-file',str(F/'private/restored-identity.json'),'--serve-management-readonly','--bundle-root',str(F/'selected-public-bundles'),'--trust-roots-file',str(F/'restoration-public-trust-roots.json'),'--source-candidate',str(REPORT),'--management-oidc-config','/Users/ddt/.aos-local-identities/qyh-20261013/aos-management-oidc.json','--installed-readonly-installation','ab2fd72f-d81c-400d-bbbc-e1589a159d6b']
 with (E/'live-api-r1.log').open('x') as log:proc=subprocess.Popen(args,cwd=R,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 save('api-started-r1.json',dict(pid=proc.pid,head=HEAD,source=str(source),spawnedOnly=True));print(dict(apiPid=proc.pid,spawnedOnly=True))
else:
 reviewed_controller();assert not (E/'web-switch-intent-r1.json').exists() and not (E/'web-started-r1.json').exists(),'existing phase:reconcile only'
 api=read(E/'api-started-r1.json');assert listeners(18080)==[api['pid']] and cwd(api['pid'])==str(source);oldweb()
 entry=(R/'.evidence/qyh-restoration-successor-latest-restart-20261013/daily-20261014-r2/web-server.mjs').read_text().replace("'web-source.json'","'creator-workflow-web-source.json'").replace('private/latest-vite-cache','private/creator-workflow-vite-cache')
 server=E/'creator-workflow-web-server.mjs';assert not server.exists();server.write_text(entry)
 save('web-switch-intent-r1.json',dict(oldPid=OLDWEB,head=HEAD,source=web['source'],pgChromeTouched=False,apiAlreadyListening=api['pid']))
 os.kill(OLDWEB,signal.SIGTERM)
 for _ in range(100):
  if not listeners(18434):break
  time.sleep(.2)
 assert not listeners(18434),'stop unresolved:reconcile only'
 save('web-old-stop-r1.json',dict(oldPid=OLDWEB,portFree=True))
 env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG','VITE_'))};env['PYTHONDONTWRITEBYTECODE']='1'
 with (E/'live-web-r1.log').open('x') as log:proc=subprocess.Popen([NODE,str(server)],cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 save('web-started-r1.json',dict(pid=proc.pid,head=HEAD,source=web['source'],spawnedOnly=True));print(dict(webPid=proc.pid,spawnedOnly=True))
