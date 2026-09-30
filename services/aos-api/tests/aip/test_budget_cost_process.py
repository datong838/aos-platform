"""Real PG/JWT service and Unix negative checks; no cross-UID positive claim."""
from dataclasses import replace
import json
import os
import socket
import threading
import time
import tempfile
from pathlib import Path

import pytest

from aos_api.aip_budget_cost_process import (
    BudgetCostProcessConfig, budget_listener, run_budget_process,
    decode_budget_request, dispatch_budget_request,
)
from aos_api.aip_budget_cost_issuer import BudgetCostIssuer, BudgetCostIssuerBlocked
from aos_api.aip_budget_activation_store import BudgetActivationDenied
from aos_api.aip_network_issuer_ipc import read_issuer_frame
from tests.aip.test_budget_cost_connection_pg import configured
from tests.aip.test_budget_cost_issuer_pg import issuer_factory, prepared, command
from tests.aip.test_network_consumer_connection_pg import private_passfile
from tests.aip.test_network_consumer_signed_https_pg import https_signer
from tests.aip.test_network_consumer_boundary_pg import SCOPE, isolated_owner


@pytest.fixture
def config(configured, https_signer, tmp_path):
    database, _ = configured
    attempt = tmp_path / 'attempts'
    attempt.mkdir(mode=0o700)
    # Darwin sockaddr_un is shorter than pytest's descriptive temporary path.
    with tempfile.TemporaryDirectory(prefix='bc-', dir='/tmp') as folder:
        directory = Path(folder)
        directory.chmod(0o750)
        os.chown(directory, -1, os.getegid())
        yield BudgetCostProcessConfig(database, SCOPE, directory/'budget.sock', attempt,
            api_uid=os.geteuid()+1, issuer_uid=os.geteuid(), ipc_gid=os.getegid(),
            accept_timeout=0.2)


def frame(cmd):
    payload = cmd.model_dump(mode='json', by_alias=True)
    payload['bearerToken'] = cmd.bearer_token.get_secret_value()
    return json.dumps(dict(schemaVersion=1, method='execute_once', payload=payload)).encode()


def test_real_service_persists_once_and_reads_back_original(config, https_signer, monkeypatch):
    sign, _ = https_signer
    maker, checker, _, _, saved = prepared()
    cmd = command(sign, checker, saved)
    method, decoded = decode_budget_request(frame(cmd))
    result = dispatch_budget_request(config, method, decoded)
    assert result['status'] == 'observed' and result['activationEligible'] is False
    # A repeated transport request must not invoke the writer even though the DB
    # core itself has idempotency. The actual first operation above is real PG.
    original = BudgetCostIssuer.execute
    monkeypatch.setattr(BudgetCostIssuer, 'execute', lambda *a: pytest.fail('writer replayed'))
    assert dispatch_budget_request(config, method, decoded) == result
    changed = cmd.model_copy(update={'decision': 'rejected'})
    assert dispatch_budget_request(config, method, changed) == {'status': 'conflict'}
    assert dispatch_budget_request(config, 'inquiry', decoded) == result
    monkeypatch.setattr(BudgetCostIssuer, 'execute', original)
    revoke = command(sign, maker, saved, operation='revoke', decision=None, reason='withdraw')
    assert dispatch_budget_request(config, method, revoke)['status'] == 'observed'
    markers = list(config.attempt_directory.iterdir())
    assert len(markers) == 2
    assert all(cmd.bearer_token.get_secret_value() not in p.read_text() and 'bearerToken' not in p.read_text()
               for p in markers)


@pytest.mark.parametrize('committed', [False, True])
def test_unknown_never_reexecutes_after_process_reconstruction(config, https_signer, monkeypatch, committed):
    sign, _ = https_signer
    _, checker, _, _, saved = prepared()
    cmd = command(sign, checker, saved)
    original = BudgetCostIssuer.execute
    calls = []
    def interrupted(self, request):
        calls.append(request.request_hash)
        if committed:
            original(self, request)
        raise ConnectionError('isolated post-dispatch failure')
    monkeypatch.setattr(BudgetCostIssuer, 'execute', interrupted)
    result = dispatch_budget_request(config, 'execute_once', cmd)
    assert result['status'] == ('observed' if committed else 'unresolved')
    monkeypatch.setattr(BudgetCostIssuer, 'execute', original)
    assert dispatch_budget_request(replace(config), 'execute_once', cmd) == result
    with isolated_owner() as conn:
        count = conn.execute('SELECT count(*) AS n FROM aip_budget_cost_decision WHERE proposal_id=%s',
                             (saved['proposalId'],)).fetchone()['n']
    assert count == int(committed) and len(calls) == 1


def test_revoked_membership_cannot_reserve_attempt(config, https_signer):
    sign, _ = https_signer
    _, checker, _, _, saved = prepared()
    cmd = command(sign, checker, saved)
    with isolated_owner() as conn:
        conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                     (*SCOPE.key, checker.subject))
        conn.commit()
    with pytest.raises(BudgetActivationDenied, match='MEMBERSHIP_REQUIRED'):
        dispatch_budget_request(config, 'execute_once', cmd)
    assert not list(config.attempt_directory.iterdir())


@pytest.mark.parametrize('raw', [b'', b'[]', b'{' + b'x'*65536,
    b'{"schemaVersion":1,"schemaVersion":1,"method":"inquiry","payload":{}}',
    b'{"schemaVersion":true,"method":"inquiry","payload":{}}',
    b'{"schemaVersion":1,"method":"inquiry","payload":{"x":NaN}}'])
def test_invalid_frames_blocked(raw):
    with pytest.raises(BudgetCostIssuerBlocked, match='WIRE'):
        decode_budget_request(raw)


def test_listener_owns_only_its_socket(config):
    with budget_listener(config):
        assert config.socket_path.is_socket()
    assert not config.socket_path.exists()
    with budget_listener(config):
        config.socket_path.unlink()
        config.socket_path.write_text('replacement')
    assert config.socket_path.read_text() == 'replacement'


def test_kernel_rejects_same_uid_client(config):
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
        assert run_budget_process(config) == {'accepted': 1, 'processed': 0}
    finally:
        thread.join(4)
    assert not thread.is_alive() and not errors
    assert responses == [{'schemaVersion': 1, 'status': 'blocked', 'code': 'BUDGET_COST_REQUEST_BLOCKED'}]
    assert not config.socket_path.exists() and not list(config.attempt_directory.iterdir())


@pytest.mark.parametrize('changes', [dict(api_uid=os.geteuid()), dict(max_connections=True),
    dict(accept_timeout=float('nan')), dict(socket_path='relative'), dict(socket_path='/'+'x'*104)])
def test_invalid_process_config_does_not_open_listener(config, changes):
    with pytest.raises(BudgetCostIssuerBlocked, match='CONFIG'):
        replace(config, **changes)
    assert not config.socket_path.exists()


def test_wrong_scope_rejected_before_attempt(config, https_signer):
    sign, _ = https_signer
    _, checker, _, _, saved = prepared()
    cmd = command(sign, checker, saved, orgId='other-org')
    with pytest.raises(BudgetCostIssuerBlocked):
        dispatch_budget_request(config, 'execute_once', cmd)
    assert not list(config.attempt_directory.iterdir())
