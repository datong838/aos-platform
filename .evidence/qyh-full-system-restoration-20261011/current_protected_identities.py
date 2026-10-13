"""Approved current-target journaled identity recovery; no runtime activation."""
from pathlib import Path
from datetime import datetime,timezone
import importlib.util,sys,os,json,hashlib,secrets,stat,shutil,subprocess
P=Path(__file__).resolve().parent;ROOT=P.parents[1];OUT=P/'current-three-plane-credential-maintenance-20261013';CREDENTIAL=P/'private/current-runtime-host-identities-20261013.json';REVIEW=ROOT/'.evidence/qyh-current-three-plane-credential-review-20261013'
os.environ['AOS_DOTENV_DISABLED']='1';sys.path.insert(0,str(ROOT/'services/aos-api'))
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from aos_api.extension_runtime.runtime_identity import probe_runtime_database_identity,require_isolated_runtime_identities
from aos_api.extension_runtime.runtime_connections import _runtime_file_dsns
from aos_api.extension_runtime.production_runtime import _PROTECTED_RELATIONS
s=importlib.util.spec_from_file_location('r',ROOT/'.evidence/qyh-host-oid-durable-full-restore-20261013/rehearse.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
s=importlib.util.spec_from_file_location('mc',ROOT/'scripts/memory/memoryctl.py');mc=importlib.util.module_from_spec(s);sys.modules[s.name]=mc;s.loader.exec_module(mc)
ROLES={'directory':'aos_a0v_directory_20260912','runtime':'aos_a0v_runtime_20260912','web':'aos_a0v_web_20260912'}
def write(path,value,private=False):
 if private:
  path.parent.mkdir(mode=0o700,exist_ok=True);assert not path.parent.is_symlink() and stat.S_IMODE(path.parent.stat().st_mode)==0o700
 fd=os.open(path,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600 if private else 0o644)
 with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
def record(n,v):write(OUT/n,v)
def read(q):return r.sql(r.SOURCE,'aos_meta_head','BEGIN READ ONLY;'+q+'COMMIT;')
def guards():
 assert mc.load_authority()['project_revision']=='AOS-002001'
 lease=next(x for x in mc.load_leases(mc.DEFAULT_PATHS)['leases'] if x['task_id']=='qyh-full-system-restoration-20261011')
 assert lease['owner']==r.OWNER and datetime.fromisoformat(lease['lease_expires_at'])>datetime.now(timezone.utc)
 assert 'aos-platform/maintenance/qiyuehui-restored-data-volume' in lease['scope']
 source=json.loads(r.docker('inspect',r.SOURCE,text=True,capture_output=True).stdout)[0]
 assert source['Id']==r.CID and source['State']['Running'] and source['Image']==r.IMAGE
 assert len(source['Mounts'])==1 and source['Mounts'][0]['Name']=='aos-qyh-history159-prepared-data-20261011'
 native=json.loads(read("SELECT json_build_object('cluster',(SELECT system_identifier::text FROM pg_control_system()),'schema',(SELECT version_num FROM alembic_version),'enabled',(SELECT count(*) FROM extension_runtime_binding WHERE enabled),'otherSessions',(SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()),'user',current_user,'oidMatches',(SELECT database_role_oid=(SELECT oid FROM pg_roles WHERE rolname='aos_a0v_directory_20260912') FROM extension_runtime_host_identity WHERE database_role='aos_a0v_directory_20260912' AND revision=2));"))
 assert native=={'cluster':'7695302940039200809','schema':'a0v_161','enabled':0,'otherSessions':0,'user':'aos_app','oidMatches':True}
 roles=json.loads(read("SELECT json_agg(row_to_json(x) ORDER BY role) FROM (SELECT rolname AS role,rolcanlogin,rolsuper,rolinherit,rolbypassrls,rolcreaterole,rolcreatedb,rolreplication,rolpassword IS NOT NULL AS has_credential FROM pg_authid WHERE rolname IN ('aos_a0v_directory_20260912','aos_a0v_runtime_20260912','aos_a0v_web_20260912'))x;"))
 assert {x['role'] for x in roles}==set(ROLES.values())
 for x in roles:assert x['rolcanlogin'] and not any(x[k] for k in ('rolsuper','rolinherit','rolbypassrls','rolcreaterole','rolcreatedb','rolreplication','has_credential'))
 return source,native,roles

def prepare():
 OUT.mkdir();source,native,roles=guards()
 baseline=json.loads((P/'current-host-oid-maintenance-20261013/verification.json').read_text());before=r.fingerprint(r.SOURCE,'aos_meta_head');meta=r.metadata(r.SOURCE,'aos_meta_head');assert before==baseline['afterFingerprints']
 lab=json.loads((ROOT/'.evidence/qyh-protected-three-plane-identity-lab-20261013/verification.json').read_text());assert lab['actualSCRAM'] and lab['currentDatabaseWrites'] is False
 record('prepare-intent.json',{'source':r.CID,'volume':source['Mounts'][0]['Name'],'native':native,'roles':roles,'writes':False})
 private=OUT/'private';private.mkdir(mode=0o700);hashes={}
 for name,args in [('current.dump',('pg_dump','-U','aos_app','-d','aos_meta_head','-Fc')),('globals.sql',('pg_dumpall','-U','aos_app','--globals-only','--no-role-passwords'))]:
  path=private/name
  with os.fdopen(os.open(path,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600),'wb') as f:r.docker('exec',r.SOURCE,*args,stdout=f,stderr=subprocess.PIPE)
  copy=private/(name+'.second');shutil.copyfile(path,copy);copy.chmod(0o600)
  for x in (path,copy):hashes[x.name]=hashlib.sha256(x.read_bytes()).hexdigest()
  assert hashes[path.name]==hashes[copy.name]
 for args in [('--list',),('--file=/dev/null',)]:r.docker('exec','-i',r.SOURCE,'pg_restore',*args,input=(private/'current.dump').read_bytes(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 assert r.fingerprint(r.SOURCE,'aos_meta_head')==before and r.metadata(r.SOURCE,'aos_meta_head')==meta
 hba=r.docker('exec',r.SOURCE,'cat','/var/lib/postgresql/data/pg_hba.conf',text=True,capture_output=True).stdout
 assert 'host all all 0.0.0.0/0 reject' in hba or any(line.split()==['host','all','all','0.0.0.0/0','reject'] for line in hba.splitlines())
 write(private/'hba-before.json',{'text':hba},True)
 write(private/'hba-before.second.json',{'text':hba},True)
 record('prepared.json',{'hbaBeforeSHA256':hashlib.sha256(hba.encode()).hexdigest(),'before':before,'metadata':meta,'backupHashes':hashes,'native':native,'roles':roles,'priorIndependentFullRestoreAndNativeSCRAMVerified':True,'freshArchiveFullyDecoded':True,'currentDatabaseWrites':False})
 print('CURRENT_THREE_PLANE_CREDENTIAL_BACKUP_PREPARED_NO_WRITES')

def execute():
 source,native,roles=guards();prepared=json.loads((OUT/'prepared.json').read_text())
 assert roles==prepared['roles'] and native==prepared['native']
 consumption=json.loads((REVIEW/'consumption-r1.json').read_text());assert consumption['status']=='CONSUMED_MATERIAL_REVIEW' and consumption['execution_authorized'] is False
 for path,digest in consumption['baseline']['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
 assert (REVIEW/'material-1.txt').read_text()==Path(__file__).read_text()
 assert json.loads((REVIEW/'material-2.txt').read_text())['preparedFileSHA256']==hashlib.sha256((OUT/'prepared.json').read_bytes()).hexdigest()
 for name,digest in prepared['backupHashes'].items():assert hashlib.sha256((OUT/'private'/name).read_bytes()).hexdigest()==digest
 assert r.fingerprint(r.SOURCE,'aos_meta_head')==prepared['before'] and r.metadata(r.SOURCE,'aos_meta_head')==prepared['metadata']
 oldhba=r.docker('exec',r.SOURCE,'cat','/var/lib/postgresql/data/pg_hba.conf',text=True,capture_output=True).stdout
 assert hashlib.sha256(oldhba.encode()).hexdigest()==prepared['hbaBeforeSHA256']
 assert json.loads((OUT/'private/hba-before.json').read_text())==json.loads((OUT/'private/hba-before.second.json').read_text())=={'text':oldhba}
 assert not CREDENTIAL.exists() and not CREDENTIAL.is_symlink()
 credentials={plane:{'role':role,'password':(pw:=secrets.token_urlsafe(48)),'dsn':make_conninfo(host='127.0.0.1',port='18446',dbname='aos_meta_head',user=role,password=pw,application_name='qyh-current-'+plane)} for plane,role in ROLES.items()}
 write(CREDENTIAL,credentials,True)
 write(OUT/'private/credential-intent.json',{'credentialFileSHA256':hashlib.sha256(CREDENTIAL.read_bytes()).hexdigest(),'roles':ROLES,'sourceContainer':r.CID},True)
 record('execute-intent.json',{'source':r.CID,'roles':ROLES,'credentialReference':str(CREDENTIAL),'passwordPrinted':False,'hostActivation':False})
 statement="BEGIN; SET LOCAL password_encryption='scram-sha-256'; "+''.join(sql.SQL('ALTER ROLE {} PASSWORD {};').format(sql.Identifier(x['role']),sql.Literal(x['password'])).as_string() for x in credentials.values())+'COMMIT;'
 try:r.sql(r.SOURCE,'aos_meta_head',statement)
 except Exception:raise RuntimeError('CURRENT_CREDENTIAL_TRANSACTION_UNKNOWN_RECONCILE_ONLY') from None
 lines=oldhba.splitlines(keepends=True);positions=[i for i,line in enumerate(lines) if line.split()==['host','all','all','0.0.0.0/0','reject']];assert len(positions)==1
 rule='host aos_meta_head '+','.join(ROLES.values())+' 0.0.0.0/0 scram-sha-256\n'
 newhba=''.join(lines[:positions[0]]+[rule]+lines[positions[0]:])
 record('hba-execute-intent.json',{'beforeSHA256':prepared['hbaBeforeSHA256'],'afterSHA256':hashlib.sha256(newhba.encode()).hexdigest(),'newRules':1,'oldRulesPreserved':True,'onlyThreeBoundedRoles':True})
 r.docker('exec','--user','postgres','-i',r.SOURCE,'sh','-c','umask 077; set -C; cat > /var/lib/postgresql/data/pg_hba.qyh-20261013-new; mv /var/lib/postgresql/data/pg_hba.qyh-20261013-new /var/lib/postgresql/data/pg_hba.conf',input=newhba,text=True,capture_output=True)
 assert r.sql(r.SOURCE,'aos_meta_head','SELECT pg_reload_conf();').strip()=='t'
 actualhba=r.docker('exec',r.SOURCE,'cat','/var/lib/postgresql/data/pg_hba.conf',text=True,capture_output=True).stdout;assert actualhba==newhba
 rules=json.loads(read("SELECT json_agg(row_to_json(x)) FROM (SELECT type,database,user_name,address,auth_method,error FROM pg_hba_file_rules WHERE type LIKE 'host%')x;"));assert all(x['error'] is None for x in rules)
 record('hba-verified.json',{'rules':rules,'oldRulesPreserved':True,'processReloadedNotRestarted':True})
 dsns,generation=_runtime_file_dsns(CREDENTIAL,with_generation=True)
 identities={}
 for plane,dsn in dsns.items():
  try:
   with psycopg.connect(dsn,row_factory=dict_row,connect_timeout=5) as conn:
    conn.read_only=True;identities[plane]=probe_runtime_database_identity(conn,protected_relations=_PROTECTED_RELATIONS)
  except Exception:raise RuntimeError('CURRENT_SCRAM_PROBE_FAILED_RECONCILE_ONLY') from None
 require_isolated_runtime_identities(**identities)
 for plane,x in credentials.items():
  bad=make_conninfo(host='127.0.0.1',port='18446',dbname='aos_meta_head',user=x['role'],password='KnownWrongNegativeCredential',application_name='qyh-negative-'+plane)
  try:
   with psycopg.connect(bad,connect_timeout=5):pass
  except psycopg.OperationalError:pass
  else:raise RuntimeError('WRONG_SECRET_NOT_REJECTED')
 assert all(x.authority[2]=='aos_meta_head' for x in identities.values())
 assert r.fingerprint(r.SOURCE,'aos_meta_head')==prepared['before'] and r.metadata(r.SOURCE,'aos_meta_head')==prepared['metadata']
 _,now_generation=_runtime_file_dsns(CREDENTIAL,with_generation=True);assert now_generation==generation
 assert read('SELECT count(*) FROM extension_runtime_binding WHERE enabled;').strip()=='0'
 after_source=json.loads(r.docker('inspect',r.SOURCE,text=True,capture_output=True).stdout)[0];assert after_source['State']['StartedAt']==source['State']['StartedAt']
 record('verification.json',{'outcome':'CURRENT_THREE_PLANE_NATIVE_SCRAM_ORIGINAL_IDENTITY_GATES_GREEN','nativeIdentities':{p:{'sessionUser':v.session_user,'roleOid':v.role_oid,'authority':list(v.authority),'directoryMember':v.directory_member,'runtimeMember':v.runtime_member,'privileged':v.privileged,'ownsProtectedRelation':v.owns_protected_relation} for p,v in identities.items()},'credentialReference':str(CREDENTIAL),'credentialFileGeneration':generation,'source650TablesUnchanged':True,'schemaRoleFlagsMembershipsSequencesUnchanged':True,'onlyExistingThreeRoleCredentialsChanged':True,'sourceVolumeAndProcessUnchanged':True,'hostActivated':False,'eightWorkbenchesAccepted':False,'secretsPrinted':False})
 print('CURRENT_THREE_PLANE_NATIVE_SCRAM_ORIGINAL_IDENTITY_GATES_GREEN')
if __name__=='__main__':
 try:
  assert len(sys.argv)==2
  if sys.argv[1]=='prepare':prepare()
  elif sys.argv[1]=='execute':execute()
  else:raise ValueError('explicit phase only; no retries')
 except Exception as e:print('CURRENT_IDENTITY_STEP_FAILED_RECONCILE_ONLY:'+type(e).__name__);sys.exit(1)
