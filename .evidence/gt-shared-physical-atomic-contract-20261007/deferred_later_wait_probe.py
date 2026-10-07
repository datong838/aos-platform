"""Native constraint-queue deadline controls, not product authority or business."""
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

BASE=Path(__file__).resolve().parent
REPO=BASE.parents[1]
TEMPLATE='aos_test_f2ef54f0da1d_ti4_test'
CLUSTER='7693564235776004128'
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):
    os.environ.pop(key,None)
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect',
    'aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip()=='4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
def connect(name,**kw):
    return psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=name,
        passfile=str(passfile),row_factory=dict_row,**kw)
def template_state():
    with connect(TEMPLATE) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert c.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster']==CLUSTER
        assert all(c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n']==0 for t in
            ('aip_agent_run','aip_model_capacity_reservation','aip_budget_reservation','aip_model_eval_budget_reservation'))
        return c.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()

from threading import Thread

attempt_path=BASE/'deferred-later-wait-attempt.json'
assert not attempt_path.exists(), 'Prior attempt must be reconciled, never replayed'
heads=template_state()
database='aos_test_later_wait_'+uuid4().hex[:12]
with connect('aos_meta',autocommit=True) as admin:
    admin.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database),sql.Identifier(TEMPLATE)))
print('Retained database',database,flush=True)
CHECK="""BEGIN
 IF pg_catalog.current_query() IS DISTINCT FROM 'COMMIT' THEN
  RAISE EXCEPTION 'GT_TEST_COMMIT_COMMAND_REQUIRED' USING ERRCODE='23514';
 END IF;
 IF clock_timestamp()>=NEW.deadline THEN
  RAISE EXCEPTION 'GT_TEST_DEADLINE_EXPIRED' USING ERRCODE='23514';
 END IF;
 INSERT INTO gt_later_wait.audit VALUES(NEW.case_id,'checked',clock_timestamp());
 RETURN NULL;
END"""
WAIT="""BEGIN
 PERFORM pg_catalog.pg_advisory_xact_lock(NEW.lock_key);
 INSERT INTO gt_later_wait.audit VALUES(NEW.case_id,'wait_completed',clock_timestamp());
 RETURN NULL;
END"""
with connect(database) as admin:
    admin.execute('CREATE SCHEMA gt_later_wait')
    admin.execute('REVOKE ALL ON SCHEMA gt_later_wait FROM PUBLIC')
    admin.execute('CREATE TABLE gt_later_wait.audit(case_id text,event text,observed_at timestamptz)')
    for name,body in [('check_deadline',CHECK),('wait_lock',WAIT)]:
        admin.execute(sql.SQL('CREATE FUNCTION gt_later_wait.{}() RETURNS trigger LANGUAGE plpgsql '
            'SECURITY INVOKER SET search_path=pg_catalog AS {}').format(sql.Identifier(name),sql.Literal(body)))
    for table,functions in [('check_then_wait',['check_deadline','wait_lock']),('wait_then_check',['wait_lock','check_deadline'])]:
        admin.execute(sql.SQL('CREATE TABLE gt_later_wait.{}(case_id text PRIMARY KEY,deadline timestamptz NOT NULL,lock_key bigint NOT NULL)').format(sql.Identifier(table)))
        for trigger,function in zip(['a_first','z_second'],functions):
            admin.execute(sql.SQL('CREATE CONSTRAINT TRIGGER {} AFTER INSERT ON gt_later_wait.{} '
                'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION gt_later_wait.{}()').format(
                    sql.Identifier(trigger),sql.Identifier(table),sql.Identifier(function)))
    admin.execute('GRANT USAGE ON SCHEMA gt_later_wait TO aos_runtime')
    admin.execute('GRANT SELECT,INSERT ON ALL TABLES IN SCHEMA gt_later_wait TO aos_runtime')
    admin.execute('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA gt_later_wait FROM PUBLIC')
    admin.execute('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA gt_later_wait TO aos_runtime')

attempt={'database':database,'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'cases':[]}
results=[]
for index,case in enumerate(('check_then_wait','wait_then_check')):
    blocker=connect(database,autocommit=True)
    caller=connect(database,autocommit=True)
    observer=connect(database,autocommit=True)
    lock_key=int(uuid4().hex[:14],16)
    terminal={}
    worker=None
    try:
        blocker.execute('SELECT pg_advisory_lock(%s)',(lock_key,))
        caller.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ WRITE')
        caller.execute('SET LOCAL ROLE aos_runtime')
        caller.execute("SET LOCAL statement_timeout='15s'")
        assert caller.pgconn.used_password
        identity=caller.execute("SELECT session_user AS login,current_user AS role,pg_backend_pid() AS pid,"
            "pg_current_xact_id()::text AS xid,current_setting('transaction_isolation') AS isolation").fetchone()
        assert identity['login']=='aos_app' and identity['role']=='aos_runtime' and identity['isolation']=='serializable'
        deadline=caller.execute(sql.SQL("INSERT INTO gt_later_wait.{} VALUES(%s,clock_timestamp()+interval '2 seconds',%s) "
            'RETURNING extract(epoch FROM deadline)::float8 AS deadline').format(sql.Identifier(case)),(case,lock_key)).fetchone()['deadline']
        before=caller.execute('SELECT extract(epoch FROM clock_timestamp())::float8 AS clock').fetchone()['clock']
        assert before<deadline
        record={'case':case,'identity':identity,'deadline':deadline,'status':'COMMIT_ATTEMPTED','end_calls':1}
        attempt['cases'].append(record)
        attempt_path.write_text(json.dumps(attempt,indent=2)+'\n')
        def end_once():
            try:
                caller.execute('COMMIT')
                terminal.update(status='COMMIT_CONFIRMED',sqlstate=None,message=None)
            except psycopg.Error as error:
                terminal.update(status='COMMIT_FAILED',sqlstate=error.sqlstate,message=error.diag.message_primary)
        worker=Thread(target=end_once,daemon=True)
        worker.start()
        limit=time.monotonic()+10
        waiting=None
        while time.monotonic()<limit:
            observer.execute('SELECT pg_stat_clear_snapshot()')
            state=observer.execute("SELECT query,wait_event_type,wait_event,extract(epoch FROM clock_timestamp())::float8 AS clock "
                'FROM pg_stat_activity WHERE pid=%s',(identity['pid'],)).fetchone()
            locks=observer.execute("SELECT count(*) AS n FROM pg_locks WHERE pid=%s AND locktype='advisory' AND NOT granted",(identity['pid'],)).fetchone()['n']
            if state and state['query']=='COMMIT' and state['wait_event']=='advisory' and locks==1:
                if waiting is None:waiting=state
                if state['clock']>deadline+0.1:
                    crossed=state
                    break
            assert worker.is_alive(), terminal
            time.sleep(0.025)
        else:raise AssertionError('Actual COMMIT advisory wait crossing deadline not observed')
        assert waiting['clock']<deadline
        assert blocker.execute('SELECT pg_advisory_unlock(%s) AS released',(lock_key,)).fetchone()['released']
        worker.join(16)
        assert not worker.is_alive(), 'Unknown COMMIT terminal; reconcile only'
        record.update(terminal)
        attempt_path.write_text(json.dumps(attempt,indent=2)+'\n')
        after=observer.execute('SELECT extract(epoch FROM clock_timestamp())::float8 AS clock').fetchone()['clock']
        observer.execute('BEGIN ISOLATION LEVEL SERIALIZABLE READ ONLY')
        rows=observer.execute(sql.SQL('SELECT count(*) AS n FROM gt_later_wait.{}').format(sql.Identifier(case))).fetchone()['n']
        audits=observer.execute('SELECT event,extract(epoch FROM observed_at)::float8 AS clock FROM gt_later_wait.audit '
            'WHERE case_id=%s ORDER BY observed_at',(case,)).fetchall()
        observer.execute('ROLLBACK')
        if index==0:
            assert terminal['status']=='COMMIT_CONFIRMED' and rows==1
            assert [x['event'] for x in audits]==['checked','wait_completed']
            assert audits[0]['clock']<deadline<audits[1]['clock']<=after
        else:
            assert terminal['status']=='COMMIT_FAILED' and terminal['sqlstate']=='23514'
            assert terminal['message']=='GT_TEST_DEADLINE_EXPIRED' and rows==0 and audits==[]
        results.append(dict(record,before=before,first_actual_wait=waiting,crossed_actual_wait=crossed,after=after,rows=rows,audits=audits))
        print(case,terminal['status'],'rows',rows,flush=True)
    finally:
        blocker.close()
        if worker is not None:worker.join(16)
        if worker is None or not worker.is_alive():caller.close()
        observer.close()
with connect(database) as observer:
    observer.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert observer.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster']==CLUSTER
    assert observer.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()==heads
    counts={t:observer.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in
        ('aip_agent_run','aip_model_capacity_reservation','aip_budget_reservation','aip_model_eval_budget_reservation')}
    assert not any(counts.values())
    triggers=observer.execute("SELECT c.relname,t.tgname,t.tgdeferrable,t.tginitdeferred,pg_get_triggerdef(t.oid) AS definition "
        "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='gt_later_wait' ORDER BY c.relname,t.tgname").fetchall()
    functions=observer.execute("SELECT p.proname,pg_get_functiondef(p.oid) AS definition FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='gt_later_wait' ORDER BY p.proname").fetchall()
assert template_state()==heads
assert len(triggers)==4 and all(t['tgdeferrable'] and t['tginitdeferred'] for t in triggers)
result={'status':'LATER_DEFERRED_WAIT_CROSSES_CHECKED_DEADLINE_NATIVE_COUNTEREXAMPLE_CONFIRMED',
    'database':database,'template':TEMPLATE,'cluster':CLUSTER,'head':attempt['head'],'migration_heads':heads,
    'probe_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':results,
    'actual_triggers':triggers,'actual_functions':functions,'original_business_counts':counts,
    'limitations':['Synthetic trusted test schema, not an original product exploit or execution authority',
        'Decision check before a later blocking deferred trigger does not guarantee deadline at commit completion',
        'Ordering the check last in this controlled two-trigger case rejects expiration; whole product queue/locks/end channels remain pending',
        'No statement about WAL flush or remote commit acknowledgement deadline; no Source/JWT/Intent/budget/product change']}
(BASE/'deferred-later-wait-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],flush=True)
