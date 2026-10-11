from pathlib import Path
import json,subprocess,uuid,hashlib
import psycopg
from psycopg import sql
B=Path(__file__).resolve().parent;R=B.parents[2];lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());spec=json.loads((B.parent/'executable-maps-1820/spec.json').read_text());cmd=['docker','--context','desktop-linux']
st=json.loads(subprocess.check_output(cmd+['inspect',lab['name']],text=True))[0];assert st['Id']==lab['container_id'] and st['Image']==lab['image'] and st['State']['Running']
assert subprocess.check_output(cmd+['exec',lab['name'],'sha256sum',spec['library']],text=True).split()[0]==spec['library_sha256']
params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=spec['database'],passfile=lab['passfile']);schema='test_owned_role_boundary_'+uuid.uuid4().hex;owner='aos_physical_capacity_occupation_owner';cases=[];roles={}
with psycopg.connect(**params) as c:
 assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 original=c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone()
 c.execute(sql.SQL('CREATE SCHEMA {} AUTHORIZATION {}').format(sql.Identifier(schema),sql.Identifier(owner)))
 for role in [owner,'aos_runtime']:
  roles[role]=c.execute('SELECT rolsuper,rolcreaterole,rolcreatedb,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s',(role,)).fetchone()
  assert not any(roles[role])
  c.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(role)))
  actions=[('load_absolute',sql.SQL('LOAD {}').format(sql.Literal(spec['library']))),('set_library_path',sql.SQL('SET LOCAL dynamic_library_path={}').format(sql.Literal('/tmp'))),('create_c',sql.SQL('CREATE FUNCTION {}.candidate() RETURNS oid[] AS {}, {} LANGUAGE C').format(sql.Identifier(schema),sql.Literal(spec['library']),sql.Literal('aos_admission_pending_relations')))]
  for name,statement in actions:
   c.execute('SAVEPOINT boundary')
   state=None;message=None
   try:c.execute(statement)
   except psycopg.Error as e:state=e.sqlstate;message=e.diag.message_primary
   finally:c.execute('ROLLBACK TO SAVEPOINT boundary')
   cases.append({'role':role,'case':name,'sqlstate':state,'message':message});assert state=='42501',(role,name,state)
  c.execute('RESET ROLE')
 c.rollback()
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT to_regnamespace(%s)',(schema,)).fetchone()[0] is None
 assert c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone()==original
result={'cases':cases,'role_flags':roles,'rollback_verified':True,'original_reader_unchanged':True,'full_reachable_native_closure':False,'execution_authorized':False}
(B/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
