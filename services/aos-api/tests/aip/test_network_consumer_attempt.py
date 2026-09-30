"""Real private-file reservations, independent of formal business authority."""
import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from aos_api.auth import Principal
from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand
from aos_api.aip_network_consumer_attempt import reserve_consumer_attempt
from aos_api.aip_network_issuer_attempt import (
    AttemptBlocked, AttemptAlreadyRecorded, AttemptConflict, AttemptUnknown,
    reserve_decision_attempt,
)
from tests.aip.test_network_consumer_contracts import raw
from tests.aip.test_aip_network_issuer_attempt import _command


def principal(subject='maker'):
    return Principal(subject=subject, org_id='org-org', project_id='dev-project', token_kind='oidc')


def test_reserved_record_private_redacted_and_never_reissued(tmp_path):
    command = NetworkConsumerCommand.model_validate(raw())
    receipt = reserve_consumer_attempt(tmp_path, command, principal())
    path = next(tmp_path.iterdir())
    assert path.stat().st_mode & 0o777 == 0o600
    assert 'header.payload.signature' not in path.read_text()
    assert json.loads(path.read_text())['namespace'] == 'network-policy-consumer/v1'
    assert receipt.idempotency_key == command.proposal_id
    with pytest.raises(AttemptAlreadyRecorded):
        reserve_consumer_attempt(tmp_path, NetworkConsumerCommand.model_validate(raw(bearerToken='new.token.signature')), principal())
    for command2, actor in (
        (NetworkConsumerCommand.model_validate(raw(bindingHash='d'*64)), principal()),
        (command, principal('other-maker')),
    ):
        with pytest.raises(AttemptConflict):
            reserve_consumer_attempt(tmp_path, command2, actor)


def test_concurrent_requests_have_one_winner(tmp_path):
    command = NetworkConsumerCommand.model_validate(raw())
    def reserve(_):
        try:
            reserve_consumer_attempt(tmp_path, command, principal())
            return True
        except AttemptBlocked:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(8))) == 1


def test_partial_or_permissive_file_never_authorizes(tmp_path):
    command = NetworkConsumerCommand.model_validate(raw())
    reserve_consumer_attempt(tmp_path, command, principal())
    path = next(tmp_path.iterdir())
    path.write_text('')
    with pytest.raises(AttemptUnknown):
        reserve_consumer_attempt(tmp_path, command, principal())
    path.chmod(0o644)
    with pytest.raises(AttemptUnknown):
        reserve_consumer_attempt(tmp_path, command, principal())


def test_issuer_and_consumer_namespaces_are_distinct(tmp_path):
    reserve_decision_attempt(tmp_path, _command(idempotencyKey='proposal-1'), principal())
    reserve_consumer_attempt(tmp_path, NetworkConsumerCommand.model_validate(raw()), principal())
    assert len(list(tmp_path.iterdir())) == 2


def test_invalid_contract_and_identity_write_nothing(tmp_path):
    command = NetworkConsumerCommand.model_validate(raw())
    bad = Principal(subject='maker', org_id='other', project_id='dev-project', token_kind='oidc')
    for request, actor in ((command.inquiry(), principal()), (command, bad)):
        with pytest.raises(AttemptBlocked):
            reserve_consumer_attempt(tmp_path, request, actor)
    assert list(tmp_path.iterdir()) == []
