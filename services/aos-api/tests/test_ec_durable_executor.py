from contextlib import contextmanager,nullcontext
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from aos_api.tenant_scope import TenantScope


def setup(monkeypatch,existing=False,wrong_version=False):
    from aos_api import ec_durable_executor as durable
    from aos_api import ec_live_executor as live
    from test_ec_ingress_input import prepared
    scope,pipeline,row,command,eng=prepared()
    pipeline.write_mode='SNAPSHOT'
    node=SimpleNamespace(id='n',pipeline_id=pipeline.id,node_type='source',config={'source_id':'source'})
    graph=dict(pipeline_id=pipeline.id,write_mode='SNAPSHOT',nodes=[vars(node)])
    events=[]
    parent=dict(runId='run',pipelineId=pipeline.id,sourceId='source',sourceRevision='00000000-0000-0000-0000-000000000001',pipelineHash='a'*64,command=command.model_dump(mode='json'),outputRows=[row])
    journal=Mock(schema='public')
    journal.read.return_value=parent if existing else None
    journal.save_for_running_schedule.side_effect=lambda *a,**kw: events.append('save') or parent
    conn=Mock();conn.transaction.return_value=nullcontext()
    conn.execute.side_effect=[SimpleNamespace(fetchone=lambda:{'payload':graph}),SimpleNamespace(fetchone=lambda:{'configuration_revision':parent['sourceRevision']})]
    @contextmanager
    def connect(scope):
        yield conn
        events.append('commit')
    monkeypatch.setattr(durable,'connect',connect)
    monkeypatch.setattr(durable,'IngressJournal',lambda:journal)
    fetch=Mock(side_effect=lambda **kw: events.append('fetch') or ([row],SimpleNamespace(resource_id='source-config-'+('wrong' if wrong_version else parent['sourceRevision']))))
    monkeypatch.setattr(durable,'fetch_source_rows_versioned',fetch)
    monkeypatch.setattr(live,'_transform_live_rows',lambda **kw: events.append('transform') or [row])
    monkeypatch.setattr(durable,'recover_saved_authoritative_stages',lambda *a,**kw: events.append('recover') or ())
    monkeypatch.setattr(durable,'project_until_caught_up',lambda *a,**kw: events.append('project') or {'projected':1,'pending':0})
    monkeypatch.setattr(durable,'finalize_saved_dataset',lambda *a,**kw: None if kw.get('only_existing') else events.append('finalize') or {'dataset':{'rid':'saved'},'build':{'rows_written':1}})
    args=dict(eng=eng,pipeline=pipeline,nodes=[node],scope=scope,run_id='run',run_started_at=1,deadline=float('inf'),cancel_event=None)
    return durable,args,events,fetch


def test_existing_batch_never_rereads_source(monkeypatch):
    durable,args,events,fetch=setup(monkeypatch,existing=True)
    result=durable.execute_durable_ingress(**args)
    assert result['output_ref']=='dataset://catalog/saved'
    assert events==['commit','recover','project','finalize']
    fetch.assert_not_called()


def test_completed_batch_skips_all_authoritative_reexecution(monkeypatch):
    durable,args,events,fetch=setup(monkeypatch,existing=True)
    result={'dataset':{'rid':'saved'},'build':{'rows_written':1},
            'completion':{'expected':2,'projected':2,'pending':0}}
    finalize=Mock(return_value=result)
    monkeypatch.setattr(durable,'finalize_saved_dataset',finalize)
    output=durable.execute_durable_ingress(**args)
    assert events==['commit']
    assert output['completed_replay'] is True
    assert output['rows_read']==0 and output['rows_written']==1
    assert output['projection']['projected']==0
    assert output['completion']==result['completion']
    assert finalize.call_args.kwargs['only_existing'] is True
    fetch.assert_not_called()


def test_new_batch_commits_input_before_authoritative_recovery(monkeypatch):
    durable,args,events,_=setup(monkeypatch)
    assert durable.execute_durable_ingress(**args)['rows_read']==1
    assert events==['fetch','transform','save','commit','recover','project','finalize']


def test_changed_source_read_version_stops_before_any_saved_effect(monkeypatch):
    durable,args,events,_=setup(monkeypatch,wrong_version=True)
    with pytest.raises(RuntimeError,match='INGRESS_SOURCE_READ_VERSION_DRIFT'):
        durable.execute_durable_ingress(**args)
    assert events==['fetch']


def test_graph_drift_stops_before_source(monkeypatch):
    durable,args,events,fetch=setup(monkeypatch)
    args['pipeline'].write_mode='DELETE'
    with pytest.raises(RuntimeError,match='INGRESS_EXECUTION_GRAPH_DRIFT'):
        durable.execute_durable_ingress(**args)
    fetch.assert_not_called()
    assert events==[]


def test_cancelled_run_does_not_start(monkeypatch):
    durable,args,events,fetch=setup(monkeypatch)
    args['cancel_event']=Mock(is_set=Mock(return_value=True))
    with pytest.raises(RuntimeError,match='INGRESS_CANCELLED'):
        durable.execute_durable_ingress(**args)
    fetch.assert_not_called()
    assert events==[]


def test_live_executor_routes_durable_run_without_legacy_source_read(monkeypatch):
    from aos_api import ec_durable_executor as durable
    from aos_api import ec_live_executor as live
    monkeypatch.setattr(live,'ensure_store_assembled',lambda _:None)
    source=Mock(side_effect=AssertionError('legacy source path'))
    monkeypatch.setattr(live,'fetch_source_rows',source)
    execute=Mock(return_value={'output_ref':'dataset://catalog/saved'})
    monkeypatch.setattr(durable,'execute_durable_ingress',execute)
    result=live.ec_live_executor(pipeline=SimpleNamespace(id='p12'),nodes=[],node_id=None,sample_input={},
        execution_kind='direct_sync',scope=TenantScope('org-org','dev-project'),cancel_event=None,deadline=float('inf'),
        run_id='run',durable_ingress=True)
    assert result['output_ref']=='dataset://catalog/saved'
    assert execute.call_args.kwargs['run_id']=='run'
    source.assert_not_called()
