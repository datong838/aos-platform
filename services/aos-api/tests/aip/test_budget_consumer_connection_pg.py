"""Disposable PG admission for the budget identity, never live credentials."""
import json
import secrets

from psycopg import sql
import pytest

from aos_api.aip_budget_consumer_connection import (
    BudgetConsumerConfig, BudgetConsumerBlocked, connect_budget_consumer,
    budget_consumer_schema_snapshot, require_budget_consumer,
)
from tests.aip.test_budget_cost_consumer_pg import approved, consume, counts
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner


@pytest.fixture
def configured(private_passfile):
    private_passfile = private_passfile.with_name('budget-consumer.pgpass')
    private_passfile.touch(mode=0o600)
    with isolated_owner() as admin:
        admin.execute("SELECT pg_advisory_lock(hashtext('budget-consumer-tests'))")
        assert admin.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname='aos_budget_consumer_call'").fetchone()['rolcanlogin'] is False
        password = secrets.token_urlsafe(32)
        admin.execute(sql.SQL('ALTER ROLE aos_budget_consumer_call LOGIN PASSWORD {}').format(sql.Literal(password)))
        admin.commit()
        host, port, database = admin.info.host, admin.info.port, admin.info.dbname
        private_passfile.write_text(f'{host}:{port}:{database}:aos_budget_consumer_call:{password}\n')
        try:
            yield BudgetConsumerConfig(host, port, database, private_passfile)
        finally:
            admin.execute('ALTER ROLE aos_budget_consumer_call NOLOGIN PASSWORD NULL')
            admin.commit()
            private_passfile.write_text('# removed\n')
            admin.execute("SELECT pg_advisory_unlock(hashtext('budget-consumer-tests'))")


def test_isolated_migration_manifest_candidate(tmp_path):
    with isolated_owner() as conn:
        actual = budget_consumer_schema_snapshot(conn)
    candidate = tmp_path / 'budget-consumer-schema-candidate.json'
    candidate.write_text(json.dumps(actual, ensure_ascii=False, indent=2)+'\n')
    print('isolated candidate:', candidate)
    from pathlib import Path
    import aos_api.aip_budget_consumer_connection as module
    assert actual == json.loads(Path(module.__file__).with_name('aip_budget_consumer_schema.json').read_text())


def test_real_connection_atomic_consume_and_rollback(configured, issuer_factory, https_signer):
    _, _, p, saved, decision = approved(issuer_factory, https_signer)
    with connect_budget_consumer(configured, SCOPE, read_only=True) as conn:
        assert conn.execute('SELECT session_user AS login,current_user AS role').fetchone() == {
            'login': 'aos_budget_consumer_call', 'role': 'aos_budget_consumer_call'}
        assert conn.read_only is True
    assert conn.closed
    with pytest.raises(BudgetConsumerBlocked, match='RECONCILE_REQUIRED'):
        with connect_budget_consumer(configured, SCOPE, read_only=True) as conn:
            consume(conn, saved, decision)
    assert counts(p) == dict(active=0, receipts=0)
    with pytest.raises(BudgetConsumerBlocked, match='RECONCILE_REQUIRED'):
        with connect_budget_consumer(configured, SCOPE) as conn:
            consume(conn, saved, decision)
            conn.execute('SELECT 1/0')
    assert conn.closed and counts(p) == dict(active=0, receipts=0)
    with connect_budget_consumer(configured, SCOPE) as conn:
        result = consume(conn, saved, decision)
    assert result['decisionId'] == decision['decisionId']
    assert counts(p) == dict(active=1, receipts=1)


@pytest.mark.parametrize('mutation', [
    'ALTER ROLE aos_budget_consumer_call BYPASSRLS',
    'ALTER ROLE aos_budget_consumer_owner LOGIN',
    'GRANT aos_runtime TO aos_budget_consumer_call',
    'GRANT SELECT(receipt_id) ON aip_budget_receipt TO aos_budget_consumer_call',
    'GRANT CREATE ON SCHEMA public TO aos_budget_consumer_owner',
    'ALTER TABLE aip_budget_cost_decision DISABLE ROW LEVEL SECURITY',
    'ALTER TABLE aip_budget_cost_runtime_fence DISABLE TRIGGER budget_cost_fence_guard',
    'ALTER POLICY budget_consumer_a0v126 ON aip_budget_head USING (true)',
    'GRANT DELETE ON aip_budget_revision TO aos_budget_consumer_owner',
    'GRANT SELECT ON aip_network_policy_receipt TO aos_budget_consumer_owner',
    'GRANT EXECUTE ON FUNCTION aip_consume_budget_cost_a0v_126(text,text,text,text) TO PUBLIC',
    "CREATE OR REPLACE FUNCTION public.aip_consume_budget_cost_a0v_126(p_org text,p_project text,p_proposal text,p_decision text) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog AS $$ BEGIN RETURN '{}'::jsonb; END $$",
    "CREATE OR REPLACE FUNCTION public.aip_budget_active_insert_guard() RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog AS $$ BEGIN RETURN NEW; END $$",
])
def test_drift_rejects_before_consume(mutation, private_passfile):
    with isolated_owner() as conn:
        config = BudgetConsumerConfig(conn.info.host, conn.info.port, conn.info.dbname, private_passfile)
        conn.execute('ALTER ROLE aos_budget_consumer_call LOGIN')
        conn.execute(mutation)
        conn.execute('SET SESSION AUTHORIZATION aos_budget_consumer_call')
        conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
        conn.execute("SET LOCAL statement_timeout='10s'")
        conn.execute("SET LOCAL lock_timeout='5s'")
        conn.execute("SET LOCAL idle_in_transaction_session_timeout='10s'")
        conn.execute("SET LOCAL search_path=pg_catalog,public")
        with pytest.raises(BudgetConsumerBlocked):
            require_budget_consumer(conn, config, SCOPE, read_only=False)
        conn.rollback()


def test_revalidates_files_scope_environment_and_transaction(configured, monkeypatch):
    from aos_api.tenant_scope import TenantScope
    with pytest.raises(BudgetConsumerBlocked):
        with connect_budget_consumer(configured, TenantScope('dev-org', 'dev-project')):
            pytest.fail('canary admitted')
    monkeypatch.setenv('PGOPTIONS', '-c role=aos_runtime')
    with pytest.raises(BudgetConsumerBlocked):
        with connect_budget_consumer(configured, SCOPE):
            pytest.fail('environment admitted')
    monkeypatch.delenv('PGOPTIONS')
    with connect_budget_consumer(configured, SCOPE) as conn:
        conn.commit()
        with pytest.raises(BudgetConsumerBlocked):
            require_budget_consumer(conn, configured, SCOPE, read_only=False)
    configured.passfile.chmod(0o644)
    with pytest.raises(BudgetConsumerBlocked):
        with connect_budget_consumer(configured, SCOPE):
            pytest.fail('changed file admitted')
