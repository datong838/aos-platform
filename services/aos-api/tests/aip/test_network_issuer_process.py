"""Real listener lifecycle and kernel rejection, not cross-UID approval proof."""
from dataclasses import replace
import json
import os
import socket
import struct
import threading
import time
import pytest

from aos_api.tenant_scope import TenantScope
from aos_api.aip_network_issuer_connection import IssuerDatabaseConfig
from aos_api.aip_network_issuer_process import IssuerProcessConfig, issuer_listener, run_issuer_process
from aos_api.aip_network_issuer_ipc import IssuerProtocolBlocked, read_issuer_frame
from tests.aip.test_network_consumer_process import config as consumer_config
from tests.aip.test_aip_network_issuer_contracts import _command


@pytest.fixture
def config(consumer_config):
    c = consumer_config
    return IssuerProcessConfig(socket_path=c.socket_path, api_uid=c.api_uid,
        issuer_uid=c.consumer_uid, ipc_gid=c.ipc_gid,
        database=IssuerDatabaseConfig(c.database.host, c.database.port, c.database.database, c.database.passfile),
        scope=TenantScope('org-org', 'dev-project'), attempt_directory=c.attempt_directory,
        max_connections=1, accept_timeout=0.2)


def test_owned_cleanup_and_exception(config):
    with pytest.raises(RuntimeError):
        with issuer_listener(config) as listener:
            assert config.socket_path.is_socket()
            raise RuntimeError('stop')
    assert listener.fileno() == -1 and not config.socket_path.exists()


def test_replaced_file_survives(config):
    with issuer_listener(config):
        config.socket_path.unlink()
        config.socket_path.write_text('replacement')
    assert config.socket_path.read_text() == 'replacement'


def test_occupied_path_survives(config):
    config.socket_path.write_text('occupied')
    with pytest.raises(IssuerProtocolBlocked):
        with issuer_listener(config): pytest.fail('occupied accepted')
    assert config.socket_path.read_text() == 'occupied'


def test_idle_no_database(config):
    start = time.monotonic()
    assert run_issuer_process(config) == {'accepted': 0, 'processed': 0}
    assert time.monotonic()-start < 2
    assert not config.socket_path.exists()


def test_kernel_wrong_uid_counts_toward_limit(config):
    errors = []
    def connect():
        try:
            deadline = time.monotonic()+2
            while not config.socket_path.exists() and time.monotonic() < deadline:
                time.sleep(0.005)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                peer.connect(str(config.socket_path))
        except Exception as exc: errors.append(type(exc).__name__)
    thread = threading.Thread(target=connect)
    thread.start()
    try:
        assert run_issuer_process(config) == {'accepted': 1, 'processed': 0}
    finally: thread.join(3)
    assert not thread.is_alive() and not errors
    assert not config.socket_path.exists()


@pytest.mark.parametrize('change', [{'max_connections': True}, {'max_connections': 65},
    {'max_connections': 0}, {'accept_timeout': float('nan')}, {'accept_timeout': 31},
    {'scope': None}, {'socket_path': 'relative'}, {'issuer_uid': os.geteuid()+1}])
def test_config_fails_before_listener(config, change):
    with pytest.raises(IssuerProtocolBlocked): replace(config, **change)
    assert not config.socket_path.exists()


def test_cross_scope_frame_rejected_before_service(config, monkeypatch):
    # Synthetic peer ONLY for reaching the scope gate; no formal identity claim.
    from aos_api import aip_network_issuer_ipc as ipc
    monkeypatch.setattr(ipc, '_peer_identity', lambda conn: (config.api_uid, config.ipc_gid))
    monkeypatch.setattr(ipc, 'issue_decision_once', lambda *a, **k: pytest.fail('service called'))
    request = _command(orgId='other-org')
    payload = request.model_dump(mode='json', by_alias=True)
    payload['bearerToken'] = request.bearer_token.get_secret_value()
    body = json.dumps(dict(schemaVersion=1, method='decide_once', payload=payload)).encode()
    left, right = socket.socketpair()
    with left, right:
        right.sendall(struct.pack('>I', len(body))+body)
        assert ipc.serve_one_issuer_connection(left, api_uid=config.api_uid,
            issuer_uid=config.issuer_uid, attempt_directory=config.attempt_directory,
            expected_database=config.database.database, expected_scope=config.scope,
            read_connect_factory=lambda: pytest.fail('DB called'),
            decision_connect_factory=lambda scope: pytest.fail('DB called')) is False
        assert json.loads(read_issuer_frame(right))['status'] == 'blocked'


def test_process_factories_remain_bound_to_configured_scope(config, monkeypatch):
    # Wiring unit only: no service execution or database effect is claimed.
    from contextlib import contextmanager
    from aos_api import aip_network_issuer_process as process
    left, right = socket.socketpair()
    class Listener:
        def settimeout(self, value): assert value == config.accept_timeout
        def accept(self): return left, None
    @contextmanager
    def listener(configuration): yield Listener()
    monkeypatch.setattr(process, 'issuer_listener', listener)
    calls = []
    monkeypatch.setattr(process, 'connect_issuer_read_only', lambda db, scope: calls.append(('read', db, scope)))
    monkeypatch.setattr(process, 'connect_issuer_decision', lambda db, scope: calls.append(('decision', db, scope)))
    def serve(conn, **kwargs):
        assert kwargs['expected_scope'] == config.scope
        assert kwargs['expected_database'] == config.database.database
        kwargs['read_connect_factory']()
        kwargs['decision_connect_factory'](config.scope)
        with pytest.raises(IssuerProtocolBlocked):
            kwargs['decision_connect_factory'](TenantScope('other-org', 'dev-project'))
        return False
    monkeypatch.setattr(process, 'serve_one_issuer_connection', serve)
    with right:
        assert run_issuer_process(config) == {'accepted': 1, 'processed': 0}
    assert left.fileno() == -1
    assert calls == [('read', config.database, config.scope), ('decision', config.database, config.scope)]
