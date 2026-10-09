from pathlib import Path
import os,sys,json,hashlib
import psycopg
from psycopg.rows import dict_row
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_shared_parent_executor_set_reader import shared_parent_executor_set_statements,FUNCTION
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
db='aos_test_8eb453b71d1c_ti4_test'
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row) as c:
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 assert c.execute('SELECT to_regprocedure(%s) AS f',(FUNCTION,)).fetchone()['f'] is None
 with c.transaction(force_rollback=True):
  for sql in shared_parent_executor_set_statements():c.execute(sql)
  metadata=c.execute('SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE oid=%s::regprocedure',(FUNCTION,)).fetchone()
  try:
   with c.transaction():c.execute('SELECT public.read_model_shared_parent_executor_set_facts(%s,%s,%s,%s)',('x','a'*64,'sha256:'+'b'*64,'sha256:'+'c'*64))
  except psycopg.errors.InsufficientPrivilege as exc:rejection=dict(sqlstate=exc.sqlstate,message=exc.diag.message_primary)
  else:raise AssertionError('admin must not impersonate occupation caller')
 assert c.execute('SELECT to_regprocedure(%s) AS f',(FUNCTION,)).fetchone()['f'] is None
 out=dict(database=db,cluster=lab['cluster'],ddl_compiled=True,administrator_rejected=rejection,metadata=metadata,installation_rolled_back=True,native_positive_verified=False,root_provenance_verified=False,execution_allowed=False,file_hashes={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in ['services/aos-api/aos_api/aip_shared_parent_executor_set_reader.py','services/aos-api/tests/aip/test_shared_parent_executor_set_reader_pg.py']})
 (B/'compile-bridge-result-r1.json').open('x').write(json.dumps(out,indent=2)+'\n')
 print(json.dumps(out))
