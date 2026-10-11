"""Single bound Web restart using existing tested controllers; no automatic replay."""
import datetime,hashlib,importlib.util,json,os,plistlib,re,subprocess,sys,time,urllib.request
from pathlib import Path
E=Path(__file__).resolve().parent; R=E.parents[2]
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
m=load('web_reboot_restore',E.parent/'registered_web_restore159.py'); stop=m.m
mem=load('web_reboot_memory',R/'scripts/memory/memoryctl.py')
def run(c):return subprocess.run(c,capture_output=True,text=True,timeout=20)
def sha(b):return hashlib.sha256(b).hexdigest()
label=stop.WEB; plist=Path.home()/'Library/LaunchAgents'/(label+'.plist');raw=plist.read_bytes();cfg=plistlib.loads(raw)
assert cfg['WorkingDirectory']==str(R/'apps/web') and cfg['ProgramArguments'][-4:]==['--host','127.0.0.1','--port','8434']
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
helper=[str(R/'node_modules/.pnpm/@esbuild+darwin-arm64@0.21.5/node_modules/@esbuild/darwin-arm64/bin/esbuild'),'--service=0.21.5','--ping']
def listeners():
 p=run(['lsof','-nP','-iTCP:8434','-sTCP:LISTEN','-t']);assert p.returncode in (0,1);return sorted(set(p.stdout.split()))
def observe():
 assert plist.read_bytes()==raw
 p=run(['launchctl','list',label]);assert p.returncode==0
 pid=int(re.search(r'"PID" = ([0-9]+);',p.stdout)[1]);x=re.search(r'"LastExitStatus" = ([0-9]+);',p.stdout)
 return dict(label=label,port=8434,plist_sha256=sha(raw),registered=True,pid=pid,last_exit_status=int(x[1]) if x else 0,listener_pids=listeners(),argv_sha256=sha(json.dumps(cfg['ProgramArguments'],separators=(',',':')).encode()),cwd=cfg['WorkingDirectory'],fingerprint=stop.original.read_service_candidate(pid=pid,expected_argv=cfg['ProgramArguments'],expected_cwd=cfg['WorkingDirectory'],expected_port=8434,expected_child_argv=helper))
def guard():
 a=mem.load_authority();assert a['project_revision']=='AOS-001791'
 t=mem.read_json(mem.DEFAULT_PATHS.receipts_path/'tasks/current159-maintenance-20261010.json'); ls=mem.load_leases(mem.DEFAULT_PATHS)['leases']
 assert t['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and t['status']=='ACTIVE'
 assert datetime.datetime.fromisoformat(t['lease_expires_at'])>datetime.datetime.now(datetime.timezone.utc)
 assert [x for x in ls if x['task_id']==t['task_id']]==[t]
 assert not any(mem.scopes_overlap(t['scope'],x['scope']) for x in ls if x['task_id']!=t['task_id'])
 assert not (mem.DEFAULT_PATHS.receipts_path/'deliveries'/ (t['task_id']+'.json')).exists()
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==head and plist.read_bytes()==raw
 with urllib.request.urlopen('http://127.0.0.1:8080/v1/ready',timeout=10) as r:assert r.status==200
expected=observe();guard()
if '--execute' not in sys.argv:
 print(json.dumps({'preflight':True,'head':head,'candidate':expected}));sys.exit(0)
state=R.parent/'aos-recovery/api159-reboot-ba05d7d655ea/web-restart-1791';state.mkdir(mode=0o700)
stop.write_record(state,'binding.json',{'head':head,'authority':'AOS-001791','candidate':expected,'script_sha256':sha(Path(__file__).read_bytes())})
for n in ('stop','restore'):(state/n).mkdir(mode=0o700)
def effect(c):
 guard();assert c in (['launchctl','bootout','gui/'+str(os.getuid())+'/'+label],['launchctl','bootstrap','gui/'+str(os.getuid()),str(plist)])
 p=run(c);return {'returncode':p.returncode}
def stopped():
 for _ in range(15):
  p=run(['launchctl','list',label]);gone=all(run(['ps','-p',str(pid),'-o','pid=']).returncode!=0 for pid in [expected['pid'],*[x['pid'] for x in expected['fingerprint']['children']]])
  if p.returncode==113 and not listeners() and gone:return dict(label=label,registered=False,listener_pids=[],old_processes_gone=True)
  time.sleep(1)
 raise RuntimeError('STOP_OBSERVATION_PENDING_RECONCILE_ONLY')
def fresh():
 for _ in range(15):
  try:
   v=observe()
   if v['pid']!=expected['pid']:return v
  except Exception:pass
  time.sleep(1)
 raise RuntimeError('START_OBSERVATION_PENDING_RECONCILE_ONLY')
stop.stop_registered(expected,observe(),journal=state/'stop',runner=effect,observe_after=stopped)
proof=dict(label=label,candidate_sha256=sha(json.dumps(expected,sort_keys=True).encode()),returncode=0,verified_stopped=True)
result=m.restore_web(expected,plist_path=plist,stop_proof=proof,before=stopped(),journal=state/'restore',runner=effect,observe_after=fresh)
result.update(before=expected['fingerprint'],after=observe()['fingerprint'],at=datetime.datetime.now(datetime.timezone.utc).isoformat())
with urllib.request.urlopen('http://127.0.0.1:8434/workshop/customer',timeout=10) as r:result['http_status']=r.status
stop.write_record(E,'web-restart-result.json',result)
print(json.dumps(result))
