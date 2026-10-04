"""Real independent login admission in a disposable database, no business grants."""
import os
from pathlib import Path
import secrets
import tempfile

import psycopg
from psycopg import sql, IsolationLevel
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
import pytest

from aos_api import aip_binding_evaluator_connection as evaluator
from aos_api.db import get_dsn
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')

@pytest.fixture
def independent_login(monkeypatch):
    parts = conninfo_to_dict(get_dsn())
    assert parts['dbname'].startswith('aos_test_') and parts['dbname'].endswith('_ti4_test')
    assert parts['host'] == '127.0.0.1' and str(parts['port']) == '5433'
    role = 'b81_evaluator_' + secrets.token_hex(6)
    password = secrets.token_urlsafe(32)
    monkeypatch.setattr(evaluator, 'EVALUATOR_LOGIN', role)
    with psycopg.connect(get_dsn(), autocommit=True) as owner:
        owner.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS PASSWORD {}').format(
            sql.Identifier(role), sql.Literal(password)))
        try:
            with tempfile.TemporaryDirectory(prefix='b81-private-') as directory:
                path = Path(directory) / 'pgpass'
                path.write_text(f"127.0.0.1:5433:{parts['dbname']}:{role}:{password}\n")
                path.chmod(0o600)
                config = evaluator.BindingEvaluatorDatabaseConfig('127.0.0.1', 5433, parts['dbname'], path)
                yield owner, role, config
        finally:
            owner.execute(sql.SQL('DROP OWNED BY {}').format(sql.Identifier(role)))
            owner.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(role)))


def test_independent_login_has_exact_transaction_and_no_business_write(independent_login):
    _, role, config = independent_login
    with evaluator.BindingEvaluatorConnectionFactory(config)(SCOPE) as conn:
        assert conn.isolation_level == IsolationLevel.SERIALIZABLE
        assert not conn.autocommit and not conn.read_only
        row = conn.execute("SELECT session_user,current_user,current_database() AS db,"
            "current_setting('aos.org_id') AS org,current_setting('aos.project_id') AS project").fetchone()
        assert (row['session_user'],row['current_user'],row['db'],row['org'],row['project']) == (
            role, role, config.database, *SCOPE.key)
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with conn.transaction():
                conn.execute("INSERT INTO aip_agent_registry_receipt SELECT * FROM aip_agent_registry_receipt LIMIT 0")

@pytest.mark.parametrize('attribute', ['INHERIT', 'CREATEDB', 'CREATEROLE', 'BYPASSRLS'])
def test_power_attribute_is_rejected(independent_login, attribute):
    owner, role, config = independent_login
    owner.execute(sql.SQL('ALTER ROLE {} {}').format(sql.Identifier(role), sql.SQL(attribute)))
    with pytest.raises(evaluator.BindingEvaluatorConnectionBlocked):
        with evaluator.BindingEvaluatorConnectionFactory(config)(SCOPE):
            pytest.fail('powerful login must never be yielded')


def test_runtime_membership_is_rejected(independent_login):
    owner, role, config = independent_login
    owner.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(role)))
    with pytest.raises(evaluator.BindingEvaluatorConnectionBlocked):
        with evaluator.BindingEvaluatorConnectionFactory(config)(SCOPE):
            pytest.fail('runtime membership must never be yielded')


def test_private_file_drift_and_pg_options_are_rejected(independent_login, monkeypatch):
    _, _, config = independent_login
    factory = evaluator.BindingEvaluatorConnectionFactory(config)
    config.passfile.chmod(0o644)
    with pytest.raises(evaluator.BindingEvaluatorConnectionBlocked):
        with factory(SCOPE): pytest.fail('unsafe file yielded')
    config.passfile.chmod(0o600)
    monkeypatch.setenv('PGOPTIONS', '-c statement_timeout=0')
    with pytest.raises(evaluator.BindingEvaluatorConnectionBlocked):
        with factory(SCOPE): pytest.fail('ambient options yielded')

@pytest.mark.parametrize('passfile', [None, 42])
def test_malformed_private_config_fails_with_safe_error(passfile):
    with pytest.raises(evaluator.BindingEvaluatorConnectionBlocked):
        evaluator.BindingEvaluatorDatabaseConfig('127.0.0.1', 5433, 'aos_test_safe_ti4_test', passfile)
