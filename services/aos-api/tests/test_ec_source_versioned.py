from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from aos_api import ec_source_adapter as source
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('state', ['ok', 'missing', 'disabled', 'agent', 'transport'])
def test_versioned_read_uses_exact_input_and_private_connection(monkeypatch, state):
    version = SimpleNamespace(source_id='source',source_type='jdbc-mysql-ssh',status='disabled' if state=='disabled' else 'registered',ref='exact-version')
    props = dict(runtimeMode='agent' if state=='agent' else 'direct',sshHost='host',sshUser='user',sshPassword='secret',dbHost='db',database='shop',username='reader',password='secret')
    store = SimpleNamespace(read_connection_input=Mock(return_value=None if state=='missing' else SimpleNamespace(revision=version,props=props)))
    monkeypatch.setattr(source, 'SourceConfigurationRevisionStore', lambda *a:store)
    fetch = Mock(return_value=[{'goods_id':1}])
    if state=='transport': fetch.side_effect=OSError('password=private')
    monkeypatch.setattr(source, '_fetch_from_jdbc_ssh', fetch)
    kwargs=dict(pipeline=SimpleNamespace(id='p02'),nodes=[SimpleNamespace(id='n',node_type='source',config={'source_id':'source'})],node_id=None,scope=TenantScope('org-org','dev-project'),transaction=object())
    if state=='ok':
        rows, ref = source.fetch_source_rows_versioned(**kwargs)
        assert rows==[{'goods_id':1}] and ref=='exact-version'
        assert fetch.call_args.kwargs['private_connection'] is True
    else:
        with pytest.raises(ValueError, match='^SOURCE_VERSIONED_READ_FAILED$'):
            source.fetch_source_rows_versioned(**kwargs)
        if state!='transport': fetch.assert_not_called()


def test_private_jdbc_read_does_not_reuse_connection_cache(monkeypatch):
    from unittest.mock import MagicMock
    runtime = MagicMock()
    runtime.__enter__.return_value.read_rows.return_value = []
    constructor = Mock(return_value=runtime)
    monkeypatch.setattr(source, 'JdbcConnectorRuntime', constructor)
    assert source._fetch_from_jdbc_ssh(pipeline=SimpleNamespace(id='p02'),node_id='n',
        node_config={'table':'ns_goods'},props={},private_connection=True) == []
    constructor.assert_called_once_with({},reuse_cache=False)
    runtime.__exit__.assert_called_once()
