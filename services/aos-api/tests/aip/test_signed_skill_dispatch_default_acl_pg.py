"""Native legacy-default ACL regression; isolated rows are not business runs."""
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
import pytest

TABLES = ('aip_skill_eval_intent', 'aip_skill_eval_dispatch', 'aip_skill_eval_dispatch_observation')


def migration_statements(filename):
    path = Path(__file__).resolve().parents[2] / 'alembic/versions' / filename
    spec = importlib.util.spec_from_file_location('acl_migration_' + uuid4().hex, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements = []
    with patch.object(module.op, 'execute', statements.append):
        module.upgrade()
    return statements


def repair(conn):
    for statement in migration_statements('a0v_161_skill_dispatch_acl.py'):
        conn.execute(statement)


@pytest.fixture
def legacy_db():
    original = os.environ['AOS_DATABASE_URL']
    parts = conninfo_to_dict(original)
    assert (parts['host'], parts['port']) == ('127.0.0.1', '18431')
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    name = 'aos_test_acl_' + uuid4().hex[:12] + '_ti4_test'
    with psycopg.connect(original, autocommit=True) as admin:
        assert admin.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()[0] == '7695416748450308141'
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    dsn = make_conninfo(**{**parts, 'dbname': name})
    try:
        with psycopg.connect(dsn) as conn:
            conn.execute('ALTER DEFAULT PRIVILEGES FOR ROLE aos_app IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO aos_runtime')
            conn.execute('CREATE TABLE old_acl_sentinel(id text PRIMARY KEY)')
            conn.execute("INSERT INTO old_acl_sentinel VALUES ('retained')")
            conn.execute('CREATE TABLE aip_eval_run(org_id text,project_id text,run_id text,PRIMARY KEY(org_id,project_id,run_id))')
            conn.execute("INSERT INTO aip_eval_run VALUES ('org-org','dev-project','fixture-only-run')")
            for statement in migration_statements('a0v_160_skill_eval_dispatch_intent.py'):
                conn.execute(statement)
            for table in TABLES:
                assert conn.execute('SELECT has_table_privilege(%s,%s,%s)', ('aos_runtime', table, 'INSERT')).fetchone()[0]
            conn.commit()
        yield dsn
    finally:
        with psycopg.connect(original, autocommit=True) as admin:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))


def snapshot(conn):
    return conn.execute("""SELECT
      (SELECT relacl::text FROM pg_class WHERE oid='old_acl_sentinel'::regclass),
      (SELECT jsonb_agg(to_jsonb(d) ORDER BY oid) FROM pg_default_acl d),
      (SELECT jsonb_agg(jsonb_build_array(c.relname,c.relowner,c.relrowsecurity,c.relforcerowsecurity,
          (SELECT jsonb_agg(pg_get_triggerdef(t.oid) ORDER BY t.tgname) FROM pg_trigger t WHERE t.tgrelid=c.oid),
          (SELECT jsonb_agg(to_jsonb(p) ORDER BY p.policyname) FROM pg_policies p WHERE p.schemaname='public' AND p.tablename=c.relname))
          ORDER BY c.relname) FROM pg_class c WHERE c.relname IN ('aip_skill_eval_intent','aip_skill_eval_dispatch','aip_skill_eval_dispatch_observation')),
      (SELECT array_agg(id ORDER BY id) FROM old_acl_sentinel)""").fetchone()


@pytest.mark.parametrize('extra', ['none', 'public', 'columns'])
def test_historical_default_grants_removed_without_old_acl_or_policy_change(legacy_db, extra):
    with psycopg.connect(legacy_db) as conn:
        if extra == 'public':
            for table in TABLES:
                conn.execute(sql.SQL('GRANT ALL ON {} TO PUBLIC').format(sql.Identifier(table)))
        if extra == 'columns':
            conn.execute('GRANT UPDATE(request_hash),INSERT(request_hash),REFERENCES(request_hash) ON aip_skill_eval_intent TO aos_runtime,PUBLIC')
        before = snapshot(conn)
        repair(conn)
        assert snapshot(conn) == before
        for table in TABLES:
            assert conn.execute('SELECT has_table_privilege(%s,%s,%s)', ('aos_runtime', table, 'SELECT')).fetchone()[0]
            for privilege in ('INSERT', 'UPDATE', 'DELETE', 'TRUNCATE', 'REFERENCES', 'TRIGGER'):
                assert not conn.execute('SELECT has_table_privilege(%s,%s,%s)', ('aos_runtime', table, privilege)).fetchone()[0]
            assert conn.execute('SELECT has_table_privilege(%s,%s,%s)', ('aos_aip_eval_writer', table, 'INSERT')).fetchone()[0]
        assert conn.execute("SELECT has_column_privilege('aos_aip_eval_writer','aip_skill_eval_intent','version','UPDATE')").fetchone()[0]
        assert not conn.execute("SELECT has_column_privilege('aos_aip_eval_writer','aip_skill_eval_intent','request_hash','UPDATE')").fetchone()[0]
        assert not conn.execute("SELECT has_column_privilege('aos_runtime','aip_skill_eval_intent','request_hash','UPDATE')").fetchone()[0]
        assert not conn.execute("SELECT has_table_privilege('aos_aip_eval_writer','aip_eval_run','UPDATE')").fetchone()[0]
        # The same original migration may be applied once; its repair logic is stable on recheck.
        repair(conn)


@pytest.mark.parametrize('table', TABLES)
@pytest.mark.parametrize('operation', ['INSERT', 'UPDATE', 'DELETE', 'TRUNCATE'])
def test_runtime_direct_sql_denied_even_without_matching_rows(legacy_db, table, operation):
    with psycopg.connect(legacy_db) as conn:
        repair(conn)
        conn.commit()
        conn.execute('SET LOCAL ROLE aos_runtime')
        conn.execute("SET LOCAL aos.org_id='org-org'")
        conn.execute("SET LOCAL aos.project_id='dev-project'")
        statement = {'INSERT': "INSERT INTO {}(org_id) VALUES ('org-org')",
                     'UPDATE': 'UPDATE {} SET org_id=org_id WHERE false',
                     'DELETE': 'DELETE FROM {} WHERE false', 'TRUNCATE': 'TRUNCATE {}'}[operation]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(sql.SQL(statement).format(sql.Identifier(table)))


def test_writer_new_fixture_and_runtime_double_scope_read_still_work(legacy_db):
    with psycopg.connect(legacy_db) as conn:
        repair(conn)
        conn.execute('SET LOCAL ROLE aos_aip_eval_writer')
        conn.execute("SET LOCAL aos.org_id='org-org'")
        conn.execute("SET LOCAL aos.project_id='dev-project'")
        conn.execute("INSERT INTO aip_skill_eval_intent(org_id,project_id,intent_id,run_id,idempotency_key,request_hash) VALUES ('org-org','dev-project','fixture-intent','fixture-only-run','fixture-key',%s)", ('a'*64,))
        conn.execute("UPDATE aip_skill_eval_intent SET version=2 WHERE intent_id='fixture-intent'")
        conn.execute("INSERT INTO aip_skill_eval_dispatch(org_id,project_id,dispatch_id,intent_id,case_id,purpose,input_hash) VALUES ('org-org','dev-project','fixture-dispatch','fixture-intent','fixture-case','target',%s)", ('b'*64,))
        conn.execute("INSERT INTO aip_skill_eval_dispatch_observation(org_id,project_id,dispatch_id,state) VALUES ('org-org','dev-project','fixture-dispatch','unknown')")
        conn.execute('SET LOCAL ROLE aos_runtime')
        for table in TABLES:
            assert conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0] == 1
        for org, project in [('dev-org','dev-project'), ('org-org','other'), ('','')]:
            conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", (org, project))
            for table in TABLES:
                assert conn.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0] == 0
        conn.rollback()


@pytest.mark.parametrize('column_grant', [False, True])
def test_unknown_grantee_refused_atomically(legacy_db, column_grant):
    with psycopg.connect(legacy_db) as conn:
        grant = 'GRANT UPDATE(request_hash) ON aip_skill_eval_intent TO pg_read_all_data' if column_grant else 'GRANT SELECT ON aip_skill_eval_intent TO pg_read_all_data'
        conn.execute(grant)
        before = snapshot(conn)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                repair(conn)
        assert snapshot(conn) == before
        assert conn.execute("SELECT has_table_privilege('aos_runtime','aip_skill_eval_intent','INSERT')").fetchone()[0]


@pytest.mark.parametrize('drift', [
    'ALTER TABLE aip_skill_eval_dispatch DISABLE ROW LEVEL SECURITY',
    'ALTER TABLE aip_skill_eval_dispatch OWNER TO aos_runtime',
    'GRANT UPDATE ON aip_skill_eval_dispatch TO aos_aip_eval_writer',
    'GRANT UPDATE(request_hash) ON aip_skill_eval_intent TO aos_aip_eval_writer',
])
def test_profile_or_writer_grant_drift_refused_without_partial_repair(legacy_db, drift):
    with psycopg.connect(legacy_db) as conn:
        conn.execute(drift)
        before = snapshot(conn)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                repair(conn)
        assert snapshot(conn) == before
        assert conn.execute("SELECT has_table_privilege('aos_runtime','aip_skill_eval_intent','INSERT')").fetchone()[0]
