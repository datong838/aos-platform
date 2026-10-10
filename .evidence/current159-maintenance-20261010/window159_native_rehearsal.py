"""Complete native isolated zero-window protocol; never mutate current formal PG."""
import ast,collections,hashlib,importlib.util,io,json,os,secrets,subprocess,sys,tarfile,time
from datetime import datetime,timezone
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[1];TASK='current159-maintenance-20261010';OWNER='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2';CTX='colima-aos-extension';DB='aos_current_preview_20260927';FORMAL_ID='9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde'

def require(v,reason):
 if not v:raise ValueError(reason)

def require_lab(x,name,image):
 require(name.startswith('window159-lab-') and x['Name']=='/'+name and x['Id']!=FORMAL_ID,'ISOLATED_EXACT_NAME_ID_REQUIRED')
 require(x['State']['Running'] is True and x['Image']==image,'LAB_IMAGE_OR_LIVENESS_DRIFT')
 require(x['HostConfig']['NetworkMode']=='none' and x['HostConfig']['Privileged'] is False and x['HostConfig']['RestartPolicy']['Name']=='no','NONE_UNPRIVILEGED_NO_RESTART_REQUIRED')
 require(x['Config']['Labels'].get('aos.maintenance-task')==TASK,'ORIGINAL_TASK_LABEL_REQUIRED')
 mounts=x['Mounts'];require(len(mounts)==1 and mounts[0]['Type']=='volume' and mounts[0]['Name']==name+'-data' and mounts[0]['Destination']=='/var/lib/postgresql/data' and mounts[0]['RW'] is True,'EXACT_DISTINCT_LAB_VOLUME_REQUIRED')
 require(not any(x['NetworkSettings']['Ports'].values()),'NO_PUBLISHED_PORTS_REQUIRED')

def require_lab_command(args,labs,tools):
 require(type(args) is list and args and not any('aos-a0v-recovery-pg' in a or FORMAL_ID in a for a in args),'FORMAL_EFFECT_FORBIDDEN')
 require(args[0] in ('run','exec','restart'),'NO_DESTRUCTIVE_OR_UNKNOWN_COMMAND')
 if args[0]=='restart':require(len(args)==2 and args[1] in labs,'EXACT_LAB_RESTART_REQUIRED')
 elif args[0]=='exec':
  index=1
  while index<len(args) and args[index].startswith('-'):
   if args[index]=='-i':index+=1
   elif args[index]=='-e':index+=2
   else:raise ValueError('UNKNOWN_EXEC_OPTION')
  require(index<len(args) and args[index] in labs,'EXACT_LAB_EXEC_REQUIRED')
 else:
  require('--name' in args and args[args.index('--name')+1] in labs|tools,'EXACT_NEW_RESOURCE_REQUIRED')
  require('--network' in args and args[args.index('--network')+1]=='none' and not any(a in args for a in ('--privileged','-p','--publish','--rm')),'ISOLATED_NONDESTRUCTIVE_RUN_REQUIRED')

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m

def require_step_preservation(before,after,step):
 require(type(step) is int and step in (158,159) and before['version']=='a0v_'+str(step-1) and after['version']=='a0v_'+str(step),'EXACT_NEXT_VERSION_REQUIRED')
 for k,v in before['tables'].items():
  if k!='["public","alembic_version"]':require(after['tables'].get(k)==v,'OLD_TABLE_CHANGED')
 added={k:v for k,v in after['tables'].items() if k not in before['tables']};require(all(x['rows']==0 for x in added.values()),'NEW_TABLE_NOT_EMPTY')
 require(all(after['sequences'].get(k)==v for k,v in before['sequences'].items()),'OLD_SEQUENCE_CHANGED')
 for field,rows in before.items():
  if type(rows) is list:
   canonical=lambda r:json.dumps(r,sort_keys=True)
   require(not (collections.Counter(map(canonical,rows))-collections.Counter(map(canonical,after[field]))),'OLD_CATALOG_MULTISET_CHANGED:'+field)
 return {'version':after['version'],'old_tables_unchanged':True,'new_empty_tables':len(added),'old_catalogue_multisets_preserved':True}

def require_full_restore(left,right):
 base=load('window_restore_compare159',E/'restore_comparison.py');sup=load('window_supplement159',E/'snapshot_supplement.py');dep=load('window_dependency159',E/'dependency_review.py')
 base.require_equivalent(left['base'],right['base'])
 for rows in (left['bindings'],right['bindings']):require(len(rows)==9 and {r['table'] for r in rows}==dep.TABLES,'NINE_NATIVE_BINDINGS_REQUIRED')
 proof={} if left['bindings']==right['bindings'] else dep.require_binding_pairs(left['bindings'],right['bindings'])
 a=sup.canonical(left['supplement'],left['base']['triggers']);b=sup.canonical(right['supplement'],right['base']['triggers'])
 a['dependencies']=dep.canonical_dependencies(a['dependencies'],proof);b['dependencies']=dep.canonical_dependencies(b['dependencies'],proof);sup.require_supplement_equivalent(a,b)
 return True

def main():
 require(sys.argv[1:]==['--run-isolated'],'EXPLICIT_ISOLATED_ENTRY_ONLY')
 sys.path.insert(0,str(E));import snapshot_all as base;import snapshot_supplement as sup;import dependency_review as dep;import psycopg
 mem=load('window_mem159',R/'scripts/memory/memoryctl.py');old=load('window_old142',R/'scripts/a0v_current_142_maintenance.py');gate=load('window_restore_gate159',R/'scripts/a0v_current_142_restore_gate.py');boot=load('window_boot159',R/'scripts/a0v_current_preview_bootstrap.py')
 code=json.loads((E/'committed-code159-r3.json').read_text());expected_manifest=json.loads((Path(code['state'])/'intent.json').read_text())['manifest']
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();authority='AOS-001709'
 archive=subprocess.check_output(['git','archive',head,'services/aos-api/aos_api','services/aos-api/alembic','services/aos-api/alembic.ini'],cwd=R)
 with tarfile.open(fileobj=io.BytesIO(archive)) as tar:actual_manifest={p.name:hashlib.sha256(tar.extractfile(p).read()).hexdigest() for p in tar if p.isfile()}
 require(actual_manifest==expected_manifest,'LATEST_COMMITTED_API_BYTES_DIFFER_FROM_FROZEN_CODE')
 def guard():
  require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()==head and mem.load_authority()['project_revision']==authority,'CURRENT_HEAD_AUTHORITY_DRIFT')
  t=mem.read_json(mem.DEFAULT_PATHS.receipts_path/'tasks'/ (TASK+'.json'));leases=mem.load_leases(mem.DEFAULT_PATHS)['leases']
  require(t['owner']==OWNER and t['status']=='ACTIVE' and datetime.fromisoformat(t['lease_expires_at'])>datetime.now(timezone.utc) and [x for x in leases if x['task_id']==TASK]==[t],'CURRENT_OWNED_TASK_LEASE_REQUIRED')
  require(not any(mem.scopes_overlap(t['scope'],x['scope']) for x in leases if x['task_id']!=TASK) and not (mem.DEFAULT_PATHS.receipts_path/'deliveries'/ (TASK+'.json')).exists(),'TASK_OVERLAP_OR_DELIVERY')
 guard();state=R.parent/'aos-recovery'/ ('window159-native-'+secrets.token_hex(6));load('window_private150',R/'scripts/a0v_current_150_restore_gate.py').require_private_parent(state.parent);state.mkdir(mode=0o700)
 labs={};tools=set();counter=0
 def save(name,data,binary=False):
  with os.fdopen(os.open(state/name,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600),'wb') as f:
   f.write(data if binary else (json.dumps(data,sort_keys=True,indent=2)+'\n').encode());f.flush();os.fsync(f.fileno())
  fd=os.open(state,os.O_RDONLY)
  try:os.fsync(fd)
  finally:os.close(fd)
 def inspect(name):return json.loads(subprocess.check_output(['docker','--context',CTX,'inspect',name],timeout=20))[0]
 formal=inspect('aos-a0v-recovery-pg');old.require_source(formal);require(formal['Id']==FORMAL_ID,'FORMAL_ID_DRIFT');image=formal['Image']
 # Compile only original read-only FK query expression, not its historical executor.
 tree=ast.parse((E/'review_native_dependencies.py').read_text());assign=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='QUERY' for t in n.targets));env={'psycopg':psycopg,'TABLES':dep.TABLES};exec(compile(ast.Module(body=[assign],type_ignores=[]),'original_native_binding_query','exec'),env);query=env['QUERY']
 def formal_read():
  guard();x=inspect('aos-a0v-recovery-pg');old.require_source(x);require(x['Id']==FORMAL_ID and x['Image']==image,'FORMAL_CHANGED')
  with psycopg.connect(**boot._connection_parameters()) as c:
   c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True
   require(c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]=='7683855731447750695','FORMAL_CLUSTER_DRIFT')
   return {'base':base.snapshot(c),'supplement':sup.supplement(c),'bindings':base.rows(c,query)}
 original=formal_read();save('formal-before.json',original)
 first=R.parent/'aos-recovery/current159-first-05b88779fad3';seed=(first/'full.dump').read_bytes();globals_data=(first/'globals.sql').read_bytes();backup=json.loads((first/'backup.json').read_text())
 require(hashlib.sha256(seed).hexdigest()==backup['sha256'] and hashlib.sha256(globals_data).hexdigest()==backup['globals_sha256'],'FIRST_BACKUP_HASH_DRIFT')
 base.compare_exact(json.loads((first/'source.json').read_text()),original['base'])
 for kind in ('source','restore'):name='window159-lab-'+kind+'-'+secrets.token_hex(6);labs[name]=None
 source,target=list(labs);save('manifest.json',{'head':head,'authority':authority,'task':TASK,'image':image,'source':source,'target':target,'code':code,'scope':'ISOLATED_NATIVE_PROTOCOL_ONLY','formal_writes':False})
 def cmd(args,data=None):
  nonlocal counter
  guard();require_lab_command(args,set(labs),tools);counter+=1;token=f'{counter:03d}'
  save(token+'-intent.json',{'args':args,'input_sha256':hashlib.sha256(data).hexdigest() if data else None,'scope':'ISOLATED_ONLY'})
  try:p=subprocess.run(['docker','--context',CTX,*args],input=data,capture_output=True,timeout=240)
  except Exception as exc:save(token+'-terminal.json',{'status':'UNKNOWN_EXTERNAL','error_type':type(exc).__name__,'reconcile_only':True});raise
  save(token+'-terminal.json',{'exit':p.returncode,'stderr':p.stderr.decode(errors='replace')});require(p.returncode==0,'KNOWN_TERMINAL_FAILURE_RECONCILE_ONLY:'+token);return p.stdout
 def lab(name):
  guard();x=inspect(name);require_lab(x,name,image)
  if labs[name] is None:labs[name]=x['Id']
  require(x['Id']==labs[name],'LAB_CONTAINER_REPLACED');return x
 def create(name):
  require(subprocess.run(['docker','--context',CTX,'container','inspect',name],capture_output=True).returncode!=0,'LAB_NAME_ALREADY_EXISTS')
  require(subprocess.run(['docker','--context',CTX,'volume','inspect',name+'-data'],capture_output=True).returncode!=0,'LAB_VOLUME_ALREADY_EXISTS')
  cmd(['run','-d','--pull','never','--name',name,'--label','aos.maintenance-task='+TASK,'--network','none','--cpus','1','--memory','768m','--mount','type=volume,source='+name+'-data,target=/var/lib/postgresql/data','-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust',image]);ready(name)
 def ready(name):
  for _ in range(45):
   lab(name)
   p=subprocess.run(['docker','--context',CTX,'exec',name,'pg_isready','-U','aos_app'],capture_output=True,timeout=10)
   if p.returncode==0:return
   time.sleep(1)
  raise ValueError('LAB_READINESS_NOT_VERIFIED')
 def sql(name,statement):
  lab(name);return cmd(['exec',name,'psql','-X','-U','aos_app','-d',DB,'-qAt','-v','ON_ERROR_STOP=1','-c',statement])
 def restore(name,dump,roles):
  lab(name);empty=cmd(['exec',name,'psql','-X','-U','aos_app','-d','postgres','-qAt','-v','ON_ERROR_STOP=1','-c',"BEGIN READ ONLY; SELECT count(*) FROM pg_database WHERE datname='"+DB+"'; SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%' ORDER BY 1; COMMIT;"]);require(empty.decode().splitlines()==['0','aos_app'],'EMPTY_NEW_RESTORE_TARGET_REQUIRED')
  cmd(['exec','-i',name,'psql','-X','-U','aos_app','-d','postgres','-q','-v','ON_ERROR_STOP=1','-f','-'],gate.prepare_globals(roles,bootstrap='aos_app'))
  cmd(['exec','-i','-e','PGOPTIONS=-c maintenance_work_mem=16MB -c work_mem=4MB',name,'pg_restore','-U','aos_app','-d','postgres','--create','--exit-on-error'],dump)
 def tool(name,program,extra=None,arguments=None):
  x=lab(name);toolname='window159-tool-'+secrets.token_hex(6);tools.add(toolname)
  args=['run','-i','--pull','never','--name',toolname,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','384m','-e','PYTHONDONTWRITEBYTECODE=1','--mount','type=bind,source='+x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql,target=/pgsocket,readonly']+(extra or [])+[code['tool'],'python','-']+(arguments or [])
  return cmd(args,program.encode())
 def native(name,version):
  program='import psycopg\n'+(E/'snapshot_all.py').read_text()+'\n'+(E/'snapshot_supplement.py').read_text().replace('from snapshot_all import rows,require_schema_set','')+f'''\nwith psycopg.connect(host='/pgsocket',user='aos_app',dbname={DB!r}) as c:\n c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True\n assert c.execute('select inet_server_addr()').fetchone()[0] is None\n assert c.execute('SELECT count(*) FROM pg_stat_activity WHERE backend_type=\\'client backend\\' AND pid<>pg_backend_pid()').fetchone()[0]==0\n assert c.execute('SELECT count(*) FROM pg_prepared_xacts').fetchone()[0]==0\n print(json.dumps({{'base':snapshot(c,version={version!r}),'supplement':supplement(c,version={version!r}),'bindings':rows(c,{query!r}),'cluster':c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]}},sort_keys=True),flush=True)\n c.rollback()\n'''
  result=json.loads(tool(name,program));require(result['cluster'] not in ('7683855731447750695','7694901228328955942'),'OLD_CLUSTER_TARGETED');return result
 def migrate(name,previous):
  current=previous
  for step in (158,159):
   # All frozen API files compared to latest committed blobs; actual volume rehashed before each step.
   check="import pathlib,json,hashlib; p=pathlib.Path('/code'); print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file()},sort_keys=True))"
   extra=['--mount','type=volume,source='+code['volume']+',target=/code,readonly']
   require(json.loads(tool(name,check,extra))==expected_manifest,'CODE_VOLUME_DRIFT')
   require(native(name,'a0v_'+str(step-1))==current,'BEFORE_STEP_NATIVE_DRIFT')
   raw=tool(name,(E/'socket_migrate159.py').read_text(),extra,[str(step),current['cluster']]);report=json.loads(raw.decode().splitlines()[-1]);require(report['status']=='ORIGINAL_NATIVE_ALEMBIC_STEP_COMMIT_CONFIRMED' and report['step']==step,'ORIGINAL_COMMIT_TERMINAL_REQUIRED')
   after=native(name,'a0v_'+str(step));save(name+'-step-'+str(step)+'-verified.json',require_step_preservation(current['base'],after['base'],step));current=after
  return current
 try:
  create(source);restore(source,seed,globals_data);before=native(source,'a0v_157');require_full_restore(original,before);save('lab-source157.json',before)
  journal=old.MaintenanceJournal(state)
  journal.perform('stop_clients',lambda:{'scope':'ISOLATED_PG_ONLY_NO_APP_RUNTIME','network':'none','no_application_image':True})
  rows=json.loads(sql(source,"BEGIN READ ONLY; SELECT coalesce(json_agg(x),'[]'::json) FROM (SELECT sourcefile,setting,applied,error FROM pg_file_settings WHERE name='listen_addresses') x; COMMIT;"));effective=sql(source,'SHOW listen_addresses').decode().strip();restore_statement=old.listen_restore_statement(rows,effective=effective);save('original-listen.json',{'rows':rows,'effective':effective,'restore_statement':restore_statement})
  def fence():
   sql(source,"ALTER SYSTEM SET listen_addresses=''");cmd(['restart',source]);ready(source)
   listen=sql(source,'SHOW listen_addresses').decode().strip();p=subprocess.run(['docker','--context',CTX,'exec',source,'pg_isready','-h','127.0.0.1','-U','aos_app'],capture_output=True,timeout=10)
   counts=sql(source,"BEGIN READ ONLY; SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid(); SELECT count(*) FROM pg_prepared_xacts; COMMIT;").decode().splitlines();clients,prepared=map(int,counts);old.require_window(listen_addresses=listen,tcp_exit=p.returncode,other_clients=clients,prepared=prepared)
   require(native(source,'a0v_157')==before,'LAB_FENCE_CHANGED_CATALOGUE');return {'listen_addresses':listen,'tcp_exit':p.returncode,'other_clients':clients,'prepared':prepared}
  journal.perform('fence_tcp',fence)
  backup_data={}
  def dump():
   lab(source);backup_data['dump']=cmd(['exec',source,'pg_dump','-U','aos_app','-d',DB,'-Fc']);backup_data['globals']=cmd(['exec',source,'pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords']);require(b'CREATE TABLESPACE' not in backup_data['globals'],'UNREVIEWED_TABLESPACE')
   toc=cmd(['exec','-i',source,'pg_restore','--list'],backup_data['dump']);require(b'TABLE DATA' in toc,'FULL_TABLE_DATA_TOC_REQUIRED')
   save('window-full.dump',backup_data['dump'],True);save('window-globals.sql',backup_data['globals'],True);save('window-toc.txt',toc,True);require(native(source,'a0v_157')==before,'SOURCE_CHANGED_DURING_BACKUP')
   return {'sha256':hashlib.sha256(backup_data['dump']).hexdigest(),'bytes':len(backup_data['dump']),'full_native_before_after_equal':True}
  journal.perform('snapshot_dump',dump)
  restored={}
  def independent():
   create(target);restore(target,backup_data['dump'],backup_data['globals']);restored.update(native(target,'a0v_157'));require(restored['cluster']!=before['cluster'],'INDEPENDENT_CLUSTER_REQUIRED');require_full_restore(before,restored);save('second-independent-full157.json',restored);return {'complete_base_supplement_native_equal':True,'independent_cluster':restored['cluster']}
  journal.perform('independent_restore',independent)
  migrated={}
  def steps():
   clone159=migrate(target,restored);save('independent159.json',clone159);require(native(source,'a0v_157')==before,'LAB_SOURCE_CHANGED_BEFORE_ORIGINAL_STEPS');source159=migrate(source,before);save('source159.json',source159);migrated.update({'source':source159,'restore':clone159});return {'clone_original158159_commit_verified':True,'lab_source_original158159_commit_verified':True,'formal_writes':0}
  journal.perform('migrate_steps',steps)
  journal.perform('verify',lambda: {'complete_migrated_catalogues_equal':require_full_restore(migrated['source'],migrated['restore'])})
  def reopen():
   sql(source,restore_statement);cmd(['restart',source]);ready(source);require(sql(source,'SHOW listen_addresses').decode().strip()==effective,'ORIGINAL_LISTEN_SOURCE_NOT_RESTORED');require(native(source,'a0v_159')==migrated['source'],'SOURCE_CHANGED_ON_RESTART');return {'original_effective_listen_restored':effective,'same_volume_cluster':True}
  journal.perform('restore_tcp',reopen);journal.perform('restart_clients',lambda:{'scope':'ISOLATED_ONLY_NO_API_WEB_HOST_OR_WORKER_STARTED'})
  def acceptance():
   base.compare_exact(original,formal_read());return {'current_formal157_full_snapshot_unchanged':True,'formal_writes':0,'lab_native_protocol_completed':True,'current_second_zero_window_backup_not_claimed':True,'natural_first_chain_pass':False}
  journal.perform('acceptance',acceptance)
  result={'status':'ISOLATED_FULL_NATIVE_WINDOW159_PROTOCOL_GREEN','head':head,'authority':authority,'state':str(state),'source_lab':source,'independent_restore':target,'lab_clusters':[before['cluster'],restored['cluster']],'tables157':len(before['base']['tables']),'code_manifest_files':len(expected_manifest),'phases':list(old.STEPS),'native_original_commits':4,'formal_database_writes':0,'current_second_zero_window_pending':True,'latest_signed_api_browser_pending':True,'goal_complete':False}
  save('result.json',result);(E/'window159-native-rehearsal-r1.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
 except Exception as exc:
  save('failure.json',{'error_type':type(exc).__name__,'reason':str(exc)[:1000],'reconcile_only':True,'formal_writes':0});print(json.dumps({'status':'FAILED_RECONCILE_ONLY','error_type':type(exc).__name__,'state':str(state)}),flush=True);raise

if __name__=='__main__':main()
