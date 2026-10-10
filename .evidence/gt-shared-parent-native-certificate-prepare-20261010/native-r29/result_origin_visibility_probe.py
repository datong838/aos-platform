"""Test-only independent visibility/FK probe, no executed case or grant."""
import json,hashlib,psycopg
from psycopg.rows import dict_row

def observe_result_visibility(conn,description,evidence_dir):
 db=conn.info.dbname;assert db.startswith('aos_test_')
 execution=str(description.plan_id);xid=description.immutable.caller_xid;pid=description.immutable.caller_pid
 current=conn.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone();assert current==dict(xid=xid,pid=pid)
 with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=db,row_factory=dict_row) as observer:
  observer.execute('SET TRANSACTION READ ONLY')
  identity=observer.execute("SELECT current_database() AS database,system_identifier::text AS cluster,pg_backend_pid() AS pid,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity['cluster']=='7694680278363095064' and identity['pid']!=pid and identity['readonly']=='on'
  status=observer.execute('SELECT pg_xact_status(%s::xid8) AS status',(xid,)).fetchone()['status'];assert status=='in progress'
  counts={table:observer.execute('SELECT count(*) AS n FROM '+table+' WHERE execution_id=%s',(execution,)).fetchone()['n'] for table in ('aos_model_eval_execution_private.manifest','aos_model_eval_issuer_private.executor_certificate')};assert set(counts.values())=={0}
  observer.rollback()
  observer.execute('BEGIN ISOLATION LEVEL SERIALIZABLE');observer.execute("SET LOCAL lock_timeout='500ms'");observer.execute("SET LOCAL statement_timeout='2s'");observer.execute("SET LOCAL ROLE aos_model_eval_execution_owner");observer.execute("SET LOCAL aos.org_id='org-org'");observer.execute("SET LOCAL aos.project_id='dev-project'")
  ox=observer.execute('SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid').fetchone();assert ox['xid']!=xid and ox['pid']!=pid
  raw=b'{"synthetic":"FK visibility probe, never an execution result"}';digest=hashlib.sha256(raw).hexdigest()
  try:
   observer.execute('INSERT INTO aos_model_eval_execution_private.case_result(org_id,project_id,execution_id,case_id,purpose,attempt,content_hash,body) VALUES (%s,%s,%s,%s,%s,1,%s,%s)',('org-org','dev-project',execution,description.immutable.manifest.cases[0].case_id,'target',digest,raw))
   raise AssertionError('independent uncommitted-manifest child unexpectedly inserted')
  except psycopg.errors.ForeignKeyViolation as exc:
   state=exc.sqlstate;constraint=exc.diag.constraint_name
  finally:observer.rollback()
  observer.execute('SET TRANSACTION READ ONLY');rolled=observer.execute('SELECT pg_xact_status(%s::xid8) AS status',(ox['xid'],)).fetchone()['status'];assert rolled=='aborted'
  retained=observer.execute('SELECT count(*) AS n FROM aos_model_eval_execution_private.case_result WHERE execution_id=%s',(execution,)).fetchone()['n'];assert retained==0
 out=dict(database=db,source_caller=current,observer=identity,source_status=status,independent_visible_counts=counts,fk_rejection=state,constraint=constraint,child_writer=ox,child_writer_status=rolled,retained_case_rows=retained,test_only_unsigned_probe=True,actual_model_execution=False,execution_allowed=False)
 (evidence_dir/'result-origin-visibility.json').open('x').write(json.dumps(out,indent=2)+'\n')
 return out
