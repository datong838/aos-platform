"""Selected reader mechanics, not current execution permission acceptance."""
from datetime import timedelta
from types import SimpleNamespace as NS

import pytest

from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.pipeline_runtime_control_contracts import PipelineSourceSelectionDraft
from aos_api.pipeline_source_selection import MappingReadSpec
from aos_api.tenant_scope import TenantScope
from tests.test_pipeline_runtime_control_contracts import payload
from aos_api.pipeline_selected_snapshot import read_selected_snapshot


@pytest.fixture
def read_case(monkeypatch):
    import aos_api.pipeline_selected_snapshot as module
    body=payload(); body.pop('sourceSelectionRef')
    draft=PipelineSourceSelectionDraft.model_validate(body)
    scope=TenantScope(draft.org_id,draft.project_id)
    spec=MappingReadSpec('ns_site','Shop','site_id',('site_id','site_name'),(('site_id',1),))
    state=dict(rows=[{'site_id':1,'site_name':'fixture'}],calls=[],closed=False,elapsed=0,
        ref=draft.source_configuration_ref)
    props=dict(sshHost='fixture',sshUser='fixture',sshPassword='fixture',dbHost='fixture',
        database='fixture',username='fixture',password='fixture',runtimeMode='direct')
    class Connection:
        def execute(self,query,params=()):
            state['calls'].append('lock')
            return NS(fetchone=lambda:{'id':draft.source_id})
    def load(self,source_id):
        return NS(props=props,revision=NS(ref=state['ref'],source_id=source_id,source_type='jdbc-mysql-ssh',status='registered'))
    class Runtime:
        def __init__(self,config,*,reuse_cache):
            assert reuse_cache is False
            state['calls'].append('connect')
        def __enter__(self):return self
        def __exit__(self,*args):state['closed']=True
        def read_rows(self,table,**kwargs):
            state['query']=(table,kwargs)
            if state.get('error'):raise RuntimeError('fixture-secret-must-not-escape')
            return state['rows']
    monkeypatch.setattr(module.SourceConfigurationRevisionStore,'read_connection_input',load)
    monkeypatch.setattr(module,'JdbcConnectorRuntime',Runtime)
    monkeypatch.setattr(module,'_clock',lambda:draft.not_before+timedelta(minutes=1))
    ticks=iter([0.0,0.0])
    monkeypatch.setattr(module,'monotonic',lambda:next(ticks)+state['elapsed'])
    return dict(transaction=HostTransaction(Connection()),scope=scope,draft=draft,read_spec=spec),state,module


def test_explicit_private_read_is_bounded_and_complete(read_case):
    args,state,_=read_case
    result=read_selected_snapshot(**args)
    assert result.rows==state['rows'] and result.source_configuration_ref==args['draft'].source_configuration_ref
    assert state['query']==('ns_site',dict(columns=('site_id','site_name'),where_equals={'site_id':1},limit=100))
    assert state['calls']==['lock','connect'] and state['closed']


@pytest.mark.parametrize('mode',['limit','extra_column','missing_column','duplicate','null_key','scope','error'])
def test_invalid_or_incomplete_result_never_returns_partial_data(read_case,mode):
    args,state,_=read_case
    if mode=='limit':state['rows']*=100
    elif mode=='extra_column':state['rows'][0]['site_tel']='private'
    elif mode=='missing_column':state['rows'][0].pop('site_name')
    elif mode=='duplicate':state['rows']*=2
    elif mode=='null_key':state['rows'][0]['site_id']=None
    elif mode=='scope':state['rows'][0]['site_id']=2
    else:state['error']=True
    with pytest.raises(ValueError,match='^SELECTED_SNAPSHOT_READ_FAILED$') as error:
        read_selected_snapshot(**args)
    assert 'fixture-secret' not in str(error.value)
    assert state['closed']


def test_current_source_revision_drift_prevents_connection(read_case):
    args,state,_=read_case
    state['ref']=state['ref'].model_copy(update={'content_hash':'sha256:'+'f'*64})
    with pytest.raises(ValueError):read_selected_snapshot(**args)
    assert state['calls']==['lock']


@pytest.mark.parametrize('mode',['elapsed','expiry','tenant'])
def test_time_and_tenant_bounds(read_case,monkeypatch,mode):
    args,state,module=read_case
    if mode=='elapsed':
        ticks=iter([0.0,31.0]);monkeypatch.setattr(module,'monotonic',lambda:next(ticks))
    elif mode=='expiry':monkeypatch.setattr(module,'_clock',lambda:args['draft'].expires_at)
    else:args['scope']=TenantScope('dev-org','dev-project')
    with pytest.raises(ValueError):read_selected_snapshot(**args)
    if mode!='elapsed':assert state['calls']==[]
    else:assert state['closed']
