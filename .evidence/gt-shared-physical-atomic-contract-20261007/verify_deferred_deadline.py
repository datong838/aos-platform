"""Independent read-only verification of retained native deadline controls."""
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BASE=Path(__file__).resolve().parent
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):
    os.environ.pop(key,None)
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert passfile.stat().st_mode&0o077==0
pairs=[('deferred_deadline_probe.py','deferred-deadline-verification.json','deferred-deadline-r1.log',
    {'default_deferred':0,'early_immediate':1,'immediate_then_deferred_no_dml':1,'rearmed_update':0}),
    ('strict_commit_deadline_probe.py','strict-commit-deadline-verification.json','strict-commit-deadline-r1.log',
    {'canonical_live_commit':1,'canonical_expired_commit':0,'early_constraints_immediate':0,'noncanonical_end':0})]
results=[]
for script,record,log,expected in pairs:
    r=json.loads((BASE/record).read_text())
    assert r['probe_sha256']==hashlib.sha256((BASE/script).read_bytes()).hexdigest()
    tree=ast.parse((BASE/script).read_text())
    body=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='BODY' for t in n.targets))
    assert body==r['trusted_test_body']
    assert set(c['case'] for c in r['cases'])==set(expected)
    for case in r['cases']:
        assert case['retained_rows']==expected[case['case']] and case['committed']==bool(expected[case['case']])
        assert case['identity']['login']=='aos_app' and case['identity']['role']=='aos_runtime'
        assert case['identity']['isolation']=='serializable'
        assert case['before_commit']['xid']==case['identity']['xid']
        if script=='deferred_deadline_probe.py':
            assert case['before_commit']['clock']>case['deadline'] and case['commit_calls']==1
    with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=r['database'],
            passfile=str(passfile),row_factory=dict_row) as c:
        c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,"
            "current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone()
        assert identity==dict(database=r['database'],cluster='7693564235776004128',readonly='on')
        fn=c.execute("SELECT prosrc,prosecdef,proconfig,proowner::regrole::text AS owner FROM pg_proc "
            "WHERE oid='gt_deferred_probe.check_deadline()'::regprocedure").fetchone()
        assert fn==dict(prosrc=body,prosecdef=False,proconfig=['search_path=pg_catalog'],owner='aos_app')
        triggers=c.execute("SELECT tgdeferrable,tginitdeferred,tgtype,tgenabled FROM pg_trigger "
            "WHERE tgrelid='gt_deferred_probe.obligation'::regclass AND NOT tgisinternal").fetchall()
        assert triggers==[dict(tgdeferrable=True,tginitdeferred=True,tgtype=21,tgenabled='O')]
        rows=c.execute('SELECT case_id,extract(epoch FROM deadline)::float8 AS deadline FROM gt_deferred_probe.obligation ORDER BY case_id').fetchall()
        assert [x['case_id'] for x in rows]==sorted(k for k,v in expected.items() if v)
        for row in rows:
            original=next(x for x in r['cases'] if x['case']==row['case_id']);assert row['deadline']==original['deadline']
            checks=c.execute("SELECT extract(epoch FROM checked_at)::float8 AS clock FROM gt_deferred_probe.audit "
                "WHERE case_id=%s AND event='deadline_checked'",(row['case_id'],)).fetchall()
            assert len(checks)==1 and checks[0]['clock']<row['deadline']
        counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in r['product_counts']}
        assert counts==r['product_counts'] and not any(counts.values())
        assert c.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()==r['migration_heads']
    results.append(dict(identity=identity,retained_case_rows={k:v for k,v in expected.items()},
        trusted_body_sha256=hashlib.sha256(body.encode()).hexdigest(),product_counts=counts,
        file_sha256={n:hashlib.sha256((BASE/n).read_bytes()).hexdigest() for n in (script,record,log)}))
result=dict(status='DEFERRED_QUEUE_DRAIN_AND_CANONICAL_COMMIT_CONTROL_RETAINED_STATE_VERIFIED',
    cases_verified=8,databases=results,verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    limitations=['Native test-only schemas and synthetic deadlines; not full joint/source/business authorization',
        'Retained rows plus original execution assertions, not independent replay of past timing',
        'Canonical current_query control remains a design candidate requiring complete protocol/end-channel review',
        'Checks within COMMIT command do not bound physical WAL flush/commit completion time'])
(BASE/'deferred-deadline-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],'8 cases; exact bodies/triggers; product0')
