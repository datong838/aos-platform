"""Actual completed PG group, with a named analysis context double for bridge tests."""
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest
from test_lifecycle_pg import database, pytestmark
from test_pipeline_source_selection_schema_pg import ledger
from test_pipeline_source_selection_owner_pg import owner_case
from test_pipeline_source_claim_owner_pg import claim_case
from test_controlled_snapshot_ingress_pg import executor_case
from test_snapshot_group_claim_owner_pg import group_claim_case
from test_controlled_snapshot_group_ingress_pg import prepared_case
from test_snapshot_group_assessment_owner_pg import assessment_case
from test_snapshot_group_relationship_journal_pg import journal_case
from test_snapshot_group_object_executor_pg import object_case
from test_snapshot_group_completed_quality_pg import completed_group
from aos_api.pipeline_controlled_ingress_journal import ControlledIngressJournal
from aos_api.ecommerce_product_event_analysis_service import ProductEventAnalysisService
from aos_api.ecommerce_analysis_continuation_context import AnalysisContinuationContext
from aos_api.ecommerce_analysis_snapshot_context import AnalysisSnapshotContext


@pytest.fixture
def bridge_case(completed_group, monkeypatch):
    executor, conn, args, state, _ = completed_group
    control_ref, run_id = args['bindings'][0]
    journal = ControlledIngressJournal(claims=executor._single._ingress._claims,
        scope=args['scope'],run_id=run_id,control_ref=control_ref,actor=args['actor'],completed_read=True)
    analysis = object.__new__(ProductEventAnalysisService)
    analysis.scope = args['scope']
    analysis.source = SimpleNamespace(actor=args['actor'], reader=SimpleNamespace(_journal=journal))
    cutoff = conn.execute('SELECT read_completed_at FROM pipeline_snapshot_group_input').fetchone()['read_completed_at']
    context = dict(origin=dict(runId=run_id,actor=args['actor']),
        analysisReceipt=dict(cutoffAt=cutoff.isoformat()), source=dict(case=dict(analysisType='initial_store_analysis')))
    def named_analysis_context(self, db, *, receipt_ref, execute):
        assert db is conn and receipt_ref == {'fixture':'accepted-analysis-receipt'}
        state['context_calls'] = state.get('context_calls',0)+1
        return execute(deepcopy(context))
    monkeypatch.setattr(AnalysisContinuationContext,'run_current',named_analysis_context)
    call = dict(receipt_ref={'fixture':'accepted-analysis-receipt'},policy_ref=args['policy_ref'],quality_ref=args['quality_ref'])
    return conn, args, state, context, AnalysisSnapshotContext(analysis), call


def test_original_analysis_routes_to_original_completed_group(bridge_case):
    conn,args,state,_,bridge,call = bridge_case
    with conn.transaction(): first = bridge.run_current(conn,**call,execute=lambda current:current)
    with conn.transaction(): again = bridge.run_current(conn,**call,execute=lambda current:current)
    assert first == again and first.quality.assessment.input.claim.group_id == args['group_id']
    assert first.quality.measurement.counts['Shop.hasWeapp']['completeRows'] == 1
    assert state['calls'] == 1 and state['context_calls'] == 2


@pytest.mark.parametrize('fault',['run','cutoff','actor','control','purpose'])
def test_analysis_origin_cannot_choose_unrelated_snapshot(bridge_case,fault):
    conn,args,state,context,bridge,call = bridge_case
    if fault=='run':context['origin']['runId']='other-run'
    if fault=='cutoff':context['analysisReceipt']['cutoffAt']=(datetime.fromisoformat(context['analysisReceipt']['cutoffAt'])+timedelta(microseconds=1)).isoformat()
    if fault=='actor':context['origin']['actor']='other-actor'
    if fault=='control':bridge.analysis.source.reader._journal._ref=args['bindings'][1][0]
    if fault=='purpose':context['source']['case']['analysisType']='unregistered_purpose'
    with pytest.raises((ValueError,PermissionError,LookupError)),conn.transaction():
        bridge.run_current(conn,**call,execute=lambda c:pytest.fail('mismatched context'))
    assert state['calls'] == 1


@pytest.mark.parametrize('fault',['analysis','counts','release','deferred'])
def test_consumption_retains_both_current_guards(bridge_case,fault):
    conn,_,state,_,bridge,call = bridge_case
    def consume(current):
        if fault=='analysis':current.analysis_context['origin']['runId']='changed'
        if fault=='counts':current.quality.measurement.counts.clear()
        if fault=='release':state['policy_denied']=True
        if fault=='deferred':return (item for item in [current])
    with pytest.raises((ValueError,PermissionError)),conn.transaction():
        bridge.run_current(conn,**call,execute=consume)
    assert state['calls'] == 1
