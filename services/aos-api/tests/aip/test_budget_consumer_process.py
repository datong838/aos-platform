"""Finite real Unix lifecycle and isolated PG dispatch; no cross-UID acceptance."""
from dataclasses import replace
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time

import pytest

from aos_api.aip_budget_consumer_process import (
    BudgetConsumerProcessConfig, BudgetConsumerProcessBlocked, consumer_listener,
    run_budget_consumer, decode_consumer_request, dispatch_consumer_request,
    load_budget_consumer_config, preflight_budget_consumer, main,
)
from aos_api.aip_network_issuer_ipc import read_issuer_frame
from tests.aip.test_budget_consumer_service_pg import case
from tests.aip.test_budget_consumer_connection_pg import configured
from tests.aip.test_budget_cost_issuer_pg import issuer_factory
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner
from tests.aip.test_budget_cost_consumer_pg import counts


@pytest.fixture
def config(configured, https_signer, tmp_path):
    attempt = tmp_path / 'process-attempt'
    attempt.mkdir(mode=0o700)
    with tempfile.TemporaryDirectory(prefix='bu-', dir='/tmp') as folder:
        directory = Path(folder)
        directory.chmod(0o750)
        os.chown(directory, -1, os.getegid())
        yield BudgetConsumerProcessConfig(configured, SCOPE, directory/'b.sock', attempt,
            api_uid=os.geteuid()+1, consumer_uid=os.geteuid(), ipc_gid=os.getegid(), accept_timeout=.2)


def test_real_dispatch_reconstruction_and_readonly_inquiry(config, case):
    _, _, p, _, _, request, _ = case
    payload = request.model_dump(mode='json', by_alias=True)
    payload['bearerToken'] = request.bearer_token.get_secret_value()
    method, decoded = decode_consumer_request(json.dumps(dict(schemaVersion=1, method='execute_once', payload=payload)).encode())
    result = dispatch_consumer_request(config, method, decoded)
    assert result['status'] == 'observed' and result['activationEligible'] is False
    assert dispatch_consumer_request(replace(config), 'inquiry', decoded) == result
    assert dispatch_consumer_request(replace(config), method, decoded) == result
    assert counts(p) == dict(active=1, receipts=1)


@pytest.mark.parametrize('raw', [b'', b'[]', b'{' + b'x'*65536,
    b'{"schemaVersion":1,"schemaVersion":1,"method":"inquiry","payload":{}}',
    b'{"schemaVersion":true,"method":"inquiry","payload":{}}',
    b'{"schemaVersion":1,"method":"inquiry","payload":{"x":NaN}}'])
def test_invalid_wire_is_rejected(raw):
    with pytest.raises(BudgetConsumerProcessBlocked, match='WIRE'):
        decode_consumer_request(raw)


def test_readonly_preflight_idle_exit_and_own_socket(config):
    assert preflight_budget_consumer(config) == {'ready': True, 'businessAuthorized': False}
    assert not config.socket_path.exists()
    assert run_budget_consumer(config) == {'accepted': 0, 'processed': 0}
    assert not config.socket_path.exists() and not list(config.attempt_directory.iterdir())
    with consumer_listener(config):
        assert config.socket_path.is_socket()
        config.socket_path.unlink()
        config.socket_path.write_text('replacement')
    assert config.socket_path.read_text() == 'replacement'


def test_same_uid_kernel_peer_rejected_without_attempt(config):
    responses, errors = [], []
    def client():
        try:
            deadline = time.monotonic()+3
            while not config.socket_path.exists() and time.monotonic()<deadline:
                time.sleep(.005)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                conn.connect(str(config.socket_path))
                responses.append(json.loads(read_issuer_frame(conn)))
        except Exception as exc:
            errors.append(type(exc).__name__)
    thread = threading.Thread(target=client)
    thread.start()
    try:
        assert run_budget_consumer(config) == {'accepted': 1, 'processed': 0}
    finally:
        thread.join(4)
    assert not thread.is_alive() and not errors
    assert responses == [{'schemaVersion': 1, 'status': 'blocked', 'code': 'BUDGET_CONSUMER_REQUEST_BLOCKED'}]
    assert not config.socket_path.exists() and not list(config.attempt_directory.iterdir())


@pytest.mark.parametrize('changes', [dict(api_uid=os.geteuid()), dict(max_connections=True),
    dict(accept_timeout=float('nan')), dict(socket_path='relative'), dict(socket_path='/'+'x'*104)])
def test_invalid_config_cannot_open_listener(config, changes):
    with pytest.raises(BudgetConsumerProcessBlocked, match='CONFIG'):
        replace(config, **changes)
    assert not config.socket_path.exists()


@pytest.mark.parametrize('drift', ['oidc', 'credential', 'attempt', 'socket', 'occupied', 'database'])
def test_startup_rejects_drift_before_bind(config, monkeypatch, drift):
    if drift == 'oidc':
        monkeypatch.setenv('AOS_AUTH_ALLOW_DEV', '1')
    elif drift == 'credential':
        config.database.passfile.chmod(0o644)
    elif drift == 'attempt':
        config.attempt_directory.chmod(0o755)
    elif drift == 'socket':
        config.socket_path.parent.chmod(0o770)
    elif drift == 'occupied':
        config.socket_path.write_text('keep')
    else:
        config = replace(config, database=replace(config.database, database='not_this_database'))
    with pytest.raises(BudgetConsumerProcessBlocked):
        with consumer_listener(config):
            pytest.fail('unsafe startup accepted')
    if drift == 'occupied':
        assert config.socket_path.read_text() == 'keep'
    else:
        assert not config.socket_path.exists()


def config_file(config):
    p = config.database.passfile.with_name('process.json')
    p.touch(mode=0o600)
    p.write_text(json.dumps(dict(schemaVersion=1, tenant=dict(orgId=SCOPE.org_id, projectId=SCOPE.project_id),
        socketPath=str(config.socket_path), attemptDirectory=str(config.attempt_directory),
        apiUid=config.api_uid, consumerUid=config.consumer_uid, ipcGid=config.ipc_gid,
        maxConnections=config.max_connections, acceptTimeout=config.accept_timeout,
        database=dict(host=config.database.host, port=config.database.port, database=config.database.database,
                      passfile=str(config.database.passfile)))))
    return p


def test_private_config_check_cli_does_not_bind(config, capsys):
    p = config_file(config)
    assert load_budget_consumer_config(p) == config
    assert main(['--mode', 'check', '--config', str(p)]) == 0
    assert json.loads(capsys.readouterr().out) == {'mode': 'check', 'ready': True, 'businessAuthorized': False}
    assert not config.socket_path.exists() and not list(config.attempt_directory.iterdir())
    assert main(['--mode', 'serve', '--config', str(p)]) == 0
    assert json.loads(capsys.readouterr().out) == {'mode': 'serve', 'accepted': 0, 'processed': 0, 'businessAuthorized': False}
    p.chmod(0o644)
    assert main(['--mode', 'check', '--config', str(p)]) == 1
    assert capsys.readouterr().err.strip() == 'BUDGET_CONSUMER_ENTRY_BLOCKED'


def test_cli_invalid_arguments_do_not_echo_values(capsys):
    assert main(['--mode', 'secret-value', '--config', '/secret/path']) == 2
    output = capsys.readouterr()
    assert 'secret' not in output.out+output.err


def test_database_privilege_drift_blocks_before_socket(config):
    with isolated_owner() as conn:
        conn.execute('GRANT SELECT ON aip_budget_receipt TO aos_budget_consumer_call')
        conn.commit()
        try:
            with pytest.raises(BudgetConsumerProcessBlocked, match='STARTUP'):
                with consumer_listener(config):
                    pytest.fail('privilege drift admitted')
            assert not config.socket_path.exists() and not list(config.attempt_directory.iterdir())
        finally:
            conn.execute('REVOKE SELECT ON aip_budget_receipt FROM aos_budget_consumer_call')
            conn.commit()


@pytest.mark.parametrize('change', ['extra', 'tenant', 'duplicate', 'symlink'])
def test_private_config_rejects_untrusted_shape(config, change):
    p = config_file(config)
    data = json.loads(p.read_text())
    if change == 'extra':
        data['database']['user'] = 'aos_app'
    elif change == 'tenant':
        data['tenant']['orgId'] = 'dev-org'
    p.write_text(json.dumps(data))
    if change == 'duplicate':
        p.write_text(p.read_text()[:-1]+',"schemaVersion":1}')
    elif change == 'symlink':
        link = p.with_name('link.json')
        link.symlink_to(p)
        p = link
    with pytest.raises(BudgetConsumerProcessBlocked, match='PRIVATE_CONFIG'):
        load_budget_consumer_config(p)
    assert not config.socket_path.exists()
