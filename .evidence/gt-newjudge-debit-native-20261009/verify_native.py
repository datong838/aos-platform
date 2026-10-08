"""Rollback-only compiler/ACL/caller proof; no fabricated Source positive."""
import hashlib
import json
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

repo=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(repo/'services/aos-api'))
from aos_api.aip_physical_capacity_occupation_authority import (
    OWNER,SCHEMA,JUDGE_DEBIT,occupation_judge_parent_debit_statements)

pf=Path('/Users/ddt/.aos-lab-secrets/aos-native-joint-memory-20261009/pgpass')
assert pf.stat().st_mode & 0o077 == 0
arguments=dict(host='127.0.0.1',port=5435,user='aos_app',
    dbname='aos_test_f70639ea0633_ti4_test',passfile=str(pf),row_factory=dict_row)
tables=[SCHEMA+'.account_guard',SCHEMA+'.parent_debit_guard',SCHEMA+'.prepared_parent_debit',
        'aos_capacity_publication_private.source_publication']
def fingerprint(c):
    return {table:dict(c.execute('SELECT count(*) AS n,md5(coalesce(string_agg(to_jsonb(t)::text,\'\' ORDER BY to_jsonb(t)::text),\'\')) AS hash FROM '+table+' t').fetchone()) for table in tables}
with psycopg.connect(**arguments) as before_conn:
    before_conn.execute('SET TRANSACTION READ ONLY')
    assert before_conn.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']=='7694371626696531992'
    assert before_conn.execute('SELECT version_num FROM alembic_version').fetchone()['version_num']=='a0v_159'
    assert before_conn.execute("SELECT count(*) AS n FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND state<>'idle'").fetchone()['n']==0
    assert before_conn.execute('SELECT to_regprocedure(%s) AS fn',(JUDGE_DEBIT,)).fetchone()['fn'] is None
    before=fingerprint(before_conn)
    assert before[tables[-1]]['n']==1
    original_functions=before_conn.execute("SELECT oid::text,md5(prosrc) AS hash,proacl::text FROM pg_proc WHERE pronamespace=%s::regnamespace ORDER BY oid",(SCHEMA,)).fetchall()
statements=occupation_judge_parent_debit_statements()
with psycopg.connect(**arguments) as installation:
    installation.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
    for statement in statements:installation.execute(statement)
    row=installation.execute('SELECT prosrc,prosecdef,proconfig,pg_get_userbyid(proowner) AS owner FROM pg_proc WHERE oid=%s::regprocedure',(JUDGE_DEBIT,)).fetchone()
    assert row['prosrc']==statements[0].split('$judgedebit$')[1]
    assert row['owner']==OWNER and row['prosecdef'] and row['proconfig']==['search_path=pg_catalog']
    acl=installation.execute("SELECT a.grantee::regrole::text AS grantee,a.privilege_type,a.is_grantable FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE p.oid=%s::regprocedure",(JUDGE_DEBIT,)).fetchall()
    assert len(acl)==2 and {r['grantee'] for r in acl}=={OWNER,'aos_runtime'}
    assert all(r['privilege_type']=='EXECUTE' and not r['is_grantable'] for r in acl)
    assert installation.execute("SELECT count(*) AS n FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='require_joint_finalization' AND tgdeferrable AND tginitdeferred",(SCHEMA+'.prepared_parent_debit',)).fetchone()['n']==1
    denied=[]
    for role,org in [('aos_runtime','org-org'),(OWNER,'org-org'),('aos_runtime','dev-org')]:
        with installation.transaction(force_rollback=True):
            installation.execute('SET LOCAL ROLE '+role)
            installation.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id','dev-project',true)",(org,))
            try:
                installation.execute('SELECT public.prepare_capacity_judge_parent_debit(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)')
            except psycopg.errors.InsufficientPrivilege as exc:
                assert 'CAPACITY_JUDGE_DEBIT_CALLER_REQUIRED' in str(exc)
                denied.append(dict(role=role,org=org,sqlstate=exc.sqlstate))
            else:raise AssertionError('wrong native caller accepted')
    installation.rollback()
with psycopg.connect(**arguments) as after_conn:
    after_conn.execute('SET TRANSACTION READ ONLY')
    assert after_conn.execute('SELECT to_regprocedure(%s) AS fn',(JUDGE_DEBIT,)).fetchone()['fn'] is None
    assert fingerprint(after_conn)==before
    assert after_conn.execute("SELECT oid::text,md5(prosrc) AS hash,proacl::text FROM pg_proc WHERE pronamespace=%s::regnamespace ORDER BY oid",(SCHEMA,)).fetchall()==original_functions
proof=dict(authority='AOS-001605',cluster='7694371626696531992',migration='a0v_159',
    compiler_installed_in_rollback_only_transaction=True,function_disappeared=True,
    original_private_functions_unchanged=True,ledger_and_source_unchanged=before,
    acl=[dict(x) for x in acl],denied=denied,sql_body_sha256=hashlib.sha256(row['prosrc'].encode()).hexdigest(),
    execution_allowed=False,limitations=['Actual Source/newJudge positive allocation and concurrent cap remain unverified',
    'No input/Intent/finalizer or joint COMMIT; old deferred deny kept', 'No original fact stub or fake Source/parent'])
with Path(__file__).with_name('native-result.json').open('x') as f:json.dump(proof,f,ensure_ascii=False,indent=2);f.write('\n')
print('native compile, exact ACL, 3 caller denials, rollback and unchanged Source/ledger verified')
