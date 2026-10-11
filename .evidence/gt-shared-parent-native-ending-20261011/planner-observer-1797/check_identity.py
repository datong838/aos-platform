import hashlib,json,subprocess,uuid
from pathlib import Path
import psycopg
from psycopg import sql
B=Path(__file__).resolve().parent;R=B.parents[2]
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
def docker(*args):return subprocess.check_output(['docker','--context',lab['context'],*args],text=True).strip()
c=json.loads(docker('inspect',lab['name']))[0];assert c['Id']==lab['container_id'] and c['Image']==lab['image'] and c['State']['Running']
token=uuid.uuid4().hex;name='aos-fixed-collector-'+token;schema='test_fixed_collector_'+token;library='/tmp/aos_fixed_collector_'+token+'.so'
image=docker('image','inspect','aos-planner-observer-1797:probe','--format','{{.Id}}')
(B/'identity-attempt.json').open('x').write(json.dumps(dict(image=image,container=name,schema=schema,library=library,source_sha256=hashlib.sha256((B/'probe.c').read_bytes()).hexdigest())))
docker('create','--name',name,image,'/never-start');docker('cp',name+':/probe.so',str(B/'probe.so'));docker('cp',str(B/'probe.so'),lab['name']+':'+library)
assert docker('exec',lab['name'],'sha256sum',library).split()[0]==hashlib.sha256((B/'probe.so').read_bytes()).hexdigest()
params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',dbname='aos_test_05f1a1dcd51f_ti4_test',passfile=lab['passfile'])
with psycopg.connect(**params) as conn:
 assert conn.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster'];conn.rollback()
 conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
 xid=conn.execute('SELECT pg_current_xact_id()::text').fetchone()[0]
 conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
 conn.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(schema)))
 conn.execute(sql.SQL("CREATE FUNCTION {}.probe(uuid,text,xid8,integer) RETURNS jsonb LANGUAGE C VOLATILE SECURITY INVOKER SET search_path=pg_catalog AS {},'probe_fixed_collector'").format(sql.Identifier(schema),sql.Literal(library)))
 conn.execute(sql.SQL('REVOKE ALL ON FUNCTION {}.probe(uuid,text,xid8,integer) FROM PUBLIC,aos_runtime').format(sql.Identifier(schema)))
 for args in [(None,None,None,None),(uuid.uuid4(),'sha256:'+'0'*64,xid,conn.info.backend_pid)]:
  try:
   with conn.transaction():conn.execute(sql.SQL('SELECT {}.probe(%s,%s,%s,%s)').format(sql.Identifier(schema)),args)
  except psycopg.Error as e:assert 'TEST_FIXED_COLLECTOR_IDENTITY_REQUIRED' in str(e)
  else:raise AssertionError('admin admitted')
 conn.rollback()
with psycopg.connect(**params) as conn:
 conn.execute('BEGIN READ ONLY')
 assert conn.execute('SELECT pg_xact_status(%s::xid8)',(xid,)).fetchone()[0]=='aborted'
 assert conn.execute('SELECT count(*) FROM pg_namespace WHERE nspname=%s',(schema,)).fetchone()[0]==0
 conn.rollback()
r=dict(admin_denied=True,null_denied=True,transaction_aborted=True,schema_absent=True,full_source_positive=False,execution_authorized=False,library_sha256=hashlib.sha256((B/'probe.so').read_bytes()).hexdigest(),xid=xid)
(B/'identity-result.json').open('x').write(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
