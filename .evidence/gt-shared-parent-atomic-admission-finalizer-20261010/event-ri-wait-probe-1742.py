"""Real deferred internal FK wait, isolated test-only rows, no business effects."""
import hashlib, json, subprocess, threading, time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import psycopg
from psycopg import sql
from psycopg.rows import dict_row

B = Path(__file__).resolve().parent
R = B.parents[1]
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
container = json.loads(subprocess.check_output(['docker', '--context', lab['context'], 'inspect', lab['name']], text=True))[0]
assert container['Id'] == lab['container_id'] and container['Image'] == lab['image'] and container['State']['Running']
database = 'aos_test_05f1a1dcd51f_ti4_test'
schema = 'test_owned_ri_' + uuid4().hex[:16]
params = dict(host='127.0.0.1', port=lab['port'], dbname=database, user='aos_app', passfile=lab['passfile'], row_factory=dict_row)


def connect():
    return psycopg.connect(**params)


def restored(c):
    flags = c.execute("SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='aos_provider_capacity_occupation'").fetchone()
    assert not any(flags.values())
    assert c.execute("SELECT count(*) AS n FROM pg_auth_members WHERE member='aos_provider_capacity_occupation'::regrole OR roleid='aos_provider_capacity_occupation'::regrole").fetchone()['n'] == 0
    assert c.execute("SELECT parname FROM pg_parameter_acl WHERE parname='track_functions'").fetchall() == []


with connect() as admin:
    admin.execute('SET TRANSACTION READ ONLY')
    assert admin.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
    restored(admin)
attempt = dict(authority='AOS-001742', cluster=lab['cluster'], database=database, schema=schema,
               head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R, text=True).strip(),
               script_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               created_at=datetime.now(timezone.utc).isoformat(), test_only=True, formal_effects=False)
(B / 'event-ri-wait-attempt-1742.json').open('x').write(json.dumps(attempt, indent=2) + '\n')
# Names are generated here, never caller-selected production objects.
with connect() as admin:
    admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    admin.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(schema)))
    admin.execute(f'CREATE TABLE {schema}.parent(id integer PRIMARY KEY)')
    admin.execute(f'''CREATE TABLE {schema}.child(id integer PRIMARY KEY,parent_id integer NOT NULL,
      deadline timestamptz NOT NULL,CONSTRAINT owned_fk FOREIGN KEY(parent_id)
      REFERENCES {schema}.parent(id) DEFERRABLE INITIALLY DEFERRED)''')
    admin.execute(f'CREATE TABLE {schema}.audit(id integer PRIMARY KEY,decision_at timestamptz NOT NULL,deadline timestamptz NOT NULL,query text NOT NULL)')
    admin.execute(f'''CREATE FUNCTION {schema}.gate() RETURNS trigger LANGUAGE plpgsql
      SET search_path=pg_catalog AS $gate$
      DECLARE observed timestamptz:=clock_timestamp(); BEGIN
        IF current_query() IS DISTINCT FROM 'COMMIT' OR observed>=NEW.deadline THEN
          RAISE EXCEPTION 'TEST_OWNED_END_DEADLINE_REQUIRED' USING ERRCODE='23514'; END IF;
        INSERT INTO {schema}.audit VALUES(NEW.id,observed,NEW.deadline,current_query());
        RETURN NEW;
      END $gate$''')
    admin.execute(f'REVOKE ALL ON FUNCTION {schema}.gate() FROM PUBLIC')
    admin.execute(f'''CREATE CONSTRAINT TRIGGER "00_gate" AFTER INSERT ON {schema}.child
      DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {schema}.gate()''')
    admin.execute(f'INSERT INTO {schema}.parent VALUES(1),(2)')


def case(number, flush):
    writer, child, observer = connect(), connect(), connect()
    outcome = {}
    thread = None
    try:
        observer.autocommit = True
        writer.execute(f'SELECT id FROM {schema}.parent WHERE id=%s FOR UPDATE', (number,))
        writer_pid = writer.info.backend_pid
        child.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
        deadline = child.execute("SELECT clock_timestamp()+interval '0.4 seconds' AS deadline").fetchone()['deadline']
        child.execute(f'INSERT INTO {schema}.child VALUES(%s,%s,%s)', (number, number, deadline))
        xid = child.execute('SELECT pg_current_xact_id()::text AS xid').fetchone()['xid']
        pid = child.info.backend_pid

        def ending():
            try:
                if flush:
                    child.execute(sql.SQL('SET CONSTRAINTS {}.owned_fk IMMEDIATE').format(sql.Identifier(schema)))
                child.commit()
                outcome['committed'] = True
            except Exception as error:
                outcome.update(committed=False, sqlstate=getattr(error, 'sqlstate', None), error=str(error).splitlines()[0])
                child.rollback()

        thread = threading.Thread(target=ending, daemon=True)
        thread.start()
        limit = time.monotonic() + 10
        wait = None
        while time.monotonic() < limit:
            row = observer.execute('SELECT query,wait_event_type,wait_event,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE pid=%s', (pid,)).fetchone()
            if row and row['wait_event_type'] == 'Lock' and writer_pid in row['blockers']:
                wait = row
                break
            time.sleep(.02)
        assert wait is not None, 'actual internal FK lock wait not observed'
        assert ('SET CONSTRAINTS' in wait['query']) if flush else wait['query'] == 'COMMIT'
        while observer.execute('SELECT clock_timestamp() AS now').fetchone()['now'] <= deadline:
            assert time.monotonic() < limit
            time.sleep(.02)
        writer.rollback()
        thread.join(10)
        assert not thread.is_alive(), 'unknown ending outcome: reconcile without replay'
        state = observer.execute('SELECT pg_xact_status(%s::xid8) AS state', (xid,)).fetchone()['state']
        audit = observer.execute(f'SELECT * FROM {schema}.audit WHERE id=%s', (number,)).fetchone()
        rows = observer.execute(f'SELECT count(*) AS n FROM {schema}.child WHERE id=%s', (number,)).fetchone()['n']
        after = observer.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if flush:
            assert outcome == dict(committed=False, sqlstate='23514', error='TEST_OWNED_END_DEADLINE_REQUIRED')
            assert state == 'aborted' and audit is None and rows == 0
        else:
            assert outcome == dict(committed=True) and state == 'committed' and rows == 1
            assert audit['query'] == 'COMMIT' and audit['decision_at'] < deadline < after
        return dict(case=number, scoped_fk_flushed=flush, deadline=deadline.isoformat(), xid=xid,
                    actual_wait=wait, outcome=outcome, transaction_state=state,
                    audit={k: v.isoformat() if hasattr(v, 'isoformat') else v for k, v in audit.items()} if audit else None,
                    post_ending_readback_at=after.isoformat(), child_rows=rows)
    finally:
        writer.rollback()
        if thread is not None and thread.is_alive():
            thread.join(10)
        child.close()
        writer.close()
        observer.close()


cases = [case(1, False), case(2, True)]
with connect() as admin:
    admin.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    restored(admin)
    triggers = admin.execute('''SELECT t.tgname,t.tgisinternal,t.tgdeferrable,t.tginitdeferred,
      p.prosrc,l.lanname FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid
      JOIN pg_language l ON l.oid=p.prolang WHERE tgrelid=%s::regclass ORDER BY tgname''', (schema + '.child',)).fetchall()
    assert triggers[0]['tgname'] == '00_gate'
    assert any(t['tgisinternal'] and t['tgdeferrable'] and t['lanname'] == 'internal' and t['prosrc'] == 'RI_FKey_check_ins' for t in triggers)
output = dict(**attempt, cases=cases, native_trigger_catalog=triggers,
              naive_commit_string_and_clock_sufficient=False, exact_scoped_fk_flush_moves_wait_before_decision=True,
              actual_product_event_queue_verified=False, execution_allowed=False, full_task_delivered=False)
(B / 'event-ri-wait-verification-1742.json').open('x').write(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(schema=schema, naive_end_red=True, scoped_flush_control_green=True, product_queue_verified=False)))
