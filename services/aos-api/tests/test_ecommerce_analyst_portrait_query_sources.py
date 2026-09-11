import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import aos_api.ecommerce_analyst_portrait_query_sources as module
from aos_api.aip_analyst_contracts import AnalystQueryStatus, MetricQueryRequest, QueryResultRevision
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.tenant_scope import TenantScope

SCOPE = TenantScope('org-org', 'dev-project')


def setup(monkeypatch):
    now = datetime.now(timezone.utc)
    metric = AnalystExactRef(resourceType='MetricDefinitionRevision', resourceId='orders', revision=1, contentHash='a'*64)
    query = MetricQueryRequest(metricRef=dict(resourceType='MetricDefinitionRevision', resourceId='orders', revision='1', authority='postgres:aip_metric_definition_revision'), windowStart=now-timedelta(days=1), windowEnd=now, cutoffAt=now)
    result = QueryResultRevision(tenant=dict(orgId=SCOPE.org_id, projectId=SCOPE.project_id), queryId='query', revision=1, kind='metric', status='complete',
        columns=[dict(key='count', label='订单数', valueType='number')], rows=[dict(rowId='total', values={'count': 2})],
        sourceRefs=[dict(ref=dict(resourceType='DatasetRevision', resourceId='orders-source', revision='1', authority='postgresql'), contentHash='b'*64, cutoffAt=now, freshness='fresh', markings=['internal'])], cutoffAt=now, createdAt=now, contentHash='c'*64)
    material = dict(cutoffAt=now.isoformat(), items=[dict(payload=dict(queryRequest=query.model_dump(mode='json', by_alias=True), queryResult=result.model_dump(mode='json', by_alias=True), metricDefinitionRef=metric.model_dump(mode='json', by_alias=True), marking=['internal']))])
    state = dict(result=result, query=query, material=material, denied=False)
    conn = object()
    class Owner:
        def __init__(self, *, connect_factory): self.factory=connect_factory
        def read_result_exact(self, scope, ref):
            with self.factory(scope) as bound: assert bound is conn
            return state['result']
        def get(self, scope, identity):
            with self.factory(scope) as bound: assert bound is conn
            return SimpleNamespace(query=state['query'], tenant=result.tenant, query_id='query', status='succeeded', latest_result=state['result'])
    def read(**kwargs):
        assert kwargs['conn'] is conn
        if state['denied']: raise ValueError('denied')
        return state['material']
    monkeypatch.setattr(module, 'AipAnalystQueryStore', Owner)
    monkeypatch.setattr(module, 'read_analysis_bundle', read)
    kwargs=dict(conn=conn, scope=SCOPE, task_id='task', actor='actor', request=object(), markings=['internal'], now=now, max_source_age=timedelta(days=2), max_bytes=10000,
        metric_ref=metric, result_ref=InvestigationExactRef(resourceType='QueryResultRevision', resourceId='query', revision=1, contentHash='sha256:'+'c'*64), window_start=query.window_start, window_end=query.window_end, cutoff_at=now)
    return kwargs,state


def test_exact_disclosed_query_is_returned_without_invented_values(monkeypatch):
    kwargs,state=setup(monkeypatch)
    query,result,material=module.read_portrait_metric_query(**kwargs)
    assert query == state['query'] and result == state['result'] and material == state['material']


@pytest.mark.parametrize('problem', ['denied','missing','pointer_only','request_missing','request_drift','body_drift','duplicate','metric','revision','authority','window','cutoff','bundle_cutoff','partial','empty','stale','old_source','future_source','source_marking','column_marking','unmarked','metric_hash','metric_bool_revision','scope','clock'])
def test_unusable_query_material_rejected(monkeypatch, problem):
    kwargs,s=setup(monkeypatch)
    p=s['material']['items'][0]['payload']
    if problem=='denied': s['denied']=True
    elif problem=='missing': s['result']=None
    elif problem=='pointer_only': p.pop('queryResult')
    elif problem=='request_missing': p.pop('queryRequest')
    elif problem=='request_drift': p['queryRequest']['dimensions']=['other']
    elif problem=='body_drift': p['queryResult']['rows'][0]['values']['count']=99
    elif problem=='duplicate': s['material']['items']*=2
    elif problem=='metric': s['query'].metric_ref.resource_id='other'
    elif problem=='revision': s['query'].metric_ref.revision='2'
    elif problem=='authority': s['query'].metric_ref.authority='untrusted'
    elif problem=='window': kwargs['window_start']-=timedelta(days=1)
    elif problem=='cutoff': kwargs['cutoff_at']-=timedelta(seconds=1)
    elif problem=='bundle_cutoff': s['material']['cutoffAt']=(kwargs['cutoff_at']-timedelta(seconds=1)).isoformat()
    elif problem=='partial': s['result']=s['result'].model_copy(update={'status':AnalystQueryStatus.PARTIAL, 'uncertainties':['incomplete']})
    elif problem=='empty': s['result']=s['result'].model_copy(update={'status':AnalystQueryStatus.EMPTY,'rows':[]})
    elif problem=='stale': s['result'].source_refs[0].freshness='stale'
    elif problem=='old_source': s['result'].source_refs[0].cutoff_at-=timedelta(days=3)
    elif problem=='future_source': s['result'].source_refs[0].cutoff_at+=timedelta(seconds=1)
    elif problem=='source_marking': s['result'].source_refs[0].markings=['secret']
    elif problem=='column_marking': s['result'].columns[0].marking='secret'
    elif problem=='unmarked': p.pop('marking')
    elif problem=='metric_hash': p['metricDefinitionRef']['contentHash']='d'*64
    elif problem=='metric_bool_revision': p['metricDefinitionRef']['revision']=True
    elif problem=='scope': s['result'].tenant.org_id='dev-org'
    elif problem=='clock': kwargs['now']=kwargs['now'].replace(tzinfo=None)
    if problem in {'source_marking','column_marking'}:
        p['queryResult']=s['result'].model_dump(mode='json', by_alias=True)
    with pytest.raises(ValueError): module.read_portrait_metric_query(**kwargs)


@pytest.mark.skipif(os.getenv('AOS_GROWTH_DRAFT_FULL_GRAPH_TEST') != '1', reason='explicit disposable database opt-in required')
def test_real_query_authority_disclosure_and_revocation(monkeypatch):
    from aos_api.aip_analyst_query_store import AipAnalystQueryStore
    from aos_api.aip_analyst_contracts import CreateQueryJobRequest, QueryJobCommand, RecordQueryResultRequest
    from aos_api.aip_task_store import AipTaskStore
    from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
    from aos_api.aip_production_contracts import BuildEvidenceBundleRequest, ResolveEvidenceDisclosureRequest, RevokeEvidenceRequest
    from aos_api.ecommerce_analyst_analysis_sources import AnalysisBundleSourceRequest
    from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, insert
    from test_aip_taor_lease_adapter import running_run
    with monkeypatch.context() as mocked:
        kwargs,state=setup(mocked)
    with disposable_database() as connect:
        query=state['query']
        owner=AipAnalystQueryStore(connect_factory=connect)
        job=owner.create(SCOPE, CreateQueryJobRequest(query=query, deadlineAt=kwargs['now']+timedelta(hours=1)), idempotency_key='portrait-query', actor='actor')
        owner.command(SCOPE, job.query_id, 'start', QueryJobCommand(expectedSequence=1, reasonCode='TEST_QUERY'), idempotency_key='portrait-start', actor='actor')
        result=state['result'].model_copy(update={'query_id':job.query_id, 'created_at':datetime.now(timezone.utc)})
        result.content_hash=owner._result_hash(SCOPE, query.model_dump(mode='json', by_alias=True), result)
        owner.record_result(SCOPE, job.query_id, RecordQueryResultRequest(expectedSequence=2,result=result), idempotency_key='portrait-result',actor='actor')
        run=running_run(AipTaskStore(connect_factory=connect))
        payload=dict(facts=['orders'], queryRequest=query.model_dump(mode='json', by_alias=True), queryResult=result.model_dump(mode='json', by_alias=True), metricDefinitionRef=kwargs['metric_ref'].model_dump(mode='json', by_alias=True), marking=['internal'])
        with connect(SCOPE) as conn:
            insert(conn, 'aip_task_brief_head', brief_id='query-brief', task_id=run.task_id, current_revision=1)
            insert(conn, 'aip_task_brief_revision', brief_id='query-brief', task_id=run.task_id, revision=1, brief_type='analysis', schema_ref=dict(resourceType='Schema',resourceId='fixture',revision='1',authority='postgresql'),spec={},content_hash='d'*64,lifecycle='frozen',created_by='actor')
            insert(conn, 'aip_evidence',evidence_id='query-evidence',run_id=run.id,evidence_type='query',subject_ref={},source_type='database',source_ref='synthetic-query-fixture',observed_at=kwargs['cutoff_at'],freshness_at=kwargs['cutoff_at'],content_hash=canonical_hash(payload),payload=payload,created_by='actor')
        production=AipProductionContractStore(connect)
        evidence=dict(resourceType='Evidence',resourceId='query-evidence',revision=1,contentHash=canonical_hash(payload))
        bundle=production.build_evidence_bundle(SCOPE,'actor','query-bundle',BuildEvidenceBundleRequest(briefRef=dict(resourceType='TaskBriefRevision',resourceId='query-brief',revision=1,contentHash='d'*64),cutoffAt=kwargs['cutoff_at'],itemRefs=[evidence],requiredFactIds=['orders'],marking=['internal']))
        body=ResolveEvidenceDisclosureRequest(evidenceRef=evidence,purpose='source',requestedLevel='l3',taskId=run.task_id)
        grant=production.resolve_evidence_disclosure(SCOPE,'actor','query-grant',body,markings=['internal','secret'])
        assert grant.status.value=='allowed'
        kwargs.update(task_id=run.task_id,now=datetime.now(timezone.utc),markings=['internal','secret'],result_ref=InvestigationExactRef(resourceType='QueryResultRevision',resourceId=job.query_id,revision=1,contentHash='sha256:'+result.content_hash),request=AnalysisBundleSourceRequest(bundleRef=dict(resourceType='EvidenceBundleRevision',resourceId=bundle.bundle_id,revision=1,contentHash=bundle.content_hash),grants=[dict(decisionId=grant.decision_id,request=body)]))
        with connect(SCOPE) as conn:
            kwargs['conn']=conn
            got=module.read_portrait_metric_query(**kwargs)
            assert got[1]==result and got[2]['items'][0]['payload']==payload
        production.revoke_evidence(SCOPE,'actor','query-evidence','query-withdraw',RevokeEvidenceRequest(expectedContentHash=canonical_hash(payload),reason='synthetic withdrawal'))
        with connect(SCOPE) as conn:
            kwargs['conn']=conn
            with pytest.raises((ValueError,RuntimeError)): module.read_portrait_metric_query(**kwargs)
