"""Independent retained commit and trusted implicit trigger body readback."""
import ast
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BASE=Path(__file__).resolve().parent
REPO=BASE.parents[1]
record=json.loads((BASE/'cost-revoke-lock-verification.json').read_text())
assert record['database']=='aos_test_860bd2813958_ti4_test'
assert record['blocked_by']==[record['caller']['pid']]
assert record['after_version']==record['before_version']+1
PASSFILE=Path(tempfile.gettempdir())/'aos-capacity-publication-scram-20261006.pgpass'
assert PASSFILE.stat().st_mode&0o077==0
for key in ('PGPASSWORD','PGPASSFILE','PGOPTIONS','PGSERVICE','PGSERVICEFILE'):
    os.environ.pop(key,None)
migration=REPO/'services/aos-api/alembic/versions/a0v_126_budget_cost_consumer.py'
ddl=[node.value for node in ast.walk(ast.parse(migration.read_text()))
    if isinstance(node,ast.Constant) and isinstance(node.value,str)
    and node.value.startswith('CREATE FUNCTION public.aip_budget_cost_revoke_fence_a0v_126()')]
assert len(ddl)==1
expected=re.search(r'\$\$(.*?)\$\$',ddl[0],re.S).group(1).strip()
observations={}
for database in (record['database'],'aos_test_ee694e57dab4_ti4_test'):
    with psycopg.connect(host='127.0.0.1',port=5434,user='aos_app',dbname=database,
            passfile=str(PASSFILE),row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
        identity=conn.execute("SELECT current_database() AS database,current_setting('transaction_read_only') AS readonly,"
            "system_identifier::text AS cluster FROM pg_control_system()").fetchone()
        assert identity==dict(database=database,readonly='on',cluster='7693564235776004128')
        function=conn.execute("SELECT prosrc,prosecdef,proconfig FROM pg_proc "
            "WHERE oid='public.aip_budget_cost_revoke_fence_a0v_126()'::regprocedure").fetchone()
        assert function['prosrc'].strip()==expected
        assert not function['prosecdef'] and function['proconfig']==['search_path=pg_catalog']
        trigger=conn.execute("SELECT tgenabled,tgtype,tgdeferrable FROM pg_trigger "
            "WHERE tgrelid='public.aip_budget_cost_revocation'::regclass AND tgname='budget_cost_revoke_fence'").fetchone()
        assert trigger==dict(tgenabled='O',tgtype=5,tgdeferrable=False)
        roles={}
        for name in ('aos_budget_cost_issuer','aos_budget_consumer_call'):
            flags=conn.execute('SELECT rolcanlogin,rolinherit,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls '
                'FROM pg_roles WHERE rolname=%s',(name,)).fetchone()
            assert flags and not any(flags.values())
            memberships=conn.execute('SELECT member::regrole::text AS member,roleid::regrole::text AS role,'
                'admin_option,inherit_option,set_option FROM pg_auth_members WHERE roleid=%s::regrole OR member=%s::regrole',
                (name,name)).fetchall()
            expected_memberships=[dict(member=name,role='aos_runtime',admin_option=False,inherit_option=False,set_option=True)] if name=='aos_budget_cost_issuer' else []
            assert memberships==expected_memberships
            roles[name]=dict(no_login_or_privileged_flags=True,original_memberships=memberships)
        counts={table:conn.execute('SELECT count(*) AS n FROM '+table).fetchone()['n'] for table in
            ('aip_agent_run','aip_budget_reservation','aip_model_eval_budget_reservation','aip_model_capacity_reservation')}
        assert all(n==0 for n in counts.values())
        canary=conn.execute("SELECT count(*) AS n FROM aip_budget_cost_revocation WHERE org_id='dev-org'").fetchone()['n']
        assert canary==0
        revocations=conn.execute('SELECT count(*) AS n FROM aip_budget_cost_revocation').fetchone()['n']
        if database==record['database']:
            assert revocations==1
            row=conn.execute('SELECT decision_id FROM aip_budget_cost_revocation WHERE revocation_id=%s',
                (record['revocation_id'],)).fetchone()
            assert row==dict(decision_id=record['decision_id'])
            fence=conn.execute('SELECT version,decision_id FROM aip_budget_cost_runtime_fence '
                'WHERE org_id=%s AND project_id=%s AND budget_id=%s AND revision=%s',
                ('org-org','dev-project',record['budget_id'],record['budget_revision'])).fetchone()
            assert fence==dict(version=2,decision_id=record['decision_id'])
            assert conn.execute("SELECT count(*) AS n FROM aip_budget_cost_issuer_receipt WHERE operation='revoke' "
                "AND result->>'revocationId'=%s",(record['revocation_id'],)).fetchone()['n']==1
        else:
            assert revocations==0  # Failed probe never began a new revoke; no old-attempt replay.
        observations[database]=dict(identity=identity,trigger_matches_trusted_migration=True,
            roles=roles,product_counts=counts,canary=canary,revocations=revocations)
names=['cost_revoke_lock_probe.py','run_cost_revoke_lock_probe.py','cost-revoke-lock-r2.log',
    'cost-revoke-lock-verification.json','verify_cost_revoke_lock.py']
result=dict(status='ORIGINAL_COST_REVOKE_COMMIT_AND_ROLE_CLEANUP_READBACK_VERIFIED',databases=observations,
    file_sha256={name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in names},
    trusted_migration_sha256=hashlib.sha256(migration.read_bytes()).hexdigest(),
    limitations=['Live wait/pid/xid proven by original probe, not reconstructed from persistent state',
        'Only original cost revoke implicit fence edge; full joint writer graph still unverified',
        'Historical Provider fixture, not a complete authorized business run'])
(BASE/'cost-revoke-lock-independent-verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['status'],'trusted trigger matches; retained r1 revocations0 / r2 revocations1; roles inert; holds0/canary0')
