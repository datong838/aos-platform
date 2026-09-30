"""Real framing and kernel rejection; not formal cross-UID deployment proof."""
import json
import os
import socket
import struct
import threading

import pytest

from aos_api.aip_network_issuer_client import (
    IssuerEndpoint, IssuerClientBlocked, request_issuer, _exchange, _decode_response,
)
from aos_api.aip_private_service_transport import require_private_peer
from aos_api.aip_network_issuer_ipc import read_issuer_frame, decode_issuer_request
from tests.aip.test_aip_network_issuer_contracts import _command


@pytest.mark.parametrize('inquiry', [False, True])
@pytest.mark.parametrize('lost', [False, True])
@pytest.mark.parametrize('decision', ['approved', 'rejected'])
def test_one_frame_no_reconnect(inquiry, lost, decision):
    command = _command(decision={'expectedProposalVersion': 1,
                                'expectedProposalHash': 'a'*64,
                                'decision': decision, 'reason': 'reviewed'})
    request = command.inquiry() if inquiry else command
    response = dict(schemaVersion=1, status='observed', eventId='event-1', decision=decision)
    received = []
    left, right = socket.socketpair()
    def server():
        with right:
            received.append(json.loads(read_issuer_frame(right)))
            if not lost:
                body = json.dumps(response).encode()
                right.sendall(struct.pack('>I', len(body)) + body)
                right.settimeout(1)
                assert right.recv(1) == b''
    worker = threading.Thread(target=server)
    worker.start()
    with left:
        result = _exchange(left, request)
    worker.join(2)
    assert not worker.is_alive()
    assert result == ({'status': 'unresolved'} if lost else
                      {k: v for k, v in response.items() if k != 'schemaVersion'})
    assert len(received) == 1
    assert received[0]['method'] == ('inquiry' if inquiry else 'decide_once')
    assert received[0]['payload']['bearerToken'] == command.bearer_token.get_secret_value()
    method, decoded = decode_issuer_request(json.dumps(received[0]).encode())
    assert method == received[0]['method']
    assert decoded.request_hash == command.request_hash


@pytest.mark.parametrize('change', [
    {'schemaVersion': True}, {'status': 'active'}, {'eventId': ''},
    {'eventId': 'bad id'}, {'decision': 'rejected'}, {'extra': 'secret'},
])
def test_invalid_observation_rejected(change):
    response = dict(schemaVersion=1, status='observed', eventId='event-1', decision='approved')
    with pytest.raises(IssuerClientBlocked):
        _decode_response(json.dumps({**response, **change}).encode(), _command())


@pytest.mark.parametrize('status', ['unresolved', 'conflict'])
def test_non_observed_has_no_event(status):
    response = dict(schemaVersion=1, status=status, eventId=None, decision=None)
    assert _decode_response(json.dumps(response).encode(), _command())['status'] == status
    response['eventId'] = 'invented'
    with pytest.raises(IssuerClientBlocked):
        _decode_response(json.dumps(response).encode(), _command())


def test_strict_json_and_blocked():
    for raw in [b'{"schemaVersion":1,"schemaVersion":1}', b'{"schemaVersion":NaN}']:
        with pytest.raises(IssuerClientBlocked):
            _decode_response(raw, _command())
    assert _decode_response(b'{"schemaVersion":1,"status":"blocked","code":"ISSUER_REQUEST_BLOCKED"}', _command())['status'] == 'blocked'


def test_real_wrong_peer_and_missing_endpoint_send_nothing(tmp_path):
    endpoint = IssuerEndpoint(tmp_path/'socket', os.geteuid(), os.geteuid()+1, os.getegid())
    with pytest.raises(IssuerClientBlocked):
        request_issuer(endpoint, _command())
    left, right = socket.socketpair()
    with left, right:
        with pytest.raises(ValueError):
            require_private_peer(left, api_uid=endpoint.api_uid,
                                 service_uid=endpoint.issuer_uid, ipc_gid=endpoint.ipc_gid)
        right.setblocking(False)
        with pytest.raises(BlockingIOError):
            right.recv(1)
    with pytest.raises(IssuerClientBlocked):
        IssuerEndpoint(tmp_path/'socket', os.geteuid(), os.geteuid(), os.getegid())
