"""Read-only verification of original Host wrapper control evidence."""
import ast
import hashlib
import json
import os
import tempfile
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

BASE=Path(__file__).resolve().parent
REPO=BASE.parents[1]
r=json.loads((BASE/'host-transaction-control-verification.json').read_text())
assert r['status']=='ORIGINAL_HOST_AND_BORROWED_SQL_END_CHANNEL_NATIVE_CONTROL_VERIFIED'
probe=BASE/'host_transaction_control_probe.py'
assert hashlib.sha256(probe.read_bytes()).hexdigest()==r['probe_sha256']
body=next(ast.literal_eval(n.value) for n in ast.parse(probe.read_text()).body if isinstance(n,ast.Assign)
    and any(isinstance(t,ast.Name) and t.id=='BODY' for t in n.targets))
assert body==r['trusted_test_body']
for name,sha in r['original_product_sha256'].items():assert hashlib.sha256((REPO/name).read_bytes()).hexdigest()==sha
expected={'direct_host_sql_commit':1,'bound_noop_then_sql_commit':1,'bound_early_constraints':0,'bound_expired_sql_commit':0}
assert {x['case']:x['retained_rows'] for x in r['cases']}==expected
for x in r['cases']:
    assert x['committed']==bool(expected[x['case']])
    assert x['bound_commit_noop_verified'] and x['bound_rollback_denied'] and x['cross_tenant_factory_denied']
    assert x['identity']['login']=='aos_app' and x['identity']['role']=='aos_runtime' and x['identity']['isolation']=='serializable'
    assert x['before_end']['xid']==x['identity']['xid']
    assert x['sql_end_calls']==(0 if x['case']=='bound_early_constraints' else 1)
    assert (x['before_end']['clock']>x['deadline'])==(x['case']=='bound_expired_sql_commit')
for key in ('PGPASSWORD','PGPASSFILE','PGSERVICE','PGSERVICEFILE','PGOPTIONS'):os.environ.pop(key,None)
passfile=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass';assert passfile.stat().st_mode&0o077==0
with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=r['database'],passfile=str(passfile),row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    identity=c.execute("SELECT current_database() AS database,system_identifier::text AS cluster,"
        "current_setting('transaction_read_only') AS readonly FROM pg_control_system()").fetchone()
    assert identity==dict(database=r['database'],cluster='7693564235776004128',readonly='on')
    fn=c.execute("SELECT prosrc,prosecdef,proconfig,proowner::regrole::text AS owner FROM pg_proc "
        "WHERE oid='gt_deferred_probe.check_deadline()'::regprocedure").fetchone()
    assert fn==dict(prosrc=body,prosecdef=False,proconfig=['search_path=pg_catalog'],owner='aos_app')
    tg=c.execute("SELECT tgdeferrable,tginitdeferred,tgtype,tgenabled FROM pg_trigger "
        "WHERE tgrelid='gt_deferred_probe.obligation'::regclass AND NOT tgisinternal").fetchall()
    assert tg==[dict(tgdeferrable=True,tginitdeferred=True,tgtype=21,tgenabled='O')]
    rows=c.execute('SELECT case_id,extract(epoch FROM deadline)::float8 AS deadline FROM gt_deferred_probe.obligation ORDER BY case_id').fetchall()
    assert [x['case_id'] for x in rows]==sorted(k for k,v in expected.items() if v)
    for x in r['cases']:
        audit=c.execute('SELECT event FROM gt_deferred_probe.audit WHERE case_id=%s ORDER BY event',(x['case'],)).fetchall()
        assert audit==x['retained_audits']
    for row in rows:
        x=next(x for x in r['cases'] if x['case']==row['case_id']);assert row['deadline']==x['deadline']
        clock=c.execute("SELECT extract(epoch FROM checked_at)::float8 AS clock FROM gt_deferred_probe.audit "
            "WHERE case_id=%s AND event='deadline_checked'",(row['case_id'],)).fetchone()['clock']
        assert clock<row['deadline']
    counts={t:c.execute('SELECT count(*) AS n FROM '+t).fetchone()['n'] for t in r['product_counts']}
    assert counts==r['product_counts'] and not any(counts.values())
    assert c.execute('SELECT version_num FROM alembic_version ORDER BY version_num').fetchall()==r['migration_heads']
result=dict(status='ORIGINAL_HOST_SQL_END_NATIVE_RESULT_AND_RETAINED_STATE_VERIFIED',identity=identity,cases_verified=4,
    original_product_hashes_unchanged=True,product_counts=counts,
    file_sha256={n:hashlib.sha256((BASE/n).read_bytes()).hexdigest() for n in
        ('host_transaction_control_probe.py','host-transaction-control-verification.json','host-transaction-control-r1.log','verify_host_transaction_control.py')},
    limitations=['Original trusted wrappers on primitive schema only, not full dispatch/Source/business or external-user access',
        'No product changes; full joint end-control and immutable Intent binding still required'])
(BASE/'host-transaction-control-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],'4 cases; exact original hashes; product0')
