"""Fresh current readonly backup and bounded isolated restore, never installation execution."""
from pathlib import Path
import importlib.util,sys,json,hashlib,os,shutil,subprocess,time
from datetime import datetime,timezone
P=Path(__file__).resolve().parent; ROOT=P.parents[1]; NAME=P.name
OWNER='codex-01a107a2-e9e4-7670-bc44-1144fa9b27e2'
s=importlib.util.spec_from_file_location('baseline',ROOT/'.evidence/qyh-host-oid-durable-full-restore-20261013/rehearse.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
s=importlib.util.spec_from_file_location('mc',ROOT/'scripts/memory/memoryctl.py');m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
def record(name,value):
 with (P/name).open('x') as f:json.dump(value,f,indent=2)
def inventory():return b.docker('ps','--no-trunc','--format','{{.ID}} {{.Names}}',capture_output=True,text=True).stdout.splitlines()
def schema(container):return b.docker('exec',container,'pg_dump','-U','aos_app','-d','aos_meta_head','--schema-only','--restrict-key=QyhReadonlySchemaComparison20261013',capture_output=True).stdout
if __name__=='__main__':
 assert m.load_authority()['project_revision']=='AOS-002003'
 lease=next(x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==NAME)
 assert lease['owner']==OWNER and datetime.fromisoformat(lease['lease_expires_at'])>datetime.now(timezone.utc)
 source=json.loads(b.docker('inspect',b.SOURCE,text=True,capture_output=True).stdout)[0]
 assert source['Id']==b.CID and source['State']['Running'] and source['Image']==b.IMAGE
 assert len(source['Mounts'])==1 and source['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
 mem=b.docker('exec',b.SOURCE,'cat','/proc/meminfo',text=True,capture_output=True).stdout
 available=int(next(x for x in mem.splitlines() if x.startswith('MemAvailable:')).split()[1]);assert available>=786432
 assert not b.docker('ps','-a','--filter','name=^/'+NAME+'$','--format','{{.ID}}',capture_output=True,text=True).stdout.strip()
 assert not b.docker('volume','ls','--filter','name=^'+NAME+'$','--format','{{.Name}}',capture_output=True,text=True).stdout.strip()
 native=json.loads(b.sql(b.SOURCE,'aos_meta_head',"BEGIN READ ONLY;SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'schema',(SELECT version_num FROM alembic_version),'enabledBindings',(SELECT count(*) FROM extension_runtime_binding WHERE enabled),'otherTransactions',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state='active' AND xact_start IS NOT NULL));COMMIT;"))
 assert native=={'cluster':'7695302940039200809','schema':'a0v_161','enabledBindings':0,'otherTransactions':0}
 start_inventory=inventory();before=b.fingerprint(b.SOURCE,'aos_meta_head');meta=b.metadata(b.SOURCE,'aos_meta_head');original_schema=schema(b.SOURCE)
 record('source-before.json',{'native':native,'fingerprints':before,'metadata':meta,'inventory':start_inventory,'sourceStartedAt':source['State']['StartedAt']})
 private=P/'private';private.mkdir(mode=0o700)
 record('backup-intent.json',{'sourceContainer':b.CID,'currentReadOnly':True,'memoryAvailableKB':available})
 hashes={}
 for filename,args in [('current.dump',('pg_dump','-U','aos_app','-d','aos_meta_head','-Fc')),('globals.sql',('pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'))]:
  path=private/filename
  with os.fdopen(os.open(path,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600),'wb') as f:b.docker('exec',b.SOURCE,*args,stdout=f,stderr=subprocess.PIPE)
  copy=private/(filename+'.second');shutil.copyfile(path,copy);copy.chmod(0o600)
  for x in (path,copy):hashes[x.name]=hashlib.sha256(x.read_bytes()).hexdigest()
  assert hashes[path.name]==hashes[copy.name]
 for args in [('--list',),('--file=/dev/null',)]:b.docker('exec','-i',b.SOURCE,'pg_restore',*args,input=(private/'current.dump').read_bytes(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 assert b.fingerprint(b.SOURCE,'aos_meta_head')==before and b.metadata(b.SOURCE,'aos_meta_head')==meta
 record('backup-verified.json',{'hashes':hashes,'sourceUnchanged':True,'fullDecodePassed':True})
 globals_text=(private/'globals.sql').read_text();assert globals_text.splitlines().count('CREATE ROLE aos_app;')==1
 globals_text='\n'.join(x for x in globals_text.splitlines() if x!='CREATE ROLE aos_app;')+'\n'
 record('volume-intent.json',{'volume':NAME,'owner':OWNER})
 b.docker('volume','create','--label','aos.task='+NAME,NAME,capture_output=True)
 record('container-intent.json',{'name':NAME,'volume':NAME,'image':b.IMAGE,'network':'none','memoryBytes':536870912})
 b.docker('run','-d','--name',NAME,'--network','none','--memory','512m','--memory-swap','512m','--mount','type=volume,src='+NAME+',dst=/var/lib/postgresql/data','--label','aos.task='+NAME,'-e','POSTGRES_USER=aos_app','-e','POSTGRES_HOST_AUTH_METHOD=trust',b.IMAGE,'-c','shared_buffers=16MB','-c','maintenance_work_mem=8MB','-c','work_mem=1MB','-c','max_parallel_workers_per_gather=0','-c','max_parallel_maintenance_workers=0','-c','max_connections=20',capture_output=True)
 for _ in range(30):
  ready=subprocess.run(['docker','--context',b.CONTEXT,'exec',NAME,'pg_isready','-U','aos_app'],capture_output=True,timeout=5)
  if ready.returncode==0:break
  time.sleep(1)
 else:raise RuntimeError('readiness unknown: reconcile only')
 clone=json.loads(b.docker('inspect',NAME,text=True,capture_output=True).stdout)[0]
 assert clone['HostConfig']['NetworkMode']=='none' and not clone['HostConfig']['PortBindings'] and clone['Image']==b.IMAGE
 assert len(clone['Mounts'])==1 and clone['Mounts'][0]['Name']==NAME
 record('globals-intent.json',{'container':clone['Id'],'skipExactExistingBootstrapCreate':1})
 b.sql(NAME,'postgres',globals_text)
 record('database-intent.json',{'container':clone['Id'],'database':'aos_meta_head'})
 b.docker('exec',NAME,'createdb','-U','aos_app','-O','aos_app','aos_meta_head',capture_output=True)
 record('restore-intent.json',{'container':clone['Id'],'singleTransaction':True,'exitOnError':True})
 try:b.docker('exec','-i',NAME,'pg_restore','--single-transaction','--exit-on-error','-U','aos_app','-d','aos_meta_head',input=(private/'current.dump').read_bytes(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 except subprocess.CalledProcessError as e:
  record('restore-failure.json',{'exitCode':e.returncode,'stderr':e.stderr.decode(errors='replace'),'noReplay':True});raise
 restored=b.fingerprint(NAME,'aos_meta_head');restored_meta=b.metadata(NAME,'aos_meta_head');clone_schema=schema(NAME)
 finite=json.loads((ROOT/'.evidence/qyh-host-oid-durable-full-restore-20261013/finite-schema-comparison.json').read_text())['acceptedRegroupings']
 checked=original_schema
 for pair in finite:
  old=pair['original'].encode();new=pair['restored'].encode()
  if old in checked:assert checked.count(old)==1;checked=checked.replace(old,new)
 schema_equal=checked==clone_schema
 record('restore-comparison.json',{'all650TablesEqual':restored==before,'rolesMembershipsSequencesEqual':all(restored_meta[k]==meta[k] for k in ('roles','sequences','sequenceStates')),'schemaBytesEqual':original_schema==clone_schema,'schemaEqualExceptExactRegisteredRegroupings':schema_equal})
 assert restored==before and schema_equal
 assert all(restored_meta[k]==meta[k] for k in ('roles','sequences','sequenceStates'))
 assert b.fingerprint(b.SOURCE,'aos_meta_head')==before and b.metadata(b.SOURCE,'aos_meta_head')==meta
 after=json.loads(b.docker('inspect',b.SOURCE,text=True,capture_output=True).stdout)[0]
 assert after['State']['StartedAt']==source['State']['StartedAt'] and after['Mounts']==source['Mounts']
 assert set(inventory())==set(start_inventory)|{clone['Id']+' '+NAME}
 record('verification.json',{'outcome':'CURRENT_COMPLETE_ISOLATED_RESTORE_GREEN','sourceContainer':b.CID,'cloneContainer':clone['Id'],'cloneVolume':NAME,'tables':650,'twoVerifiedBackups':True,'all650TablesAndSourceMetadataUnchanged':True,'schemaFiniteExactComparisonPassed':True,'currentDatabaseWrites':False,'currentServicesRestarted':False,'runtimeOperationRequested':False,'hostStarted':False,'eightPagesAccepted':False,'scriptSHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
 print('CURRENT_COMPLETE_ISOLATED_RESTORE_GREEN',flush=True)
