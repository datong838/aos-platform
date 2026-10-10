from pathlib import Path
import json,os,hashlib,psycopg
from psycopg.rows import dict_row
R=Path.cwd();B=R/'.evidence/gt-original-target-persisted-reader-20261010'
result=json.loads((B/'result-r5.json').read_text());proof=json.loads((B/'r5/native-proof.json').read_text());assert result['pytest_exit']==0
lab=json.loads((R/'.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text());database=proof['database'].split('/')[-1];assert database in result['databases'] and database.startswith('aos_test_')
for k in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(k,None)
with psycopg.connect(host='127.0.0.1',port=5441,user='aos_app',dbname=database,passfile=lab['passfile'],row_factory=dict_row) as c:
 c.execute('SET TRANSACTION READ ONLY');identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone();assert identity['cluster']==lab['cluster'] and identity['readonly']=='on'
 rows=c.execute('''SELECT o.origin_xid::text AS xid,o.origin_pid AS pid,pg_xact_status(o.origin_xid) AS status,
 x.content_hash,encode(sha256(x.body),'hex') AS body_hash FROM aos_model_eval_issuer_private.target_result_origin o
 JOIN aos_model_eval_execution_private.case_result x USING(org_id,project_id,execution_id,case_id,purpose,attempt,content_hash)
 WHERE o.origin_xid=%s::xid8''',(proof['producer_xid'],)).fetchall()
 assert len(rows)==1 and rows[0]['xid']==proof['origin']['xid'] and rows[0]['pid']==proof['origin']['pid'] and rows[0]['status']=='committed' and rows[0]['body_hash']==rows[0]['content_hash']
 waited=c.execute('SELECT pg_xact_status(%s::xid8) AS status',(proof['actual_wait']['caller_xid'],)).fetchone();assert waited['status']=='aborted'
 canary=c.execute("SELECT count(*) AS n FROM aos_model_eval_execution_private.case_result WHERE org_id='dev-org'").fetchone()['n'];assert canary==0
assert all(hashlib.sha256((R/p).read_bytes()).hexdigest()==h for p,h in result['file_hashes'].items())
assert proof['judge_input']['canonical'] and proof['judge_input']['actual_bytes_preserved'] and proof['judge_input']['uncommitted_and_runtime_rejected'] and not proof['actual_transport'] and not proof['bootstrap_trusted']
out=dict(authority='AOS-001693',identity=identity,exact_original_producer_rows=rows,expired_lock_wait_caller_status=waited['status'],canary_rows=canary,source_hashes_match=True,pytest_reports=result['reports'],judge_input=proof['judge_input'],raw_log_sha256={f:hashlib.sha256((B/f).read_bytes()).hexdigest() for f in ('native-r4.log','native-r5.log')},actual_transport=False,formal_root_provenance=False,execution_allowed=False,full_task_delivered=False)
(B/'independent-judge-input-1693.json').open('x').write(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(database=database,committed_original_producer_rows=1,source_hashes_match=True,execution_allowed=False)))
