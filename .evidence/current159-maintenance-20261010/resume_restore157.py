"""Fixed failed-before-connection restore resume; original source remains read-only."""
import sys,os,json,importlib.util,subprocess,secrets
from pathlib import Path
from datetime import datetime,timezone
import psycopg
E=Path(__file__).resolve().parent;R=E.parents[1];S=R.parent/'aos-recovery/current159-first-05b88779fad3'
CTX='colima-aos-extension';PG='current159-first-1579cb9f5251';DB='aos_current_preview_20260927';TASK='current159-maintenance-20261010'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
m=load('mr159',R/'scripts/memory/memoryctl.py');g=load('gr159',R/'scripts/a0v_current_142_restore_gate.py');b=load('br159',R/'scripts/a0v_current_preview_bootstrap.py');snap=load('sr159',E/'snapshot_all.py')
intent=json.loads((S/'intent.json').read_text());backup=json.loads((S/'backup.json').read_text());before=json.loads((S/'source.json').read_text())
assert json.loads((S/'failure.json').read_text())['stage']=='isolated_restore'
failed=[json.loads(p.read_text()) for p in S.glob('*-terminal.json') if json.loads(p.read_text())['exit']]
assert len(failed)==1 and 'No such file or directory' in failed[0]['stderr']
assert g.sha(S/'full.dump')==backup['sha256'] and g.sha(S/'globals.sql')==backup['globals_sha256']
J=S/'resume-r1';J.mkdir(mode=0o700)
def save(n,v):
 with os.fdopen(os.open(J/n,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as out:json.dump(v,out,sort_keys=True,indent=2);out.flush();os.fsync(out.fileno())
def guard():
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==intent['head']
 assert m.load_authority()['project_revision']=='AOS-001699'
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{TASK}.json').read_text())
 assert t['status']=='ACTIVE' and t['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
 assert [z for z in m.load_leases(m.DEFAULT_PATHS)['leases'] if z['task_id']==TASK]==[t]
 x=json.loads(subprocess.check_output(['docker','--context',CTX,'inspect',PG]))[0]
 assert x['Image']==intent['source_image'] and x['State']['Running'] and x['HostConfig']['NetworkMode']=='none'
 assert x['Config']['Labels'].get('aos.maintenance-task')==TASK
 assert len(x['Mounts'])==1 and x['Mounts'][0]['Name']==intent['volume']
 return x

def cmd(args,data=None):
 guard();token=secrets.token_hex(6);save(token+'-intent.json',{'args':args})
 p=subprocess.run(['docker','--context',CTX,*args],input=data,capture_output=True,timeout=240)
 save(token+'-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace')})
 if p.returncode:raise RuntimeError('KNOWN_TERMINAL_FAILURE_RECONCILE_ONLY')
 return p.stdout
x=guard()
r=cmd(['exec',PG,'psql','-U','aos_app','-d','postgres','-Atq','-v','ON_ERROR_STOP=1','-c',"BEGIN READ ONLY; SELECT count(*) FROM pg_database WHERE datname='aos_current_preview_20260927'; SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%' ORDER BY 1; COMMIT;"])
assert r.decode().splitlines()==['0','aos_app'];save('empty-target-verified.json',{'target_database_absent':True,'only_bootstrap_role':True})
cmd(['exec','-i',PG,'psql','-U','aos_app','-d','postgres','-q','-v','ON_ERROR_STOP=1','-f','-'],g.prepare_globals((S/'globals.sql').read_bytes(),bootstrap='aos_app'))
cmd(['exec','-i','-e','PGOPTIONS=-c maintenance_work_mem=16MB -c work_mem=4MB',PG,'pg_restore','-U','aos_app','-d','postgres','--create','--exit-on-error'],(S/'full.dump').read_bytes())
x=guard();socket=x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql'
tool='sha256:2376642dd6f7f8645411408371ea354046448d7b65f182dba762fb4df1f10312'
name='current159-native-readonly-'+secrets.token_hex(6)
raw=cmd(['run','--pull','never','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','384m','--mount','type=bind,source='+socket+',target=/pgsocket,readonly','--mount','type=bind,source='+str(E)+',target=/evidence,readonly',tool,'python','/evidence/native_snapshot159.py'])
after=json.loads(raw);save('restored.json',after)
differences={k:{'before_hash':snap.digest(before.get(k)),'after_hash':snap.digest(after.get(k))} for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
save('differences.json',differences)
with psycopg.connect(**b._connection_parameters()) as c:
 c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True
 source_after=snap.snapshot(c);snap.compare_exact(before,source_after)
result={'status':'FIRST_FULL157_RESTORE_NATIVE_COMPARISON_REQUIRES_REVIEW' if differences else 'FIRST_FULL157_RESTORE_NATIVE_EXACT_GREEN','task':TASK,'state':str(S),'pg':PG,'table_count':len(after['tables']),'differences':sorted(differences),'source_unchanged':True,'source_writes':0,'migration_allowed':False,'second_window_pending':True}
save('result.json',result);(E/'first-restore-native-comparison.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
