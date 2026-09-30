"""Private startup configuration and lifecycle boundaries; no instance deployment."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
from types import SimpleNamespace
import pytest

from aos_api.aip_network_issuer_startup import configured_api_issuer, IssuerStartupBlocked
from tests.aip.test_aip_network_issuer_auth import _external_config


@pytest.fixture
def private_config(tmp_path, monkeypatch):
    _external_config(monkeypatch)
    directory = tmp_path/'private'
    directory.mkdir(mode=0o700)
    attempts = directory/'attempts'
    attempts.mkdir(mode=0o700)
    data = dict(schemaVersion=1, socketPath=str(tmp_path/'issuer.sock'), apiUid=os.geteuid(),
                issuerUid=os.geteuid()+1, ipcGid=os.getegid(), apiAttemptDirectory=str(attempts))
    path = directory/'config.json'
    path.write_text(json.dumps(data)); path.chmod(0o600)
    monkeypatch.setenv('AOS_NETWORK_ISSUER_API_CONFIG', str(path))
    return path, data


def test_default_disabled(monkeypatch):
    monkeypatch.delenv('AOS_NETWORK_ISSUER_API_CONFIG', raising=False)
    assert configured_api_issuer() is None


def test_private_config_no_business_activity(private_config):
    config = configured_api_issuer()
    assert not config.endpoint.socket_path.exists()
    assert not list(config.attempt_directory.iterdir())


@pytest.mark.parametrize('change', [{'schemaVersion': True}, {'password': 'private'},
    {'apiUid': True}, {'issuerUid': os.geteuid()}, {'apiAttemptDirectory': 'relative'}])
def test_invalid_config(private_config, change):
    path, data = private_config
    path.write_text(json.dumps({**data, **change}))
    with pytest.raises(IssuerStartupBlocked) as error:
        configured_api_issuer()
    assert str(error.value) == 'ISSUER_API_STARTUP_BLOCKED'


@pytest.mark.parametrize('failure', [None, 'config', 'body'])
def test_lifespan_prebody_gate_and_cleanup(private_config, monkeypatch, failure):
    from aos_api import main
    monkeypatch.delenv('AOS_NETWORK_CONSUMER_API_CONFIG', raising=False)
    path, _ = private_config
    if failure == 'config': path.chmod(0o644)
    app = SimpleNamespace(state=SimpleNamespace())
    entered = []
    @asynccontextmanager
    async def body(application):
        assert application.state.network_issuer_config is not None
        entered.append(True)
        if failure == 'body': raise RuntimeError('body failed')
        yield
    async def cleanup(application):
        assert application.state.network_issuer_config is None
    monkeypatch.setattr(main, '_lifespan_body', body)
    monkeypatch.setattr(main, '_shutdown_application_runtime', cleanup)
    async def probe():
        async with main.lifespan(app): pass
    if failure:
        with pytest.raises((IssuerStartupBlocked, RuntimeError)): asyncio.run(probe())
    else: asyncio.run(probe())
    assert entered == ([] if failure == 'config' else [True])
