"""Recovery must not overwrite the prior installation command namespace."""
import json
from pathlib import Path
import sys
from uuid import uuid4
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'scripts'))
import a0v_ecommerce_1_7_configure as executor
import a0v_ecommerce_1_7_disable as disable


def test_setup_uses_file_reference_without_connecting(tmp_path, monkeypatch):
    import os
    from types import SimpleNamespace
    from aos_api.asset_registry.installation_store import PostgresInstallationStore
    from aos_api.extension_runtime import runtime_connections
    host = executor.load('a0v_ecommerce_runtime_host')
    path = tmp_path / 'identities.json'
    path.write_text(json.dumps({plane: {'role': role, 'dsn': plane, 'password': 'fixture-only'}
                               for plane, role in host.EXPECTED_ROLES.items()}))
    path.chmod(0o600)
    host.DEFAULT_CREDENTIALS = path
    trust = tmp_path / 'signing'
    trust.mkdir()
    (trust / 'trust-roots.json').write_text('{}')
    monkeypatch.setattr(os, 'environ', dict(os.environ))
    monkeypatch.setattr(executor, 'BUNDLE_ROOT', tmp_path)
    monkeypatch.setattr(executor, 'TRUST_STATE', tmp_path)
    store = PostgresInstallationStore()
    activation = SimpleNamespace(_services=lambda *a: (store, SimpleNamespace(_reader=object(), _revalidator=object())))
    monkeypatch.setattr(executor, 'load', lambda name: host if name == 'a0v_ecommerce_runtime_host' else activation)
    monkeypatch.setattr(runtime_connections.psycopg, 'connect', lambda *a, **kw: pytest.fail('setup connected'))
    connect, selected, authorize, service = executor.setup()
    assert connect is runtime_connections.runtime_worker_connection
    assert selected is activation and callable(authorize) and service._store is store
    assert os.environ['AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE'] == str(path)
    assert all(name not in os.environ for name in ('AOS_DATABASE_URL', 'AOS_EXTENSION_RUNTIME_DATABASE_URL', 'AOS_EXTENSION_DIRECTORY_DATABASE_URL'))


def test_original_target_is_unchanged():
    installation,state,key,command=executor.configuration_target()
    assert installation==executor.INSTALLATION and state==executor.STATE
    assert key=='a0v-ecommerce-1.7' and command=='ecommerce-1.7'


def test_disable_recovery_keeps_original_command_namespace(tmp_path,monkeypatch):
    monkeypatch.setattr(executor,'RECOVERY',tmp_path)
    state=tmp_path/'state';state.mkdir()
    identity=str(uuid4())
    (state/'ecommerce-1.7-recovered-first-install.json').write_text(json.dumps({'installationId':identity}))
    old,old_path,old_key=disable.disable_target()
    fresh,fresh_path,fresh_key=disable.disable_target(True)
    assert old==executor.INSTALLATION and fresh==identity
    assert old_path.name=='ecommerce-1.7-disable-command.json'
    assert fresh_path.name=='ecommerce-1.7-recovered-disable-command.json'
    assert old_key=='a0v-ecommerce-1.7-disable-after-config-host-loss-v1'
    assert fresh_key!=old_key


@pytest.mark.parametrize('case',['fresh','old','invalid'])
def test_recovery_requires_distinct_valid_installation_and_state(tmp_path,monkeypatch,case):
    monkeypatch.setattr(executor,'RECOVERY',tmp_path)
    state=tmp_path/'state';state.mkdir()
    identity=str(uuid4()) if case=='fresh' else executor.INSTALLATION if case=='old' else 'invalid'
    (state/'ecommerce-1.7-recovered-first-install.json').write_text(json.dumps({'installationId':identity}))
    if case!='fresh':
        with pytest.raises(ValueError):executor.configuration_target(True)
    else:
        installation,path,key,command=executor.configuration_target(True)
        assert installation==identity and path.name=='ecommerce-1.7-recovered-configuration.json'
        assert key=='a0v-ecommerce-1.7-recovered' and command=='ecommerce-1.7-recovered'


@pytest.mark.parametrize('case',['fresh','configured-predecessor','sleep-predecessor','invalid','both'])
def test_sleep_recovery_uses_a_new_installation_and_command_namespace(tmp_path,monkeypatch,case):
    monkeypatch.setattr(executor,'RECOVERY',tmp_path)
    state=tmp_path/'state';state.mkdir()
    identity={'configured-predecessor':executor.INSTALLATION,
              'sleep-predecessor':'af1992e8-89c2-406a-816d-01e61d7bf982',
              'invalid':'bad'}.get(case,str(uuid4()))
    (state/'ecommerce-1.7-sleep-recovered-first-install.json').write_text(json.dumps({'installationId':identity}))
    if case!='fresh':
        with pytest.raises(ValueError):executor.configuration_target(case=='both',sleep_recovery=True)
    else:
        installation,path,key,command=executor.configuration_target(sleep_recovery=True)
        assert installation==identity
        assert path.name=='ecommerce-1.7-sleep-recovered-configuration.json'
        assert key=='a0v-ecommerce-1.7-sleep-recovered'
        assert command=='ecommerce-1.7-sleep-recovered'
