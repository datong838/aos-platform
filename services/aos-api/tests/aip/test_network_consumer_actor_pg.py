"""Isolated SQL actor gate; subject is trusted only after future service auth."""
import pytest
import psycopg
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
from tests.aip.test_network_atomic_consumer_pg import _approved, counts
from tests.aip.test_network_consumer_connection_pg import private_passfile, live_test_config
from aos_api.aip_network_consumer_connection import connect_consumer


def approved_args():
    proposal, event, checker, _ = _approved(None)
    with isolated_owner() as conn:
        row = conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                           (*SCOPE.key, proposal)).fetchone()
    return [*SCOPE.key, proposal, event, row['created_by'], row['proposal_hash'],
            row['payload']['targetContentHash'], row['action_binding_hash']], checker


def call(conn, args, read=False):
    name = 'reconcile' if read else 'consume'
    return conn.execute(f'SELECT public.aip_{name}_network_as_actor_a0v_122(%s,%s,%s,%s,%s,%s,%s,%s) AS result',
                        args).fetchone()['result']


def test_original_maker_can_consume_and_observe_exact_receipt(private_passfile):
    args, _ = approved_args()
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE, read_only=True) as conn:
            assert call(conn, args, True) == {'status': 'unresolved'}
        assert counts(args[2]) == (0, 0, 0)
        with connect_consumer(config, SCOPE) as conn:
            receipt = call(conn, args)
        with connect_consumer(config, SCOPE, read_only=True) as conn:
            assert call(conn, args, True) == {'status': 'observed', 'receipt': receipt}
        assert counts(args[2]) == (1, 1, 1)


def test_read_wrapper_requires_read_only_transaction(private_passfile):
    args, _ = approved_args()
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                call(conn, args, True)
            conn.rollback()
    assert counts(args[2]) == (0, 0, 0)


def test_committed_receipt_does_not_bypass_current_maker_role(private_passfile):
    args, _ = approved_args()
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE) as conn:
            call(conn, args)
        with isolated_owner() as conn:
            conn.execute('UPDATE meta_membership SET role=%s WHERE org_id=%s AND project_id=%s AND subject=%s',
                         ('viewer', *SCOPE.key, args[4]))
        for read in (False, True):
            with connect_consumer(config, SCOPE, read_only=read) as conn:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    call(conn, args, read)
                conn.rollback()
    assert counts(args[2]) == (1, 1, 1)


def test_wrong_approval_event_cannot_consume_or_observe_receipt(private_passfile):
    args, _ = approved_args()
    bad = list(args)
    bad[3] = 'unknown-approval-event'
    with live_test_config(private_passfile) as config:
        with connect_consumer(config, SCOPE) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                call(conn, bad)
            conn.rollback()
        assert counts(args[2]) == (0, 0, 0)
        with connect_consumer(config, SCOPE) as conn:
            call(conn, args)
        with connect_consumer(config, SCOPE, read_only=True) as conn:
            assert call(conn, bad, True) == {'status': 'conflict'}
    assert counts(args[2]) == (1, 1, 1)


@pytest.mark.parametrize('field', [0, 4, 5, 6, 7])
def test_wrong_scope_actor_or_exact_reference_is_rejected(private_passfile, field):
    args, checker = approved_args()
    bad = list(args)
    bad[field] = checker if field == 4 else ('other-org' if field == 0 else 'd'*64)
    with live_test_config(private_passfile) as config:
        for read in (False, True):
            with connect_consumer(config, SCOPE, read_only=read) as conn:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    call(conn, bad, read)
                conn.rollback()
        assert counts(args[2]) == (0, 0, 0)


def test_original_maker_membership_revocation_blocks_both_paths(private_passfile):
    args, _ = approved_args()
    with isolated_owner() as conn:
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                     (*SCOPE.key, args[4]))
    with live_test_config(private_passfile) as config:
        for read in (False, True):
            with connect_consumer(config, SCOPE, read_only=read) as conn:
                with pytest.raises(psycopg.errors.InsufficientPrivilege, match='ACTOR_AUTHORITY_REQUIRED'):
                    call(conn, args, read)
                conn.rollback()
        assert counts(args[2]) == (0, 0, 0)
