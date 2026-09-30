"""Real private listener lifecycle; no formal cross-UID business acceptance."""
import os
import socket
import threading
import time
import tempfile
from pathlib import Path
import pytest
from aos_api.aip_network_consumer_connection import ConsumerDatabaseConfig
from aos_api.aip_network_consumer_process import ConsumerProcessConfig, consumer_listener, run_consumer_process
from aos_api.aip_network_consumer_ipc import ConsumerProtocolBlocked
from aos_api.aip_network_issuer_ipc import open_private_issuer_listener, IssuerProtocolBlocked
from tests.aip.test_aip_network_issuer_auth import _external_config


@pytest.fixture
def config(tmp_path, monkeypatch):
    _external_config(monkeypatch)
    short_root = tempfile.TemporaryDirectory(prefix='aos-er-', dir='/tmp')
    root = Path(short_root.name)
    sockets = root / 'ipc'
    sockets.mkdir(mode=0o750)
    os.chown(sockets, -1, os.getegid())
    private = root / 'private'
    private.mkdir(mode=0o700)
    secret = private / 'pgpass'
    secret.write_text('# isolated placeholder; lifecycle test never connects to DB\n')
    secret.chmod(0o600)
    try:
        yield ConsumerProcessConfig(socket_path=sockets/'c.sock', api_uid=os.geteuid()+1,
            consumer_uid=os.geteuid(), ipc_gid=os.getegid(),
            database=ConsumerDatabaseConfig('127.0.0.1', 5433, 'isolated', secret),
            attempt_directory=private, max_connections=1, accept_timeout=0.2)
    finally:
        short_root.cleanup()


def test_group_writable_directory_is_rejected(config):
    config.socket_path.parent.chmod(0o770)
    info = config.socket_path.parent.stat()
    assert (info.st_uid, info.st_gid, info.st_mode & 0o777) == (config.consumer_uid, config.ipc_gid, 0o770)
    with pytest.raises(IssuerProtocolBlocked, match='PRIVATE_PATHS_REQUIRED'):
        listener = open_private_issuer_listener(config.socket_path, api_uid=config.api_uid,
            issuer_uid=config.consumer_uid, ipc_gid=config.ipc_gid, credential_file=config.database.passfile)
        listener.close()
    assert not config.socket_path.exists()


def test_own_socket_is_closed_and_removed(config):
    with consumer_listener(config) as listener:
        assert config.socket_path.is_socket()
        assert config.socket_path.stat().st_mode & 0o777 == 0o660
        assert listener.fileno() >= 0
    assert listener.fileno() == -1
    assert not config.socket_path.exists()


def test_replaced_path_is_preserved(config):
    with consumer_listener(config):
        config.socket_path.unlink()
        config.socket_path.write_text('replacement-must-survive')
    assert config.socket_path.read_text() == 'replacement-must-survive'


def test_occupied_path_is_not_removed(config):
    config.socket_path.write_text('occupied')
    with pytest.raises(ConsumerProtocolBlocked):
        with consumer_listener(config):
            pytest.fail('occupied path accepted')
    assert config.socket_path.read_text() == 'occupied'


def test_idle_process_exits_without_database(config):
    started = time.monotonic()
    assert run_consumer_process(config) == {'accepted': 0, 'processed': 0}
    assert time.monotonic() - started < 2
    assert not config.socket_path.exists()


def test_one_real_same_uid_connection_counts_and_exits(config):
    errors = []
    def connect():
        try:
            deadline = time.monotonic()+2
            while not config.socket_path.exists() and time.monotonic()<deadline:
                time.sleep(0.005)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as peer:
                peer.connect(str(config.socket_path))
        except Exception as error:
            errors.append(type(error).__name__)
    thread = threading.Thread(target=connect)
    thread.start()
    try:
        assert run_consumer_process(config) == {'accepted': 1, 'processed': 0}
    finally:
        thread.join(timeout=3)
    assert not thread.is_alive() and errors == []
    assert not config.socket_path.exists()


def test_parent_path_replacement_retains_original_socket(config):
    old_parent = config.socket_path.parent
    moved = old_parent.with_name('moved')
    with consumer_listener(config):
        old_parent.rename(moved)
        old_parent.mkdir(mode=0o750)
        (old_parent / config.socket_path.name).write_text('new-parent-object')
    assert config.socket_path.read_text() == 'new-parent-object'
    assert (moved / config.socket_path.name).is_socket()


def test_exception_closes_and_removes_only_owned_socket(config):
    with pytest.raises(RuntimeError, match='stop'):
        with consumer_listener(config) as listener:
            raise RuntimeError('stop')
    assert listener.fileno() == -1
    assert not config.socket_path.exists()


@pytest.mark.parametrize('changes', [
    {'max_connections': 0}, {'max_connections': True}, {'max_connections': 65},
    {'accept_timeout': float('nan')}, {'accept_timeout': 0}, {'accept_timeout': 31},
    {'socket_path': 'relative.sock'}, {'attempt_directory': 'relative'},
])
def test_invalid_config_never_starts(config, changes):
    from dataclasses import replace
    with pytest.raises(ConsumerProtocolBlocked):
        replace(config, **changes)
    assert not config.socket_path.exists()
