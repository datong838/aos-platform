"""Owned isolated SCRAM proof; no current database or secret output."""
from pathlib import Path
import importlib.util,sys,os,json,hashlib,secrets,subprocess,stat
from contextlib import contextmanager
from datetime import datetime,timezone
P=Path(__file__).resolve().parent;ROOT=P.parents[1];NAME='qyh-host-oid-durable-full-restore-20261013';DB='qyh_oid_full_restore'
os.environ['AOS_DOTENV_DISABLED']='1'
sys.path.insert(0,str(ROOT/'services/aos-api'))
from psycopg import sql
from psycopg.pq import TransactionStatus
from psycopg.conninfo import make_conninfo
from aos_api.extension_runtime.runtime_identity import probe_runtime_database_identity,require_isolated_runtime_identities
from aos_api.extension_runtime.runtime_connections import _runtime_file_dsns,pin_runtime_file_generation
from aos_api.extension_runtime.production_runtime import _PROTECTED_RELATIONS
s=importlib.util.spec_from_file_location('r',ROOT/'.evidence/qyh-host-oid-durable-full-restore-20261013/rehearse.py');r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
s=importlib.util.spec_from_file_location('mc',ROOT/'scripts/memory/memoryctl.py');mc=importlib.util.module_from_spec(s);sys.modules[s.name]=mc;s.loader.exec_module(mc)
ROLES={'directory':'aos_a0v_directory_20260912','runtime':'aos_a0v_runtime_20260912','web':'aos_a0v_web_20260912'}

def write(path,value,private=False):
 if private:path.parent.mkdir(mode=0o700,exist_ok=True);assert stat.S_IMODE(path.parent.stat().st_mode)==0o700
 fd=os.open(path,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600 if private else 0o644)
 with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
def record(n,v):write(P/n,v)
def secret_file(filename,text):
 path='/tmp/'+P.name+'-'+filename
 # No secret command arguments or environment values. Transport is stdin only.
 r.docker('exec','-i',NAME,'sh','-c','umask 077; set -C; cat > "$1"','owned-file',path,input=text,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 return path
class Info:transaction_status=TransactionStatus.IDLE
class NativeConnection:
 def __init__(self,role,passfile):self.role=role;self.passfile=passfile;self.info=Info()
 @contextmanager
 def transaction(self):yield
 def execute(self,query,params):
  parts=query.split('%s');assert len(parts)==len(params)+1
  statement=parts[0]
  for value,part in zip(params,parts[1:]):statement+=sql.Literal(value).as_string()+part
  wrapper='BEGIN READ ONLY; SELECT row_to_json(x) FROM ('+statement+')x; COMMIT;'
  result=r.docker('exec','-i','-e','PGPASSFILE='+self.passfile,NAME,'psql','-X','-w','-qAt','-v','ON_ERROR_STOP=1','-h','127.0.0.1','-U',self.role,'-d',DB,input=wrapper,text=True,capture_output=True)
  self.row=json.loads(result.stdout);return self
 def fetchone(self):return self.row

def main():
 assert mc.load_authority()['project_revision']=='AOS-002000'
 lease=next(x for x in mc.load_leases(mc.DEFAULT_PATHS)['leases'] if x['task_id']==P.name)
 assert lease['owner']==r.OWNER and datetime.fromisoformat(lease['lease_expires_at'])>datetime.now(timezone.utc)
 old=json.loads((ROOT/'.evidence/qyh-host-oid-durable-full-restore-20261013/verification.json').read_text())
 clone=json.loads(r.docker('inspect',NAME,text=True,capture_output=True).stdout)[0]
 assert clone['Id']==old['cloneContainer'] and clone['State']['Running'] and clone['Image']==r.IMAGE
 assert clone['HostConfig']['NetworkMode']=='none' and not clone['HostConfig']['PortBindings'] and len(clone['Mounts'])==1 and clone['Mounts'][0]['Name']==NAME
 before=r.fingerprint(NAME,DB);meta=r.metadata(NAME,DB)
 record('intent.json',{'container':clone['Id'],'volume':NAME,'task':P.name,'authority':'AOS-002000','currentDatabaseWrites':False,'hostActivated':False})
 credentials={plane:{'role':role,'password':(pw:=secrets.token_urlsafe(48)),'dsn':make_conninfo(host='127.0.0.1',port='5432',dbname=DB,user=role,password=pw,application_name='qyh-isolated-'+plane)} for plane,role in ROLES.items()}
 write(P/'private/identities.json',credentials,True)
 write(P/'private/role-intent.json',{'roles':ROLES,'credentialsSHA256':hashlib.sha256((P/'private/identities.json').read_bytes()).hexdigest()},True)
 command='BEGIN; SET LOCAL password_encryption=\'scram-sha-256\'; '+''.join(sql.SQL('ALTER ROLE {} PASSWORD {};').format(sql.Identifier(x['role']),sql.Literal(x['password'])).as_string() for x in credentials.values())+'COMMIT;'
 # Native errors deliberately discarded: never print a password-bearing SQL query.
 try:r.sql(NAME,DB,command)
 except Exception:raise RuntimeError('ISOLATED_ROLE_WRITE_FAILED_RECONCILE_ONLY') from None
 hba=r.docker('exec',NAME,'cat','/var/lib/postgresql/data/pg_hba.conf',text=True,capture_output=True).stdout
 lines=[];changes=0
 for line in hba.splitlines():
  if line.strip().startswith('host') and not line.strip().startswith('#'):
   fields=line.split();assert fields[-1]=='trust';fields[-1]='scram-sha-256';line='\t'.join(fields);changes+=1
  lines.append(line)
 assert changes>=2
 new='\n'.join(lines)+'\n';write(P/'private/hba-before.json',{'text':hba},True)
 record('hba-intent.json',{'beforeSHA256':hashlib.sha256(hba.encode()).hexdigest(),'afterSHA256':hashlib.sha256(new.encode()).hexdigest(),'changedHostRules':changes,'cloneOnly':True})
 r.docker('exec','-i',NAME,'sh','-c','cat > /var/lib/postgresql/data/pg_hba.conf',input=new,text=True,capture_output=True)
 assert r.sql(NAME,DB,'SELECT pg_reload_conf();').strip()=='t'
 rules=json.loads(r.sql(NAME,DB,"BEGIN READ ONLY;SELECT json_agg(row_to_json(x)) FROM (SELECT type,auth_method,error FROM pg_hba_file_rules WHERE type LIKE 'host%')x;COMMIT;"));assert all(x['auth_method']=='scram-sha-256' and x['error'] is None for x in rules)
 record('hba-verified.json',{'hostRules':rules,'currentDatabaseChanged':False})
 pgpass=''.join('127.0.0.1:5432:'+DB+':'+x['role']+':'+x['password']+'\n' for x in credentials.values())
 passfile=secret_file('pgpass',pgpass)
 ids={plane:probe_runtime_database_identity(NativeConnection(x['role'],passfile),protected_relations=_PROTECTED_RELATIONS) for plane,x in credentials.items()}
 require_isolated_runtime_identities(**ids)
 badfile=secret_file('bad-pgpass','127.0.0.1:5432:'+DB+':'+ROLES['directory']+':WrongKnownNegativeCredential\n')
 try:probe_runtime_database_identity(NativeConnection(ROLES['directory'],badfile),protected_relations=_PROTECTED_RELATIONS)
 except subprocess.CalledProcessError:pass
 else:raise AssertionError('wrong secret unexpectedly authenticated')
 negatives=['wrongSecretNativeSCRAMRejected']
 for label,value in [('duplicatePrincipal',{**ids,'runtime':ids['directory']}),('crossPlaneMembership',{'directory':ids['runtime'],'runtime':ids['directory'],'web':ids['web']})]:
  try:require_isolated_runtime_identities(**value)
  except RuntimeError:negatives.append(label)
  else:raise AssertionError('identity isolation negative passed')
 file=P/'private/identities.json';dsns,generation=_runtime_file_dsns(file,with_generation=True);assert set(dsns)==set(ROLES)
 for label,path in [('relativePath',Path('relative.json')),('symlink',P/'private/symlink.json'),('wrongMode',P/'private/wrongmode.json')]:
  if label=='symlink':path.symlink_to(file.resolve())
  if label=='wrongMode':write(path,credentials,True);path.chmod(0o644)
  try:_runtime_file_dsns(path)
  except RuntimeError:negatives.append(label)
  else:raise AssertionError('protected-file negative passed')
 pin_runtime_file_generation(file,generation)
 file.touch()
 try:_runtime_file_dsns(file)
 except RuntimeError:negatives.append('changedGeneration')
 else:raise AssertionError('generation drift passed')
 assert r.fingerprint(NAME,DB)==before and r.metadata(NAME,DB)==meta
 assert r.sql(NAME,DB,'BEGIN READ ONLY;SELECT count(*) FROM extension_runtime_binding WHERE enabled;COMMIT;').strip()=='0'
 record('verification.json',{'outcome':'ISOLATED_THREE_PLANE_NATIVE_SCRAM_AND_ORIGINAL_IDENTITY_GATES_GREEN','container':clone['Id'],'actualSCRAM':True,'nativeIdentities':{p:{'sessionUser':v.session_user,'roleOid':v.role_oid,'authority':list(v.authority),'directoryMember':v.directory_member,'runtimeMember':v.runtime_member,'privileged':v.privileged,'ownsProtectedRelation':v.owns_protected_relation} for p,v in ids.items()},'negativeGates':negatives,'all650TablesUnchanged':True,'schemaRolesMembershipSequencesUnchanged':True,'currentDatabaseWrites':False,'hostActivated':False,'eightWorkbenchesAccepted':False,'secretsPrinted':False})
 print('ISOLATED_THREE_PLANE_NATIVE_SCRAM_AND_ORIGINAL_IDENTITY_GATES_GREEN')
if __name__=='__main__':
 try:main()
 except Exception as e:
  # No stack/query/repr from password-bearing driver errors.
  print('ISOLATED_IDENTITY_STEP_FAILED_RECONCILE_ONLY:'+type(e).__name__);sys.exit(1)
