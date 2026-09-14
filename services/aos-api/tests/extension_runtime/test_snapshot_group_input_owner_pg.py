"""Current original saved input consumption; source and signed authority are fixtures."""
import pytest
from test_lifecycle_pg import database,pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from aos_api.pipeline_snapshot_group_input_owner import PipelineSnapshotGroupInputOwner
from aos_api.ec_ingress_journal import IngressJournalConflict

@pytest.mark.parametrize('empty',[False,True])
def test_original_group_input_consumed_without_another_source_call(prepared_case,empty):
    executor,conn,args,state=prepared_case;state['empty']=empty
    original=executor.prepare(**args);owner=PipelineSnapshotGroupInputOwner(claims=executor._claims)
    with conn.transaction():current=owner.run_current(conn,**args,execute=lambda value:value)
    with conn.transaction():again=owner.run_current(conn,**args,execute=lambda value:value)
    assert current==again and current.parents==original.parents and current.manifest_hash==original.manifest_hash
    assert sum(m['rowCount'] for m in current.manifest['members'])==(0 if empty else 2)
    assert state['calls']==1

@pytest.mark.parametrize('claimed',[False,True])
def test_missing_original_input_does_not_start_collection(prepared_case,claimed):
    executor,conn,args,state=prepared_case;owner=PipelineSnapshotGroupInputOwner(claims=executor._claims)
    if claimed:
        with conn.transaction():executor._groups.reserve(conn,**args)
    with pytest.raises((LookupError,IngressJournalConflict)),conn.transaction():owner.run_current(conn,**args,execute=lambda v:pytest.fail('missing group consumed'))
    assert state['calls']==0
    assert conn.execute('SELECT count(*) AS n FROM ecommerce_ingress_command').fetchone()['n']==0

@pytest.mark.parametrize('fault',['actor','binding','denied','stopped'])
def test_saved_input_cannot_escape_current_binding(prepared_case,fault):
    executor,conn,args,state=prepared_case;executor.prepare(**args)
    owner=PipelineSnapshotGroupInputOwner(claims=executor._claims)
    if fault=='actor':args=args|{'actor':'different-actor'}
    elif fault=='binding':args=args|{'bindings':((args['bindings'][0][0],'other-run'),args['bindings'][1])}
    elif fault=='denied':state['deny']=True
    else:
        conn.execute('RESET ROLE');conn.execute("UPDATE meta_schedule_run SET status='stopped' WHERE id='run-one'");conn.execute('SET ROLE aos_runtime')
    with pytest.raises((ValueError,RuntimeError,PermissionError)),conn.transaction():owner.run_current(conn,**args,execute=lambda v:pytest.fail('invalid current consumed'))
    assert state['calls']==1

@pytest.mark.parametrize('fault',['mutate','deferred','denied'])
def test_callback_cannot_change_or_export_current_input(prepared_case,fault):
    executor,conn,args,state=prepared_case;executor.prepare(**args)
    owner=PipelineSnapshotGroupInputOwner(claims=executor._claims)
    def consume(current):
        if fault=='mutate':current.parents[0]['outputRows'].clear()
        elif fault=='denied':state['deny']=True
        else:return (x for x in [1])
    with pytest.raises((ValueError,RuntimeError,PermissionError,TypeError)),conn.transaction():owner.run_current(conn,**args,execute=consume)
    assert state['calls']==1


def test_saved_read_interval_outside_claim_window_is_not_consumed(prepared_case,monkeypatch):
    from dataclasses import replace
    from datetime import timedelta
    import aos_api.pipeline_controlled_snapshot_group_ingress as ingress_module
    executor,conn,args,state=prepared_case;source=ingress_module.read_selected_snapshot_group
    def fake_bad_source_interval(**kwargs):
        result=source(**kwargs)
        return replace(result,started_at=kwargs['group'].not_before-timedelta(seconds=1))
    # Deliberately bypass the separately tested source reader to test persisted-input defense.
    monkeypatch.setattr(ingress_module,'read_selected_snapshot_group',fake_bad_source_interval)
    executor.prepare(**args)
    owner=PipelineSnapshotGroupInputOwner(claims=executor._claims)
    with pytest.raises(IngressJournalConflict,match='BINDING_DRIFT'),conn.transaction():
        owner.run_current(conn,**args,execute=lambda value:pytest.fail('out-of-window input consumed'))
    assert state['calls']==1
