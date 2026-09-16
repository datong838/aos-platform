from contextlib import contextmanager
from types import SimpleNamespace
import pytest
from pymysql.err import OperationalError
from aos_api import source_connection_probe as probe
from aos_api.tenant_scope import TenantScope


@pytest.mark.parametrize('failure',['none','missing','version','state','type','transport','ssh','mysql','agent','worker','missing_mode'])
def test_saved_source_probe_scope_version_and_private_connection(monkeypatch,failure):
    config=dict(sshHost='example.invalid',sshUser='reader',sshPassword='synthetic-ssh',
                dbHost='127.0.0.1',database='shop',username='reader',password='synthetic-db',runtimeMode='direct')
    row=dict(type='jdbc-mysql-ssh',status='registered',configuration_revision='version',props=config)
    if failure in {'agent','worker'}:config['runtimeMode']=failure
    if failure=='missing_mode':config.pop('runtimeMode')
    if failure=='version':row['configuration_revision']='other'
    if failure=='state':row['status']='disabled'
    if failure=='type':row['type']='file'
    active=[];calls=[]
    class Connection:
        def execute(self,query,params):
            assert 'FOR SHARE' in query
            assert params==('org-org','dev-project','source')
            return SimpleNamespace(fetchone=lambda:None if failure=='missing' else row)
    @contextmanager
    def connect(scope):
        assert scope.key==('org-org','dev-project')
        active.append('db')
        try:yield Connection()
        finally:active.pop()
    class Runtime:
        def __init__(self,config,**options):
            assert options=={'reuse_cache':False}
            assert active==['db']
            calls.append('constructed')
        def __enter__(self):return self
        def __exit__(self,*args):calls.append('closed')
        def list_configured_tables(self):
            if failure=='transport':raise RuntimeError('sensitive-transport-error')
            if failure=='ssh':raise RuntimeError(
                'SSH tunnel failed to become ready; diagnostic=NO_STDERR')
            if failure=='mysql':raise OperationalError(2003,'sensitive-host-and-credential')
            return {'tables':[{'name':'ns_goods','type':'BASE TABLE'}],'truncated':False}
    monkeypatch.setattr(probe.data_os_store,'connect',connect)
    monkeypatch.setattr(probe,'JdbcConnectorRuntime',Runtime)
    if failure=='none':
        result=probe.probe_source_tables(TenantScope('org-org','dev-project'),'source','version')
        assert result['ok'] and result['configurationRevision']=='version'
        assert result['tables'][0]['name']=='ns_goods'
    else:
        with pytest.raises(probe.data_os_store.ApiError) as exc:
            probe.probe_source_tables(TenantScope('org-org','dev-project'),'source','version')
        assert 'sensitive' not in str(exc.value)
        if failure=='ssh':assert exc.value.code=='SSH_TUNNEL_NOT_READY'
        if failure=='mysql':assert exc.value.code=='MYSQL_CONNECT_FAILED'
        if failure=='transport':assert exc.value.code=='SOURCE_PROBE_FAILED'
    assert not active
    assert calls==(['constructed','closed'] if failure in {'none','transport','ssh','mysql'} else [])
