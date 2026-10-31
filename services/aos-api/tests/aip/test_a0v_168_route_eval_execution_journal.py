from importlib import util
from pathlib import Path


MIGRATION=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_168_route_eval_execution_journal.py'


def load():
    spec=util.spec_from_file_location('a0v_168_route_eval_execution_journal',MIGRATION)
    module=util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_route_eval_journal_migration_is_default_empty_scoped_and_append_only(monkeypatch):
    migration=load()
    statements=[];monkeypatch.setattr(migration.op,'execute',statements.append)
    migration.upgrade();sql='\n'.join(statements)
    assert migration.revision=='a0v_168' and migration.down_revision=='a0v_167'
    for table in ('aip_route_eval_execution_command','aip_route_eval_execution_result'):
        assert 'CREATE TABLE '+table in sql
        assert 'ALTER TABLE '+table+' ENABLE ROW LEVEL SECURITY' in sql
        assert 'ALTER TABLE '+table+' FORCE ROW LEVEL SECURITY' in sql
        assert 'BEFORE UPDATE OR DELETE ON '+table in sql
        assert 'BEFORE TRUNCATE ON '+table in sql
        assert 'GRANT SELECT ON '+table+' TO aos_runtime' in sql
        assert 'GRANT SELECT,INSERT ON '+table+' TO aos_route_eval_journal' in sql
    assert 'CREATE ROLE aos_route_eval_journal NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS' in sql
    assert 'REFERENCES aip_budget_reservation(org_id,project_id,reservation_id)' in sql
    assert 'octet_length(input_bytes) BETWEEN 1 AND 1048576' in sql
    assert 'octet_length(output_bytes) BETWEEN 0 AND 1048576' in sql
    assert 'GRANT aos_route_eval_journal TO' not in sql
    assert 'INSERT INTO' not in sql


def test_route_eval_journal_migration_refuses_destructive_downgrade():
    migration=load()
    try:migration.downgrade()
    except RuntimeError as exc:assert 'reconciliation' in str(exc)
    else:raise AssertionError('journal evidence cannot be silently dropped')
