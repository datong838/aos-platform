"""Real isolated SQL/file composition; injected identity is NOT formal OIDC proof."""
from contextlib import contextmanager
import pytest
from aos_api.auth import Principal
from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand
from aos_api.aip_network_consumer_attempt import reserve_consumer_attempt
from aos_api.aip_network_consumer_service import consume_network_once, inquire_network
from tests.aip.test_network_consumer_actor_pg import approved_args
from tests.aip.test_network_consumer_connection_pg import private_passfile, live_test_config
from tests.aip.test_network_atomic_consumer_pg import counts
from tests.aip.test_network_consumer_boundary_pg import isolated_owner, SCOPE


def fixture_request(monkeypatch):
    args, checker = approved_args()
    command = NetworkConsumerCommand.model_validate({
        'schemaVersion': 1, 'bearerToken': 'header.payload.signature',
        'orgId': args[0], 'projectId': args[1], 'proposalId': args[2],
        'approvalEventId': args[3], 'proposalHash': args[5],
        'targetContentHash': args[6], 'bindingHash': args[7],
    })
    actor = Principal(subject=args[4], org_id=args[0], project_id=args[1], token_kind='oidc')
    from aos_api import aip_network_consumer_service as module
    monkeypatch.setattr(module, 'authenticate_consumer_request', lambda request: actor)
    return command, actor


def test_one_commit_then_read_only_recovery(private_passfile, tmp_path, monkeypatch):
    command, _ = fixture_request(monkeypatch)
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    with live_test_config(private_passfile) as config:
        assert inquire_network(command.inquiry(), config) == {'status': 'unresolved'}
        result = consume_network_once(command, config, attempts)
        assert result['status'] == 'observed'
        assert consume_network_once(command, config, attempts) == result
        assert inquire_network(command.inquiry(), config) == result
    assert counts(command.proposal_id) == (1, 1, 1)


def test_prior_attempt_without_receipt_does_not_authorize_resend(private_passfile, tmp_path, monkeypatch):
    command, actor = fixture_request(monkeypatch)
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    reserve_consumer_attempt(attempts, command, actor)
    with live_test_config(private_passfile) as config:
        assert consume_network_once(command, config, attempts) == {'status': 'unresolved'}
        next(attempts.iterdir()).write_text('')
        assert consume_network_once(command, config, attempts) == {'status': 'unresolved'}
    assert counts(command.proposal_id) == (0, 0, 0)


def test_disconnect_after_actual_commit_reconciles_without_second_write(private_passfile, tmp_path, monkeypatch):
    command, _ = fixture_request(monkeypatch)
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    from aos_api import aip_network_consumer_service as module
    original = module.connect_consumer
    writes = []
    @contextmanager
    def disconnected(config, scope, *, read_only=False):
        with original(config, scope, read_only=read_only) as conn:
            yield conn
        if not read_only:
            writes.append(1)
            raise ConnectionError('injected lost commit response')
    monkeypatch.setattr(module, 'connect_consumer', disconnected)
    with live_test_config(private_passfile) as config:
        result = consume_network_once(command, config, attempts)
        assert result['status'] == 'observed'
        assert consume_network_once(command, config, attempts) == result
    assert len(writes) == 1
    assert counts(command.proposal_id) == (1, 1, 1)


def test_wrong_actor_cannot_reserve_attempt_or_write(private_passfile, tmp_path, monkeypatch):
    command, actor = fixture_request(monkeypatch)
    from aos_api import aip_network_consumer_service as module
    from aos_api.aip_network_consumer_connection import ConsumerDatabaseBlocked
    monkeypatch.setattr(module, 'authenticate_consumer_request', lambda request:
                        Principal(subject='other', org_id=actor.org_id,
                                  project_id=actor.project_id, token_kind='oidc'))
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    with live_test_config(private_passfile) as config:
        with pytest.raises(ConsumerDatabaseBlocked):
            consume_network_once(command, config, attempts)
    assert list(attempts.iterdir()) == []
    assert counts(command.proposal_id) == (0, 0, 0)


def test_failure_before_commit_rolls_back_and_next_request_never_retries(private_passfile, tmp_path, monkeypatch):
    command, _ = fixture_request(monkeypatch)
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    from aos_api import aip_network_consumer_service as module
    original = module.connect_consumer
    writes = []
    @contextmanager
    def broken(config, scope, *, read_only=False):
        with original(config, scope, read_only=read_only) as conn:
            yield conn
            if not read_only:
                writes.append(1)
                raise ConnectionError('injected failure before commit')
    monkeypatch.setattr(module, 'connect_consumer', broken)
    with live_test_config(private_passfile) as config:
        assert consume_network_once(command, config, attempts) == {'status': 'unresolved'}
        assert consume_network_once(command, config, attempts) == {'status': 'unresolved'}
    assert len(writes) == 1
    assert counts(command.proposal_id) == (0, 0, 0)


def test_revocation_after_read_gate_is_rechecked_before_write(private_passfile, tmp_path, monkeypatch):
    command, actor = fixture_request(monkeypatch)
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    from aos_api import aip_network_consumer_service as module
    original = module.reserve_consumer_attempt
    def revoked(*args):
        receipt = original(*args)
        with isolated_owner() as conn:
            conn.execute('DELETE FROM meta_membership WHERE org_id=%s AND project_id=%s AND subject=%s',
                         (*SCOPE.key, actor.subject))
        return receipt
    monkeypatch.setattr(module, 'reserve_consumer_attempt', revoked)
    with live_test_config(private_passfile) as config:
        assert consume_network_once(command, config, attempts) == {'status': 'unresolved'}
    assert len(list(attempts.iterdir())) == 1
    assert counts(command.proposal_id) == (0, 0, 0)


def test_parallel_consumers_commit_one_receipt(private_passfile, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    command, _ = fixture_request(monkeypatch)
    attempts = tmp_path / 'attempts'
    attempts.mkdir(mode=0o700)
    with live_test_config(private_passfile) as config:
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: consume_network_once(command, config, attempts), range(4)))
        assert all(r['status'] in {'observed', 'unresolved'} for r in results)
        assert inquire_network(command.inquiry(), config)['status'] == 'observed'
    assert len(list(attempts.iterdir())) == 1
    assert counts(command.proposal_id) == (1, 1, 1)
