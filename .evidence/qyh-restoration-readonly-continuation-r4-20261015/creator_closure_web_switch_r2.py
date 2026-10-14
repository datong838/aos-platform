from pathlib import Path
import argparse,datetime,hashlib,json,os,signal,subprocess,sys,time
E=Path(__file__).resolve().parent;R=E.parents[1];HEAD='1627a39050cc5e8c88f223c56eb870f085091dd9';OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';OLD=64614;API=72678;NODE='/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node'
sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as gate
def read(p):return json.loads(p.read_text())
def cmd(*a):return subprocess.check_output(a,cwd=R,text=True,timeout=30).strip()
def save(n,v):
 with (E/n).open('x') as f:json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno())
def listeners(port):return sorted({int(x) for x in cmd('lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN').split()})
def cwd(pid):return next(x[1:] for x in cmd('lsof','-a','-p',str(pid),'-d','cwd','-Fn').splitlines() if x.startswith('n'))
def legal(folder,req,res,con):
 q=read(folder/req);v=read(folder/res);t=read((folder/res).with_suffix('.transport.json'));assert gate.consumption_record(q,v,t,v['runner_sha256'])==read(folder/con) and v['result']['verdict']=='PASS'
def base():
 assert cmd('git','rev-parse','HEAD')==HEAD and cmd('git','branch','--show-current')=='m1'
 m=R.parent/'docs/palantier/AOS项目开发上下文/memory';l=read(m/'receipts/tasks'/(E.name+'.json'));assert l in read(m/'leases.json')['leases'] and l['owner']==OWNER and l['base_revision']==read(m/'authority.json')['project_revision']=='AOS-002031' and datetime.datetime.fromisoformat(l['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
 assert listeners(18080)==[API] and cwd(API)==str(R/'.evidence/qyh-full-system-restoration-20261011/private/api-source-53d572ba3265d77835a49ee92441c7ce26ea7faa') and not cmd('git','diff','53d572ba3265d77835a49ee92441c7ce26ea7faa','HEAD','--','services/aos-api','scripts','bundles')
 assert listeners(18434)==[OLD] and cwd(OLD)==str(R) and cmd('ps','-p',str(OLD),'-o','command=')==NODE+' '+str(R/'.evidence/qyh-restoration-readonly-continuation-r3-20261014/daily-20261015/web-server.mjs')
 pg=json.loads(cmd('docker','--context','colima-aos-extension','inspect','qyh-restored-pg-20261011'))[0];assert pg['Id']=='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c' and pg['State']['Running'] and pg['State']['StartedAt']=='2026-10-14T20:36:36.408087963Z' and len(pg['Mounts'])==1 and pg['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
 legal(R/'.evidence/qyh-creator-closure-readonly-client-20261015','code-review-request-r3.json','code-review-result-r3.json','code-review-consumption-r3.json');legal(R/'.evidence/qyh-creator-closure-readonly-contract-20261015','code-review-request-r1.json','code-review-result-r1.json','code-review-consumption-r1.json')
 w=read(E/'creator-closure-web-source.json');s=Path(w['source']);assert w['head']==HEAD and w['port']==18434 and w['apiTarget']=='http://127.0.0.1:18080';assert {str(p.relative_to(s)):hashlib.sha256(p.read_bytes()).hexdigest() for p in s.rglob('*') if p.is_file()}==w['manifest'];assert all(hashlib.sha256((s/f).read_bytes()).hexdigest()==h for f,h in w['sourceHashes'].items())
 return w
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['preflight','web'],required=True);a=p.parse_args();web=base()
if a.phase=='preflight':save('web-preflight-r2.json',dict(head=HEAD,oldWebPid=OLD,apiPid=API,manifestVerified=True,sourceHashesVerified=True,otherServicesTouched=False));sys.exit(0)
req=read(E/'web-controller-review-request-r2.json');assert req['task_id']==E.name and req['owner']==OWNER;gate.validate_request(R,req);legal(E,'web-controller-review-request-r2.json','web-controller-review-result-r2.json','web-controller-review-consumption-r2.json');assert 'CONTROLLER_SHA '+hashlib.sha256(Path(__file__).read_bytes()).hexdigest() in (E/'web-controller-review-package-r2.txt').read_text()
assert not (E/'closure-web-switch-intent-r1.json').exists() and not (E/'closure-web-started-r1.json').exists();assert read(E/'web-preflight-r2.json')['head']==HEAD
entry=(R/'.evidence/qyh-restoration-readonly-continuation-r3-20261014/daily-20261015/web-server.mjs').read_text().replace("'web-source.json'","'creator-closure-web-source.json'").replace('private/daily-vite-cache','private/creator-closure-vite-cache');server=E/'creator-closure-web-server.mjs';assert not server.exists();server.write_text(entry)
save('closure-web-switch-intent-r1.json',dict(head=HEAD,oldPid=OLD,source=web['source'],pgApiChromeTouched=False));os.kill(OLD,signal.SIGTERM)
for _ in range(100):
 r=subprocess.run(['lsof','-t','-nP','-iTCP:18434','-sTCP:LISTEN'],capture_output=True,text=True)
 if not r.stdout.strip():break
 time.sleep(.2)
else:raise RuntimeError('stop unknown: reconcile only')
save('closure-web-old-stop-r1.json',dict(oldPid=OLD,portFree=True))
env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG','VITE_'))}
with (E/'creator-closure-live-web-r1.log').open('x') as log:proc=subprocess.Popen([NODE,str(server)],cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
save('closure-web-started-r1.json',dict(head=HEAD,pid=proc.pid,source=web['source'],spawnedOnly=True));print(dict(webPid=proc.pid,spawnedOnly=True))
