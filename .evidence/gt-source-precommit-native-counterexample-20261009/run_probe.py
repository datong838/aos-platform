import json,subprocess,time
from pathlib import Path
from datetime import datetime,timezone
import psycopg
from psycopg.rows import dict_row
from psycopg.pq import TransactionStatus
B=Path(__file__).resolve().parent;lab=json.loads((B/'lab.json').read_text())
def connection():return psycopg.connect(host='127.0.0.1',port=lab['port'],user='aos_app',dbname='aos_meta',passfile=lab['passfile'],row_factory=dict_row,require_auth='scram-sha-256')
with (B/'install-attempt.json').open('x') as f:json.dump(dict(cluster=lab['cluster'],admin_owned_test_only=True),f)
with connection() as c:
    assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
    c.execute('CREATE TABLE aos_precommit_probe_result (label text PRIMARY KEY, deadline timestamptz NOT NULL, xid text NOT NULL)')
    c.execute("CREATE FUNCTION public.aos_precommit_probe_arm(timestamptz,boolean) RETURNS void AS '$libdir/aos_precommit_probe','aos_precommit_probe_arm' LANGUAGE C STRICT VOLATILE")
    c.execute('REVOKE ALL ON FUNCTION public.aos_precommit_probe_arm(timestamptz,boolean) FROM PUBLIC')
(B/'installation.json').write_text(json.dumps(dict(known_committed=True,cluster=lab['cluster'])))
results=[]
for label,first in (('check_then_wait',True),('wait_then_check',False)):
    with connection() as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        c.execute("SET LOCAL statement_timeout='5s'")
        c.execute("SET LOCAL synchronous_commit='on'")
        identity=c.execute("SELECT pg_current_xact_id()::text AS xid,pg_backend_pid() AS pid,clock_timestamp()+interval '400 milliseconds' AS deadline").fetchone()
        c.execute('INSERT INTO aos_precommit_probe_result VALUES (%s,%s,%s)',(label,identity['deadline'],identity['xid']))
        c.execute('SELECT public.aos_precommit_probe_arm(%s,%s)',(identity['deadline'],first))
        before=c.execute('SELECT clock_timestamp() AS now').fetchone()['now'];assert before<identity['deadline']
        record=dict(label=label,xid=identity['xid'],pid=identity['pid'],deadline=identity['deadline'].isoformat(),before_commit=before.isoformat(),check_first=first)
        with (B/(label+'-attempt.json')).open('x') as f:json.dump(record,f,indent=2)
        start=time.monotonic()
        try:
            c.commit();record.update(known_terminal='COMMITTED',sqlstate=None)
        except psycopg.errors.CheckViolation as exc:
            assert str(exc).startswith('AOS_TEST_PRECOMMIT_DEADLINE_EXPIRED')
            c.rollback();record.update(known_terminal='REJECTED_ROLLED_BACK',sqlstate=exc.sqlstate)
        record['elapsed_seconds']=time.monotonic()-start
        assert c.info.transaction_status==TransactionStatus.IDLE
        after=c.execute('SELECT clock_timestamp() AS now').fetchone()['now'];record['after_commit']=after.isoformat();assert after>identity['deadline']
        c.rollback()
        assert record['known_terminal']==('COMMITTED' if first else 'REJECTED_ROLLED_BACK')
        (B/(label+'-result.json')).write_text(json.dumps(record,indent=2));results.append(record)
(B/'results.json').write_text(json.dumps(dict(cases=results,synthetic_callback_mechanism_only=True,source_authorization=False,strict_completion_candidate='RED'),indent=2))
print('Two known native terminal outcomes; post-check callback crossed deadline and committed; reverse order rejected 23514')
