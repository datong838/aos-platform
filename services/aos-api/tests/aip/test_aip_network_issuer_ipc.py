"""Private Unix issuer protocol rejects weak peer identity and untrusted wire fields."""

import json
import os
import socket
import struct

import pytest


def _payload():
    return {
        "schemaVersion": 1, "bearerToken": "header.payload.signature",
        "orgId": "org-org", "projectId": "dev-project",
        "proposalId": "proposal-1", "idempotencyKey": "decision-1",
        "requestHash": "a" * 64,
    }


def _frame(method="inquiry", payload=None):
    body = json.dumps({"schemaVersion": 1, "method": method,
                       "payload": payload if payload is not None else _payload()},
                      separators=(",", ":")).encode()
    return struct.pack(">I", len(body)) + body


@pytest.mark.parametrize("raw", [
    b'{"schemaVersion":1,"schemaVersion":1,"method":"inquiry","payload":{}}',
    b'{"schemaVersion":1,"method":"unknown","payload":{}}',
    b'{"schemaVersion":1,"method":"inquiry","payload":{},"role":"owner"}',
    json.dumps({"schemaVersion":1,"method":"inquiry","payload":{
        **_payload(),"role":"owner"}}).encode(),
    json.dumps({"schemaVersion":1,"method":"inquiry","payload":{
        **_payload(),"dbPassword":"secret"}}).encode(),
])
def test_wire_contract_rejects_duplicates_unknowns_and_authority_fields(raw):
    from aos_api.aip_network_issuer_ipc import decode_issuer_request, IssuerProtocolBlocked
    with pytest.raises(IssuerProtocolBlocked):
        decode_issuer_request(raw)


def test_wire_contract_accepts_only_exact_command_or_inquiry():
    from aos_api.aip_network_issuer_ipc import decode_issuer_request
    method, request = decode_issuer_request(_frame()[4:])
    assert method == "inquiry" and request.org_id == "org-org"
    command = {k:v for k,v in _payload().items() if k != "requestHash"}
    command["decision"] = {"expectedProposalVersion":1,
                            "expectedProposalHash":"a"*64,
                            "decision":"approved","reason":"reviewed"}
    method, request = decode_issuer_request(_frame("decide_once", command)[4:])
    assert method == "decide_once" and request.request_hash


def test_real_unix_same_uid_peer_is_rejected():
    from aos_api.aip_network_issuer_ipc import require_issuer_peer, IssuerProtocolBlocked, _peer_identity
    left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        assert _peer_identity(left)[0] == os.geteuid()
        with pytest.raises(IssuerProtocolBlocked):
            require_issuer_peer(left, api_uid=os.geteuid(), issuer_uid=os.geteuid())
    finally:
        left.close(); right.close()


def test_tcp_socket_and_truncated_or_oversize_frame_rejected():
    from aos_api.aip_network_issuer_ipc import read_issuer_frame, IssuerProtocolBlocked
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp:
        with pytest.raises(IssuerProtocolBlocked):
            read_issuer_frame(tcp)
    left, right = socket.socketpair()
    try:
        right.sendall(struct.pack(">I", 65_537))
        with pytest.raises(IssuerProtocolBlocked):
            read_issuer_frame(left)
    finally:
        left.close(); right.close()
    left, right = socket.socketpair()
    try:
        right.sendall(struct.pack(">I", 5) + b"ab")
        right.close()
        with pytest.raises(IssuerProtocolBlocked):
            read_issuer_frame(left)
    finally:
        left.close()


def test_same_uid_transport_rejects_before_database_or_attempt(tmp_path):
    from aos_api.aip_network_issuer_ipc import serve_one_issuer_connection
    left, right = socket.socketpair()
    try:
        right.sendall(_frame())
        result = serve_one_issuer_connection(left, api_uid=os.geteuid(),
            issuer_uid=os.geteuid(), attempt_directory=tmp_path,
            expected_database="isolated", read_connect_factory=lambda: pytest.fail("DB opened"),
            decision_connect_factory=lambda _: pytest.fail("DB opened"))
        assert result is False
        assert not list(tmp_path.iterdir())
    finally:
        left.close(); right.close()


def test_synthetic_distinct_peer_still_requires_formal_oidc_before_database(monkeypatch, tmp_path):
    from aos_api import aip_network_issuer_ipc as module
    synthetic_api_uid = os.geteuid() + 1
    monkeypatch.setattr(module, "_peer_identity", lambda _: (synthetic_api_uid, os.getegid()))
    left, right = socket.socketpair()
    try:
        right.sendall(_frame())
        assert module.serve_one_issuer_connection(left, api_uid=synthetic_api_uid,
            issuer_uid=os.geteuid(), attempt_directory=tmp_path,
            expected_database="isolated", read_connect_factory=lambda: pytest.fail("DB opened"),
            decision_connect_factory=lambda _: pytest.fail("DB opened")) is False
        header = right.recv(4)
        size = struct.unpack(">I", header)[0]
        response = json.loads(right.recv(size))
        assert response == {"schemaVersion":1,"status":"blocked","code":"ISSUER_REQUEST_BLOCKED"}
        assert b"header.payload.signature" not in json.dumps(response).encode()
        assert not list(tmp_path.iterdir())
    finally:
        left.close(); right.close()


def test_listener_cannot_start_with_same_uid_or_missing_private_credential(tmp_path):
    from aos_api.aip_network_issuer_ipc import open_private_issuer_listener, IssuerProtocolBlocked
    socket_dir = tmp_path / "socket-dir"
    socket_dir.mkdir(mode=0o770)
    os.chmod(socket_dir, 0o770)
    credential_dir = tmp_path / "credential-dir"
    credential_dir.mkdir(mode=0o700)
    credential = credential_dir / "issuer.pgpass"
    credential.write_text("not-a-real-secret")
    os.chmod(credential, 0o600)
    socket_path = socket_dir / "issuer.sock"
    with pytest.raises(IssuerProtocolBlocked):
        open_private_issuer_listener(socket_path, api_uid=os.geteuid(),
            issuer_uid=os.geteuid(), ipc_gid=os.getegid(), credential_file=credential)
    assert not socket_path.exists()
    with pytest.raises(IssuerProtocolBlocked):
        open_private_issuer_listener(socket_path, api_uid=os.geteuid()+1,
            issuer_uid=os.geteuid(), ipc_gid=os.getegid(),
            credential_file=credential_dir / "missing")
    assert not socket_path.exists()


def test_synthetic_peer_routes_inquiry_once_without_wire_authority(monkeypatch, tmp_path):
    from aos_api import aip_network_issuer_ipc as module
    from aos_api.aip_network_issuer_reconcile import ReconcileResult, ReconcileStatus
    synthetic_api_uid = os.geteuid() + 1
    monkeypatch.setattr(module, "_peer_identity", lambda _: (synthetic_api_uid, os.getegid()))
    calls = []
    def inquiry(request, *, read_connect_factory, expected_database):
        calls.append((request.org_id, request.project_id, expected_database))
        return ReconcileResult(ReconcileStatus.UNRESOLVED)
    monkeypatch.setattr(module, "dispatch_issuer_request", inquiry)
    left, right = socket.socketpair()
    try:
        right.sendall(_frame())
        assert module.serve_one_issuer_connection(left, api_uid=synthetic_api_uid,
            issuer_uid=os.geteuid(), attempt_directory=tmp_path,
            expected_database="isolated", read_connect_factory=lambda: pytest.fail("DB opened"),
            decision_connect_factory=lambda _: pytest.fail("decide opened")) is True
        size = struct.unpack(">I", right.recv(4))[0]
        assert json.loads(right.recv(size)) == {
            "schemaVersion": 1, "status": "unresolved", "eventId": None, "decision": None}
        assert calls == [("org-org", "dev-project", "isolated")]
    finally:
        left.close(); right.close()
