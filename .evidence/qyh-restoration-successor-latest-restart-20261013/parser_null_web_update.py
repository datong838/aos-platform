"""One-attempt owned latest frozen Web-only update after exact consumed PASS."""
from pathlib import Path
import json,hashlib,subprocess,os,signal,time,sys,io,tarfile,datetime
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent
Q=R/'.evidence/qyh-investigation-null-receipt-parser-20261013'
NODE='/Users/ddt/.workbuddy/binaries/node/versions/22.22.2-2/bin/node'
def cmd(*a):return subprocess.check_output(list(a),text=True).strip()
def record(n,v):
 with (P/n).open('x') as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def listeners(port):
 v=subprocess.run(['lsof','-t','-nP','-iTCP:'+str(port),'-sTCP:LISTEN'],capture_output=True,text=True)
 return sorted({int(x) for x in v.stdout.split()})
def cwd(pid):return next(x[1:] for x in cmd('lsof','-a','-p',str(pid),'-d','cwd','-Fn').splitlines() if x.startswith('n'))
assert not (P/'parser-null-web-intent.json').exists() and not (P/'parser-null-web-started.json').exists(),'existing attempt:reconcile,never resend'
e=json.loads((Q/'review-result-r2.json').read_text());c=json.loads((Q/'review-consumption-r2.json').read_text())
assert e['result']['verdict']=='PASS' and c['status']=='CONSUMED_MATERIAL_REVIEW'
assert c['result_sha256']==hashlib.sha256(json.dumps(e,sort_keys=True).encode()).hexdigest()
ls=json.loads((R.parent/'docs/palantier/AOS项目开发上下文/memory/leases.json').read_text())['leases']
l=next(x for x in ls if x['task_id']==P.name);assert l['owner']=='codex-01a13484-f019-7d82-94ce-812396db9124' and datetime.datetime.fromisoformat(l['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
assert cmd('git','branch','--show-current')=='m1'
head=cmd('git','rev-parse','HEAD')
assert listeners(18434)==[81203] and cwd(81203)==str(R)
assert listeners(18080)==[1234]
sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
guard.require_api_source_candidate((R/'.evidence/qyh-full-system-restoration-20261011/successor-analyst-learning-r5-api-20261013.json').resolve())
old=json.loads((P/'web-source.json').read_text())
assert old['head']=='2324ba3916b39ed81d6527577f4d20ab3bd86071'
assert all(hashlib.sha256((Path(old['source'])/f).read_bytes()).hexdigest()==h for f,h in old['manifest'].items())
children=[line.split(maxsplit=2) for line in cmd('ps','-axo','pid=,ppid=,comm=').splitlines() if len(line.split(maxsplit=2))==3 and line.split(maxsplit=2)[1]=='81203']
assert len(children)<=1 and all(Path(x[2]).name=='esbuild' for x in children),'unexpected Web children:reconcile'
source=P/'private'/('web-source-'+head);assert not source.exists()
raw=subprocess.check_output(['git','archive',head,'apps/web','packages/ontology-sdk','packages/ui-kit'])
manifest={}
record('parser-null-web-intent.json',{'head':head,'oldPid':81203,'oldCwd':str(R),'oldChildren':[int(x[0]) for x in children],'source':str(source),'apiPgChromeTouched':False,'exactConsumedPass':True})
source.mkdir(parents=True,mode=0o700)
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
 for item in archive.getmembers():
  rel=Path(item.name);assert not rel.is_absolute() and '..' not in rel.parts and (item.isfile() or item.isdir())
  if not item.isfile() or any(x.startswith('.env') for x in rel.parts):continue
  data=archive.extractfile(item).read();dest=source/rel;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700);dest.write_bytes(data);dest.chmod(0o600);manifest[item.name]=hashlib.sha256(data).hexdigest()
assert {str(x.relative_to(source)):hashlib.sha256(x.read_bytes()).hexdigest() for x in source.rglob('*') if x.is_file()}==manifest
(source/'apps/web/node_modules').symlink_to(R/'apps/web/node_modules',target_is_directory=True)
report={'head':head,'source':str(source),'manifest':manifest,'port':18434,'apiTarget':'http://127.0.0.1:18080','dirtyCopied':False,'credentialsCopied':False}
record('parser-null-web-source.json',report)
entry=(P/'web-server.mjs').read_text().replace("'web-source.json'","'parser-null-web-source.json'").replace('private/latest-vite-cache','private/parser-null-vite-cache')
server=P/'parser-null-web-server.mjs';assert not server.exists();server.write_text(entry)
# All checks and frozen source precede the only exact owned process signal.
assert listeners(18434)==[81203] and cwd(81203)==str(R)
os.kill(81203,signal.SIGTERM)
for _ in range(100):
 if not listeners(18434):break
 time.sleep(.2)
assert not listeners(18434),'stop outcome unsettled:readonly reconcile'
record('parser-null-web-old-stop.json',{'oldPid':81203,'portFree':True})
env={k:v for k,v in os.environ.items() if not k.startswith(('AOS_','PG','VITE_'))};env['PYTHONDONTWRITEBYTECODE']='1'
with (P/'live-web-parser-null.log').open('x') as log:proc=subprocess.Popen([NODE,str(server)],cwd=R,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
record('parser-null-web-started.json',{'pid':proc.pid,'head':head,'source':str(source),'port':18434,'terminalVerified':False,'apiPgChromeTouched':False,'webOnlyNotFullRestart':True})
print(json.dumps({'newWebPid':proc.pid,'head':head,'spawnedOnly':True,'apiPgChromeTouched':False}))
