"""Two exact original native steps on retained isolated restore, never source."""
import sys,json,subprocess,secrets,os,importlib.util,hashlib
from pathlib import Path
from datetime import datetime,timezone
E=Path(__file__).resolve().parent;R=E.parents[1];sys.path.insert(0,str(E))
import snapshot_all as base
S=R.parent/'aos-recovery/current159-first-05b88779fad3';J=S/'native-rehearsal-r2';J.mkdir(mode=0o700)
CODE=json.loads((E/'committed-code159-r3.json').read_text());CTX='colima-aos-extension';PG='current159-first-1579cb9f5251';CLUSTER='7694901228328955942';SOURCE='aos-a0v-recovery-pg';TASK='current159-maintenance-20261010'
s=importlib.util.spec_from_file_location('mem_reh159',R/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
assert json.loads((E/'supplement-reviewed-r2.json').read_text())['status']=='SUPPLEMENT_COMPLETE_NATIVE_REVIEWED_EQUIVALENCE_GREEN'
initial=json.loads((S/'supplement-r1/restored.json').read_text())['base']
def save(n,v):
 with os.fdopen(os.open(J/n,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as out:json.dump(v,out,sort_keys=True,indent=2);out.flush();os.fsync(out.fileno())
def guard():
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==CODE['head'] and m.load_authority()['project_revision']=='AOS-001705'
 t=json.loads((m.DEFAULT_PATHS.receipts_path/'tasks'/f'{TASK}.json').read_text());assert t['owner']=='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2' and t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc) and [z for z in m.load_leases(m.DEFAULT_PATHS)['leases'] if z['task_id']==TASK]==[t]
 x=json.loads(subprocess.check_output(['docker','--context',CTX,'inspect',PG]))[0];i=json.loads((S/'intent.json').read_text());assert x['Id']!='9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde' and x['State']['Running'] and x['Image']==i['source_image'] and x['HostConfig']['NetworkMode']=='none' and x['Config']['Labels'].get('aos.maintenance-task')==TASK and len(x['Mounts'])==1 and x['Mounts'][0]['Name']==i['volume']
 return x

def native_read(version,label):
 x=guard();program=(E/'snapshot_all.py').read_text()+f'''\nimport psycopg\nwith psycopg.connect(host='/pgsocket',user='aos_app',dbname='aos_current_preview_20260927') as c:\n c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True\n assert c.execute('select system_identifier::text from pg_control_system()').fetchone()[0]=='{CLUSTER}'\n assert c.execute('select inet_server_addr()').fetchone()[0] is None\n assert c.execute('SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()').fetchone()[0]==0\n assert c.execute('SELECT count(*) FROM pg_prepared_xacts').fetchone()[0]==0\n print(json.dumps(snapshot(c,version='{version}'),sort_keys=True),flush=True)\n c.rollback()\n'''
 args=['docker','--context',CTX,'run','-i','--pull','never','--name','current159-'+label+'-'+secrets.token_hex(6),'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','384m','--mount','type=bind,source='+x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql,target=/pgsocket,readonly',CODE['tool'],'python','-']
 save(label+'-intent.json',{'args':args,'program_sha256':hashlib.sha256(program.encode()).hexdigest(),'read_only':True})
 p=subprocess.run(args,input=program.encode(),capture_output=True,timeout=180);save(label+'-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace')});assert p.returncode==0
 result=json.loads(p.stdout);save(label+'-snapshot.json',result);return result
before=native_read('a0v_157','before');base.compare_exact(initial,before)
steps=[]
for step in (158,159):
 x=guard();program=(E/'socket_migrate159.py').read_text()
 args=['docker','--context',CTX,'run','-i','--pull','never','--name','current159-original-step-'+str(step)+'-'+secrets.token_hex(6),'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','384m','-e','PYTHONDONTWRITEBYTECODE=1','--mount','type=bind,source='+x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql,target=/pgsocket,readonly','--mount','type=volume,source='+CODE['volume']+',target=/code,readonly',CODE['tool'],'python','-',str(step),CLUSTER]
 save(str(step)+'-intent.json',{'args':args,'program_sha256':hashlib.sha256(program.encode()).hexdigest(),'before_version':'a0v_'+str(step-1),'cluster':CLUSTER,'current_source_targeted':False})
 p=subprocess.run(args,input=program.encode(),capture_output=True,timeout=180);save(str(step)+'-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace'),'stdout':p.stdout.decode(errors='replace')});assert p.returncode==0
 report=json.loads(p.stdout.decode().splitlines()[-1]);assert report['status']=='ORIGINAL_NATIVE_ALEMBIC_STEP_COMMIT_CONFIRMED' and report['step']==step
 after=native_read('a0v_'+str(step),'after-'+str(step))
 old={k:v for k,v in before['tables'].items() if k!='["public","alembic_version"]'}
 assert all(after['tables'].get(k)==v for k,v in old.items())
 added={k:v for k,v in after['tables'].items() if k not in before['tables']};assert all(v['rows']==0 for v in added.values())
 for field in ('relations','columns','constraints','indexes','triggers','functions','policies','column_acl','relation_acl','schema_acl','function_acl','types','extensions','default_acl','role_memberships','event_triggers'):
  canonical=lambda row:json.dumps(row,sort_keys=True)
  assert set(map(canonical,before[field]))<=set(map(canonical,after[field])),field+' OLD_CATALOG_CHANGED'
 done={'step':step,'version':after['version'],'old_614_table_data_unchanged':True,'all_old_listed_catalogue_rows_unchanged':True,'new_tables_empty':sorted(added),'isolated_actual_commit_confirmed':True}
 save(str(step)+'-done.json',done);steps.append(done)
# Current source still unchanged and never targeted by this executor.
bs=importlib.util.spec_from_file_location('boot_reh159_r2',R/'scripts/a0v_current_preview_bootstrap.py');boot=importlib.util.module_from_spec(bs);sys.modules[bs.name]=boot;bs.loader.exec_module(boot)
import psycopg
with psycopg.connect(**boot._connection_parameters()) as c:
 c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True
 assert c.execute('select system_identifier::text from pg_control_system()').fetchone()[0]=='7683855731447750695'
 original=base.snapshot(c);base.compare_exact(json.loads((S/'source.json').read_text()),original)
guard();result={'status':'FIRST_FULL157_RESTORE_ORIGINAL158159_NATIVE_REHEARSAL_GREEN','steps':steps,'cluster':CLUSTER,'source_157_unchanged':True,'current_database_writes':0,'second_zero_window_full_restore_rehearsal_pending':True,'current_migration_allowed':False,'code':CODE,'state':str(J)}
save('result.json',result);(E/'first-native-rehearsal159-r2.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'steps':[s['step'] for s in steps],'current_database_writes':0}),flush=True)
