"""Native SERIAL snapshot/lock primitives, not a capacity authority or Owner."""
import hashlib
import json
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

base = Path(__file__).resolve().parent
repo = base.parents[1]
passfile = Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode & 0o077 == 0
assert subprocess.check_output(['docker','--context','colima-aos-a0v-test-only','inspect',
    'aos-capacity-publication-scram-20261006','--format','{{.Id}}'],text=True).strip() == '4be7e2967dfd98ad81a6d9e554c420024e9e4e90cdf5649e19355d940542aad2'
for key in ('PGPASSWORD','PGPASSFILE','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
template = json.loads((base/'legacy-ttl-r2.json').read_text())['template']
assert template == 'aos_test_f2ef54f0da1d_ti4_test'
database = 'aos_test_snapshot_lock_'+uuid4().hex[:12]
schema = 'gt_snapshot_probe'
def connect(name, **options):
    return psycopg.connect(host='127.0.0.1',port=5434,dbname=name,user='aos_app',
        passfile=str(passfile),row_factory=dict_row,**options)
def empty_template():
    with connect(template) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        assert str(c.execute('SELECT system_identifier FROM pg_control_system()').fetchone()['system_identifier']) == '7693564235776004128'
        assert all(c.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(t))).fetchone()['n']==0
            for t in ('aip_agent_run','aip_model_capacity_reservation','aip_model_capacity_event'))
        return c.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()
heads = empty_template()
with connect('aos_meta',autocommit=True) as c:
    c.execute(sql.SQL('CREATE DATABASE {} TEMPLATE {}').format(sql.Identifier(database),sql.Identifier(template)))
print('Retained native snapshot lock database:',database,flush=True)
with connect(database) as c:
    c.execute('CREATE SCHEMA gt_snapshot_probe')
    c.execute("""CREATE TABLE gt_snapshot_probe.guard(
        org_id text NOT NULL,project_id text NOT NULL,case_id text PRIMARY KEY,epoch bigint NOT NULL)""")
    c.execute("""CREATE TABLE gt_snapshot_probe.obligation(
        org_id text NOT NULL,project_id text NOT NULL,case_id text NOT NULL,id text PRIMARY KEY,units integer NOT NULL)""")
    for table in ('guard','obligation'):
        c.execute(sql.SQL('ALTER TABLE gt_snapshot_probe.{} ENABLE ROW LEVEL SECURITY').format(sql.Identifier(table)))
        c.execute(sql.SQL('ALTER TABLE gt_snapshot_probe.{} FORCE ROW LEVEL SECURITY').format(sql.Identifier(table)))
        c.execute(sql.SQL("""CREATE POLICY scoped ON gt_snapshot_probe.{} TO aos_runtime
            USING(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))
            WITH CHECK(org_id=current_setting('aos.org_id',true) AND project_id=current_setting('aos.project_id',true))""").format(sql.Identifier(table)))
    c.execute('GRANT USAGE ON SCHEMA gt_snapshot_probe TO aos_runtime')
    c.execute('GRANT SELECT,UPDATE ON gt_snapshot_probe.guard TO aos_runtime')
    c.execute('GRANT SELECT,INSERT ON gt_snapshot_probe.obligation TO aos_runtime')
    for case in ('advisory_only','row_lock_unchanged','versioned_row_update'):
        c.execute("INSERT INTO gt_snapshot_probe.guard VALUES('org-org','dev-project',%s,0)",(case,))

def begin(c):
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE')
    c.execute('SET LOCAL ROLE aos_runtime')
    c.execute("SELECT set_config('aos.org_id','org-org',true),set_config('aos.project_id','dev-project',true)")
    c.execute("SET LOCAL lock_timeout='5s'")
    c.execute("SET LOCAL statement_timeout='8s'")
    r=c.execute("SELECT current_user AS role,current_setting('transaction_isolation') AS isolation,pg_backend_pid() AS pid,pg_current_xact_id()::text AS xid").fetchone()
    assert r['role']=='aos_runtime' and r['isolation']=='serializable'
    return r
def lock(c,case):
    if case=='advisory_only':
        c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('test-only/physical/'+case,))
    elif case=='row_lock_unchanged':
        c.execute('SELECT epoch FROM gt_snapshot_probe.guard WHERE case_id=%s FOR UPDATE',(case,)).fetchone()
    else:
        c.execute('UPDATE gt_snapshot_probe.guard SET epoch=epoch+1 WHERE case_id=%s',(case,))
def count(c,case):
    return c.execute('SELECT count(*) AS n FROM gt_snapshot_probe.obligation WHERE case_id=%s',(case,)).fetchone()['n']
def insert(c,case,label):
    c.execute("INSERT INTO gt_snapshot_probe.obligation VALUES('org-org','dev-project',%s,%s,1)",(case,case+'/'+label))
results=[]
for case in ('advisory_only','row_lock_unchanged','versioned_row_update'):
    with connect(database) as first,connect(database) as second,connect(database,autocommit=True) as observer:
        first_id=begin(first);lock(first,case);assert count(first,case)==0
        second_id=begin(second)
        assert second.execute('SELECT epoch FROM gt_snapshot_probe.guard WHERE case_id=%s',(case,)).fetchone()['epoch']==0
        insert(first,case,'first')
        def compete():
            stage='lock';out={}
            try:
                lock(second,case)
                out['lock_acquired']=True
                stage='count';out['snapshot_count']=count(second,case)
                stage='insert';insert(second,case,'second')
                stage='commit';second.commit()
                out['unexpected_commit']=True
            except psycopg.Error as e:
                out.update(rejected_at=stage,sqlstate=e.sqlstate)
                second.rollback()
            return out
        with ThreadPoolExecutor(max_workers=1) as executor:
            future=executor.submit(compete)
            deadline=time.monotonic()+3
            blocking=[]
            while first_id['pid'] not in blocking:
                blocking=observer.execute('SELECT pg_blocking_pids(%s) AS pids',(second_id['pid'],)).fetchone()['pids']
                assert not future.done(), 'Expected native contender wait missing'
                assert time.monotonic()<deadline,'Blocking-pid evidence timed out'
                time.sleep(.01)
            first.commit()
            result=future.result(timeout=10)
        assert result['sqlstate']=='40001' and not result.get('unexpected_commit')
        if case=='versioned_row_update':
            assert result['rejected_at']=='lock' and 'snapshot_count' not in result
        else:
            assert result['snapshot_count']==0 and result['rejected_at'] in ('insert','commit')
        visible=observer.execute('SELECT count(*) AS n FROM gt_snapshot_probe.obligation WHERE case_id=%s',(case,)).fetchone()['n']
        assert visible==1
        results.append(dict(case=case,first_caller=first_id,second_caller=second_id,
            observed_blockers=blocking,final_count=visible,**result))
        print(case,result,'final_count=',visible,flush=True)

with connect(database) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()==heads
    assert c.execute('SELECT count(*) AS n FROM aip_agent_run').fetchone()['n']==0
    assert c.execute("SELECT count(*) AS n FROM gt_snapshot_probe.obligation WHERE org_id='dev-org'").fetchone()['n']==0
    persisted=c.execute('SELECT case_id,epoch FROM gt_snapshot_probe.guard ORDER BY case_id').fetchall()
assert empty_template()==heads
result=dict(status='SERIAL_SNAPSHOT_LOCK_PRIMITIVES_VERIFIED',database=database,template=template,
    cluster='7693564235776004128',migration_heads=heads,cases=results,guard_rows=persisted,
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
    probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    limitations=['Test-only primitive schema; not physical ledger implementation or Source authorization',
        'Both native callers use owned admin login with transaction-local runtime role, not dedicated signed occupation identity',
        'No Task, AgentRun, Provider, budget, Intent or business execution'])
(base/'snapshot-lock-verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
