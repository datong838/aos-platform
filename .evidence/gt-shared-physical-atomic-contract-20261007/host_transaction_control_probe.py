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
heads=template_state()
database='aos_test_host_control_'+uuid4().hex[:12]
with connect('aos_meta',autocommit=True) as c:
    c.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database),sql.Identifier(TEMPLATE)))
print('Retained native deferred control database',database,flush=True)
BODY="""BEGIN
 IF pg_catalog.current_query() IS DISTINCT FROM 'COMMIT' THEN
  RAISE EXCEPTION 'GT_TEST_COMMIT_COMMAND_REQUIRED' USING ERRCODE='23514';
 END IF;
 IF clock_timestamp()>=NEW.deadline THEN
  RAISE EXCEPTION 'GT_TEST_DEADLINE_EXPIRED' USING ERRCODE='23514';
 END IF;
 INSERT INTO gt_deferred_probe.audit VALUES(NEW.case_id,'deadline_checked',clock_timestamp());
 RETURN NULL;
END"""
with connect(database) as c:
    c.execute('CREATE SCHEMA gt_deferred_probe')
    c.execute('CREATE TABLE gt_deferred_probe.obligation(case_id text PRIMARY KEY,deadline timestamptz NOT NULL)')
    c.execute('CREATE TABLE gt_deferred_probe.audit(case_id text NOT NULL,event text NOT NULL,checked_at timestamptz NOT NULL)')
    c.execute('CREATE FUNCTION gt_deferred_probe.check_deadline() RETURNS trigger LANGUAGE plpgsql '
        'SECURITY INVOKER SET search_path=pg_catalog AS '+sql.Literal(BODY).as_string(c))
    c.execute('CREATE CONSTRAINT TRIGGER deadline_gate AFTER INSERT OR UPDATE ON gt_deferred_probe.obligation '
        'DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION gt_deferred_probe.check_deadline()')
    c.execute('REVOKE ALL ON SCHEMA gt_deferred_probe FROM PUBLIC')
    c.execute('GRANT USAGE ON SCHEMA gt_deferred_probe TO aos_runtime')
    c.execute('GRANT SELECT,INSERT,UPDATE ON gt_deferred_probe.obligation TO aos_runtime')
    c.execute('GRANT SELECT,INSERT ON gt_deferred_probe.audit TO aos_runtime')
import sys
from psycopg.pq import TransactionStatus
sys.path.insert(0,str(REPO/'services/aos-api'))
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.tenant_scope import TenantScope

results=[]
scope=TenantScope('org-org','dev-project')
for case in ('direct_host_sql_commit','bound_noop_then_sql_commit','bound_early_constraints','bound_expired_sql_commit'):
    with connect(database) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE')
        c.execute('SET LOCAL ROLE aos_runtime')
        assert c.pgconn.used_password
        identity=c.execute("SELECT session_user AS login,current_user AS role,pg_backend_pid() AS pid,"
            "pg_current_xact_id()::text AS xid,current_setting('transaction_isolation') AS isolation").fetchone()
        assert identity['login']=='aos_app' and identity['role']=='aos_runtime' and identity['isolation']=='serializable'
        deadline=c.execute("INSERT INTO gt_deferred_probe.obligation VALUES(%s,clock_timestamp()+interval '1 seconds') "
            "RETURNING extract(epoch FROM deadline)::float8 AS deadline",(case,)).fetchone()['deadline']
        c.execute("INSERT INTO gt_deferred_probe.audit VALUES(%s,'transaction_witness',clock_timestamp())",(case,))
        host=HostTransaction(c)
        factory=TransactionBoundConnectFactory(host,scope)
        cross_scope_denied=False
        try:
            with factory(TenantScope('dev-org','dev-project')):
                raise AssertionError('Cross-tenant factory unexpectedly yielded')
        except PermissionError:
            cross_scope_denied=True
        assert c.info.transaction_status==TransactionStatus.INTRANS
        with factory(scope) as bound:
            assert bound.commit() is None and c.info.transaction_status==TransactionStatus.INTRANS
            assert c.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']==identity['xid']
            rollback_denied=False
            try:
                bound.rollback()
            except RuntimeError:
                rollback_denied=True
            assert rollback_denied and c.info.transaction_status==TransactionStatus.INTRANS
            if case=='bound_expired_sql_commit':
                limit=time.monotonic()+4
                while c.execute('SELECT extract(epoch FROM clock_timestamp())::float8 AS clock').fetchone()['clock']<deadline+0.1:
                    assert time.monotonic()<limit;time.sleep(0.025)
            before=c.execute('SELECT extract(epoch FROM clock_timestamp())::float8 AS clock,pg_current_xact_id()::text AS xid').fetchone()
            assert before['xid']==identity['xid']
            if case!='bound_expired_sql_commit':assert before['clock']<deadline
            state=None;message=None;committed=False;end_calls=0
            try:
                if case=='bound_early_constraints':
                    bound.execute('SET CONSTRAINTS gt_deferred_probe.deadline_gate IMMEDIATE')
                    raise AssertionError('Early trigger check unexpectedly allowed')
                else:
                    end_calls=1
                    (host if case=='direct_host_sql_commit' else bound).execute('COMMIT')
                    assert c.info.transaction_status==TransactionStatus.IDLE
                    committed=True
            except psycopg.Error as error:
                state=error.sqlstate;message=error.diag.message_primary
                assert state=='23514' and message==('GT_TEST_COMMIT_COMMAND_REQUIRED'
                    if case=='bound_early_constraints' else 'GT_TEST_DEADLINE_EXPIRED')
                c.rollback()
    with connect(database) as observer:
        observer.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        rows=observer.execute('SELECT count(*) AS n FROM gt_deferred_probe.obligation WHERE case_id=%s',(case,)).fetchone()['n']
        audits=observer.execute('SELECT event FROM gt_deferred_probe.audit WHERE case_id=%s ORDER BY event',(case,)).fetchall()
        assert committed==(case in ('direct_host_sql_commit','bound_noop_then_sql_commit'))
        assert rows==(1 if committed else 0)
        assert audits==([{'event':'deadline_checked'},{'event':'transaction_witness'}] if committed else [])
    results.append(dict(case=case,identity=identity,deadline=deadline,before_end=before,committed=committed,
        sqlstate=state,message=message,sql_end_calls=end_calls,bound_commit_noop_verified=True,
        bound_rollback_denied=rollback_denied,cross_tenant_factory_denied=cross_scope_denied,
        retained_rows=rows,retained_audits=audits))
    print(case,'SQL COMMIT' if committed else message,'retained',rows,flush=True)
with connect(database) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SELECT system_identifier::text AS cluster FROM pg_control_system()').fetchone()['cluster']==CLUSTER
    assert c.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()==heads
    counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in
        ('aip_agent_run','aip_model_capacity_reservation','aip_budget_reservation','aip_model_eval_budget_reservation')}
    assert not any(counts.values())
assert template_state()==heads
files=('services/aos-api/aos_api/ecommerce_growth_host_ports.py',
       'services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py',
       'services/aos-api/aos_api/ecommerce_growth_runtime_connection.py')
r=dict(status='ORIGINAL_HOST_AND_BORROWED_SQL_END_CHANNEL_NATIVE_CONTROL_VERIFIED',database=database,
    template=TEMPLATE,cluster=CLUSTER,migration_heads=heads,cases=results,product_counts=counts,trusted_test_body=BODY,
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
    probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    original_product_sha256={n:hashlib.sha256((REPO/n).read_bytes()).hexdigest() for n in files},
    limitations=['Original trusted Host wrappers on an isolated primitive schema, not full Host dispatch/lifespan/business',
        'SQL COMMIT forwarding is not proof that any untrusted package or user can access this trusted interface',
        'No original product changes, no Source/evaluator/budget/AgentRun or formal authority',
        'Candidate deadline trigger blocks early SET/expired end only in this synthetic control',
        'Host end-channel ownership and full joint wiring remain pending'])
(BASE/'host-transaction-control-verification.json').write_text(json.dumps(r,indent=2)+'\n')
print(r['status'],flush=True)
