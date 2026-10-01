"""Disposable PostgreSQL schema gate; no issuer or business rows are seeded."""
import os
import psycopg
from psycopg.conninfo import conninfo_to_dict
import pytest


def test_subject_receipts_have_dedicated_schema_and_no_runtime_write():
    dsn=os.environ['AOS_DATABASE_URL']
    name=conninfo_to_dict(dsn)['dbname']
    assert name.startswith('aos_test_') and name.endswith('_ti4_test')
    with psycopg.connect(dsn) as conn:
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone()==('a0v_131',)
        for table in ('aip_eval_issuer_root','aip_eval_executor_identity','aip_eval_subject_receipt'):
            acl=conn.execute('''SELECT has_table_privilege('aos_runtime',%s,'SELECT'),
                has_table_privilege('aos_runtime',%s,'INSERT'),
                has_table_privilege('aos_runtime',%s,'UPDATE'),
                has_table_privilege('aos_runtime',%s,'DELETE'),
                has_table_privilege('aos_runtime',%s,'TRUNCATE')''',(table,)*5).fetchone()
            assert acl==(True,False,False,False,False)
        checks={r[0]:r[1] for r in conn.execute('''SELECT conname,pg_get_constraintdef(oid)
            FROM pg_constraint WHERE conrelid='aip_eval_subject_receipt'::regclass''')}
        assert any("source-witness" in value and "judge" in value for value in checks.values())
        assert any('FOREIGN KEY (org_id, project_id, eval_run_id)' in value for value in checks.values())
        assert any('source_receipt_hash' in value and 'FOREIGN KEY' in value for value in checks.values())
        assert any('identity_id' in value and 'certificate_hash' in value and 'FOREIGN KEY' in value for value in checks.values())
        for table,value in [('aip_eval_issuer_root','subject-review'),('aip_eval_executor_identity','source-witness')]:
            constraints=[r[0] for r in conn.execute('''SELECT pg_get_constraintdef(oid)
                FROM pg_constraint WHERE conrelid=%s::regclass AND contype='c' ''',(table,))]
            assert any(value in check for check in constraints)
        settings=conn.execute('''SELECT relrowsecurity,relforcerowsecurity FROM pg_class
            WHERE oid='aip_eval_subject_receipt'::regclass''').fetchone()
        assert settings==(True,True)
        triggers={r[0] for r in conn.execute('''SELECT tgname FROM pg_trigger
            WHERE tgrelid='aip_eval_subject_receipt'::regclass AND NOT tgisinternal''')}
        assert any('append_only' in value for value in triggers)
        assert any('truncate_guard' in value for value in triggers)
        for org in ('org-org','dev-org'):
            with conn.transaction():
                conn.execute('SET LOCAL ROLE aos_runtime')
                conn.execute("SELECT set_config('aos.org_id',%s,true)",(org,))
                conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
                assert conn.execute('SELECT count(*) FROM aip_eval_subject_receipt').fetchone()==(0,)
