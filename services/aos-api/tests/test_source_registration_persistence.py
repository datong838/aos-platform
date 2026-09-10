from types import SimpleNamespace
import pytest
from aos_api.routers import wave_ext as api
from aos_api import connector_registry, data_os_store


@pytest.mark.parametrize('existing', [False, True])
def test_failed_source_save_never_reports_success_or_changes_cache(monkeypatch, existing):
    old = {'id':'source-test','type':'file','orgId':'org-org','projectId':'dev-project'}
    cache = {'source-test':old.copy()} if existing else {}
    monkeypatch.setattr(api, '_connectors', cache)
    monkeypatch.setattr(api, '_hydrate_data_os_scope', lambda _: None)
    monkeypatch.setattr(connector_registry, 'assert_type_installed', lambda _: 'file')
    def fail(*args):
        raise RuntimeError('sensitive-connection-error')
    monkeypatch.setattr(data_os_store, 'persist_source', fail)
    with pytest.raises(api.ApiError) as exc:
        api.create_source(api.ConnectorIn(id='source-test'), SimpleNamespace(org_id='org-org',project_id='dev-project'))
    assert 'sensitive' not in str(exc.value)
    assert cache == ({'source-test':old} if existing else {})


def test_source_cache_updates_only_after_persistence(monkeypatch):
    cache = {}
    monkeypatch.setattr(api, '_connectors', cache)
    monkeypatch.setattr(api, '_hydrate_data_os_scope', lambda _: None)
    monkeypatch.setattr(connector_registry, 'assert_type_installed', lambda _: 'file')
    saved = []
    def persist(scope, item):
        assert cache == {}
        assert scope.key == ('org-org','dev-project')
        saved.append(item.copy())
    monkeypatch.setattr(data_os_store, 'persist_source', persist)
    api.create_source(api.ConnectorIn(id='source-test'), SimpleNamespace(org_id='org-org',project_id='dev-project'))
    assert cache['source-test'] == saved[0]


def test_connection_config_is_persisted_but_not_returned(monkeypatch):
    monkeypatch.setattr(api, '_connectors', {})
    monkeypatch.setattr(api, '_hydrate_data_os_scope', lambda _: None)
    monkeypatch.setattr(connector_registry, 'assert_type_installed', lambda _: 'jdbc-mysql-ssh')
    saved=[]
    monkeypatch.setattr(data_os_store,'persist_source',lambda scope,item:saved.append(item.copy()))
    config=dict(sshHost='example.invalid',sshUser='reader',sshPassword='synthetic-ssh',
                dbHost='127.0.0.1',database='shop',username='reader',password='synthetic-db')
    body=api.ConnectorIn(id='source-test',type='jdbc-mysql-ssh',config=config)
    assert 'synthetic' not in repr(body)
    result=api.create_source(body,SimpleNamespace(org_id='org-org',project_id='dev-project'))
    assert saved[0]['password']=='synthetic-db'
    assert saved[0]['connector_type']=='jdbc-mysql-ssh'
    assert 'config' not in saved[0]
    assert not set(config).intersection(result)
    assert result['id']=='source-test'


def test_metadata_reregistration_preserves_connection(monkeypatch):
    original=dict(id='source-test',type='jdbc-mysql-ssh',connector_type='jdbc-mysql-ssh',
                  orgId='org-org',projectId='dev-project',password='synthetic-old',database='shop')
    monkeypatch.setattr(api,'_connectors',{'source-test':original.copy()})
    monkeypatch.setattr(api,'_hydrate_data_os_scope',lambda _:None)
    monkeypatch.setattr(connector_registry,'assert_type_installed',lambda _:'jdbc-mysql-ssh')
    saved=[]
    monkeypatch.setattr(data_os_store,'persist_source',lambda scope,item:saved.append(item.copy()))
    api.create_source(api.ConnectorIn(id='source-test',type='jdbc-mysql-ssh'),SimpleNamespace(org_id='org-org',project_id='dev-project'))
    assert saved[0]['password']=='synthetic-old'
    assert saved[0]['database']=='shop'


@pytest.mark.parametrize('change_type',[False,True])
def test_explicit_config_replaces_credentials_and_type_change_is_rejected(monkeypatch,change_type):
    old=dict(id='source-test',type='jdbc-mysql-ssh',orgId='org-org',projectId='dev-project',
             sshPassword='synthetic-old-ssh',password='synthetic-old-db')
    monkeypatch.setattr(api,'_connectors',{'source-test':old.copy()})
    monkeypatch.setattr(api,'_hydrate_data_os_scope',lambda _:None)
    monkeypatch.setattr(connector_registry,'assert_type_installed',lambda _: 'file' if change_type else 'jdbc-mysql-ssh')
    saved=[]
    monkeypatch.setattr(data_os_store,'persist_source',lambda scope,item:saved.append(item.copy()))
    config=dict(sshHost='example.invalid',sshUser='reader',sshKeyRef='vault://secrets/ssh',
                dbHost='127.0.0.1',database='shop',username='reader',secretRef='vault://secrets/db')
    body=api.ConnectorIn(id='source-test',type='file' if change_type else 'jdbc-mysql-ssh',config=None if change_type else config)
    principal=SimpleNamespace(org_id='org-org',project_id='dev-project')
    if change_type:
        with pytest.raises(api.ApiError): api.create_source(body,principal)
        assert not saved
        assert api._connectors['source-test']==old
    else:
        api.create_source(body,principal)
        assert 'password' not in saved[0] and 'sshPassword' not in saved[0]
        assert saved[0]['secretRef']==config['secretRef']
