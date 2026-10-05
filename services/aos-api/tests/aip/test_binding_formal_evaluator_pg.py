"""Complete b90 evaluator acceptance, starting with isolated identity admission.

Session-authorization fault tests prove role checks only, never SCRAM or business
authority. A separate temporary LOGIN test proves actual SCRAM and is cleaned
after verifying its members and shared dependencies. No business ACL is granted.
"""
import os

import psycopg
from psycopg import sql
import pytest

from aos_api.aip_binding_evaluator_connection import (
    BindingEvaluatorConnectionBlocked, BindingEvaluatorDatabaseConfig,
    BindingEvaluatorConnectionFactory, EVALUATOR_LOGIN, _require_identity,
)
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE


def _config(tmp_path, database):
    tmp_path.chmod(0o700)
    passfile = tmp_path / 'passfile'
    passfile.write_text('', encoding='utf-8')
    passfile.chmod(0o600)
    return BindingEvaluatorDatabaseConfig('127.0.0.1', 5432, database, passfile)


@pytest.mark.parametrize('fault', ['outgoing_membership', 'incoming_membership', 'search_path'])
def test_evaluator_rejects_identity_drift_in_actual_pg(tmp_path, fault):
    with isolated_owner() as conn:
        conn.isolation_level = psycopg.IsolationLevel.SERIALIZABLE
        config = _config(tmp_path, conn.info.dbname)
        with conn.transaction(force_rollback=True):
            existing = conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (EVALUATOR_LOGIN,)).fetchone()
            if existing is None:
                conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
                    'NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(EVALUATOR_LOGIN)))
            else:
                conn.execute(sql.SQL('ALTER ROLE {} LOGIN').format(sql.Identifier(EVALUATOR_LOGIN)))
            if fault == 'outgoing_membership':
                conn.execute(sql.SQL('GRANT {} TO aos_runtime').format(sql.Identifier(EVALUATOR_LOGIN)))
            elif fault == 'incoming_membership':
                conn.execute(sql.SQL('GRANT aos_runtime TO {}').format(sql.Identifier(EVALUATOR_LOGIN)))
            conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(EVALUATOR_LOGIN)))
            try:
                conn.execute("SET LOCAL statement_timeout='10s'")
                conn.execute("SET LOCAL lock_timeout='5s'")
                conn.execute("SET LOCAL idle_in_transaction_session_timeout='10s'")
                conn.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
                conn.execute("SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)", SCOPE.key)
                if fault == 'search_path':
                    conn.execute('SET LOCAL search_path=public,pg_catalog')
                with pytest.raises(BindingEvaluatorConnectionBlocked, match='EVALUATOR_DATABASE_IDENTITY_REQUIRED'):
                    _require_identity(conn, config, SCOPE)
            finally:
                conn.execute('RESET SESSION AUTHORIZATION')


def test_evaluator_private_passfile_rejects_hardlink(tmp_path):
    config = _config(tmp_path, 'aos_test_identity')
    alias = tmp_path / 'alias'
    os.link(config.passfile, alias)
    with pytest.raises(BindingEvaluatorConnectionBlocked, match='EVALUATOR_EXACT_PRIVATE_CONFIGURATION_REQUIRED'):
        BindingEvaluatorDatabaseConfig(config.host, config.port, config.database, config.passfile)


def test_evaluator_actual_scram_admission_and_live_outgoing_membership_rejection(tmp_path):
    import secrets
    with isolated_owner() as owner:
        assert owner.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (EVALUATOR_LOGIN,)).fetchone() is None
        secret = secrets.token_urlsafe(32)
        owner.execute("SET LOCAL password_encryption='scram-sha-256'")
        owner.execute(sql.SQL('CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB '
            'NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(
                sql.Identifier(EVALUATOR_LOGIN), sql.Literal(secret)))
        database = owner.info.dbname
        owner.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(
            sql.Identifier(database), sql.Identifier(EVALUATOR_LOGIN)))
        owner.commit()
        try:
            config = _config(tmp_path, database)
            config.passfile.write_text(
                f'127.0.0.1:{owner.info.port}:{database}:{EVALUATOR_LOGIN}:{secret}\n', encoding='utf-8')
            config = BindingEvaluatorDatabaseConfig('127.0.0.1', owner.info.port, database, config.passfile)
            factory = BindingEvaluatorConnectionFactory(config)
            with factory(SCOPE) as actual:
                assert actual.pgconn.used_password
                assert actual.execute('SELECT session_user AS login,current_user AS role').fetchone() == {
                    'login': EVALUATOR_LOGIN, 'role': EVALUATOR_LOGIN}
                assert actual.isolation_level == psycopg.IsolationLevel.SERIALIZABLE
                assert actual.execute('SHOW search_path').fetchone()['search_path'].replace(' ', '') == 'pg_catalog,public,pg_temp'
                actual.execute('CREATE TEMP TABLE aip_model_route_head(fake_head boolean)')
                assert actual.execute("SELECT to_regclass('aip_model_route_head')="
                    "'public.aip_model_route_head'::regclass AS original").fetchone()['original']
            original_passfile = config.passfile.read_text(encoding='utf-8')
            config.passfile.write_text(original_passfile.replace(secret, secrets.token_urlsafe(32)), encoding='utf-8')
            with pytest.raises(BindingEvaluatorConnectionBlocked, match='EVALUATOR_CONNECTION_FAILED'):
                with factory(SCOPE):
                    pytest.fail('wrong password admitted')
            config.passfile.write_text(original_passfile, encoding='utf-8')
            owner.execute(sql.SQL('GRANT {} TO aos_runtime').format(sql.Identifier(EVALUATOR_LOGIN)))
            owner.commit()
            with pytest.raises(BindingEvaluatorConnectionBlocked, match='EVALUATOR_DATABASE_IDENTITY_REQUIRED'):
                with factory(SCOPE):
                    pytest.fail('membership drift admitted')
        finally:
            owner.execute(sql.SQL('REVOKE {} FROM aos_runtime').format(sql.Identifier(EVALUATOR_LOGIN)))
            owner.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM {}').format(
                sql.Identifier(database), sql.Identifier(EVALUATOR_LOGIN)))
            owner.execute(sql.SQL('ALTER ROLE {} NOLOGIN PASSWORD NULL').format(sql.Identifier(EVALUATOR_LOGIN)))
            assert owner.execute('SELECT count(*) AS n FROM pg_auth_members WHERE '
                'roleid=%s::regrole OR member=%s::regrole', (EVALUATOR_LOGIN, EVALUATOR_LOGIN)).fetchone()['n'] == 0
            assert owner.execute("SELECT count(*) AS n FROM pg_shdepend WHERE refclassid='pg_authid'::regclass "
                'AND refobjid=%s::regrole', (EVALUATOR_LOGIN,)).fetchone()['n'] == 0
            owner.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(EVALUATOR_LOGIN)))
            owner.commit()
            assert owner.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (EVALUATOR_LOGIN,)).fetchone() is None
