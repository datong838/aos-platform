"""One-intent-per-phase exact existing-volume restart through original guarded entry."""
from pathlib import Path
import argparse,datetime,hashlib,io,json,os,signal,subprocess,sys,tarfile,time
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent;F=R/'.evidence/qyh-full-system-restoration-20261011'
TASK=P.name;OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';PG='qyh-restored-pg-20261011';CID='84989681fb7d3fc0f42d750672547ca0208fbba08dfef0d93837d8e64245dc3c';VOL='aos-qyh-history159-prepared-data-20261011'
PY=R/'services/aos-api/.venv/bin/python';NODE=Path('/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node')
API_REPORT=F/'successor-media-current-api-20261013.json'
def command(*args):return subprocess.check_output(list(args),text=True,timeout=30).strip()
def record(name,value):
 with (P/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def lease():
 m=R.parent/'docs/palantier/AOS项目开发上下文/memory';ls=json.loads((m/'leases.json').read_text())['leases'];x=[l for l in ls if l['task_id']==TASK];assert len(x)==1 and x[0]['owner']==OWNER and datetime.datetime.fromisoformat(x[0]['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc);assert not any(l['task_id']=='qyh-full-system-restoration-20261011' for l in ls)
def pg():
 x=json.loads(command('docker','--context','colima-aos-extension','inspect',PG))[0];assert x['Id']==CID and len(x['Mounts'])==1 and x['Mounts'][0]['Name']==VOL and x['NetworkSettings']['Ports']['5432/tcp']==[{'HostIp':'127.0.0.1','HostPort':'18446'}];return x
def cwd(pid):
 s=command('lsof','-a','-p',str(pid),'-d','cwd','-Fn');return next(x[1:] for x in s.splitlines() if x.startswith('n'))
def listeners(port):
 p=subprocess.run(['lsof','-t','-nP','-iTCP:'+str(port),'-sTCP:LISTEN'],text=True,capture_output=True);return sorted({int(x) for x in p.stdout.split()})
def stop(pid,port,expected_cwd):
 assert listeners(port)==[pid] and cwd(pid)==expected_cwd
 os.kill(pid,signal.SIGTERM)
 for _ in range(100):
  if not listeners(port):return
  time.sleep(.2)
 raise RuntimeError('known stop has not settled; reconcile existing PID, do not resend')
def original_guard():
 sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
 assert guard.require_api_source_candidate(API_REPORT.resolve())==Path(json.loads(API_REPORT.read_text())['source']);return guard
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['prepare','pg','api','web'],required=True);a=parser.parse_args();lease()
assert not (P/(a.phase+'-intent.json')).exists() and not (P/(a.phase+'-terminal.json')).exists(),'existing phase: readonly reconcile,never resend'
r=json.loads(API_REPORT.read_text());assert r['head']==command('git','rev-parse','HEAD') and r['outcome']=='CURRENT_M1_API_SOURCE_CANDIDATE_FROZEN_NO_START'
assert r['startupFlags']['AOS_EXTENSION_RUNTIME_HOST_ENABLED']=='0' and r['startupFlags']['AOS_DB_MIGRATION_MODE']=='disabled';assert all(r['startupFlags'][k] in ['false','0'] for k in r['explicitStartupEnabledSwitches']);original_guard();x=pg();assert x['State']['Running']
if a.phase=='prepare':
 before=json.loads((P/'before-restart.json').read_text());assert before['native']['schema']=='a0v_161' and before['native']['enabledBindings']==0 and len(before['fingerprints'])==650
 assert listeners(18080)==[58363] and cwd(58363)==str(F/'private/api-source-ceba8ba4c63bcfa8c3690d6f05d24cb1ed6a5f08');assert listeners(18434)==[58523] and cwd(58523)==str(R)
 b=json.loads((P/'backup-readback.json').read_text());assert b['existingTwoBackupCopiesReadbackEqual']
 source=P/'private'/('web-source-'+r['head']);assert not source.exists();raw=subprocess.check_output(['git','archive',r['head'],'apps/web','packages/ontology-sdk','packages/ui-kit'],cwd=R,timeout=60);manifest={}
 with tarfile.open(fileobj=io.BytesIO(raw)) as t:
  members=t.getmembers();assert all(not Path(m.name).is_absolute() and '..' not in Path(m.name).parts and (m.isfile() or m.isdir()) for m in members)
  record('prepare-intent.json',{'head':r['head'],'volume':VOL,'oldApiPid':58363,'oldWebPid':58523,'apiCwd':cwd(58363),'webCwd':cwd(58523),'newWebSource':str(source),'noServiceActions':True})
  source.mkdir(parents=True,mode=0o700)
  for member in members:
   if not member.isfile() or any(part.startswith('.env') for part in Path(member.name).parts):continue
   data=t.extractfile(member).read();p=source/member.name;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700);p.write_bytes(data);p.chmod(0o600);manifest[member.name]=hashlib.sha256(data).hexdigest()
 assert {str(p.relative_to(source)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}==manifest
 (source/'apps/web/node_modules').symlink_to(R/'apps/web/node_modules',target_is_directory=True)
 report={'head':r['head'],'source':str(source),'manifest':manifest,'port':18434,'apiTarget':'http://127.0.0.1:18080','dirtyCopied':False,'credentialsCopied':False};record('web-source.json',report)
 entry=(F/'restart-20261013-032343-web.mjs').read_text().replace('restart-20261013-032343-web.json','web-source.json').replace('restart-20261013-032343-vite-cache','latest-vite-cache');(P/'web-server.mjs').write_text(entry)
 record('prepare-terminal.json',{'head':r['head'],'webFiles':len(manifest),'allCurrentSourceGuardPassed':True,'noServiceActions':True})
else:
 prep=json.loads((P/'prepare-terminal.json').read_text());assert prep['head']==r['head']
 if a.phase=='pg':
  record('pg-intent.json',{'target':CID,'volume':VOL,'startedBefore':x['State']['StartedAt'],'schema':'a0v_161','noMigration':True})
  res=subprocess.run(['docker','--context','colima-aos-extension','restart','--time','30',PG],text=True,capture_output=True,timeout=60);assert res.returncode==0
  y=pg();assert y['State']['Running'] and y['State']['StartedAt']!=x['State']['StartedAt'];record('pg-terminal.json',{'containerId':y['Id'],'volume':VOL,'startedBefore':x['State']['StartedAt'],'startedAfter':y['State']['StartedAt'],'restartReturnCode':0,'schemaWriteOrMigration':False})
 if a.phase=='api':
  after=json.loads((P/'after-pg-restart.json').read_text());before=json.loads((P/'before-restart.json').read_text());assert after['fingerprints']==before['fingerprints'] and after['native']['enabledBindings']==0
  args=[str(PY),str(R/'scripts/a0v_qyh_restored_http.py'),'--api-identity-file',str(F/'private/restored-identity.json'),'--serve-management-readonly','--bundle-root',str(F/'selected-public-bundles'),'--trust-roots-file',str(F/'restoration-public-trust-roots.json'),'--source-candidate',str(API_REPORT),'--management-oidc-config','/Users/ddt/.aos-local-identities/qyh-20261013/aos-management-oidc.json','--installed-readonly-installation','ab2fd72f-d81c-400d-bbbc-e1589a159d6b']
  record('api-intent.json',{'head':r['head'],'oldPid':58363,'oldCwd':cwd(58363),'source':r['source'],'readonly':True,'port':18080,'noUnknownReplay':True});stop(58363,18080,str(F/'private/api-source-ceba8ba4c63bcfa8c3690d6f05d24cb1ed6a5f08'));record('api-old-stop.json',{'oldPid':58363,'portFree':not listeners(18080)})
  env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
  with (P/'live-api.log').open('x') as log:proc=subprocess.Popen(args,cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  record('api-started.json',{'pid':proc.pid,'head':r['head'],'port':18080,'source':r['source'],'terminalVerified':False});print(json.dumps({'phase':'api','pid':proc.pid,'spawnedOnly':True}));sys.exit(0)
 if a.phase=='web':
  api=json.loads((P/'api-started.json').read_text());assert listeners(18080)==[api['pid']] and cwd(api['pid'])==r['source']
  record('web-intent.json',{'oldPid':58523,'oldCwd':cwd(58523),'head':r['head'],'port':18434});stop(58523,18434,str(R));record('web-old-stop.json',{'oldPid':58523,'portFree':not listeners(18434)})
  env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG','VITE_'))};env['PYTHONDONTWRITEBYTECODE']='1'
  with (P/'live-web.log').open('x') as log:proc=subprocess.Popen([str(NODE),str(P/'web-server.mjs')],cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  record('web-started.json',{'pid':proc.pid,'head':r['head'],'port':18434,'terminalVerified':False});print(json.dumps({'phase':'web','pid':proc.pid,'spawnedOnly':True}));sys.exit(0)
print(json.dumps({'phase':a.phase,'outcome':'TERMINAL_RECORDED','servicesStarted':False if a.phase=='prepare' else None}))
