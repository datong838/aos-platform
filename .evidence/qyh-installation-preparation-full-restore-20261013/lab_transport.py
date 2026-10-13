"""Owned clone-only SCRAM transport for original lifecycle qualification."""
from pathlib import Path
import runpy,json,subprocess,os,secrets,socket,sys,hashlib
from datetime import datetime,timezone
P=Path(__file__).resolve().parent;N=runpy.run_path(str(P/'restore.py'),run_name='transport_baseline');b=N['b'];m=N['m'];NAME=P.name;NEW=NAME+'-transport';NET=NAME+'-internal';PORT=18549
os.environ['AOS_DOTENV_DISABLED']='1';sys.path.insert(0,str(N['ROOT']/'services/aos-api'))
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from aos_api.extension_runtime.runtime_identity import probe_runtime_database_identity,require_isolated_runtime_identities
from aos_api.extension_runtime.production_runtime import _PROTECTED_RELATIONS
from aos_api.extension_runtime.runtime_connections import _runtime_file_dsns
from contextlib import contextmanager

def record(name,value):
 with (P/name).open('x') as f:json.dump(value,f,indent=2)
def private(name,value):
 with os.fdopen(os.open(P/'private'/name,os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600),'w') as f:json.dump(value,f,indent=2)
if __name__=='__main__':
 assert m.load_authority()['project_revision']=='AOS-002003'
 lease=next(x for x in m.load_leases(m.DEFAULT_PATHS)['leases'] if x['task_id']==NAME)
 assert lease['owner']==N['OWNER'] and datetime.fromisoformat(lease['lease_expires_at'])>datetime.now(timezone.utc)
 verification=json.loads((P/'verification.json').read_text());assert verification['outcome']=='CURRENT_COMPLETE_ISOLATED_RESTORE_GREEN'
 old=json.loads(b.docker('inspect',NAME,capture_output=True,text=True).stdout)[0];assert old['Id']==verification['cloneContainer'] and old['State']['Running']
 assert old['Mounts'][0]['Name']==NAME and old['Image']==b.IMAGE and old['HostConfig']['NetworkMode']=='none'
 assert not b.docker('ps','-a','--filter','name=^/'+NEW+'$','--format','{{.ID}}',capture_output=True,text=True).stdout.strip()
 assert not b.docker('network','ls','--filter','name=^'+NET+'$','--format','{{.Name}}',capture_output=True,text=True).stdout.strip()
 with socket.socket() as test:test.bind(('127.0.0.1',PORT))
 before=b.fingerprint(NAME,'aos_meta_head');meta=b.metadata(NAME,'aos_meta_head');source=b.fingerprint(b.SOURCE,'aos_meta_head');source_meta=b.metadata(b.SOURCE,'aos_meta_head')
 record('transport-stop-intent.json',{'exactContainer':old['Id'],'volumeRetained':NAME,'currentServicesTouched':False})
 b.docker('stop','--time','30',old['Id'],capture_output=True)
 assert json.loads(b.docker('inspect',old['Id'],capture_output=True,text=True).stdout)[0]['State']['Running'] is False
 record('internal-network-intent.json',{'name':NET,'internal':True,'owner':N['OWNER']})
 b.docker('network','create','--internal','--label','aos.task='+NAME,NET,capture_output=True)
 network=json.loads(b.docker('network','inspect',NET,capture_output=True,text=True).stdout)[0];assert network['Internal']
 record('transport-create-intent.json',{'name':NEW,'volume':NAME,'oldContainerStopped':old['Id'],'loopbackPort':PORT,'network':network['Id']})
 b.docker('run','-d','--name',NEW,'--network',NET,'--publish','127.0.0.1:'+str(PORT)+':5432','--memory','512m','--memory-swap','512m','--label','aos.task='+NAME,'--mount','type=volume,src='+NAME+',dst=/var/lib/postgresql/data',b.IMAGE,'-c','shared_buffers=16MB','-c','maintenance_work_mem=8MB','-c','work_mem=1MB','-c','max_parallel_workers_per_gather=0','-c','max_connections=20',capture_output=True)
 import time
 for _ in range(30):
  r=subprocess.run(['docker','--context',b.CONTEXT,'exec',NEW,'pg_isready','-U','aos_app'],capture_output=True,timeout=5)
  if r.returncode==0:break
  time.sleep(1)
 else:raise RuntimeError('transport readiness unknown: reconcile only')
 new=json.loads(b.docker('inspect',NEW,capture_output=True,text=True).stdout)[0]
 assert new['Mounts'][0]['Name']==NAME and new['Image']==b.IMAGE and new['HostConfig']['PortBindings']=={'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':str(PORT)}]}
 roles={'directory':'aos_a0v_directory_20260912','runtime':'aos_a0v_runtime_20260912','web':'aos_a0v_web_20260912'}
 identities={plane:{'role':role,'password':(pw:=secrets.token_urlsafe(48)),'dsn':make_conninfo(host='127.0.0.1',port=PORT,dbname='aos_meta_head',user=role,password=pw)} for plane,role in roles.items()}
 private('lab-identities.json',identities)
 record('lab-credential-intent.json',{'exactContainer':new['Id'],'roles':roles,'newGrants':False,'currentCredentialsChanged':False})
 command="BEGIN;SET LOCAL password_encryption='scram-sha-256';"+''.join(sql.SQL('ALTER ROLE {} PASSWORD {};').format(sql.Identifier(x['role']),sql.Literal(x['password'])).as_string() for x in identities.values())+'COMMIT;'
 try:b.sql(NEW,'aos_meta_head',command)
 except Exception:raise RuntimeError('lab credential result unknown: reconcile only') from None
 hba=b.docker('exec',NEW,'cat','/var/lib/postgresql/data/pg_hba.conf',capture_output=True,text=True).stdout
 lines=[];changes=0
 for line in hba.splitlines():
  if line.strip().startswith('host'):
   fields=line.split();assert fields[-1]=='trust';fields[-1]='scram-sha-256';line='\t'.join(fields);changes+=1
  lines.append(line)
 assert changes>=2
 record('lab-hba-intent.json',{'exactContainer':new['Id'],'changedHostRules':changes,'beforeSHA256':hashlib.sha256(hba.encode()).hexdigest()})
 b.docker('exec','-i',NEW,'sh','-c','cat > /var/lib/postgresql/data/pg_hba.conf',input='\n'.join(lines)+'\n',text=True,capture_output=True)
 assert b.sql(NEW,'aos_meta_head','SELECT pg_reload_conf();').strip()=='t'
 checked={}
 for plane,item in identities.items():
  with psycopg.connect(item['dsn'],row_factory=dict_row,connect_timeout=5) as conn:
   if plane=='directory':conn.read_only=True
   checked[plane]=probe_runtime_database_identity(conn,protected_relations=_PROTECTED_RELATIONS)
 require_isolated_runtime_identities(**checked)
 for plane,item in identities.items():
  try:psycopg.connect(make_conninfo(item['dsn'],password='KnownNegativeWrongLabSecret'),connect_timeout=5)
  except psycopg.OperationalError:pass
  else:raise AssertionError('wrong lab secret admitted')
 _runtime_file_dsns(str((P/'private/lab-identities.json').resolve()))
 assert b.fingerprint(NEW,'aos_meta_head')==before and b.metadata(NEW,'aos_meta_head')==meta
 assert b.fingerprint(b.SOURCE,'aos_meta_head')==source and b.metadata(b.SOURCE,'aos_meta_head')==source_meta
 record('lab-transport-verification.json',{'outcome':'REAL_ISOLATED_THREE_PLANE_LAB_TRANSPORT_GREEN','container':new['Id'],'originalStoppedContainer':old['Id'],'volume':NAME,'internalNetwork':network['Id'],'loopbackPort':PORT,'allThreeOriginalPhysicalIdentityProbesPassed':True,'allThreeWrongPasswordRejected':True,'lab650TablesMetadataUnchanged':True,'current650TablesMetadataUnchanged':True,'newGrants':False,'currentDatabaseWrites':False,'runtimeOperationRequested':False,'hostStarted':False,'eightPagesAccepted':False})
 print('REAL_ISOLATED_THREE_PLANE_LAB_TRANSPORT_GREEN',flush=True)
