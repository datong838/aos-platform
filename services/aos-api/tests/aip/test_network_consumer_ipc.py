"""Consumer wire contract and actual same-UID denial, not OS isolation acceptance."""
import json
import os
import socket
import struct
import pytest
from aos_api.aip_network_consumer_ipc import (
    ConsumerProtocolBlocked, decode_consumer_request, serve_one_consumer_connection,
    open_private_consumer_listener,
)
from tests.aip.test_network_consumer_contracts import raw


def wire(method='inquiry', **changes):
    return json.dumps({'schemaVersion': 1, 'method': method, 'payload': raw(**changes)}).encode()


@pytest.mark.parametrize('data', [
    b'{"schemaVersion":1,"schemaVersion":1,"method":"inquiry","payload":{}}',
    b'{"schemaVersion":true,"method":"inquiry","payload":{}}',
    b'{"schemaVersion":1,"method":"inquiry","payload":NaN}',
    wire('unknown'), wire(apiUid=501), wire(dsn='untrusted'), wire(actorId='other'),
    wire(attemptDirectory='/tmp/other'), b'x'*65537,
])
def test_wire_rejects_ambiguous_or_caller_authority(data):
    with pytest.raises(ConsumerProtocolBlocked):
        decode_consumer_request(data)


@pytest.mark.parametrize('method', ['inquiry', 'consume_once'])
def test_wire_accepts_only_exact_request(method):
    decoded, request = decode_consumer_request(wire(method))
    assert decoded == method and request.proposal_id == 'proposal-1'
    assert 'header.payload.signature' not in repr(request)


def test_same_uid_real_socket_is_rejected_before_config_or_attempt(tmp_path):
    left, right = socket.socketpair()
    try:
        data = wire('consume_once')
        right.sendall(struct.pack('>I', len(data)) + data)
        assert serve_one_consumer_connection(left, api_uid=os.geteuid(), consumer_uid=os.geteuid(),
                config=None, attempt_directory=tmp_path) is False
        assert list(tmp_path.iterdir()) == []
    finally:
        left.close()
        right.close()


def test_listener_invalid_config_does_not_create_socket(tmp_path):
    path = tmp_path / 'consumer.sock'
    with pytest.raises(ConsumerProtocolBlocked):
        open_private_consumer_listener(path, api_uid=os.geteuid(), consumer_uid=os.geteuid(),
                                      ipc_gid=os.getegid(), config=None, attempt_directory=tmp_path)
    assert not path.exists()


def test_protocol_routes_once_and_sanitizes_failures(monkeypatch, tmp_path):
    # Routing-only unit test. It does not establish a genuine distinct kernel UID.
    from aos_api import aip_network_consumer_ipc as module
    monkeypatch.setattr(module, 'require_issuer_peer', lambda *a, **kw: None)
    calls = []
    def fail(*args):
        calls.append(1)
        raise RuntimeError('header.payload.signature private-db-detail')
    monkeypatch.setattr(module, 'consume_network_once', fail)
    left, right = socket.socketpair()
    try:
        data = wire('consume_once')
        right.sendall(struct.pack('>I', len(data)) + data)
        assert module.serve_one_consumer_connection(left, api_uid=1, consumer_uid=2,
                    config=None, attempt_directory=tmp_path) is False
        size = struct.unpack('>I', right.recv(4))[0]
        response = json.loads(right.recv(size))
        assert response == {'schemaVersion': 1, 'status': 'blocked', 'code': 'CONSUMER_REQUEST_BLOCKED'}
        assert calls == [1]
    finally:
        left.close()
        right.close()


def test_actual_kernel_peer_must_match_configured_api_uid(tmp_path):
    left, right = socket.socketpair()
    try:
        assert serve_one_consumer_connection(left, api_uid=os.geteuid()+1, consumer_uid=os.geteuid(),
                    config=None, attempt_directory=tmp_path) is False
        assert list(tmp_path.iterdir()) == []
    finally:
        left.close()
        right.close()


def test_response_loss_never_dispatches_command_twice(monkeypatch, tmp_path):
    # Routing-only failure injection; actual socket send fails after one dispatch.
    from aos_api import aip_network_consumer_ipc as module
    monkeypatch.setattr(module, 'require_issuer_peer', lambda *a, **kw: None)
    calls = []
    def once(*args):
        calls.append(1)
        return {'status': 'unresolved'}
    monkeypatch.setattr(module, 'consume_network_once', once)
    left, right = socket.socketpair()
    try:
        data = wire('consume_once')
        right.sendall(struct.pack('>I', len(data)) + data)
        right.shutdown(socket.SHUT_RD)
        assert module.serve_one_consumer_connection(left, api_uid=1, consumer_uid=2,
                    config=None, attempt_directory=tmp_path) is False
        assert calls == [1]
    finally:
        left.close()
        right.close()
