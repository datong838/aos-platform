"""Real PG source claims/input; explicit downstream substitutes test recovery routing."""
import pytest
from test_controlled_snapshot_ingress_pg import executor_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_selection_schema_pg import ledger
from test_lifecycle_pg import database,pytestmark
from aos_api.ec_ingress_journal import IngressJournalConflict


def assembled(executor_case,monkeypatch):
    import aos_api.pipeline_controlled_executor as module
    preparation,conn,args,state=executor_case
    executor=module.ControlledSnapshotExecutor(claims=preparation._claims,store=preparation._store,
        connect=preparation._connect,eng=object())
    downstream={'failure':None,'completed':None,'recover':0,'project':0,'finalize':0}
    def recover(factory,scope,run_id,**kwargs):
        downstream['recover']+=1
        assert conn.execute('SELECT count(*) FROM ecommerce_ingress_command').fetchone()=={'count':1}
        if downstream['failure']=='recover':raise RuntimeError('recover interrupted')
        return ()
    def project(db,scope,run_id,**kwargs):
        downstream['project']+=1
        if downstream['failure']=='project':raise RuntimeError('project interrupted')
        return {'projected':1,'pending':0}
    def finalize(factory,scope,run_id,**kwargs):
        if kwargs.get('only_existing'):return downstream['completed']
        downstream['finalize']+=1
        if downstream['failure']=='finalize':raise RuntimeError('finalize interrupted')
        downstream['completed']={'dataset':{'rid':'fixture'},'build':{'rows_written':1},
            'completion':{'expected':1,'projected':1,'pending':0}}
        return downstream['completed']
    monkeypatch.setattr(module,'recover_saved_authoritative_stages',recover)
    monkeypatch.setattr(module,'project_saved_batch',project)
    monkeypatch.setattr(module,'finalize_saved_dataset',finalize)
    return executor,args,state,downstream


@pytest.mark.parametrize('phase',['recover','project','finalize'])
def test_downstream_retry_reuses_committed_input_and_completion(executor_case,monkeypatch,phase):
    executor,args,state,downstream=assembled(executor_case,monkeypatch)
    downstream['failure']=phase
    with pytest.raises(RuntimeError,match='interrupted'):executor.execute(**args)
    assert state['calls']==1
    downstream['failure']=None
    result=executor.execute(**args)
    assert result['rows_read']==0 and result['rows_written']==1
    assert state['calls']==1
    before=downstream.copy()
    again=executor.execute(**args)
    assert again['completed_replay'] is True and state['calls']==1
    assert downstream==before


def test_unknown_source_never_reaches_downstream(executor_case,monkeypatch):
    executor,args,state,downstream=assembled(executor_case,monkeypatch)
    state['source_error']=True
    with pytest.raises(ValueError,match='SELECTED_SNAPSHOT_READ_FAILED'):executor.execute(**args)
    state['source_error']=False
    with pytest.raises(IngressJournalConflict,match='SOURCE_OUTCOME_UNCONFIRMED'):executor.execute(**args)
    assert state['calls']==1
    assert all(downstream[stage]==0 for stage in ('recover','project','finalize'))
