import pytest
from aos_api.source_connection_config import normalize_source_connection_config


def config():
    return dict(sshHost='example.invalid',sshUser='reader',sshPassword='synthetic-ssh',
                dbHost='127.0.0.1',database='shop',username='reader',password='synthetic-db')


def test_valid_config_uses_server_connector_and_defaults():
    value=config()
    result=normalize_source_connection_config('jdbc-mysql-ssh',value)
    assert result == dict(value,sshPort=22,dbPort=3306,connector_type='jdbc-mysql-ssh')
    assert 'connector_type' not in value


@pytest.mark.parametrize('update', [
    {'sshPort':True},{'dbPort':0},{'sshPort':'22'},{'dbPort':65536},
    {'sshKeyRef':'key'},{'secretRef':'secret'},{'password':''},
    {'sshHost':' '},{'username':' reader'},{'orgId':'other'},
    {'connector_type':'mysql'},{'password':42},
])
def test_invalid_config_is_rejected_without_echo(update):
    value=config();value.update(update)
    with pytest.raises(ValueError) as exc:
        normalize_source_connection_config('jdbc-mysql-ssh',value)
    assert str(exc.value)=='SOURCE_CONNECTION_CONFIG_INVALID'


def test_references_replace_passwords():
    value=config();value.pop('password');value.pop('sshPassword')
    value.update(secretRef='vault://secrets/db',sshKeyRef='vault://secrets/ssh')
    assert normalize_source_connection_config('jdbc-mysql-ssh',value)['secretRef']==value['secretRef']


def test_other_connector_is_not_silently_treated_as_mysql():
    with pytest.raises(ValueError,match='SOURCE_CONNECTION_CONFIG_INVALID'):
        normalize_source_connection_config('file',config())
