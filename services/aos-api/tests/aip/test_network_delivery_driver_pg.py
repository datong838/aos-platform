"""TLS + disposable PG composition; service bridge is not cross-UID acceptance."""
import pytest

from aos_api import aip_network_consumer_application as application
from aos_api import aip_network_delivery_driver as driver
from aos_api.aip_network_consumer_application import ConsumerApplicationBlocked
from aos_api.aip_network_consumer_contracts import (
    NetworkConsumerCommand, NetworkConsumerInquiry, NetworkDeliveryClaim, NetworkDeliveryFinish,
)
from aos_api.aip_network_consumer_service import process_network_delivery, consume_network_once, inquire_network
from tests.aip.test_network_consumer_application import configuration, principal
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_connection_pg import private_passfile, live_test_config
from tests.aip.test_network_approval_event_driver_pg import event
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE
from tests.aip.test_network_atomic_consumer_pg import counts


def bridge(monkeypatch, config, tmp_path, calls, lose=None):
    attempts = tmp_path/'service-attempts'; attempts.mkdir(mode=0o700)
    def request(endpoint, message):
        calls.append(type(message))
        if type(message) in (NetworkDeliveryClaim, NetworkDeliveryFinish):
            result = process_network_delivery(message, config)
        elif type(message) is NetworkConsumerCommand:
            result = consume_network_once(message, config, attempts)
        else:
            assert type(message) is NetworkConsumerInquiry
            result = inquire_network(message, config)
        if type(message) is lose:
            raise OSError('response lost after real PG commit')
        return result
    monkeypatch.setattr(driver, 'request_consumer', request)
    monkeypatch.setattr(application, 'request_consumer', request)


@pytest.mark.parametrize('lose', [None, NetworkConsumerCommand, NetworkDeliveryFinish])
def test_bounded_step_uses_actual_receipt_and_never_repeats(configuration, https_signer,
        private_passfile, tmp_path, monkeypatch, lose):
    sign, _ = https_signer
    row, approval, actor = event(); calls = []
    token = sign(actor.subject)
    with live_test_config(private_passfile) as config:
        bridge(monkeypatch, config, tmp_path, calls, lose)
        result = driver.process_network_delivery_once(configuration, actor, 'Bearer '+token)
        assert result['status'] == ('unresolved' if lose is NetworkDeliveryFinish else 'delivered')
        assert driver.process_network_delivery_once(configuration, actor, 'Bearer '+token) == {'status': 'idle'}
    assert calls == [NetworkDeliveryClaim, NetworkConsumerCommand, NetworkDeliveryFinish, NetworkDeliveryClaim]
    assert counts(row['proposal_id']) == (1, 1, 1)
    with isolated_owner() as conn:
        saved = conn.execute('SELECT status,receipt_id FROM aip_network_approval_delivery '
            'WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
            (*SCOPE.key, approval['approval_event_id'])).fetchone()
        assert saved['status'] == 'delivered' and saved['receipt_id']
    assert all(token not in p.read_text() for p in configuration.attempt_directory.iterdir())


def test_lost_claim_never_dispatches_after_expiry_even_without_marker(configuration, https_signer,
        private_passfile, tmp_path, monkeypatch):
    sign, _ = https_signer
    row, approval, actor = event(); calls = []
    with live_test_config(private_passfile) as config:
        bridge(monkeypatch, config, tmp_path, calls, NetworkDeliveryClaim)
        assert driver.process_network_delivery_once(configuration, actor, 'Bearer '+sign(actor.subject)) == {'status': 'unresolved'}
        assert not list(configuration.attempt_directory.iterdir())
        with isolated_owner() as conn:
            conn.execute("UPDATE aip_network_approval_delivery SET claim_until=clock_timestamp()-interval '1 second' "
                'WHERE org_id=%s AND project_id=%s AND approval_event_id=%s', (*SCOPE.key, approval['approval_event_id']))
        # Restore only the local transport observation; the durable original claim remains.
        def request(endpoint, message):
            calls.append(type(message))
            if type(message) in (NetworkDeliveryClaim, NetworkDeliveryFinish):
                return process_network_delivery(message, config)
            assert type(message) is NetworkConsumerInquiry
            return inquire_network(message, config)
        monkeypatch.setattr(driver, 'request_consumer', request)
        monkeypatch.setattr(application, 'request_consumer', request)
        assert driver.process_network_delivery_once(configuration, actor, 'Bearer '+sign(actor.subject)) == {'status': 'unknown'}
    assert calls == [NetworkDeliveryClaim, NetworkDeliveryClaim, NetworkConsumerInquiry, NetworkDeliveryFinish]
    assert counts(row['proposal_id']) == (0, 0, 0)
    assert not list(configuration.attempt_directory.iterdir())


@pytest.mark.parametrize('bad', ['forged', 'expired', 'dev'])
def test_identity_failure_never_claims(configuration, https_signer, monkeypatch, bad):
    sign, _ = https_signer
    actor = principal('maker')
    token = 'dev' if bad == 'dev' else sign('other' if bad == 'forged' else 'maker',
        changes={'exp': 1} if bad == 'expired' else None)
    monkeypatch.setattr(driver, 'request_consumer', lambda *a: pytest.fail('identity must precede claim'))
    with pytest.raises(ConsumerApplicationBlocked):
        driver.process_network_delivery_once(configuration, actor, 'Bearer '+token)


def test_checker_cannot_drain_original_maker_delivery(configuration, https_signer,
        private_passfile, tmp_path, monkeypatch):
    sign, _ = https_signer
    row, approval, actor = event(); calls = []
    checker = principal(approval['actor_id'])
    with live_test_config(private_passfile) as config:
        bridge(monkeypatch, config, tmp_path, calls)
        assert driver.process_network_delivery_once(configuration, checker, 'Bearer '+sign(checker.subject)) == {'status': 'idle'}
    assert calls == [NetworkDeliveryClaim] and counts(row['proposal_id']) == (0, 0, 0)
