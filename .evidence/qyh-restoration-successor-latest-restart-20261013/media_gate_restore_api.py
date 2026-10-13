"""Fresh one-attempt reload of exact current readonly API; no PG/Web/Chrome action."""
from pathlib import Path
import datetime,json,os,signal,subprocess,sys,time
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parents[2];P=Path(__file__).resolve().parent;F=R/'.evidence/qyh-full-system-restoration-20261011';PY=R/'services/aos-api/.venv/bin/python'
OWNER='codex-01a13484-f019-7d82-94ce-812396db9124';OLD=95278;OLD_SOURCE=F/'private/api-source-f28ef48c48ae4cebd144f3b986635cbc2a52de04';REPORT=F/'successor-media-reviewgate-restored-api-20261013.json'
assert not (P/'media-gate-restore-api-reload-intent.json').exists() and not (P/'media-gate-restore-api-started.json').exists(),'Existing operation: readonly reconcile,never resend'
m=R.parent/'docs/palantier/AOS项目开发上下文/memory';lease=[x for x in json.loads((m/'leases.json').read_text())['leases'] if x['task_id']==P.name];assert len(lease)==1 and lease[0]['owner']==OWNER and datetime.datetime.fromisoformat(lease[0]['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
sys.path.insert(0,str(R/'scripts'));import a0v_qyh_restored_http as guard
source=guard.require_api_source_candidate(REPORT.resolve());report=json.loads(REPORT.read_text());assert report['head']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
assert 'n'+str(OLD_SOURCE)+'\n' in subprocess.check_output(['lsof','-a','-p',str(OLD),'-d','cwd','-Fn'],text=True)
def listeners():
 x=subprocess.run(['lsof','-t','-nP','-iTCP:18080','-sTCP:LISTEN'],capture_output=True,text=True);return sorted({int(i) for i in x.stdout.split()})
assert listeners()==[OLD]
def record(name,value):
 with (P/name).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
record('media-gate-restore-api-reload-intent.json',{'oldPid':OLD,'oldCwd':str(OLD_SOURCE),'newHead':report['head'],'source':str(source),'port':18080,'sourceGuardPassed':True,'pgWebChromeTouched':False,'normalReadonlyFlagsRetained':True})
os.kill(OLD,signal.SIGTERM)
for _ in range(100):
 if not listeners():break
 time.sleep(.2)
assert not listeners(),'old stop not settled;reconcile-only'
record('media-gate-restore-api-old-stop.json',{'oldPid':OLD,'portFree':True})
args=[str(PY),str(R/'scripts/a0v_qyh_restored_http.py'),'--api-identity-file',str(F/'private/restored-identity.json'),'--serve-management-readonly','--bundle-root',str(F/'selected-public-bundles'),'--trust-roots-file',str(F/'restoration-public-trust-roots.json'),'--source-candidate',str(REPORT),'--management-oidc-config','/Users/ddt/.aos-local-identities/qyh-20261013/aos-management-oidc.json','--installed-readonly-installation','ab2fd72f-d81c-400d-bbbc-e1589a159d6b']
with (P/'live-api-media-gate-restore.log').open('x') as log:proc=subprocess.Popen(args,cwd=R,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
record('media-gate-restore-api-started.json',{'pid':proc.pid,'head':report['head'],'source':str(source),'port':18080,'terminalVerified':False,'pgWebChromeTouched':False});print(json.dumps({'newPid':proc.pid,'spawnedOnly':True,'pgWebChromeTouched':False}))
