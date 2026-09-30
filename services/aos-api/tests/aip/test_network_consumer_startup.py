"""Private file and lifecycle wiring; not formal service deployment acceptance."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from types import SimpleNamespace
import pytest

from aos_api.aip_network_consumer_startup import configured_api_consumer, ConsumerStartupBlocked
from tests.aip.test_aip_network_issuer_auth import _external_config


@pytest.fixture
def private_config(tmp_path, monkeypatch):
    _external_config(monkeypatch)
    directory = tmp_path/'api-private'
    directory.mkdir(mode=0o700)
    attempts = directory/'attempts'
    attempts.mkdir(mode=0o700)
    data = {'schemaVersion': 1, 'socketPath': str(tmp_path/'consumer.sock'),
            'apiUid': os.geteuid(), 'consumerUid': os.geteuid()+1,
            'ipcGid': os.getegid(), 'apiAttemptDirectory': str(attempts)}
    path = directory/'config.json'
    path.write_text(json.dumps(data))
    path.chmod(0o600)
    monkeypatch.setenv('AOS_NETWORK_CONSUMER_API_CONFIG', str(path))
    return path, data


def test_unconfigured_keeps_default_disabled(monkeypatch):
    monkeypatch.delenv('AOS_NETWORK_CONSUMER_API_CONFIG', raising=False)
    assert configured_api_consumer() is None


def test_private_config_only_assembles_no_socket_or_attempt(private_config):
    path, data = private_config
    config = configured_api_consumer()
    assert str(config.endpoint.socket_path) == data['socketPath']
    assert not config.endpoint.socket_path.exists()
    assert not list(config.attempt_directory.iterdir())


@pytest.mark.parametrize('changes', [{'schemaVersion': True}, {'password': 'secret-sentinel'},
    {'apiUid': True}, {'consumerUid': os.geteuid()}, {'orgId': 'org-org'},
    {'apiAttemptDirectory': 'relative'}])
def test_invalid_private_config_fails_closed(private_config, changes):
    path, data = private_config
    path.write_text(json.dumps({**data, **changes}))
    with pytest.raises(ConsumerStartupBlocked) as error:
        configured_api_consumer()
    assert str(error.value) == 'CONSUMER_API_STARTUP_BLOCKED'


def test_permissions_and_auth_are_not_optional(private_config, monkeypatch):
    path, _ = private_config
    path.chmod(0o644)
    with pytest.raises(ConsumerStartupBlocked):
        configured_api_consumer()
    path.chmod(0o600)
    monkeypatch.setenv('AOS_AUTH_ALLOW_DEV', '1')
    with pytest.raises(ConsumerStartupBlocked):
        configured_api_consumer()


@pytest.mark.parametrize('failure', [None, 'config', 'body'])
def test_lifecycle_loads_before_body_and_always_clears(private_config, monkeypatch, failure):
    from aos_api import main
    path, _ = private_config
    if failure == 'config':
        path.chmod(0o644)
    app = SimpleNamespace(state=SimpleNamespace())
    entered = []
    @asynccontextmanager
    async def body(application):
        assert application.state.network_consumer_config is not None
        entered.append(True)
        if failure == 'body':
            raise RuntimeError('body failure')
        yield
    async def cleanup(application):
        assert application.state.network_consumer_config is None
    monkeypatch.setattr(main, '_lifespan_body', body)
    monkeypatch.setattr(main, '_shutdown_application_runtime', cleanup)
    async def probe():
        async with main.lifespan(app):
            assert app.state.network_consumer_config is not None
    if failure:
        with pytest.raises((ConsumerStartupBlocked, RuntimeError)):
            asyncio.run(probe())
    else:
        asyncio.run(probe())
    assert entered == ([] if failure == 'config' else [True])
    assert app.state.network_consumer_config is None
