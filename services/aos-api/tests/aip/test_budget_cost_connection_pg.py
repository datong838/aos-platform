"""Actual disposable PG login and TLS JWT; no live deployment authority."""
from dataclasses import replace
import time

import psycopg
import pytest

from aos_api.aip_budget_cost_connection import (
    BudgetCostDatabaseConfig, BudgetCostConnectionFactory, require_budget_connection,
)
from aos_api.aip_budget_cost_issuer import BudgetCostIssuer, BudgetCostIssuerBlocked
from aos_api.tenant_scope import TenantScope
from tests.aip.test_budget_cost_issuer_pg import issuer_factory, prepared, command
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner


@pytest.fixture
def configured(issuer_factory, private_passfile):
    with issuer_factory(SCOPE, True) as conn:
        config = BudgetCostDatabaseConfig(conn.info.host, conn.info.port,
                                        conn.info.dbname, private_passfile)
    return config, BudgetCostConnectionFactory(config, SCOPE)


@pytest.mark.parametrize('read_only', [True, False])
def test_actual_login_scope_isolation_and_limits_survive_boundaries(configured, read_only):
    config, factory = configured
    with factory(SCOPE, read_only) as conn:
        for action in (lambda: None, conn.commit, conn.rollback):
            action()
            require_budget_connection(conn, config, SCOPE, read_only=read_only)
            assert conn.execute('SELECT session_user AS u').fetchone()['u'] == 'aos_budget_cost_issuer'
        assert conn.read_only is read_only
    assert conn.closed


def test_signed_approval_inquiry_and_revocation_through_real_factory(configured, https_signer, monkeypatch):
    _, factory = configured
    # Build normal proposal fixtures first, then make the shared API DSN unusable.
    sign, fetched = https_signer
    maker, checker, _, proposal, saved = prepared()
    monkeypatch.setenv('AOS_DATABASE_URL', 'postgresql://aos_app@127.0.0.1:1/unavailable')
    issuer = BudgetCostIssuer(factory)
    cmd = command(sign, checker, saved)
    assert issuer.inquire(cmd) == {'status': 'unresolved'}
    result = issuer.execute(cmd)
    assert issuer.inquire(cmd)['result'] == result
    assert issuer.execute(cmd) == result
    revoke = command(sign, maker, saved, operation='revoke', decision=None, reason='withdraw')
    assert issuer.execute(revoke)['decisionId'] == result['decisionId']
    assert issuer.inquire(revoke)['status'] == 'observed'
    assert result['activationEligible'] is False and fetched
    with factory(SCOPE, True) as conn:
        assert conn.execute("SELECT count(*) AS n FROM aip_budget_revision WHERE budget_id=%s AND lifecycle='active'",
                            (proposal.target.budget_id,)).fetchone()['n'] == 0


def test_readonly_rejects_write(configured):
    _, factory = configured
    with factory(SCOPE, True) as conn:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            conn.execute('DELETE FROM aip_budget_cost_proposal WHERE false')
        conn.rollback()
        assert conn.execute('SELECT 1 AS n').fetchone()['n'] == 1


@pytest.mark.parametrize('name', ['PGPASSWORD', 'PGPASSFILE', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'])
def test_no_environment_fallback(configured, monkeypatch, name):
    _, factory = configured
    monkeypatch.setenv(name, 'test-only-invalid')
    with pytest.raises(BudgetCostIssuerBlocked, match='CONNECTION_CONFIG'):
        with factory(SCOPE, True):
            pytest.fail('environment accepted')


def test_rechecks_private_file_permissions(configured):
    config, factory = configured
    config.passfile.chmod(0o644)
    try:
        with pytest.raises(BudgetCostIssuerBlocked, match='CONFIG'):
            with factory(SCOPE, True):
                pytest.fail('public credential accepted')
    finally:
        config.passfile.chmod(0o600)


@pytest.mark.parametrize('changes', [dict(host='example.com'), dict(port=True),
    dict(database='bad;db'), dict(passfile='relative.pgpass')])
def test_exact_config_required(configured, changes):
    config, _ = configured
    with pytest.raises(BudgetCostIssuerBlocked, match='CONFIG'):
        replace(config, **changes)


def test_symlink_credential_is_rejected(configured):
    config, _ = configured
    link = config.passfile.parent / 'link.pgpass'
    link.symlink_to(config.passfile)
    with pytest.raises(BudgetCostIssuerBlocked, match='CONFIG'):
        replace(config, passfile=link)


@pytest.mark.parametrize('scope,read_only', [(TenantScope('dev-org', 'dev-project'), True),
                                           (SCOPE, 1), (SCOPE, None)])
def test_scope_and_mode_are_fixed(configured, scope, read_only):
    _, factory = configured
    with pytest.raises(BudgetCostIssuerBlocked, match='CONNECTION_CONFIG'):
        with factory(scope, read_only):
            pytest.fail('scope or mode accepted')


def test_database_and_timeout_drift_rejected(configured):
    config, factory = configured
    with factory(SCOPE, False) as conn:
        with pytest.raises(BudgetCostIssuerBlocked, match='DATABASE'):
            require_budget_connection(conn, replace(config, database='wrong_db'), SCOPE, read_only=False)
        conn.execute('SET LOCAL statement_timeout=0')
        with pytest.raises(BudgetCostIssuerBlocked, match='DATABASE'):
            require_budget_connection(conn, config, SCOPE, read_only=False)
        conn.rollback()
        require_budget_connection(conn, config, SCOPE, read_only=False)


def test_real_statement_timeout_and_rollback(configured):
    config, factory = configured
    with factory(SCOPE, False) as conn:
        start = time.monotonic()
        with pytest.raises(psycopg.errors.QueryCanceled):
            conn.execute('SELECT pg_sleep(12)')
        assert 9 <= time.monotonic() - start < 12
        conn.rollback()
        require_budget_connection(conn, config, SCOPE, read_only=False)


def test_real_lock_timeout(configured):
    config, factory = configured
    with isolated_owner() as blocker:
        blocker.execute('SELECT pg_advisory_xact_lock(937510001)')
        with factory(SCOPE, False) as conn:
            start = time.monotonic()
            with pytest.raises(psycopg.errors.LockNotAvailable):
                conn.execute('SELECT pg_advisory_xact_lock(937510001)')
            assert 4 <= time.monotonic() - start < 8
            conn.rollback()
            require_budget_connection(conn, config, SCOPE, read_only=False)


def test_network_credentials_do_not_become_budget_authority(private_passfile):
    from tests.aip.test_network_issuer_timeouts_pg import live_issuer
    with live_issuer(private_passfile) as network:
        config = BudgetCostDatabaseConfig(network.host, network.port, network.database, private_passfile)
        with pytest.raises(BudgetCostIssuerBlocked, match='CONNECTION_FAILED'):
            with BudgetCostConnectionFactory(config, SCOPE)(SCOPE, True):
                pytest.fail('wrong domain credential accepted')
