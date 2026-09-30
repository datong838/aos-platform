"""Real isolated issuer login/timeouts; no current database or formal identity proof."""
from contextlib import contextmanager
import secrets
import time
import pytest
import psycopg
from psycopg import sql

from aos_api.aip_network_issuer_connection import (
    IssuerDatabaseConfig, IssuerDatabaseBlocked, connect_issuer_read_only,
    connect_issuer_decision, _require_identity,
)
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
from tests.aip.test_network_consumer_connection_pg import private_passfile


@contextmanager
def live_issuer(private_passfile):
    with isolated_owner() as admin:
        admin.execute("SELECT pg_advisory_lock(hashtext('bg00fb-issuer-login-test'))")
        original = admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password "
                                 "FROM pg_authid WHERE rolname='aos_network_approval_issuer'").fetchone()
        assert original == {'rolcanlogin': False, 'no_password': True}
        password = secrets.token_urlsafe(32)
        admin.execute(sql.SQL('ALTER ROLE aos_network_approval_issuer LOGIN PASSWORD {}').format(sql.Literal(password)))
        admin.commit()
        try:
            host, port, database = admin.info.host, admin.info.port, admin.info.dbname
            private_passfile.write_text(f'{host}:{port}:{database}:aos_network_approval_issuer:{password}\n')
            yield IssuerDatabaseConfig(host, port, database, private_passfile)
        finally:
            admin.execute('ALTER ROLE aos_network_approval_issuer NOLOGIN PASSWORD NULL')
            admin.commit()
            private_passfile.write_text('# removed temporary issuer credential\n')
            assert admin.execute("SELECT rolcanlogin,rolpassword IS NULL AS no_password "
                                 "FROM pg_authid WHERE rolname='aos_network_approval_issuer'").fetchone() == original
            admin.execute("SELECT pg_advisory_unlock(hashtext('bg00fb-issuer-login-test'))")


def limits(conn):
    return {row['name']: int(row['setting']) for row in conn.execute(
        "SELECT name,setting FROM pg_settings WHERE name=ANY(%s)",
        (['statement_timeout', 'lock_timeout', 'idle_in_transaction_session_timeout'],)).fetchall()}


EXPECTED = dict(statement_timeout=10000, lock_timeout=5000, idle_in_transaction_session_timeout=10000)


@pytest.mark.parametrize('read_only', [False, True])
def test_real_login_and_limits_survive_transaction_boundaries(private_passfile, read_only):
    with live_issuer(private_passfile) as config:
        factory = connect_issuer_read_only if read_only else connect_issuer_decision
        with factory(config, SCOPE) as conn:
            assert conn.execute('SELECT session_user AS login').fetchone()['login'] == 'aos_network_approval_issuer'
            assert limits(conn) == EXPECTED
            conn.commit()
            assert limits(conn) == EXPECTED
            conn.rollback()
            assert limits(conn) == EXPECTED
        assert conn.closed


def test_real_long_sql_is_cancelled_then_rollback_restores_scope(private_passfile):
    with live_issuer(private_passfile) as config:
        with connect_issuer_decision(config, SCOPE) as conn:
            assert limits(conn) == EXPECTED
            start = time.monotonic()
            with pytest.raises(psycopg.errors.QueryCanceled):
                conn.execute('SELECT pg_sleep(12)')
            assert 9 <= time.monotonic()-start < 12
            conn.rollback()
            _require_identity(conn, config, SCOPE, read_only=False)
            assert limits(conn) == EXPECTED


def test_real_lock_wait_is_cancelled_without_retry(private_passfile):
    with live_issuer(private_passfile) as config:
        with isolated_owner() as blocker:
            key = secrets.randbelow(2**30)
            blocker.execute('SELECT pg_advisory_lock(%s)', (key,))
            try:
                with connect_issuer_decision(config, SCOPE) as conn:
                    assert limits(conn) == EXPECTED
                    start = time.monotonic()
                    with pytest.raises(psycopg.errors.LockNotAvailable):
                        conn.execute('SELECT pg_advisory_xact_lock(%s)', (key,))
                    assert 4 <= time.monotonic()-start < 8
                    conn.rollback()
                    _require_identity(conn, config, SCOPE, read_only=False)
                    assert limits(conn) == EXPECTED
            finally:
                blocker.execute('SELECT pg_advisory_unlock(%s)', (key,))


def test_timeout_drift_denied_and_rollback_restores(private_passfile):
    with live_issuer(private_passfile) as config:
        with connect_issuer_decision(config, SCOPE) as conn:
            conn.execute('SET LOCAL statement_timeout = 0')
            with pytest.raises(IssuerDatabaseBlocked):
                _require_identity(conn, config, SCOPE, read_only=False)
            conn.rollback()
            assert limits(conn) == EXPECTED


def test_real_idle_transaction_is_terminated(private_passfile):
    with live_issuer(private_passfile) as config:
        with pytest.raises(psycopg.errors.IdleInTransactionSessionTimeout):
            with connect_issuer_read_only(config, SCOPE) as conn:
                assert limits(conn) == EXPECTED
                time.sleep(10.3)
                conn.execute('SELECT 1')
        assert conn.closed
