"""Exact owned isolated native package test; retain unknown effects for reconciliation."""
import hashlib,json,os,subprocess,uuid
from pathlib import Path
import psycopg
B=Path(__file__).resolve().parent;R=B.parents[1];lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());image=(B/'image-id.txt').read_text().strip();uid=uuid.uuid4().hex;artifact='aos-native-end-artifact-'+uid;library='/tmp/aos_admission_end_'+uid+'.so';db='aos_test_05f1a1dcd51f_ti4_test'
p=R/'services/aos-api/postgres-extensions/aos_admission_end';names=['aos_admission_end.c','aos_admission_end.control','aos_admission_end--0.1.sql','Makefile'];hashes={f:hashlib.sha256((p/f).read_bytes()).hexdigest() for f in names}
def call(args):return subprocess.check_output(['docker',*args],text=True).strip()
state=json.loads(call(['inspect',lab['name']]))[0];assert state['Id']==lab['container_id'] and state['Image']==lab['image'] and state['State']['Running']
with psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname=db,passfile=lab['passfile']) as c:
 c.execute('SET TRANSACTION READ ONLY');assert c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0]==lab['cluster']
 assert c.execute("SELECT to_regprocedure('aos_admission_native_private.pending_relations()')").fetchone()[0] is None
(B/'reader-attempt-r1.json').open('x').write(json.dumps(dict(image=image,artifact_container=artifact,library=library,database=db,cluster=lab['cluster'],source_hashes=hashes,red_missing_native_function=True,full_admission=False),indent=2)+'\n')
id=call(['create','--network','none','--name',artifact,image]);(B/'artifact-container-r1.json').open('x').write(json.dumps(dict(id=id)))
subprocess.run(['docker','cp',artifact+':/aos_admission_end.so',str(B/'reader.so')],check=True);sha=hashlib.sha256((B/'reader.so').read_bytes()).hexdigest();subprocess.run(['docker','cp',str(B/'reader.so'),lab['name']+':'+library],check=True);assert call(['exec',lab['name'],'sha256sum',library]).split()[0]==sha
spec=B/'reader-spec-r1.json';spec.open('x').write(json.dumps(dict(cluster=lab['cluster'],database=db,library=library,library_sha256=sha,source_hashes=hashes,evidence=str(B)),indent=2)+'\n')
env=os.environ.copy();env['AOS_NATIVE_END_TEST_SPEC']=str(spec);env['PYTHONPATH']=str(R/'services/aos-api')
with (B/'native-reader-r1.log').open('x') as out:
 run=subprocess.run([str(R/'services/aos-api/.venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider','services/aos-api/tests/aip/test_shared_parent_native_ending_pg.py'],cwd=R,env=env,stdout=out,stderr=subprocess.STDOUT)
assert hashes=={f:hashlib.sha256((p/f).read_bytes()).hexdigest() for f in names}
result=dict(pytest_exit=run.returncode,source_files_unchanged=True,library_sha256=sha,full_admission=False,full_task_delivered=False,execution_allowed=False)
(B/'reader-result-r1.json').open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
