from pathlib import Path
import os,sys,json,hashlib
import psycopg
from psycopg.rows import dict_row
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_shared_parent_certificate_prepare import shared_parent_certificate_prepare_statements,FUNCTION,MANIFEST
from aos_api.aip_shared_parent_executor_set_reader import shared_parent_executor_set_statements,FUNCTION as READER
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());db='aos_test_8eb453b71d1c_ti4_test'
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=db,passfile=lab['passfile'],row_factory=dict_row) as c:
 assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
 signatures=(FUNCTION,MANIFEST,READER)
 assert all(c.execute('SELECT to_regprocedure(%s) AS f',(f,)).fetchone()['f'] is None for f in signatures)
 baseline=c.execute("SELECT has_function_privilege('aos_model_eval_execution_owner','public.read_capacity_shared_risk_description_origin(bytea,jsonb,uuid,text)','EXECUTE') AS origin").fetchone()
 with c.transaction(force_rollback=True):
  for sql in (*shared_parent_executor_set_statements(),*shared_parent_certificate_prepare_statements()):c.execute(sql)
  metadata={f:c.execute('SELECT prosecdef,proconfig,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE oid=%s::regprocedure',(f,)).fetchone() for f in signatures}
  try:
   with c.transaction():c.execute('SELECT public.prepare_model_shared_parent_certificate_set(%s,%s::jsonb,%s::uuid,%s,%s)',(b'{}','{}','00000000-0000-0000-0000-000000000000','sha256:'+'a'*64,b'[]'))
  except psycopg.errors.InsufficientPrivilege as exc:rejection=dict(sqlstate=exc.sqlstate,message=exc.diag.message_primary)
  else:raise AssertionError('admin must not impersonate occupation caller')
 assert all(c.execute('SELECT to_regprocedure(%s) AS f',(f,)).fetchone()['f'] is None for f in signatures)
 assert c.execute("SELECT has_function_privilege('aos_model_eval_execution_owner','public.read_capacity_shared_risk_description_origin(bytea,jsonb,uuid,text)','EXECUTE') AS origin").fetchone()==baseline
 out=dict(database=db,cluster=lab['cluster'],ddl_compiled=True,administrator_rejected=rejection,metadata=metadata,installation_and_grants_rolled_back=True,native_positive_verified=False,root_provenance_verified=False,execution_allowed=False,file_hashes={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in ['services/aos-api/aos_api/aip_shared_parent_certificate_prepare.py','services/aos-api/tests/aip/test_shared_parent_certificate_prepare_pg.py','services/aos-api/aos_api/aip_shared_parent_executor_set_reader.py']})
 (B/'compile-protocol-result-r1.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
