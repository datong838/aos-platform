from pathlib import Path
import subprocess,json,uuid,hashlib
import psycopg
from psycopg import sql
B=Path(__file__).resolve().parent;R=B.parents[2];N=B.parent
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());spec=json.loads((N/'executable-maps-1820/spec.json').read_text());cmd=['docker','--context','desktop-linux']
def docker(args):return subprocess.check_output(cmd+args,text=True).strip()
st=json.loads(docker(['inspect',lab['name']]))[0];assert st['Id']==lab['container_id'] and st['Image']==lab['image'] and st['State']['Running']
for name,digest in spec['source_hashes'].items():assert hashlib.sha256((R/'services/aos-api/postgres-extensions/aos_admission_end'/name).read_bytes()).hexdigest()==digest
assert docker(['exec',lab['name'],'sha256sum',spec['library']]).split()[0]==spec['library_sha256']
image=(B/'image-id.txt').read_text().strip();cid=docker(['create','--network=none',image,'/never-start']);(B/'artifact.json').write_text(json.dumps({'container':cid,'image':image})+'\n');assert not json.loads(docker(['inspect',cid]))[0]['Mounts']
subprocess.run(cmd+['cp',cid+':/probe.so',str(B/'probe.so')],check=True)
u=uuid.uuid4().hex;lib='/tmp/aos_anonymous_probe_'+u+'.so';subprocess.run(cmd+['cp',str(B/'probe.so'),lab['name']+':'+lib],check=True);digest=hashlib.sha256((B/'probe.so').read_bytes()).hexdigest();assert docker(['exec',lab['name'],'sha256sum',lib]).split()[0]==digest
params=dict(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=spec['database'],passfile=lab['passfile']);schema='test_owned_anonymous_'+u
fn='aos_admission_native_private.executable_mapping_facts()';loader='aos_admission_native_private.loaded_module_paths()';original='aos_admission_native_private.pending_relations()'
with psycopg.connect(**params) as c:
 assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 assert c.execute('SELECT to_regprocedure(%s)',(fn,)).fetchone()[0] is None
 before=c.execute('SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid=%s::regprocedure',(original,)).fetchone()
 c.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
 c.execute(sql.SQL('CREATE FUNCTION {}.probe(boolean) RETURNS bigint AS {}, {} LANGUAGE C STRICT').format(sql.Identifier(schema),sql.Literal(lib),sql.Literal('test_mapping')))
 c.execute(sql.SQL('REVOKE ALL ON FUNCTION {}.probe(boolean) FROM PUBLIC').format(sql.Identifier(schema)))
 ddl=(R/'services/aos-api/postgres-extensions/aos_admission_end/aos_admission_end--0.1.sql').read_text().split('-- Supported loader observation, never a caller-supplied package allowlist.',1)[1]
 c.execute(ddl.replace("'MODULE_PATHNAME'",sql.Literal(spec['library']).as_string(c)),prepare=False)
 def probe(value):return c.execute(sql.SQL('SELECT {}.probe(%s)').format(sql.Identifier(schema)),(value,)).fetchone()[0]
 def observe():
  c.execute('SET LOCAL ROLE aos_physical_capacity_occupation_owner')
  mappings=c.execute('SELECT '+fn).fetchone()[0];modules=c.execute('SELECT '+loader).fetchone()[0]
  c.execute('RESET ROLE');return mappings,modules
 def contains(lines,address):return any(int(x.split()[0].split('-')[0],16)<=address<int(x.split()[0].split('-')[1],16) for x in lines)
 probe(False);baseline,old_modules=observe();address=probe(True)
 mapped,new_modules=observe();pid=c.execute('SELECT pg_backend_pid()').fetchone()[0]
 raw=docker(['exec',lab['name'],'cat',f'/proc/{pid}/maps']);expected=[x for x in raw.splitlines() if 'x' in x.split()[1]]
 assert mapped['mappings']==expected and contains(expected,address) and not contains(baseline['mappings'],address)
 assert old_modules==new_modules
 probe(False);released,_=observe();assert not contains(released['mappings'],address)
 c.rollback()
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute('SELECT to_regprocedure(%s)',(fn,)).fetchone()[0] is None
 assert c.execute('SELECT to_regnamespace(%s)',(schema,)).fetchone()[0] is None
 assert c.execute('SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid=%s::regprocedure',(original,)).fetchone()==before
result={'helper_sha256':digest,'backend_pid':pid,'anonymous_rx_address':hex(address),'loader_unchanged':True,'new_reader_matches_independent_kernel_maps':True,'anonymous_rx_seen_then_released':True,'page_executed':False,'sql_rollback_verified':True,'original_reader_unchanged':True,'execution_authorized':False,'full_task_delivered':False}
(B/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
