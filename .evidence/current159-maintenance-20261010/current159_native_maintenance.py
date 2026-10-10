"""One fully bound current159 native maintenance; existing attempts reconcile only."""
import ast,hashlib,importlib.util,io,json,os,plistlib,re,secrets,subprocess,sys,tarfile,time
from datetime import datetime,timezone
from pathlib import Path
E=Path(__file__).resolve().parent;R=E.parents[1];CTX='colima-aos-extension'
TASK='current159-maintenance-20261010';THREAD='01a107a2-e9e4-7670-bc44-1144fa9b27e2';OWNER='codex-'+THREAD
SOURCE='9cc6091c304b55f637987f1fb7ffff57d64cc5020e65f2912a18969df99e9cde';DB='aos_current_preview_20260927';CLUSTER='7683855731447750695'
def require(v,s):
 if not v:raise ValueError(s)
def sha(v):return hashlib.sha256(v).hexdigest()
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
old=load('current159_original142',R/'scripts/a0v_current_142_maintenance.py')
launch=load('current159_registered_stop',E/'registered_launch159.py')
api=load('current159_registered_api',E/'registered_api_restore159.py')
web=load('current159_registered_web',E/'registered_web_restore159.py')
entry=load('current159_frozen_entry',E/'api159_registered_entrypoint.py')
protocol=load('current159_protocol',E/'window159_native_rehearsal.py')
surface=load('current159_surface',E/'execution_surface159.py')
contract=load('current159_contract',E/'current_window159_contract.py')
mem=load('current159_memory',R/'scripts/memory/memoryctl.py')
restoregate=load('current159_roles',R/'scripts/a0v_current_142_restore_gate.py')

def require_owner(task,leases,authority,head,current_authority,current_head,delivered,now):
 require(authority==current_authority and head==current_head,'HEAD_AUTHORITY_DRIFT')
 require(task.get('task_id')==TASK and task.get('owner')==OWNER and task.get('status')=='ACTIVE' and datetime.fromisoformat(task['lease_expires_at'])>now,'ORIGINAL_LIVE_TASK_REQUIRED')
 require([x for x in leases if x.get('task_id')==TASK]==[task] and not delivered,'EXACT_TASK_LEASE_DELIVERY_REQUIRED')
 require(not any(mem.scopes_overlap(task['scope'],x['scope']) for x in leases if x['task_id']!=TASK),'UNRESOLVED_OVERLAP')
 require(all('aos-platform/maintenance/current-preview-'+x in task['scope'] for x in ('database','api','web')),'EXACT_CURRENT_MAINTENANCE_SCOPE_REQUIRED')

def require_current_migration(proof,current,clone,step):
 require(type(step) is int and step in (158,159),'ORIGINAL_STEP_REQUIRED')
 require(proof.get('complete_original157_restore') is True and proof.get('clone_original_steps')==[158,159] and proof.get('second_window_backup') is True and proof.get('unknown_external') is False,'SECOND_FULL_RESTORE_REHEARSAL_REQUIRED')
 require(current['cluster']==CLUSTER and clone['cluster']!=CLUSTER and current['base']['version']=='a0v_'+str(step-1) and clone['base']['version']=='a0v_159','EXACT_CURRENT_AND_INDEPENDENT_VERSION_REQUIRED')

def require_effect(args,*,target,tools,image,tool_image):
 require(type(args) is list and args and all(type(x) is str for x in args),'EXACT_COMMAND_REQUIRED')
 if args[0]=='restart':require(args==['restart',SOURCE] or args==['restart',target],'EXACT_PG_RESTART_ONLY');return
 if args[0]=='exec':
  i=1
  while i<len(args) and args[i].startswith('-'):
   if args[i]=='-i':i+=1
   elif args[i]=='-e':require(i+1<len(args) and args[i+1]=='PGOPTIONS=-c maintenance_work_mem=16MB -c work_mem=4MB','EXACT_RESTORE_OPTIONS');i+=2
   else:raise ValueError('UNKNOWN_EXEC_OPTION')
  require(args[i] in (SOURCE,target),'ORIGINAL_OR_NEW_RESTORE_ONLY');command=args[i+1:];require(command and command[0] in ('psql','pg_dump','pg_dumpall','pg_restore'),'POSTGRES_COMMAND_ONLY')
  if args[i]==SOURCE:
   ordinary=[['pg_dump','-U','aos_app','-d',DB,'-Fc'],['pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'],['pg_restore','--list']]
   alter=[['psql','-X','-U','aos_app','-d',DB,'-qAt','-v','ON_ERROR_STOP=1','-c',q] for q in ("ALTER SYSTEM SET listen_addresses=''","ALTER SYSTEM RESET listen_addresses","ALTER SYSTEM SET listen_addresses = '*'")]
   require(command in ordinary+alter,'CURRENT_EXACT_NATIVE_COMMAND_REQUIRED')
  return
 require(args[0]=='run' and '--name' in args and '--network' in args and args[args.index('--network')+1]=='none' and not any(x in args for x in ('--rm','--privileged','-p','--publish')),'EXACT_ISOLATED_RUN_REQUIRED')
 name=args[args.index('--name')+1]
 if name==target:
  require(args[-1]==image and '--mount' in args and args[args.index('--mount')+1]=='type=volume,source='+target+'-data,target=/var/lib/postgresql/data','EXACT_NEW_RESTORE_RESOURCE_REQUIRED')
 else:require(name in tools and tool_image in args and '--read-only' in args and '--cap-drop' in args and args[args.index('--cap-drop')+1]=='ALL','EXACT_NATIVE_TOOL_REQUIRED')

class Executor:
 def __init__(self):
  self.head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip();self.authority=mem.load_authority()['project_revision'];require(self.authority=='AOS-001714','REGISTERED_AUTHORITY_REQUIRED')
  self.code=json.loads((E/'committed-code159-r3.json').read_text());self.manifest=json.loads((Path(self.code['state'])/'intent.json').read_text())['manifest'];self.image=entry.IMAGE
  self.state=R.parent/'aos-recovery'/('current159-window-'+secrets.token_hex(6));self.target='current159-second-'+secrets.token_hex(6);self.tools=set();self.counter=0;self.version='a0v_157';self.stopped={};self.migration_proof={};self.clone=None
  self.candidates=json.loads((E/'current-window159-service-candidates.json').read_text());self.api_plan=json.loads((entry.STATE/'registered-api-restoration-plan.json').read_text())
  names=['current159_native_maintenance.py','registered_launch159.py','registered_api_restore159.py','registered_web_restore159.py','api159_registered_entrypoint.py','execution_surface159.py','current_window159_contract.py','window159_native_rehearsal.py','snapshot_all.py','snapshot_supplement.py','socket_migrate159.py','restore_comparison.py','dependency_review.py','review_native_dependencies.py']
  self.inputs={x:sha((E/x).read_bytes()) for x in names}
  require(all(subprocess.check_output(['git','show',self.head+':'+str((E/x).relative_to(R))],cwd=R)==(E/x).read_bytes() for x in names),'EXACT_COMMITTED_MAINTENANCE_INPUTS_REQUIRED')
  self.guard();self.state.mkdir(mode=0o700);self.save('manifest.json',{'head':self.head,'authority':self.authority,'task':TASK,'thread':THREAD,'owner':OWNER,'source_id':SOURCE,'cluster':CLUSTER,'database':DB,'target':self.target,'code':self.code,'api_plan_sha256':sha((entry.STATE/'registered-api-restoration-plan.json').read_bytes()),'no_automatic_retry':True,'evidence_input_sha256':self.inputs})
  tree=ast.parse((E/'review_native_dependencies.py').read_text());env={};sys.path.insert(0,str(E));import psycopg
  env.update({'psycopg':psycopg,'TABLES':tuple(sorted(protocol.load('current159_dep',E/'dependency_review.py').TABLES))})
  exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='QUERY' for x in n.targets)],type_ignores=[]),'<native-frozen-query>','exec'),env);self.query=env['QUERY']
 def guard(self):
  t=mem.read_json(mem.DEFAULT_PATHS.receipts_path/'tasks'/(TASK+'.json'));leases=mem.load_leases(mem.DEFAULT_PATHS)['leases']
  require_owner(t,leases,self.authority,self.head,mem.load_authority()['project_revision'],subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),(mem.DEFAULT_PATHS.receipts_path/'deliveries'/(TASK+'.json')).exists(),datetime.now(timezone.utc))
  require(all(sha((E/x).read_bytes())==digest for x,digest in self.inputs.items()),'FROZEN_MAINTENANCE_INPUT_DRIFT')
  item=self.inspect(SOURCE);entry.require_source(item)
  archive=subprocess.check_output(['git','archive',self.head,'services/aos-api/aos_api','services/aos-api/alembic','services/aos-api/alembic.ini'],cwd=R)
  with tarfile.open(fileobj=io.BytesIO(archive)) as tar:actual={x.name:sha(tar.extractfile(x).read()) for x in tar if x.isfile()}
  require(actual==self.manifest,'LATEST_COMMITTED_CODE_DRIFT');entry.verify_source(entry.SOURCE,json.loads((entry.STATE/'manifest.json').read_text()));api.require_entry(self.api_plan)
 def inspect(self,name):return json.loads(subprocess.check_output(['docker','--context',CTX,'inspect',name],timeout=20))[0]
 def save(self,name,v,binary=False):
  raw=v if binary else (json.dumps(v,sort_keys=True,indent=2)+'\n').encode()
  with os.fdopen(os.open(self.state/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  fd=os.open(self.state,os.O_RDONLY)
  try:os.fsync(fd)
  finally:os.close(fd)
 def readonly(self,args):
  r=subprocess.run(args,capture_output=True,timeout=240);require(r.returncode==0,'READONLY_OBSERVATION_FAILED');return r.stdout
 def effect(self,args,data=None):
  self.guard();require_effect(args,target=self.target,tools=self.tools,image=self.image,tool_image=self.code['tool']);self.counter+=1;key=f'{self.counter:03d}'
  self.save(key+'-intent.json',{'args':args,'input_sha256':sha(data) if data else None,'head':self.head,'authority':self.authority})
  try:r=subprocess.run(['docker','--context',CTX,*args],input=data,capture_output=True,timeout=240)
  except Exception as exc:self.save(key+'-terminal.json',{'status':'UNKNOWN_EXTERNAL','error_type':type(exc).__name__,'reconcile_only':True});raise
  self.save(key+'-terminal.json',{'exit':r.returncode,'stderr':r.stderr.decode(errors='replace'),'stdout_sha256':sha(r.stdout),'reconcile_only':r.returncode!=0});require(r.returncode==0,'KNOWN_COMMAND_FAILURE_RECONCILE_ONLY:'+key);return r.stdout
 def sql(self,name,query,effect=False):
  args=['exec',name,'psql','-X','-U','aos_app','-d',DB,'-qAt','-v','ON_ERROR_STOP=1','-c',query]
  return self.effect(args) if effect else self.readonly(['docker','--context',CTX,*args])
 def lab(self):
  item=self.inspect(self.target);require(item['Name']=='/'+self.target and item['Image']==self.image and item['HostConfig']['NetworkMode']=='none' and item['HostConfig']['Privileged'] is False and item['HostConfig']['RestartPolicy']['Name']=='no','EXACT_INDEPENDENT_RESTORE_REQUIRED')
  require(item['Id']==self.target_id and len(item['Mounts'])==1 and item['Mounts'][0]['Name']==self.target+'-data' and item['Mounts'][0]['Destination']=='/var/lib/postgresql/data' and item['Mounts'][0]['RW'] is True and not any(item['NetworkSettings']['Ports'].values()),'INDEPENDENT_RESTORE_RESOURCE_DRIFT');return item
 def ready(self,name):
  for _ in range(45):
   item=self.inspect(name);top=self.readonly(['docker','--context',CTX,'top',name,'-eo','pid,comm,args']).decode();p=subprocess.run(['docker','--context',CTX,'exec',name,'pg_isready','-U','aos_app'],capture_output=True,timeout=10)
   try:protocol.require_final_postmaster(item,top,p.returncode);return
   except ValueError:time.sleep(1)
  raise ValueError('FINAL_POSTMASTER_NOT_READY')
 def tool(self,name,program,extra=None,arguments=None):
  x=self.inspect(name) if name==SOURCE else self.lab();tn='current159-tool-'+secrets.token_hex(6);self.tools.add(tn)
  args=['run','-i','--pull','never','--name',tn,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','384m','-e','PYTHONDONTWRITEBYTECODE=1','--mount','type=bind,source='+x['GraphDriver']['Data']['MergedDir']+'/var/run/postgresql,target=/pgsocket,readonly']+(extra or [])+[self.code['tool'],'python','-']+(arguments or [])
  return self.effect(args,program.encode())
 def native(self,name,version):
  program='import psycopg\n'+(E/'snapshot_all.py').read_text()+'\n'+(E/'snapshot_supplement.py').read_text().replace('from snapshot_all import rows,require_schema_set','')+f'''\nwith psycopg.connect(host='/pgsocket',user='aos_app',dbname={DB!r}) as c:\n c.isolation_level=psycopg.IsolationLevel.REPEATABLE_READ;c.read_only=True\n assert c.execute('select inet_server_addr()').fetchone()[0] is None\n assert c.execute("SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid()").fetchone()[0]==0\n assert c.execute('SELECT count(*) FROM pg_prepared_xacts').fetchone()[0]==0\n print(json.dumps({{'base':snapshot(c,version={version!r}),'supplement':supplement(c,version={version!r}),'bindings':rows(c,{self.query!r}),'cluster':c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]}},sort_keys=True),flush=True)\n c.rollback()\n'''
  v=json.loads(self.tool(name,program));require((v['cluster']==CLUSTER)==(name==SOURCE),'EXACT_SOURCE_DISTINCT_CLUSTER_REQUIRED');return v
 def listeners(self,port):
  p=subprocess.run(['lsof','-nP',f'-iTCP:{port}','-sTCP:LISTEN','-t'],capture_output=True,text=True,timeout=10);require(p.returncode in (0,1),'LISTENER_OBSERVATION_FAILED');return sorted(set(p.stdout.split()))
 def service(self,label,*,stopped=False,new=False):
  expected=self.candidates[label];path=Path.home()/'Library/LaunchAgents'/(label+'.plist');raw=path.read_bytes();cfg=plistlib.loads(raw);p=subprocess.run(['launchctl','list',label],capture_output=True,text=True,timeout=10);ls=self.listeners(expected['port'])
  if stopped:
   require(p.returncode==113 and p.stderr==f'Could not find service "{label}" in domain for port\n','EXACT_JOB_NOT_UNREGISTERED');pids=[expected['pid']] if expected['pid'] else []
   if expected.get('fingerprint'):pids.extend(x['pid'] for x in expected['fingerprint']['children'])
   gone=all(subprocess.run(['ps','-p',str(pid),'-o','pid='],capture_output=True).returncode!=0 for pid in pids)
   return {'label':label,'registered':False,'listener_pids':ls,'old_processes_gone':gone}
  require(p.returncode==0,'ORIGINAL_REGISTERED_SERVICE_REQUIRED');match=re.search(r'"PID" = ([0-9]+);',p.stdout);pid=int(match[1]) if match else None;exitmatch=re.search(r'"LastExitStatus" = ([0-9]+);',p.stdout);status=int(exitmatch[1]) if exitmatch else 0
  value={'label':label,'port':expected['port'],'plist_sha256':sha(raw),'registered':True,'pid':pid,'last_exit_status':status,'listener_pids':ls,'argv_sha256':sha(json.dumps(cfg['ProgramArguments'],separators=(',',':')).encode()),'cwd':cfg['WorkingDirectory']}
  if pid is not None:
   helper=None
   if label==launch.WEB:helper=[str(R/'node_modules/.pnpm/@esbuild+darwin-arm64@0.21.5/node_modules/@esbuild/darwin-arm64/bin/esbuild'),'--service=0.21.5','--ping']
   value['fingerprint']=old.read_service_candidate(pid=pid,expected_argv=cfg['ProgramArguments'],expected_cwd=cfg['WorkingDirectory'],expected_port=expected['port'],expected_child_argv=helper)
  return value
 def observe_new(self,label):
  for _ in range(45):
   try:v=self.service(label,new=True);require(v['pid'] is not None,'STARTUP_PROCESS_PENDING');return v
   except (ValueError,old.MaintenanceBlocked):time.sleep(1)
  raise ValueError('STARTUP_PROCESS_NOT_VERIFIED_RECONCILE_ONLY')
 def launch_run(self,args):
  self.guard();r=subprocess.run(args,capture_output=True,timeout=30);return {'returncode':r.returncode}
 def off(self):
  return all(self.service(x,stopped=True)['old_processes_gone'] and not self.listeners(self.candidates[x]['port']) for x in (launch.API,launch.WEB))
 def window(self):
  self.guard();require(self.off(),'REGISTERED_CLIENTS_NOT_OFF');proof=surface.collect();listen=self.sql(SOURCE,'SHOW listen_addresses').decode().strip();p=subprocess.run(['docker','--context',CTX,'exec',SOURCE,'pg_isready','-h','127.0.0.1','-U','aos_app'],capture_output=True,timeout=10)
  version=self.sql(SOURCE,'BEGIN READ ONLY; SELECT version_num FROM alembic_version; ROLLBACK;').decode().strip();require(version==self.version,'NATIVE_CURRENT_WINDOW_VERSION_DRIFT')
  counts=list(map(int,self.sql(SOURCE,"BEGIN READ ONLY; SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid(); SELECT count(*) FROM pg_prepared_xacts; ROLLBACK;").decode().splitlines()));old.require_window(listen_addresses=listen,tcp_exit=p.returncode,other_clients=counts[0],prepared=counts[1]);observed={'execution_surface':proof,'listen_addresses':listen,'tcp_exit':p.returncode,'other_clients':counts[0],'prepared':counts[1],'services':dict.fromkeys(contract.SERVICES,False),'unknown_external':False}
  if version=='a0v_157':
   expected={'thread':THREAD,'owner':OWNER,'task_id':TASK,'authority_revision':self.authority,'head':self.head,'source_id':SOURCE,'volume':'aos-a0v-recovery-pg-data','cluster':CLUSTER,'database':DB,'version':version,'image':self.image,'code_archive_sha256':self.code['archive_sha256'],'first_rehearsal_sha256':sha((E/'window159-native-rehearsal-r1.json').read_bytes())}
   t=mem.read_json(mem.DEFAULT_PATHS.receipts_path/'tasks'/(TASK+'.json'));contract.require_zero_window(expected,{**expected,**observed},task=t,leases=mem.load_leases(mem.DEFAULT_PATHS)['leases'],now=datetime.now(timezone.utc),delivered=(mem.DEFAULT_PATHS.receipts_path/'deliveries'/(TASK+'.json')).exists())
  return observed
 def migrate(self,name,previous):
  current=previous
  for step in (158,159):
   self.window()
   if name==SOURCE:require_current_migration(self.migration_proof,current,self.clone,step)
   extra=['--mount','type=volume,source='+self.code['volume']+',target=/code,readonly'];check="import pathlib,json,hashlib; p=pathlib.Path('/code'); print(json.dumps({str(f.relative_to(p)):hashlib.sha256(f.read_bytes()).hexdigest() for f in p.rglob('*') if f.is_file()},sort_keys=True))"
   require(json.loads(self.tool(name,check,extra))==self.manifest,'CODE_VOLUME_DRIFT');require(self.native(name,'a0v_'+str(step-1))==current,'BEFORE_STEP_NATIVE_DRIFT')
   self.window()
   report=json.loads(self.tool(name,(E/'socket_migrate159.py').read_text(),extra,[str(step),current['cluster']]).decode().splitlines()[-1]);require(report['status']=='ORIGINAL_NATIVE_ALEMBIC_STEP_COMMIT_CONFIRMED' and report['step']==step,'ORIGINAL_TRANSACTION_COMMIT_REQUIRED')
   if name==SOURCE:self.version='a0v_'+str(step)
   after=self.native(name,'a0v_'+str(step));self.save(('current' if name==SOURCE else 'clone')+'-step-'+str(step)+'.json',protocol.require_step_preservation(current['base'],after['base'],step));current=after
  return current
 def run(self):
  journal=old.MaintenanceJournal(self.state)
  before=self.native(SOURCE,'a0v_157');self.save('original-full157.json',before)
  retained=json.loads((R.parent/'aos-recovery/window159-native-f1775d3bc3f4/formal-before.json').read_text());require(before['base']==retained['base'] and before['supplement']==retained['supplement'] and before['bindings']==retained['bindings'],'FORMAL_ORIGINAL157_CHANGED')
  rows=json.loads(self.sql(SOURCE,"BEGIN READ ONLY; SELECT coalesce(json_agg(x),'[]'::json) FROM (SELECT sourcefile,setting,applied,error FROM pg_file_settings WHERE name='listen_addresses') x; ROLLBACK;"));effective=self.sql(SOURCE,'SHOW listen_addresses').decode().strip();statement=old.listen_restore_statement(rows,effective=effective);self.save('original-listen.json',{'rows':rows,'effective':effective,'restore_statement':statement})
  def stop():
   for label in (launch.API,launch.WEB):
    self.guard();observed=self.service(label);candidate=self.candidates[label];launch.require_candidate(candidate,observed);folder=self.state/('stop-api' if label==launch.API else 'stop-web');folder.mkdir(mode=0o700)
    launch.stop_registered(candidate,observed,journal=folder,runner=self.launch_run,observe_after=lambda label=label:self.service(label,stopped=True));self.stopped[label]={'label':label,'candidate_sha256':sha(json.dumps(candidate,sort_keys=True).encode()),'returncode':0,'verified_stopped':True}
   require(self.off(),'CLIENT_STOP_UNVERIFIED');proof=surface.collect()
   counts=self.sql(SOURCE,"BEGIN READ ONLY; SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend' AND pid<>pg_backend_pid(); SELECT count(*) FROM pg_prepared_xacts; ROLLBACK;").decode().splitlines();require(counts==['0','0'],'PRE_FENCE_CLIENTS_OR_PREPARED_NOT_ZERO');self.save('pre-fence-current-surface.json',proof);return {'exact_registered_api_web_stopped':True,'native_pre_fence_client_prepared_zero':True}

  journal.perform('stop_clients',stop)
  def fence():
   self.sql(SOURCE,"ALTER SYSTEM SET listen_addresses=''",effect=True);self.effect(['restart',SOURCE]);self.ready(SOURCE);proof=self.window();require(self.native(SOURCE,'a0v_157')==before,'FENCE_CHANGED_CURRENT_CATALOGUE');self.save('zero-window-native.json',proof);return {'verified_current_zero_window':True}
  journal.perform('fence_tcp',fence);back={}
  def dump():
   self.window();back['dump']=self.effect(['exec',SOURCE,'pg_dump','-U','aos_app','-d',DB,'-Fc']);back['globals']=self.effect(['exec',SOURCE,'pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords']);require(b'CREATE TABLESPACE' not in back['globals'],'UNREVIEWED_TABLESPACE');toc=self.effect(['exec','-i',SOURCE,'pg_restore','--list'],back['dump']);require(b'TABLE DATA' in toc,'FULL_TABLE_DATA_REQUIRED')
   for name,data in [('window-full.dump',back['dump']),('window-globals.sql',back['globals']),('window-toc.txt',toc)]:self.save(name,data,True)
   require(self.native(SOURCE,'a0v_157')==before,'SOURCE_CHANGED_DURING_BACKUP');self.window();return {'sha256':sha(back['dump']),'globals_sha256':sha(back['globals']),'bytes':len(back['dump']),'full_current_before_after_equal':True}
  journal.perform('snapshot_dump',dump)
  def independent():
   self.window()
   for kind,name in [('container',self.target),('volume',self.target+'-data')]:require(subprocess.run(['docker','--context',CTX,kind,'inspect',name],capture_output=True).returncode!=0,'NEW_RESTORE_NAME_EXISTS')
   self.effect(['run','-d','--pull','never','--name',self.target,'--label','aos.maintenance-task='+TASK,'--network','none','--cpus','1','--memory','768m','--mount','type=volume,source='+self.target+'-data,target=/var/lib/postgresql/data','-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust',self.image]);self.target_id=self.inspect(self.target)['Id'];self.ready(self.target);self.lab()
   empty=self.readonly(['docker','--context',CTX,'exec',self.target,'psql','-X','-U','aos_app','-d','postgres','-qAt','-v','ON_ERROR_STOP=1','-c',"BEGIN READ ONLY; SELECT count(*) FROM pg_database WHERE datname='"+DB+"'; SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%' ORDER BY 1; ROLLBACK;"]).decode().splitlines();require(empty==['0','aos_app'],'EMPTY_NEW_RESTORE_REQUIRED')
   self.effect(['exec','-i',self.target,'psql','-X','-U','aos_app','-d','postgres','-q','-v','ON_ERROR_STOP=1','-f','-'],restoregate.prepare_globals(back['globals'],bootstrap='aos_app'));self.effect(['exec','-i','-e','PGOPTIONS=-c maintenance_work_mem=16MB -c work_mem=4MB',self.target,'pg_restore','-U','aos_app','-d','postgres','--create','--exit-on-error'],back['dump'])
   restored=self.native(self.target,'a0v_157');protocol.require_full_restore(before,restored);self.save('independent-full157.json',restored);self.clone=self.migrate(self.target,restored);self.save('independent-full159.json',self.clone);require(self.native(SOURCE,'a0v_157')==before,'SOURCE_CHANGED_DURING_REHEARSAL');self.migration_proof={'complete_original157_restore':True,'clone_original_steps':[158,159],'second_window_backup':True,'unknown_external':False};self.save('current-migration-prerequisites.json',self.migration_proof);return self.migration_proof
  journal.perform('independent_restore',independent)
  def migrate():
   self.window();require(self.native(SOURCE,'a0v_157')==before,'CURRENT_CHANGED_BEFORE_ORIGINAL_STEPS');self.current=self.migrate(SOURCE,before);self.version='a0v_159';self.save('current-full159.json',self.current);return {'current_original_steps':[158,159],'same_volume_cluster':True}
  journal.perform('migrate_steps',migrate);journal.perform('verify',lambda:{'complete_migrated_catalogues_equal':protocol.require_full_restore(self.current,self.clone)})
  def reopen():
   self.window();self.sql(SOURCE,statement,effect=True);self.effect(['restart',SOURCE]);self.ready(SOURCE);require(self.sql(SOURCE,'SHOW listen_addresses').decode().strip()==effective,'ORIGINAL_LISTEN_NOT_RESTORED');fresh=json.loads(self.sql(SOURCE,"BEGIN READ ONLY; SELECT coalesce(json_agg(x),'[]'::json) FROM (SELECT sourcefile,setting,applied,error FROM pg_file_settings WHERE name='listen_addresses') x; ROLLBACK;"));require(fresh==rows,'ORIGINAL_CONFIGURATION_SOURCE_DRIFT');require(self.native(SOURCE,'a0v_159')==self.current,'RESTART_CHANGED_CURRENT_CATALOGUE');return {'original_configuration_source_restored':True,'same_volume_cluster':True}
  journal.perform('restore_tcp',reopen)
  def restart():
   self.guard();window={'source_id':SOURCE,'cluster':CLUSTER,'database':DB,'version':'a0v_159','volume':'aos-a0v-recovery-pg-data','original_configuration_source_restored':True,'complete_migrated_catalogues_equal':True,'source_original158159_commit_verified':True,'unknown_external':False};folder=self.state/'restore-api';folder.mkdir(mode=0o700)
   a=api.restore_api(self.api_plan,stop_proof=self.stopped[launch.API],before=self.service(launch.API,stopped=True),window=window,journal=folder,guard=self.guard,runner=self.launch_run,observe_after=lambda:self.observe_new(launch.API));self.save('api-current-process.json',self.service(launch.API,new=True))
   self.guard();folder=self.state/'restore-web';folder.mkdir(mode=0o700);w=web.restore_web(self.candidates[launch.WEB],plist_path=Path.home()/'Library/LaunchAgents'/(launch.WEB+'.plist'),stop_proof=self.stopped[launch.WEB],before=self.service(launch.WEB,stopped=True),journal=folder,runner=self.launch_run,observe_after=lambda:self.observe_new(launch.WEB));self.save('web-current-process.json',self.service(launch.WEB,new=True));return {'api':a,'web':w,'browser_acceptance_pending':True}
  journal.perform('restart_clients',restart)
  result={'status':'CURRENT159_DATABASE_MIGRATED_AND_REGISTERED_PROCESSES_STARTED_ACCEPTANCE_PENDING','state':str(self.state),'head':self.head,'authority':self.authority,'source_id':SOURCE,'cluster':CLUSTER,'volume':'aos-a0v-recovery-pg-data','version':self.version,'target':self.target,'original_full_backup_sha256':sha(back['dump']),'current_native_original_commits':2,'independent_native_original_commits':2,'browser_acceptance_pending':True,'health_acceptance_pending':True,'business_runtime_authorized':False,'goal_complete':False};self.save('result.json',result);(E/'current159-native-maintenance-result.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

def main():
 require(sys.argv[1:]==['--run-current-maintenance'],'EXPLICIT_ORIGINAL_CURRENT_MAINTENANCE_ONLY');x=Executor()
 try:x.run()
 except Exception as exc:x.save('failure.json',{'error_type':type(exc).__name__,'reason':str(exc)[:1000],'reconcile_only':True});print(json.dumps({'status':'FAILED_RECONCILE_ONLY','state':str(x.state),'reason':str(exc)[:300]}),flush=True);raise
if __name__=='__main__':main()
