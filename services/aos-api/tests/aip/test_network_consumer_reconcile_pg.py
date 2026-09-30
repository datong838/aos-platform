"""Actual read-only reconciliation of isolated committed/unknown transactions."""
import pytest
from aos_api.aip_network_consumer_connection import connect_consumer
from aos_api.aip_network_consumer_reconcile import reconcile_network_receipt, ConsumerReconcileBlocked
from aos_api.tenant_scope import TenantScope
from tests.aip.test_network_consumer_connection_pg import private_passfile, live_test_config
from tests.aip.test_network_atomic_consumer_pg import _approved, consume, counts
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE


def test_receipt_reconcile_never_consumes_missing_then_observes_committed(private_passfile):
    proposal, event, _, _ = _approved(None)
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE, read_only=True) as conn:
            assert reconcile_network_receipt(conn, SCOPE, proposal, event, config.database) == {'status': 'unresolved'}
        assert counts(proposal) == (0, 0, 0)
        with connect_consumer(config, SCOPE) as conn:
            receipt = consume(conn, proposal, event)
        with connect_consumer(config, SCOPE, read_only=True) as conn:
            assert reconcile_network_receipt(conn, SCOPE, proposal, event, config.database) == {
                'status': 'observed', 'receipt': receipt}
            assert reconcile_network_receipt(conn, SCOPE, proposal, 'wrong-event', config.database) == {'status': 'conflict'}
        with connect_consumer(config, TenantScope('other-org', 'dev-project'), read_only=True) as conn:
            assert reconcile_network_receipt(conn, TenantScope('other-org', 'dev-project'), proposal,
                                            event, config.database) == {'status': 'unresolved'}
        assert counts(proposal) == (1, 1, 1)


def test_rolled_back_consumption_is_unresolved_without_resend(private_passfile):
    proposal, event, _, _ = _approved(None)
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE) as conn:
            consume(conn, proposal, event)
            conn.rollback()
        with connect_consumer(config, SCOPE, read_only=True) as conn:
            assert reconcile_network_receipt(conn, SCOPE, proposal, event, config.database) == {'status': 'unresolved'}
        assert counts(proposal) == (0, 0, 0)


def test_read_write_connection_cannot_reconcile(private_passfile):
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE) as conn:
            with pytest.raises(ConsumerReconcileBlocked, match='READ_ONLY_REQUIRED'):
                reconcile_network_receipt(conn, SCOPE, 'missing', 'missing', config.database)


def test_read_only_observation_does_not_lock_proposal(private_passfile):
    proposal, event, _, _ = _approved(None)
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE) as conn:
            receipt = consume(conn, proposal, event)
        with isolated_owner() as blocker:
            blocker.execute('SELECT 1 FROM aip_action_proposal WHERE org_id=%s AND project_id=%s '
                            'AND proposal_id=%s FOR UPDATE', (*SCOPE.key, proposal))
            with connect_consumer(config, SCOPE, read_only=True) as conn:
                conn.execute("SET LOCAL statement_timeout='1s'")
                assert reconcile_network_receipt(conn, SCOPE, proposal, event, config.database)['receipt'] == receipt
            blocker.rollback()
        assert counts(proposal) == (1, 1, 1)


@pytest.mark.parametrize('read_only,other_scope', [(False, False), (True, True)])
def test_sql_gate_itself_rejects_wrong_transaction_or_scope(private_passfile, read_only, other_scope):
    import psycopg
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE, read_only=read_only) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege, match='READ_ONLY_IDENTITY_REQUIRED'):
                conn.execute('SELECT public.aip_reconcile_network_receipt_a0v_121(%s,%s,%s,%s)',
                             ('other-org' if other_scope else SCOPE.org_id, SCOPE.project_id, 'missing', 'missing'))
            conn.rollback()


@pytest.mark.parametrize('role', ['aos_runtime', 'aos_network_approval_issuer'])
def test_other_roles_cannot_call_sql_reconcile(role):
    import psycopg
    from psycopg import sql
    with isolated_owner() as conn:
        conn.execute(sql.SQL('SET SESSION AUTHORIZATION {}').format(sql.Identifier(role)))
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match='permission denied for function'):
            conn.execute("SELECT public.aip_reconcile_network_receipt_a0v_121('org-org','dev-project','missing','missing')")
        conn.rollback()


def test_completed_receipt_survives_approval_expiry_and_member_removal(private_passfile):
    proposal, event, checker, expires = _approved('approval')
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE) as conn:
            receipt = consume(conn, proposal, event)
        with isolated_owner() as conn:
            conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                         (*SCOPE.key, checker))
            now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            conn.execute('SELECT pg_sleep(%s)', (max(0, (expires-now).total_seconds()) + .05,))
        with connect_consumer(config, SCOPE, read_only=True) as conn:
            assert reconcile_network_receipt(conn, SCOPE, proposal, event, config.database) == {
                'status': 'observed', 'receipt': receipt}
        assert counts(proposal) == (1, 1, 1)
