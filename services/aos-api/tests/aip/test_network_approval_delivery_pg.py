"""Disposable PG delivery state; no current-instance migration or natural worker."""
import uuid
import psycopg
import pytest
from aos_api.db import connect
from tests.aip.test_network_approval_event_driver_pg import event
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
from tests.aip.test_network_consumer_connection_pg import private_passfile, live_test_config
from aos_api.aip_network_consumer_connection import connect_consumer
from tests.aip.test_network_consumer_actor_pg import call as consume_call


def claim(conn, actor, token):
    return conn.execute('SELECT public.aip_claim_network_delivery_a0v_123(%s,%s,%s,%s) AS r',
                        (*SCOPE.key, actor, token)).fetchone()['r']


def finish(conn, actor, event_id, token):
    return conn.execute('SELECT public.aip_finish_network_delivery_a0v_123(%s,%s,%s,%s,%s) AS r',
                        (*SCOPE.key, actor, event_id, token)).fetchone()['r']


def test_new_approval_enqueues_and_receipt_is_required_for_ack(private_passfile):
    row, approval, actor = event()
    with isolated_owner() as conn:
        saved = conn.execute('SELECT * FROM aip_network_approval_delivery WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
                             (*SCOPE.key, approval['approval_event_id'])).fetchone()
        assert saved['status'] == 'pending' and saved['proposal_id'] == row['proposal_id']
    token = uuid.uuid4()
    with live_test_config(private_passfile) as cfg:
        with connect_consumer(cfg, SCOPE) as conn:
            work = claim(conn, actor.subject, token)
        assert work['mode'] == 'dispatch' and work['proposalId'] == row['proposal_id']
        with connect_consumer(cfg, SCOPE) as conn:
            assert claim(conn, actor.subject, uuid.uuid4()) is None
            assert finish(conn, actor.subject, approval['approval_event_id'], token)['status'] == 'unknown'
        # Fault fixture advances delivery availability, never execution authority.
        with isolated_owner() as conn:
            conn.execute("UPDATE aip_network_approval_delivery SET next_attempt=clock_timestamp() WHERE approval_event_id=%s", (approval['approval_event_id'],))
        token2 = uuid.uuid4()
        with connect_consumer(cfg, SCOPE) as conn:
            assert claim(conn, actor.subject, token2)['mode'] == 'inquiry'
        with connect_consumer(cfg, SCOPE) as conn:
            args = [*SCOPE.key, row['proposal_id'], approval['approval_event_id'], actor.subject,
                    row['proposal_hash'], row['payload']['targetContentHash'], row['action_binding_hash']]
            consume_call(conn, args)
        with connect_consumer(cfg, SCOPE) as conn:
            done = finish(conn, actor.subject, approval['approval_event_id'], token2)
            assert done['status'] == 'delivered' and done['receiptId']
        with connect_consumer(cfg, SCOPE) as conn:
            assert claim(conn, actor.subject, uuid.uuid4()) is None


def test_expired_claim_can_only_inquire_and_old_token_cannot_finish(private_passfile):
    row, approval, actor = event()
    first, second = uuid.uuid4(), uuid.uuid4()
    with live_test_config(private_passfile) as cfg:
        with connect_consumer(cfg, SCOPE) as conn:
            assert claim(conn, actor.subject, first)['mode'] == 'dispatch'
        with isolated_owner() as conn:
            conn.execute("UPDATE aip_network_approval_delivery SET claim_until=clock_timestamp()-interval '1 second' WHERE approval_event_id=%s", (approval['approval_event_id'],))
        with connect_consumer(cfg, SCOPE) as conn:
            assert claim(conn, actor.subject, second)['mode'] == 'inquiry'
        with connect_consumer(cfg, SCOPE) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                finish(conn, actor.subject, approval['approval_event_id'], first)
            conn.rollback()


def test_runtime_cannot_claim_or_write_delivery():
    with connect(SCOPE) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            claim(conn, 'maker', uuid.uuid4())
        conn.rollback()
    with connect(SCOPE) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE aip_network_approval_delivery SET status='delivered'")
        conn.rollback()


def test_wrong_maker_and_scope_cannot_claim(private_passfile):
    row, approval, actor = event()
    with live_test_config(private_passfile) as cfg:
        with connect_consumer(cfg, SCOPE) as conn:
            assert claim(conn, approval['actor_id'], uuid.uuid4()) is None
        with connect_consumer(cfg, SCOPE) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute('SELECT public.aip_claim_network_delivery_a0v_123(%s,%s,%s,%s)',
                             ('dev-org', SCOPE.project_id, actor.subject, uuid.uuid4()))
            conn.rollback()


def test_locked_claim_is_skipped_and_rollback_preserves_first_dispatch(private_passfile):
    row, approval, actor = event()
    with live_test_config(private_passfile) as cfg:
        with connect_consumer(cfg, SCOPE) as first:
            assert claim(first, actor.subject, uuid.uuid4())['mode'] == 'dispatch'
            with connect_consumer(cfg, SCOPE) as second:
                assert claim(second, actor.subject, uuid.uuid4()) is None
            first.rollback()  # No command was dispatched by this database-only test.
        with connect_consumer(cfg, SCOPE) as after_rollback:
            assert claim(after_rollback, actor.subject, uuid.uuid4())['mode'] == 'dispatch'


def test_enqueue_failure_rolls_back_the_approval_transaction():
    # Disposable owner installs an AFTER INSERT failure: this is a real PG rollback,
    # not a simulated approval result or a mutation of the current instance.
    with isolated_owner() as conn:
        before = tuple(conn.execute('SELECT count(*) AS n FROM '+t).fetchone()['n']
                       for t in ('aip_action_approval_event', 'aip_network_approval_delivery'))
        conn.execute("""CREATE FUNCTION public.bg00fi_rollback_probe() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                RAISE EXCEPTION 'DELIVERY_ROLLBACK_PROBE';
            END $$""")
        conn.execute('CREATE TRIGGER bg00fi_rollback_probe AFTER INSERT ON aip_network_approval_delivery '
                     'FOR EACH ROW EXECUTE FUNCTION public.bg00fi_rollback_probe()')
    try:
        with pytest.raises(psycopg.errors.RaiseException, match='DELIVERY_ROLLBACK_PROBE'):
            event()
        with isolated_owner() as conn:
            after = tuple(conn.execute('SELECT count(*) AS n FROM '+t).fetchone()['n']
                          for t in ('aip_action_approval_event', 'aip_network_approval_delivery'))
            assert after == before
    finally:
        with isolated_owner() as conn:
            conn.execute('DROP TRIGGER bg00fi_rollback_probe ON aip_network_approval_delivery')
            conn.execute('DROP FUNCTION public.bg00fi_rollback_probe()')


def test_revoked_maker_and_caller_direct_mutation_are_denied(private_passfile):
    row, approval, actor = event()
    with isolated_owner() as conn:
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                     (*SCOPE.key, actor.subject))
    with live_test_config(private_passfile) as cfg:
        with connect_consumer(cfg, SCOPE) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege, match='MEMBER_REQUIRED'):
                claim(conn, actor.subject, uuid.uuid4())
            conn.rollback()
        with connect_consumer(cfg, SCOPE) as conn:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute("UPDATE aip_network_approval_delivery SET status='pending'")
            conn.rollback()
