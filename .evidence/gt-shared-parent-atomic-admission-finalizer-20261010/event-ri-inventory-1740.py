"""Read current retained constraints; catalog is not an event queue proof."""
from pathlib import Path
import hashlib, json
import psycopg
from psycopg.rows import dict_row
from aos_api import aip_shared_parent_atomic_admission as api

B = Path(__file__).resolve().parent
R = B.parents[1]
result = json.loads((B / 'parent-risk-native-1739-r2/result-r2.json').read_text())
lab = json.loads((R / '.evidence/gt-source-desktop-shm-lab-20261009/lab.json').read_text())
with psycopg.connect(host='127.0.0.1', port=lab['port'], user='aos_app', dbname=result['databases'][0], passfile=lab['passfile'], row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id'] == lab['cluster']
    triggers = c.execute("""SELECT n.nspname||'.'||t.relname AS relation,g.tgname,g.tgisinternal,
      g.tgdeferrable,g.tginitdeferred,g.tgtype,g.tgenabled,
      p.oid::regprocedure::text AS function,pg_get_userbyid(p.proowner) AS owner,
      p.prosecdef,p.proconfig,p.prosrc
      FROM pg_trigger g JOIN pg_class t ON t.oid=g.tgrelid
      JOIN pg_namespace n ON n.oid=t.relnamespace JOIN pg_proc p ON p.oid=g.tgfoid
      WHERE n.nspname LIKE 'aos_shared_parent%' OR n.nspname='aos_physical_capacity_occupation_private'
      ORDER BY 1,g.tgname""").fetchall()
    for trigger in triggers:
        trigger['body_sha256'] = hashlib.sha256(trigger.pop('prosrc').encode()).hexdigest()
    constraints = c.execute("""SELECT n.nspname||'.'||t.relname AS relation,k.conname,
      k.contype,k.condeferrable,k.condeferred,pg_get_constraintdef(k.oid) AS definition
      FROM pg_constraint k JOIN pg_class t ON t.oid=k.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
      WHERE n.nspname LIKE 'aos_shared_parent%' OR n.nspname='aos_physical_capacity_occupation_private'
      ORDER BY 1,k.conname""").fetchall()
    absent = {}
    for signature in (api.END_CHANNEL, api.PHYSICAL_END):
        absent[signature] = c.execute('SELECT to_regprocedure(%s) IS NULL AS absent', (signature,)).fetchone()['absent']
        assert absent[signature]
    counts = {}
    for row in c.execute("SELECT n.nspname,t.relname FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname LIKE 'aos_shared_parent%' AND t.relkind='r'").fetchall():
        table = row['nspname'] + '.' + row['relname']
        counts[table] = c.execute('SELECT count(*) AS n FROM ' + table).fetchone()['n']
        assert counts[table] == 0
output = dict(authority='AOS-001740', database=result['databases'][0], cluster=lab['cluster'], transaction='SERIALIZABLE READ ONLY', triggers=triggers, constraints=constraints, absent_end_functions=absent, zero_shared_rows=counts, actual_event_queue_observed=False, set_constraints_executed=False, full_admission_commit=False, full_task_delivered=False, execution_allowed=False)
(B / 'event-ri-inventory-1740.json').open('x').write(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(triggers=len(triggers), constraints=len(constraints), deferred_triggers=sum(t['tgdeferrable'] for t in triggers), absent_end_functions=absent, queue_proof=False)))
