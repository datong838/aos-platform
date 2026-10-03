"""BI private wire must reject authority supplied by a client frame."""

import json
import os
import socket
import struct
import tempfile
from pathlib import Path

import pytest

from aos_api.tenant_scope import TenantScope


SCOPE = TenantScope("org-org", "dev-project")


def _payload():
    return {"schemaVersion": 1, "bearerToken": "header.payload.signature",
            "orgId": "org-org", "projectId": "dev-project",
            "installationId": "ccdcb0f0-1040-4bc6-aa0c-d045f5689813",
            "expectedETagVersion": 3, "idempotencyKey": "bi-once-1"}


def _frame(payload=None, method="prepare"):
    body = json.dumps({"schemaVersion": 1, "method": method,
                       "payload": _payload() if payload is None else payload},
                      separators=(",", ":")).encode()
    return struct.pack(">I", len(body)) + body


@pytest.mark.parametrize("raw", [
    b'{"schemaVersion":1,"schemaVersion":1,"method":"prepare","payload":{}}',
    b'{"schemaVersion":1,"method":"prepare","payload":{"orgId":"org-org","orgId":"dev-org"}}',
    b'{"schemaVersion":1,"method":"unknown","payload":{}}',
    b'{"schemaVersion":1,"method":"prepare","payload":{},"dbPassword":"x"}',
    json.dumps({"schemaVersion":1,"method":"prepare","payload":{
        **_payload(),"actor":"admin"}}).encode(),
    json.dumps({"schemaVersion":1,"method":"prepare","payload":{
        **_payload(),"socketPath":"/tmp/fake"}}).encode(),
])
def test_wire_rejects_duplicate_and_authority_fields(raw):
    from aos_api.aip_bi_plan_issuer_ipc import BIIssuerProtocolBlocked, decode_bi_issuer_request
    with pytest.raises(BIIssuerProtocolBlocked):
        decode_bi_issuer_request(raw)


def test_wire_accepts_only_strict_prepare_and_rebind():
    from aos_api.aip_bi_plan_issuer_ipc import decode_bi_issuer_request
    method, prepare = decode_bi_issuer_request(_frame()[4:])
    assert method == "prepare" and prepare.org_id == SCOPE.org_id
    rebind = {**_payload(), "planId": "plan-1", "prepareIdempotencyKey": "bi-once-1",
              "expectedPlanVersion": 1}
    method, command = decode_bi_issuer_request(_frame(rebind, "rebind")[4:])
    assert method == "rebind" and command.plan_id == "plan-1"


def test_same_uid_rejects_before_frame_or_handler():
    from aos_api.aip_bi_plan_issuer_ipc import serve_one_bi_issuer_connection
    left, right = socket.socketpair()
    called = []
    try:
        right.sendall(_frame())
        assert serve_one_bi_issuer_connection(
            left, api_uid=os.geteuid(), issuer_uid=os.geteuid(), expected_scope=SCOPE,
            dispatch=lambda _: called.append("called")) is False
        assert called == []
    finally:
        left.close(); right.close()


def test_real_unix_peer_wrong_uid_rejects_before_dispatch():
    """Real macOS kernel peer negative; no synthetic credential or formal positive claim."""
    from aos_api.aip_bi_plan_issuer_ipc import serve_one_bi_issuer_connection
    from aos_api.aip_network_issuer_ipc import open_private_issuer_listener
    from aos_api.aip_private_listener import owned_private_listener

    # macOS AF_UNIX paths have a short fixed limit; pytest's long fixture path
    # would fail at bind() before reaching the kernel peer check.
    with tempfile.TemporaryDirectory(prefix="bi-", dir="/tmp") as short:
        socket_dir = Path(short) / "ipc"
        socket_dir.mkdir(mode=0o750)
        os.chown(socket_dir, -1, os.getegid())
        os.chmod(socket_dir, 0o750)
        credential_dir = Path(short) / "private"
        credential_dir.mkdir(mode=0o700)
        credential_file = credential_dir / "issuer.pgpass"
        credential_file.write_text("test-only-placeholder")
        os.chmod(credential_file, 0o600)
        socket_path = socket_dir / "issuer.sock"
        api_uid, issuer_uid = os.geteuid() + 1, os.geteuid()
        called = []
        with owned_private_listener(
            socket_path, service_uid=issuer_uid, ipc_gid=os.getegid(),
            blocked=ValueError, error_code="PRIVATE_LISTENER_BLOCKED",
            open_listener=lambda: open_private_issuer_listener(
                socket_path, api_uid=api_uid, issuer_uid=issuer_uid,
                ipc_gid=os.getegid(), credential_file=credential_file,
            ),
        ) as listener:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(str(socket_path))
                accepted, _ = listener.accept()
                assert serve_one_bi_issuer_connection(
                    accepted, api_uid=api_uid, issuer_uid=issuer_uid,
                    expected_scope=SCOPE, dispatch=lambda _: called.append("called"),
                ) is False
                assert client.recv(1) == b""
            assert called == []
        assert not socket_path.exists()


def test_synthetic_wrong_tenant_is_blocked_before_dispatch(monkeypatch):
    from aos_api import aip_network_issuer_ipc as peer
    from aos_api.aip_bi_plan_issuer_ipc import serve_one_bi_issuer_connection
    api_uid = os.geteuid() + 1
    monkeypatch.setattr(peer, "_peer_identity", lambda _: (api_uid, os.getegid()))
    left, right = socket.socketpair()
    called = []
    try:
        right.sendall(_frame({**_payload(), "orgId": "dev-org"}))
        assert serve_one_bi_issuer_connection(
            left, api_uid=api_uid, issuer_uid=os.geteuid(), expected_scope=SCOPE,
            dispatch=lambda _: called.append("called")) is False
        size = struct.unpack(">I", right.recv(4))[0]
        response = json.loads(right.recv(size))
        assert response == {"schemaVersion": 1, "status": "blocked",
                            "code": "BI_ISSUER_REQUEST_BLOCKED"}
        assert b"header.payload.signature" not in json.dumps(response).encode()
        assert called == []
    finally:
        left.close(); right.close()


def test_synthetic_peer_transports_only_status_once(monkeypatch):
    """Unit protocol test only; synthetic peer cannot prove formal cross-UID admission."""
    from aos_api import aip_network_issuer_ipc as peer
    from aos_api.aip_bi_plan_issuer_ipc import serve_one_bi_issuer_connection
    from aos_api.aip_bi_plan_issuer_service import BIIssuerOutcome
    api_uid = os.geteuid() + 1
    monkeypatch.setattr(peer, "_peer_identity", lambda _: (api_uid, os.getegid()))
    left, right = socket.socketpair()
    called = []
    try:
        right.sendall(_frame())
        assert serve_one_bi_issuer_connection(
            left, api_uid=api_uid, issuer_uid=os.geteuid(), expected_scope=SCOPE,
            dispatch=lambda command: (called.append(command.idempotency_key)
                                      or BIIssuerOutcome("unresolved"))) is True
        size = struct.unpack(">I", right.recv(4))[0]
        response = json.loads(right.recv(size))
        assert response == {"schemaVersion": 1, "status": "unresolved"}
        assert called == ["bi-once-1"]
        assert b"header.payload.signature" not in json.dumps(response).encode()
    finally:
        left.close(); right.close()
