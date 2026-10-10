"""Exact module reader trial; transaction-only native SQL, no Source replay."""
import hashlib,json,os,subprocess,uuid
from pathlib import Path
import psycopg
B=Path(__file__).resolve().parent;R=B.parents[2];l=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());u=uuid.uuid4().hex
image=(B/'image-id.txt').read_text().strip();lib='/tmp/aos_admission_modules_'+u+'.so';artifact='aos-modules-artifact-'+u
p=R/'services/aos-api/postgres-extensions/aos_admission_end';hashes={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in ['aos_admission_end.c','Makefile','aos_admission_end.control','aos_admission_end--0.1.sql']}
def docker(args):return subprocess.check_output(['docker',*args],text=True).strip()
st=json.loads(docker(['inspect',l['name']]))[0];assert st['Id']==l['container_id'] and st['Image']==l['image'] and st['State']['Running']
params=dict(host='127.0.0.1',port=l['port'],user='aos_app',dbname='aos_test_05f1a1dcd51f_ti4_test',passfile=l['passfile'])
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==l['cluster']
 assert c.execute("SELECT to_regprocedure('aos_admission_native_private.loaded_module_paths()')").fetchone()[0] is None
 before=c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone()
(B/'attempt.json').open('x').write(json.dumps(dict(image=image,library=lib,source_hashes=hashes,red_missing_modules_function=True,no_business_effects=True),indent=2)+'\n')
aid=docker(['create','--network','none','--name',artifact,image]);(B/'artifact.json').open('x').write(json.dumps(dict(id=aid)))
subprocess.run(['docker','cp',artifact+':/aos_admission_end.so',str(B/'modules.so')],check=True);sha=hashlib.sha256((B/'modules.so').read_bytes()).hexdigest();subprocess.run(['docker','cp',str(B/'modules.so'),l['name']+':'+lib],check=True);assert docker(['exec',l['name'],'sha256sum',lib]).split()[0]==sha
foreign=json.loads((B.parent/'callback-order-r1/installation.json').read_text());spec=B/'spec.json';spec.open('x').write(json.dumps(dict(cluster=l['cluster'],database=params['dbname'],library=lib,library_sha256=sha,source_hashes=hashes,evidence=str(B),foreign_library=foreign['library'],foreign_library_sha256=foreign['binary_sha256']),indent=2)+'\n')
env=os.environ.copy();env.update(AOS_TEST_USE_SHARED_DATABASE='1',AOS_NATIVE_MODULE_TEST_SPEC=str(spec),PYTHONPATH=str(R/'services/aos-api'))
with (B/'pytest.log').open('x') as out:
 run=subprocess.run([str(R/'services/aos-api/.venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider','services/aos-api/tests/aip/test_shared_parent_native_ending_pg.py','-k','native_modules'],cwd=R,env=env,stdout=out,stderr=subprocess.STDOUT)
with psycopg.connect(**params) as c:
 c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
 assert c.execute("SELECT to_regprocedure('aos_admission_native_private.loaded_module_paths()')").fetchone()[0] is None
 assert c.execute("SELECT prosrc,probin,proacl::text FROM pg_proc WHERE oid='aos_admission_native_private.pending_relations()'::regprocedure").fetchone()==before
 assert c.execute("SELECT count(*) FROM pg_auth_members WHERE roleid='aos_physical_capacity_occupation_owner'::regrole OR member='aos_physical_capacity_occupation_owner'::regrole").fetchone()[0]==0
 verifier=docker(['exec',l['name'],'sha256sum','/usr/local/lib/postgresql/aos_ed25519.so']).split()[0];assert verifier=='6054f5dd98337b2da957ba7984333f96e26c7141b0a8d8fbd4e3981d2bc4745e'
assert hashes=={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in hashes}
result=dict(pytest_exit=run.returncode,source_hashes=hashes,library_sha256=sha,original_pending_reader_exact=True,new_function_absent_after_rollback=True,owner_memberships_zero=True,original_signature_binary_exact=True,original_guard_changed=False,formal_database_changed=False,full_admission=False,full_task_delivered=False,execution_allowed=False)
(B/'result.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps({'pytest_exit':run.returncode,'new_function_absent_after_rollback':True,'full_admission':False}))
