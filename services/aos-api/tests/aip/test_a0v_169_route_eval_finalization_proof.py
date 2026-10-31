from importlib import util
from pathlib import Path


MIGRATION=Path(__file__).resolve().parents[2]/'alembic/versions/a0v_169_route_eval_finalization_proof.py'


def load():
    spec=util.spec_from_file_location('a0v_169_route_eval_finalization_proof',MIGRATION)
    module=util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_route_finalization_migration_is_default_empty_narrow_and_immutable(monkeypatch):
    migration=load();statements=[];monkeypatch.setattr(migration.op,'execute',statements.append)
    migration.upgrade();sql='\n'.join(statements)
    assert migration.revision=='a0v_169' and migration.down_revision=='a0v_168'
    for table in ('aip_route_eval_finalization_proof','aip_route_eval_finalized_call_proof'):
        assert 'CREATE TABLE '+table in sql
        assert 'ALTER TABLE '+table+' ENABLE ROW LEVEL SECURITY' in sql
        assert 'ALTER TABLE '+table+' FORCE ROW LEVEL SECURITY' in sql
        assert 'BEFORE UPDATE OR DELETE ON '+table in sql
        assert 'BEFORE TRUNCATE ON '+table in sql
        assert 'GRANT SELECT ON '+table+' TO aos_runtime' in sql
        assert 'GRANT SELECT,INSERT ON '+table+' TO aos_route_eval_finalizer' in sql
    assert 'CREATE ROLE aos_route_eval_finalizer NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS' in sql
    assert 'REFERENCES aip_route_eval_execution_result(org_id,project_id,reservation_id)' in sql
    assert 'REFERENCES aip_eval_run(org_id,project_id,run_id)' in sql
    assert 'REFERENCES aip_eval_report_revision(org_id,project_id,report_id,revision)' in sql
    for table in ('aip_route_eval_execution_command','aip_route_eval_execution_result',
                  'aip_budget_reservation','aip_eval_run','aip_eval_report_revision'):
        assert 'CREATE POLICY route_eval_finalizer_read_'+table+'_a0v169 ON '+table in sql
    assert 'GRANT aos_route_eval_finalizer TO' not in sql
    assert 'INSERT INTO' not in sql


def test_route_finalization_migration_refuses_destructive_downgrade():
    migration=load()
    try:migration.downgrade()
    except RuntimeError as exc:assert 'reconciliation' in str(exc)
    else:raise AssertionError('Route finalization proof cannot be silently dropped')
