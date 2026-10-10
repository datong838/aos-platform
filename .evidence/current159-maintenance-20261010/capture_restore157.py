"""First consistent backup/full restore only; never source DDL/service control."""
import importlib.util,sys,json,os,secrets,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
import psycopg
E=Path(__file__).resolve().parent;R=E.parents[1]
HEAD='fa70a7123d1625f6845f418326797ce121482e3b';TASK='current159-maintenance-20261010'
OWNER='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
CTX='colima-aos-extension';SOURCE='aos-a0v-recovery-pg';DB='aos_current_preview_20260927'
SID='9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde'
VOLUME='aos-a0v-recovery-pg-data'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
m=load('m159',R/'scripts/memory/memoryctl.py');snap=load('snap159',E/'snapshot_all.py')
b=load('b159',R/'scripts/a0v_current_preview_bootstrap.py');g=load('g159',R/'scripts/a0v_current_142_restore_gate.py');f=load('f159',R/'scripts/a0v_current_150_restore_gate.py')
def guard():
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==HEAD
 assert m.load_authority()['project_revision']=='AOS-001699'
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{TASK}.json').read_text())
 assert t['owner']==OWNER and t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert [x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==TASK]==[t]
 assert not (m.DEFAULT_PATHS.receipts_path/'deliveries'/f'{TASK}.json').exists()
 return t

def inspect(name):return json.loads(subprocess.check_output(['docker','--context',CTX,'inspect',name],timeout=20))[0]

def source_guard():
 guard();x=inspect(SOURCE)
 assert x['Id']==SID and x['State']['Running']
 assert [a['Name'] for a in x['Mounts'] if a['Type']=='volume']==[VOLUME]
 return x

guard();source=source_guard();image=source['Image'];state=R.parent/'aos-recovery'/('current159-first-'+secrets.token_hex(6));f.require_private_parent(state.parent);state.mkdir(mode=0o700)
pg='current159-first-'+secrets.token_hex(6);stage='preflight'
def save(n,v):
 with os.fdopen(os.open(state/n,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as out:json.dump(v,out,indent=2,sort_keys=True);out.flush();os.fsync(out.fileno())
def binary(n,v):
 with os.fdopen(os.open(state/n,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as out:out.write(v);out.flush();os.fsync(out.fileno())
def cmd(args,data=None):
 source_guard();token=secrets.token_hex(6)
 save(token+'-intent.json',{'stage':stage,'args':args})
 p=subprocess.run(['docker','--context',CTX,*args],input=data,capture_output=True,timeout=240)
 save(token+'-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace')})
 if p.returncode:raise RuntimeError('COMMAND_FAILED_'+stage)
 return p.stdout

def target_guard():
 x=inspect(pg)
 assert x['Image']==image and x['State']['Running'] and x['HostConfig']['NetworkMode']=='none' and not x['HostConfig']['Privileged']
 assert x['Config']['Labels'].get('aos.maintenance-task')==TASK
 assert len(x['Mounts'])==1 and x['Mounts'][0]['Name']==pg+'-data' and x['Mounts'][0]['Name']!=VOLUME
 assert not any(x['NetworkSettings']['Ports'].values())
 return x
try:
 save('intent.json',{'task':TASK,'head':HEAD,'source_id':SID,'source_image':image,'pg':pg,'volume':pg+'-data','source_writes':False})
 p=b._connection_parameters()
 with psycopg.connect(**p) as c:
  c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True
  assert c.execute('select system_identifier from pg_control_system()').fetchone()[0]==7683855731447750695
  before=snap.snapshot(c);assert before['version']=='a0v_157'
  xid=c.execute('select pg_export_snapshot()').fetchone()[0]
  stage='consistent_dump';dump=cmd(['exec',SOURCE,'pg_dump','-U','aos_app','-d',DB,'-Fc','--snapshot',xid])
 save('source.json',before);binary('full.dump',dump)
 glob=cmd(['exec',SOURCE,'pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords']);assert b'CREATE TABLESPACE' not in glob;binary('globals.sql',glob)
 toc=cmd(['exec','-i',SOURCE,'pg_restore','--list'],dump);assert b'TABLE DATA' in toc;binary('toc.txt',toc)
 save('backup.json',{'sha256':g.sha(state/'full.dump'),'globals_sha256':g.sha(state/'globals.sql'),'bytes':len(dump)})
 stage='isolated_create';cmd(['run','-d','--pull','never','--name',pg,'--label','aos.maintenance-task='+TASK,'--network','none','--cpus','1','--memory','768m','--mount','type=volume,source='+pg+'-data,target=/var/lib/postgresql/data','-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust',image]);target_guard()
 for _ in range(30):
  q=subprocess.run(['docker','--context',CTX,'exec',pg,'pg_isready','-U','aos_app'],capture_output=True)
  if q.returncode==0:break
  time.sleep(1)
 else:raise RuntimeError('TARGET_NOT_READY')
 stage='isolated_restore';target_guard()
 cmd(['exec','-i',pg,'psql','-U','aos_app','-d','postgres','-v','ON_ERROR_STOP=1','-q','-f','-'],g.prepare_globals(glob,bootstrap='aos_app'))
 cmd(['exec','-i','-e','PGOPTIONS=-c maintenance_work_mem=16MB -c work_mem=4MB',pg,'pg_restore','-U','aos_app','-d','postgres','--create','--exit-on-error'],dump)
 # Snapshot through a read-only UNIX-socket tool is a separate next step.
 # No source migration is reachable from this first-backup executor.
 with psycopg.connect(**p) as c:
  c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True
  after=snap.snapshot(c);snap.compare_exact(before,after)
 source_guard();target_guard();stage='complete'
 result={'status':'FIRST_CONSISTENT157_FULL_BACKUP_RESTORE_COMMANDS_COMPLETED_COMPARISON_PENDING','task':TASK,'head':HEAD,'state':str(state),'pg':pg,'volume':pg+'-data','source_unchanged':True,'tables':len(before['tables']),'source_writes':0,'migration_allowed':False,'full_restore_verified':False}
 save('result.json',result);(E/'first-backup-restore.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
except Exception as exc:
 save('failure.json',{'stage':stage,'exception_type':type(exc).__name__,'pg':pg,'reconcile_only':True})
 print(json.dumps({'status':'FAILED','stage':stage,'state':str(state),'pg':pg}),flush=True)
 raise
