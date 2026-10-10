"""Read-only compare of a full restore whose two effects are terminal0."""
import sys,json,subprocess,importlib.util,hashlib,os,secrets
from pathlib import Path
from datetime import datetime,timezone
import psycopg
E=Path(__file__).resolve().parent;R=E.parents[1];S=R.parent/'aos-recovery/current159-first-05b88779fad3';PG='current159-first-1579cb9f5251';CTX='colima-aos-extension'
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
m=load('mcomp159',R/'scripts/memory/memoryctl.py');b=load('bcomp159',R/'scripts/a0v_current_preview_bootstrap.py');snap=load('scomp159',E/'snapshot_all.py')
intent=json.loads((S/'intent.json').read_text());before=json.loads((S/'source.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==intent['head']
assert m.load_authority()['project_revision']=='AOS-001699'
t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks/current159-maintenance-20261010.json').read_text())
assert t['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc)
assert [z for z in m.load_leases(m.DEFAULT_PATHS)['leases'] if z['task_id']==t['task_id']]==[t]
J=S/'readonly-compare-r2';J.mkdir(mode=0o700)
def save(n,v):
 with os.fdopen(os.open(J/n,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as out:json.dump(v,out,indent=2,sort_keys=True);out.flush();os.fsync(out.fileno())
for f in (S/'resume-r1').glob('*-intent.json'):
 a=json.loads(f.read_text())['args']
 if 'pg_restore' in a or ('psql' in a and '-f' in a):assert json.loads(f.with_name(f.name.replace('-intent','-terminal')).read_text())['exit']==0
x=json.loads(subprocess.check_output(['docker','--context',CTX,'inspect',PG]))[0]
assert x['Image']==intent['source_image'] and x['State']['Running'] and x['HostConfig']['NetworkMode']=='none'
assert len(x['Mounts'])==1 and x['Mounts'][0]['Name']==intent['volume']
program=(E/'snapshot_all.py').read_text()+'''\nimport psycopg\nwith psycopg.connect(host='/pgsocket',user='aos_app',dbname='aos_current_preview_20260927') as c:\n c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True\n assert c.execute('select inet_server_addr()').fetchone()[0] is None\n assert c.execute("select current_setting('transaction_read_only')").fetchone()[0]=='on'\n print(json.dumps(snapshot(c),sort_keys=True),flush=True)\n c.rollback()\n'''
name='current159-readonly-r2-'+secrets.token_hex(6)
args=['docker','--context',CTX,'run','-i','--pull','never','--name',name,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','384m','--mount','type=bind,source='+x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql,target=/pgsocket,readonly','sha256:2376642dd6f7f8645411408371ea354046448d7b65f182dba762fb4df1f10312','python','-']
save('intent.json',{'args':args,'program_sha256':hashlib.sha256(program.encode()).hexdigest(),'database_writes':0})
p=subprocess.run(args,input=program.encode(),capture_output=True,timeout=180);save('terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace')});assert p.returncode==0
restored=json.loads(p.stdout);save('restored.json',restored)
differences={k:{'before_hash':snap.digest(before.get(k)),'after_hash':snap.digest(restored.get(k))} for k in before.keys()|restored.keys() if before.get(k)!=restored.get(k)};save('differences.json',differences)
with psycopg.connect(**b._connection_parameters()) as c:
 c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True
 source_after=snap.snapshot(c);snap.compare_exact(before,source_after)
result={'status':'FIRST_FULL157_RESTORE_NATIVE_COMPARISON_REQUIRES_REVIEW' if differences else 'FIRST_FULL157_RESTORE_NATIVE_EXACT_GREEN','task':t['task_id'],'state':str(S),'pg':PG,'tables':len(restored['tables']),'functions':len(restored['functions']),'differences':sorted(differences),'source_unchanged':True,'database_writes':0,'migration_allowed':False,'second_window_pending':True}
save('result.json',result);(E/'first-restore-native-comparison.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
