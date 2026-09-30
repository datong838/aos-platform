"""Exact event routing in disposable PG; captured IPC is not activation proof."""
import pytest

from aos_api import aip_network_consumer_application as consumer
from aos_api.aip_network_approval_event_driver import process_network_approval_event
from aos_api.aip_network_consumer_application import ConsumerApplicationBlocked
from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand, NetworkConsumerInquiry
from aos_api.db import connect
from tests.aip.test_network_consumer_application import configuration, principal
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_proposal_reconcile_pg import saved_request, counts
from tests.aip.test_network_consumer_boundary_pg import isolated_owner
from tests.aip.test_network_consumer_connection_pg import private_passfile, live_test_config
from tests.aip.test_network_atomic_consumer_pg import counts as consumption_counts
from aos_api.aip_network_consumer_service import consume_network_once, inquire_network


def event():
    row, _, actor, _ = saved_request()
    with isolated_owner() as conn:
        a = conn.execute('SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s '
            'AND proposal_id=%s', (actor.org_id, actor.project_id, row['proposal_id'])).fetchone()
    return row, a, actor


def test_exact_durable_event_resolves_refs_and_repeat_only_inquires(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    row, approval, actor = event()
    before = counts(); calls = []
    monkeypatch.setattr(consumer, 'request_consumer', lambda endpoint, request: calls.append(request) or {'status': 'unresolved'})
    for _ in range(2):
        assert process_network_approval_event(configuration, row['proposal_id'], approval['approval_event_id'],
            actor, 'Bearer '+sign(actor.subject)) == {'status': 'unresolved'}
    assert [type(r) for r in calls] == [NetworkConsumerCommand, NetworkConsumerInquiry]
    assert calls[0].proposal_hash == row['proposal_hash']
    assert calls[0].target_content_hash == row['payload']['targetContentHash']
    assert calls[0].binding_hash == row['action_binding_hash']
    assert calls[0].approval_event_id == approval['approval_event_id']
    assert calls[0].request_hash == calls[1].request_hash
    assert counts() == before


def test_real_consumer_receipt_reconciled_after_transport_response_loss(configuration, https_signer,
                                                                       private_passfile, tmp_path, monkeypatch):
    sign, _ = https_signer
    row, approval, actor = event()
    service_attempts = tmp_path/'service-attempts'; service_attempts.mkdir(mode=0o700)
    calls = []
    with live_test_config(private_passfile) as db_config:
        def direct_transport(endpoint, request):
            calls.append(type(request))
            if type(request) is NetworkConsumerCommand:
                result = consume_network_once(request, db_config, service_attempts)
                assert result['status'] == 'observed'
                raise OSError('simulated response loss after actual PG receipt')
            return inquire_network(request, db_config)
        monkeypatch.setattr(consumer, 'request_consumer', direct_transport)
        args = (configuration, row['proposal_id'], approval['approval_event_id'], actor, 'Bearer '+sign(actor.subject))
        assert process_network_approval_event(*args) == {'status': 'unresolved'}
        result = process_network_approval_event(*args)
        assert result['status'] == 'observed'
        assert result['receipt']['proposalId'] == row['proposal_id']
        assert calls == [NetworkConsumerCommand, NetworkConsumerInquiry]
    assert consumption_counts(row['proposal_id']) == (1, 1, 1)


@pytest.mark.parametrize('bad', ['checker', 'other', 'event', 'scope', 'expired', 'forged'])
def test_missing_exact_maker_event_never_sends_or_reserves(configuration, https_signer, monkeypatch, bad):
    sign, _ = https_signer
    row, approval, actor = event()
    token_actor = actor.subject
    event_id = approval['approval_event_id']
    if bad == 'checker': actor = principal(approval['actor_id']); token_actor = actor.subject
    if bad == 'other': actor = principal('other'); token_actor = actor.subject
    if bad == 'event': event_id = 'missing-event'
    if bad == 'scope': actor.org_id = 'dev-org'
    if bad == 'forged': token_actor = 'different'
    token = sign(token_actor, changes={'exp': 1} if bad == 'expired' else None)
    monkeypatch.setattr(consumer, 'request_consumer', lambda *a: pytest.fail('must not send'))
    before = counts()
    with pytest.raises(ConsumerApplicationBlocked):
        process_network_approval_event(configuration, row['proposal_id'], event_id, actor, 'Bearer '+token)
    assert not list(configuration.attempt_directory.iterdir()) and counts() == before


def test_writeable_discovery_connection_is_rejected(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    row, approval, actor = event()
    monkeypatch.setattr(consumer, 'request_consumer', lambda *a: pytest.fail('must not send'))
    with pytest.raises(ConsumerApplicationBlocked) as e:
        process_network_approval_event(configuration, row['proposal_id'], approval['approval_event_id'],
            actor, 'Bearer '+sign(actor.subject), connect_factory=connect)
    assert e.value.status_code == 503 and not list(configuration.attempt_directory.iterdir())


def test_durable_inquiry_never_sends_command_without_local_marker(configuration, https_signer, monkeypatch):
    sign, _ = https_signer
    row, approval, actor = event()
    calls = []
    monkeypatch.setattr(consumer, 'request_consumer', lambda endpoint, request: calls.append(request) or {'status': 'unresolved'})
    assert not list(configuration.attempt_directory.iterdir())
    process_network_approval_event(configuration, row['proposal_id'], approval['approval_event_id'],
        actor, 'Bearer '+sign(actor.subject), inquiry=True)
    assert [type(r) for r in calls] == [NetworkConsumerInquiry]
    assert not list(configuration.attempt_directory.iterdir())
