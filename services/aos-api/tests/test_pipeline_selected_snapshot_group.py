"""Configuration-bound group read mechanics; current authorization is doubled."""
from datetime import timedelta
from dataclasses import replace
from types import SimpleNamespace as NS
import pytest
from tests.test_pipeline_snapshot_group_owner import case
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.pipeline_snapshot_group_read import SnapshotGroupResult
from aos_api.tenant_scope import TenantScope
from aos_api.pipeline_selected_snapshot_group import read_selected_snapshot_group

@pytest.fixture
def selected(case,monkeypatch):
    import aos_api.pipeline_selected_snapshot_group as module
    owner,conn,scope,refs,state=case
    group=owner.run_current(conn,scope=scope,refs=refs,actor='fixture',execute=lambda group:group)
    draft=group.members[0][1]
    state.update(connects=0,reads=0,closed=False,source_ref=draft.source_configuration_ref,status='registered',mode='direct')
    props=dict(sshHost='fixture',sshUser='fixture',sshPassword='fixture',dbHost='fixture',database='fixture',username='fixture',password='fixture')
    def load(self,source_id):
        return NS(props={**props,'runtimeMode':state['mode']},revision=NS(ref=state['source_ref'],source_id=source_id,source_type='jdbc-mysql-ssh',status=state['status']))
    class Runtime:
        def __init__(self,config,*,reuse_cache):
            assert reuse_cache is False
            state['connects']+=1
        def __enter__(self):return self
        def __exit__(self,*a):state['closed']=True
    def read(runtime,specs,**limits):
        state['reads']+=1;state['limits']=limits
        if state.get('error'):raise RuntimeError('private-secret')
        return SnapshotGroupResult({spec.table:[] for spec in specs},state['now'],state.get('read_end',state['now']))
    monkeypatch.setattr(module.SourceConfigurationRevisionStore,'read_connection_input',load)
    monkeypatch.setattr(module,'JdbcConnectorRuntime',Runtime)
    monkeypatch.setattr(module,'read_snapshot_group',read)
    monkeypatch.setattr(module,'_clock',lambda:state['now'])
    monkeypatch.setattr(module,'monotonic',lambda:0)
    return dict(transaction=HostTransaction(conn),scope=scope,group=group),state,module

def test_reads_one_private_group_with_actual_minimum_limits(selected):
    args,state,_=selected
    result=read_selected_snapshot_group(**args)
    assert state['reads']==state['connects']==1 and state['closed']
    assert state['limits']==dict(row_limit=50,timeout_seconds=args['group'].timeout_seconds)
    assert result.source_configuration_ref==state['source_ref']
    assert set(result.rows_by_table)=={'table_a','table_b'}

@pytest.mark.parametrize('fault',['ref','status','mode','tenant','expired','widened_limit','widened_window','source'])
def test_pre_read_rejection_never_connects(selected,fault):
    args,state,_=selected
    group=args['group']
    if fault=='ref':state['source_ref']=state['source_ref'].model_copy(update={'content_hash':'sha256:'+'f'*64})
    elif fault=='status':state['status']='disabled'
    elif fault=='mode':state['mode']='cached'
    elif fault=='tenant':args['scope']=TenantScope('dev-org','dev-project')
    elif fault=='expired':state['now']=group.expires_at
    elif fault=='widened_limit':args['group']=replace(group,row_limit=51)
    elif fault=='widened_window':args['group']=replace(group,expires_at=group.expires_at+timedelta(seconds=1))
    else:
        ref,draft,mapping=group.members[1]
        args['group']=replace(group,members=(group.members[0],(ref,draft.model_copy(update={'source_id':'different'}),mapping)))
    with pytest.raises(ValueError,match='^SELECTED_SNAPSHOT_GROUP_READ_FAILED$'):read_selected_snapshot_group(**args)
    assert state['connects']==state['reads']==0

@pytest.mark.parametrize('fault',['error','elapsed','future_result'])
def test_post_read_rejection_closes_without_partial_result_or_retry(selected,monkeypatch,fault):
    args,state,module=selected
    if fault=='error':state['error']=True
    elif fault=='future_result':state['read_end']=state['now']+timedelta(seconds=1)
    else:
        ticks=iter([0,31]);monkeypatch.setattr(module,'monotonic',lambda:next(ticks))
    with pytest.raises(ValueError,match='^SELECTED_SNAPSHOT_GROUP_READ_FAILED$') as error:read_selected_snapshot_group(**args)
    assert 'private-secret' not in str(error.value)
    assert state['reads']==1 and state['closed']
