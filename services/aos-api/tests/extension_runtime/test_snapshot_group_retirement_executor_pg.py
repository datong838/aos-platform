"""Current conditional retirement through original Store and Projector, isolated PG."""
from contextlib import contextmanager
import pytest
from test_lifecycle_pg import database,pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from test_snapshot_group_assessment_owner_pg import assessment_case
from test_snapshot_group_retirement_journal_pg import retirement_case
from aos_api.pipeline_snapshot_group_retirement_executor import ControlledSnapshotGroupRetirementExecutor


@pytest.fixture
def retirement_executor_case(retirement_case,monkeypatch):
    from aos_api import ecom_projector
    old,conn,args,state,journal=retirement_case
    # Establish an already projected historical edge in this isolated fixture.
    monkeypatch.setattr(ecom_projector,'connect',old._transaction)
    assert ecom_projector.project_pending(args['scope'])['pending']==0
    object_executor=old._objects
    executor=ControlledSnapshotGroupRetirementExecutor(claims=object_executor._claims,store=old._store,
        connect=object_executor._single._ingress._connect,eng=object_executor._single._eng)
    return executor,conn,args,state


def test_old_edge_retired_projected_and_original_receipt_replayed(retirement_executor_case):
    executor,conn,args,state=retirement_executor_case
    assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n']==2
    first=executor.execute(**args);replay=executor.execute(**args)
    assert first['reconciliation_status']=='complete' and first['reconciliation_scope']=='current_present_rows'
    assert first['completion']=={'expected':1,'projected':1,'pending':0}
    assert replay['replayed'] and replay['projection']['projected']==0
    assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n']==1
    assert conn.execute('SELECT count(*) AS n FROM ecom_link WHERE deleted_at IS NULL').fetchone()['n']==1
    assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n']==5
    assert state['calls']==1


def test_preparation_ack_loss_never_retires(retirement_executor_case,monkeypatch):
    executor,conn,args,_=retirement_executor_case;original=executor._transaction
    @contextmanager
    def lost(scope):
        with original(scope) as db:yield db
        raise RuntimeError('preparation ack lost')
    monkeypatch.setattr(executor,'_transaction',lost)
    with pytest.raises(RuntimeError,match='ack lost'):executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM pipeline_snapshot_group_retirement').fetchone()['n']==1
    assert conn.execute('SELECT count(*) AS n FROM ecom_link WHERE deleted_at IS NULL').fetchone()['n']==2
    monkeypatch.setattr(executor,'_transaction',original)
    assert executor.execute(**args)['reconciliation_status']=='complete'


def test_retirement_ack_loss_recovers_original_conditional_receipt(retirement_executor_case,monkeypatch):
    executor,conn,args,state=retirement_executor_case;original=executor._store.apply_strict_link_retirement_batch
    def lost(command):
        original(command);raise RuntimeError('retirement ack lost')
    monkeypatch.setattr(executor._store,'apply_strict_link_retirement_batch',lost)
    with pytest.raises(RuntimeError,match='ack lost'):executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM ecom_link WHERE deleted_at IS NULL').fetchone()['n']==1
    assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n']==2
    monkeypatch.setattr(executor._store,'apply_strict_link_retirement_batch',original)
    assert executor.execute(**args)['replayed']
    assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n']==1
    assert state['calls']==1


def test_graph_delete_failure_rolls_back_projection(retirement_executor_case,monkeypatch):
    from aos_api import pipeline_controlled_projection as projection
    executor,conn,args,_=retirement_executor_case;original=projection._project_link
    def fail(*a,**kw):
        original(*a,**kw);raise RuntimeError('after graph deletion')
    monkeypatch.setattr(projection,'_project_link',fail)
    with pytest.raises(RuntimeError,match='graph deletion'):executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM graph_edge').fetchone()['n']==2
    monkeypatch.setattr(projection,'_project_link',original)
    assert executor.execute(**args)['completion']['pending']==0


def test_revocation_after_preparation_stops_retirement(retirement_executor_case,monkeypatch):
    executor,conn,args,state=retirement_executor_case;original=executor._transaction
    @contextmanager
    def revoke(scope):
        with original(scope) as db:yield db
        state['deny']=True
    monkeypatch.setattr(executor,'_transaction',revoke)
    with pytest.raises(PermissionError):executor.execute(**args)
    assert conn.execute('SELECT count(*) AS n FROM ecom_link WHERE deleted_at IS NULL').fetchone()['n']==2


def test_newer_residual_is_reported_requires_attention(retirement_executor_case):
    from datetime import timedelta
    from aos_api.ec_ot_writer import _build_batch_command
    executor,conn,args,_=retirement_executor_case
    with executor._transaction(args['scope']) as db:
        audit=executor._retirement._audit.read_current(db,**args)
        parent=executor._links._commands.read_current(db,**args)
    old=audit.cleanup_candidates[0];candidate=parent.command.links[0]
    newer=candidate.model_copy(update={'source':candidate.source.model_copy(update={'external_id':old['sourceId']}),
        'source_updated_at':candidate.source_updated_at+timedelta(seconds=1),'cursor_external_id':'future-fixture'})
    update=_build_batch_command(sync_scope=parent.command.scope.model_copy(update={'stream':'future-fixture'}),
        objects=[],links=[newer],pipeline_id='future-fixture',store=executor._store)
    executor._store.apply_batch(update)
    result=executor.execute(**args)
    assert result['reconciliation_status']=='requires_attention'
    assert result['relationship_counts']['Shop.hasWeapp']['futureExtras']==1
    assert result['completion']['expected']==0
    assert conn.execute('SELECT count(*) AS n FROM ecom_link WHERE deleted_at IS NULL').fetchone()['n']==2
    assert executor._store.read_batch_projection_completion(update,[])['pending']==1


@pytest.mark.parametrize('retirement_case',[False],indirect=True)
def test_empty_retirement_has_no_additional_receipt(retirement_executor_case):
    executor,conn,args,state=retirement_executor_case
    result=executor.execute(**args)
    assert result['reconciliation_status']=='complete' and result['completion']['expected']==0
    assert conn.execute('SELECT count(*) AS n FROM ecom_ingest_receipt').fetchone()['n']==3
    assert state['calls']==1
