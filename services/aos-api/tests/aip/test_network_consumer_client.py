"""Real transport contract and kernel rejection, not cross-UID deployment proof."""
import json
import os
import socket
import struct
import threading
import pytest

from aos_api.aip_network_consumer_client import (
    ConsumerEndpoint, ConsumerClientBlocked, request_consumer,
    _exchange, _require_server, _decode_response,
)
from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand
from aos_api.aip_network_issuer_ipc import read_issuer_frame
from tests.aip.test_network_consumer_contracts import raw


@pytest.fixture
def command():
    return NetworkConsumerCommand.model_validate(raw())


def observed():
    return {'schemaVersion': 1, 'status': 'observed', 'receipt': {
        'resourceType': 'NetworkPolicyRevision', 'resourceId': 'policy-1', 'revision': 1,
        'proposalId': 'proposal-1', 'approvalEventId': 'approval-1',
        'contentHash': 'b'*64, 'receiptId': 'receipt-1'}}


@pytest.mark.parametrize('inquiry', [False, True])
def test_one_actual_frame_and_exact_response(command, inquiry):
    left, right = socket.socketpair()
    received = []
    def server():
        with right:
            received.append(json.loads(read_issuer_frame(right)))
            body = json.dumps(observed()).encode()
            right.sendall(struct.pack('>I', len(body)) + body)
            right.settimeout(1)
            assert right.recv(1) == b''
    worker = threading.Thread(target=server)
    worker.start()
    try:
        with left:
            result = _exchange(left, command.inquiry() if inquiry else command)
        assert result == {k: v for k, v in observed().items() if k != 'schemaVersion'}
    finally:
        worker.join(2)
    assert not worker.is_alive()
    assert len(received) == 1
    assert received[0]['method'] == ('inquiry' if inquiry else 'consume_once')
    assert received[0]['payload']['bearerToken'] == command.bearer_token.get_secret_value()


def test_response_loss_returns_unknown_without_second_send(command):
    left, right = socket.socketpair()
    received = []
    def server():
        with right:
            received.append(read_issuer_frame(right))
    worker = threading.Thread(target=server)
    worker.start()
    with left:
        assert _exchange(left, command) == {'status': 'unresolved'}
    worker.join(2)
    assert len(received) == 1
    assert not worker.is_alive()


@pytest.mark.parametrize('change', [
    {'schemaVersion': True}, {'status': 'active'}, {'extra': 'secret-sentinel'},
    {'receipt': {**observed()['receipt'], 'proposalId': 'other'}},
    {'receipt': {**observed()['receipt'], 'contentHash': 'd'*64}},
    {'receipt': {**observed()['receipt'], 'revision': True}},
    {'receipt': {**observed()['receipt'], 'receiptId': ''}},
])
def test_invalid_response_cannot_claim_observed(command, change):
    with pytest.raises(ConsumerClientBlocked):
        _decode_response(json.dumps({**observed(), **change}).encode(), command)


def test_duplicate_and_nan_rejected(command):
    for body in [b'{"schemaVersion":1,"schemaVersion":1,"status":"unresolved"}',
                 b'{"schemaVersion":1,"status":"unresolved","x":NaN}']:
        with pytest.raises(ConsumerClientBlocked):
            _decode_response(body, command)


@pytest.mark.parametrize('status', ['unresolved', 'conflict', 'blocked'])
def test_exact_non_observed_responses(command, status):
    data = {'schemaVersion': 1, 'status': status}
    if status == 'blocked':
        data['code'] = 'CONSUMER_REQUEST_BLOCKED'
    assert _decode_response(json.dumps(data).encode(), command)['status'] == status


def test_same_uid_endpoint_is_never_accepted(tmp_path, command):
    with pytest.raises(ConsumerClientBlocked):
        request_consumer(ConsumerEndpoint(tmp_path/'s', os.geteuid(), os.geteuid(), os.getegid()), command)


def test_real_kernel_server_mismatch_sends_nothing(tmp_path):
    endpoint = ConsumerEndpoint(tmp_path/'s', os.geteuid(), os.geteuid()+1, os.getegid())
    left, right = socket.socketpair()
    with left, right:
        with pytest.raises(ConsumerClientBlocked):
            _require_server(left, endpoint)
        right.setblocking(False)
        with pytest.raises(BlockingIOError):
            right.recv(1)


def test_missing_endpoint_fails_before_send(tmp_path, command):
    endpoint = ConsumerEndpoint(tmp_path/'s', os.geteuid(), os.geteuid()+1, os.getegid())
    with pytest.raises(ConsumerClientBlocked):
        request_consumer(endpoint, command)
