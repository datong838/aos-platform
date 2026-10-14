"""Daily same-volume PG->API->Web; fresh durable intents, never replay."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,signal,subprocess,sys,time
sys.dont_write_bytecode=True
P=Path(__file__).resolve().parent;E=P.parent;R=P.parents[2];F=R/'.evidence/qyh-full-system-restoration-20261011'
TASK=E.name;OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';PG='qyh-restored-pg-20261011';CID='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c';VOL='aos-qyh-history159-prepared-data-20261011'
NODE='/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node';PY=R/'services/aos-api/.venv/bin/python'
def read(p):return json.loads(p.read_text())
def command(*a):return subprocess.check_output(list(a),cwd=R,text=True,timeout=30).strip()
def record(n,v):
 with (P/n).open('x') as f:json.dump(v,f,indent=2);f.flush();os.fsync(f.fileno())
def listeners(port):
 r=subprocess.run(['lsof','-t','-nP',f'-iTCP:{port}','-sTCP:LISTEN'],capture_output=True,text=True);return sorted({int(x) for x in r.stdout.split()})
def cwd(pid):return next(x[1:] for x in command('lsof','-a','-p',str(pid),'-d','cwd','-Fn').splitlines() if x.startswith('n'))
def pg():
 x=readjson= json.loads(command('docker','--context','colima-aos-extension','inspect',PG))[0]
 assert x['Id']==CID and x['State']['Running'] and len(x['Mounts'])==1 and x['Mounts'][0]['Name']==VOL and x['NetworkSettings']['Ports']['5432/tcp']==[dict(HostIp='127.0.0.1',HostPort='18446')]
 return x
def stop(pid,port,path):
 assert listeners(port)==[pid] and cwd(pid)==path
 assert command('ps','-p',str(pid),'-o','command=')==cfg['oldApiCommand' if port==18080 else 'oldWebCommand']
 os.kill(pid,signal.SIGTERM)
 for _ in range(100):
  if not listeners(port):return
  time.sleep(.2)
 raise RuntimeError('stop unresolved; reconcile only')
def quality():
 sys.path.insert(0,str(R/'scripts/long-task-watchdog'));import aos_review as gate
 request=read(P/'controller-review-request.json');assert request['task_id']==TASK and request['owner']==OWNER and request['kind']=='quality'
 assert request['materials'][str((P/'controller-review-package.txt').relative_to(R))]==(P/'controller-review-package.txt').read_text()
 gate.validate_request(R,request)
 r=read(P/'controller-review-result.json');c=read(P/'controller-review-consumption.json')
 transport=read(P/'controller-review-result.transport.json')
 runner=Path(cfg['reviewRunner']);assert runner.is_file() and runner.resolve().is_relative_to(E.resolve())
 assert r['validator_sha256']==hashlib.sha256(Path(gate.__file__).read_bytes()).hexdigest()
 assert gate.consumption_record(request,r,transport,hashlib.sha256(runner.read_bytes()).hexdigest())==c
 assert r['result']['verdict']=='PASS' and c['status']=='CONSUMED_MATERIAL_REVIEW'
 assert 'CONTROLLER_SHA '+hashlib.sha256(Path(__file__).read_bytes()).hexdigest() in (P/'controller-review-package.txt').read_text()
def fingerprint(report,started):
 assert report['containerId']==CID and report['volume']==VOL and report['pgStartedAt']==started
 assert report['native']['cluster']=='7695302940039200809' and report['native']['schema']=='a0v_161' and report['native']['enabledBindings']==0 and len(report['fingerprints'])==650
def base():
 cfg=read(P/'config.json');assert cfg['head']==command('git','rev-parse','HEAD') and command('git','branch','--show-current')=='m1'
 m=R.parent/'docs/palantier/AOS项目开发上下文/memory';lease=[x for x in read(m/'leases.json')['leases'] if x['task_id']==TASK];assert len(lease)==1 and lease[0]['owner']==OWNER and lease[0]['base_revision']==read(m/'authority.json')['project_revision']=='AOS-002030' and datetime.datetime.fromisoformat(lease[0]['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
 sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
 report=Path(cfg['apiReport']);source=guard.require_api_source_candidate(report);r=read(report);assert r['head']==cfg['head'] and r['startupFlags']['AOS_DB_MIGRATION_MODE']=='disabled' and r['startupFlags']['AOS_EXTENSION_RUNTIME_HOST_ENABLED']=='0'
 web=read(Path(cfg['webReport']));w=Path(web['source']);assert web['head']==cfg['head'] and web['port']==18434 and web['apiTarget']=='http://127.0.0.1:18080';assert {str(p.relative_to(w)):hashlib.sha256(p.read_bytes()).hexdigest() for p in w.rglob('*') if p.is_file()}==web['manifest']
 return cfg,source,web
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['preflight','pg','api','web'],required=True);a=parser.parse_args();cfg,source,web=base();x=pg()
assert not (P/(a.phase+'-intent.json')).exists() and not (P/(a.phase+'-terminal.json')).exists(),'known phase: reconcile never replay'
if a.phase=='preflight':
 assert listeners(18080)==[cfg['oldApiPid']] and cwd(cfg['oldApiPid'])==cfg['oldApiCwd'];assert listeners(18434)==[cfg['oldWebPid']] and cwd(cfg['oldWebPid'])==str(R)
 assert command('ps','-p',str(cfg['oldApiPid']),'-o','command=')==cfg['oldApiCommand'] and command('ps','-p',str(cfg['oldWebPid']),'-o','command=')==cfg['oldWebCommand']
 before=read(Path(cfg['beforeFingerprint']));fingerprint(before,x['State']['StartedAt'])
 assert read(R/'.evidence/qyh-restoration-successor-latest-restart-20261013/backup-readback.json')['existingTwoBackupCopiesReadbackEqual']
 record('preflight-terminal.json',dict(head=cfg['head'],containerId=CID,volume=VOL,apiPid=cfg['oldApiPid'],webPid=cfg['oldWebPid'],fullSourceGuard=True,serviceEffects=False));sys.exit(0)
quality();assert read(P/'preflight-terminal.json')['head']==cfg['head']
if a.phase=='pg':
 fingerprint(read(Path(cfg['beforeFingerprint'])),x['State']['StartedAt'])
 assert listeners(18080)==[cfg['oldApiPid']] and cwd(cfg['oldApiPid'])==cfg['oldApiCwd'] and command('ps','-p',str(cfg['oldApiPid']),'-o','command=')==cfg['oldApiCommand']
 assert listeners(18434)==[cfg['oldWebPid']] and cwd(cfg['oldWebPid'])==str(R) and command('ps','-p',str(cfg['oldWebPid']),'-o','command=')==cfg['oldWebCommand']
 record('pg-intent.json',dict(containerId=CID,volume=VOL,startedBefore=x['State']['StartedAt'],noMigration=True))
 res=subprocess.run(['docker','--context','colima-aos-extension','restart','--time','30',PG],capture_output=True,text=True,timeout=60);assert res.returncode==0
 y=pg();assert y['State']['StartedAt']!=x['State']['StartedAt'];record('pg-terminal.json',dict(containerId=CID,volume=VOL,startedAfter=y['State']['StartedAt'],noMigration=True))
elif a.phase=='api':
 terminal=read(P/'pg-terminal.json');assert terminal['containerId']==CID and terminal['volume']==VOL and terminal['startedAfter']==x['State']['StartedAt']
 before=read(Path(cfg['beforeFingerprint']));after=read(Path(cfg['afterPgFingerprint']));fingerprint(before,read(P/'pg-intent.json')['startedBefore']);fingerprint(after,terminal['startedAfter']);assert before['fingerprints']==after['fingerprints']
 record('api-intent.json',dict(oldPid=cfg['oldApiPid'],head=cfg['head'],source=str(source),readonly=True));stop(cfg['oldApiPid'],18080,cfg['oldApiCwd']);record('api-old-stop.json',dict(portFree=True))
 args=[str(PY),str(R/'scripts/a0v_qyh_restored_http.py'),'--api-identity-file',str(F/'private/restored-identity.json'),'--serve-management-readonly','--bundle-root',str(F/'selected-public-bundles'),'--trust-roots-file',str(F/'restoration-public-trust-roots.json'),'--source-candidate',cfg['apiReport'],'--management-oidc-config','/Users/ddt/.aos-local-identities/qyh-20261013/aos-management-oidc.json','--installed-readonly-installation','ab2fd72f-d81c-400d-bbbc-e1589a159d6b']
 with (P/'live-api.log').open('x') as log:proc=subprocess.Popen(args,cwd=R,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 record('api-started.json',dict(pid=proc.pid,head=cfg['head'],source=str(source),spawnedOnly=True));print(dict(apiPid=proc.pid,spawnedOnly=True))
else:
 api=read(P/'api-started.json');assert listeners(18080)==[api['pid']] and cwd(api['pid'])==str(source)
 entry=(E/'creator-workflow-web-server.mjs').read_text().replace("'creator-workflow-web-source.json'","'web-source.json'").replace('private/creator-workflow-vite-cache','private/daily-vite-cache');server=P/'web-server.mjs';assert not server.exists();server.write_text(entry)
 record('web-intent.json',dict(oldPid=cfg['oldWebPid'],head=cfg['head'],source=web['source']));stop(cfg['oldWebPid'],18434,str(R));record('web-old-stop.json',dict(portFree=True))
 env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG','VITE_'))};env['PYTHONDONTWRITEBYTECODE']='1'
 with (P/'live-web.log').open('x') as log:proc=subprocess.Popen([NODE,str(server)],cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 record('web-started.json',dict(pid=proc.pid,head=cfg['head'],source=web['source'],spawnedOnly=True));print(dict(webPid=proc.pid,spawnedOnly=True))
