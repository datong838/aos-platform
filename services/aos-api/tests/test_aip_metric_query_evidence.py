"""Owned disposable DB tests; synthetic source data is not business acceptance."""
from datetime import datetime, timedelta, timezone
import os

import pytest

from aos_api.aip_metric_query_evidence import record_metric_query_evidence
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_analyst_contracts import CreateQueryJobRequest, QueryJobCommand, RecordQueryResultRequest
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
from aos_api.aip_production_contracts import ExactRevisionRef, ResolveEvidenceDisclosureRequest, RevokeEvidenceRequest
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.aip_task_store import AipTaskStore
from test_ecommerce_analyst_portrait_query_sources import setup, SCOPE
from test_ecommerce_analyst_portrait_sources import metric
from test_ecommerce_analyst_growth_plan_full_graph import disposable_database, insert
from test_aip_taor_lease_adapter import running_run

pytestmark=pytest.mark.skipif(os.getenv('AOS_GROWTH_DRAFT_FULL_GRAPH_TEST')!='1',reason='explicit disposable database opt-in required')


def seed(connect, monkeypatch, *, source_kind='Evidence', source_freshness='fresh'):
    with monkeypatch.context() as patch:
        args,state=setup(patch)
    run=running_run(AipTaskStore(connect_factory=connect))
    definition=metric()
    AipEvalAuthorityStore(connect).create_metric_definition(SCOPE,definition,actor='actor')
    query=state['query']
    query.metric_ref.resource_id=definition.metric_id
    payload=dict(factIds=[definition.metric_id],marking=['internal'],count=2)
    with connect(SCOPE) as conn:
        insert(conn,'aip_evidence',evidence_id='raw-count',run_id=run.id,evidence_type='query',subject_ref={},source_type='database',source_ref='synthetic-original',observed_at=query.cutoff_at,freshness_at=query.cutoff_at,content_hash=canonical_hash(payload),payload=payload,created_by='actor')
    raw=ExactRevisionRef(resourceType='Evidence',resourceId='raw-count',revision=1,contentHash=canonical_hash(payload))
    body=ResolveEvidenceDisclosureRequest(evidenceRef=raw.model_dump(mode='json',by_alias=True),purpose='source',requestedLevel='l3',taskId=run.task_id)
    production=AipProductionContractStore(connect)
    grant=production.resolve_evidence_disclosure(SCOPE,'actor','raw-grant',body,markings=['internal','secret'])
    assert grant.status.value=='allowed'
    owner=AipAnalystQueryStore(connect_factory=connect)
    job=owner.create(SCOPE,CreateQueryJobRequest(query=query,deadlineAt=args['now']+timedelta(hours=1)),idempotency_key='query',actor='actor')
    owner.command(SCOPE,job.query_id,'start',QueryJobCommand(expectedSequence=1,reasonCode='TEST'),idempotency_key='start',actor='actor')
    result=state['result'].model_copy(update={'query_id':job.query_id,'created_at':datetime.now(timezone.utc)})
    result.source_refs[0].ref.resource_type=source_kind
    result.source_refs[0].freshness=source_freshness
    result.source_refs[0].ref.resource_id=raw.resource_id
    result.source_refs[0].ref.authority='postgres:aip_evidence'
    result.source_refs[0].content_hash=raw.content_hash
    result.content_hash=owner._result_hash(SCOPE,query.model_dump(mode='json',by_alias=True),result)
    owner.record_result(SCOPE,job.query_id,RecordQueryResultRequest(expectedSequence=2,result=result),idempotency_key='result',actor='actor')
    return dict(scope=SCOPE,run_id=run.id,actor='actor',metric_ref=ExactRevisionRef(resourceType='MetricDefinitionRevision',resourceId=definition.metric_id,revision=1,contentHash=definition.content_hash),result_ref=InvestigationExactRef(resourceType='QueryResultRevision',resourceId=job.query_id,revision=1,contentHash='sha256:'+result.content_hash),source_grants=[dict(decisionId=grant.decision_id,request=body.model_dump(mode='json',by_alias=True))],now=datetime.now(timezone.utc),max_bytes=100000,markings=['internal','secret']),production,body


def test_persist_replay_and_upstream_revocation_blocks_derived_disclosure(monkeypatch):
    with disposable_database() as connect:
        args,production,raw_body=seed(connect,monkeypatch)
        with connect(SCOPE) as conn:
            ref=record_metric_query_evidence(conn=conn,**args)
            assert record_metric_query_evidence(conn=conn,**args)==ref
            assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE evidence_id=%s",(ref.resource_id,)).fetchone()['n']==1
        request=ResolveEvidenceDisclosureRequest(evidenceRef=ref.model_dump(mode='json',by_alias=True),purpose='source',requestedLevel='l3',taskId=raw_body.task_id)
        grant=production.resolve_evidence_disclosure(SCOPE,'actor','derived-grant',request,markings=args['markings'])
        assert grant.status.value=='allowed'
        with connect(SCOPE) as conn:
            material=production.read_disclosed_evidence_source(conn,SCOPE,'actor',grant.decision_id,request,markings=args['markings'])
            assert material['payload']['queryResult']['rows'][0]['values']['count']==2
        production.revoke_evidence(SCOPE,'actor','raw-count','withdraw',RevokeEvidenceRequest(expectedContentHash=raw_body.evidence_ref.content_hash,reason='test withdrawal'))
        with connect(SCOPE) as conn:
            with pytest.raises(RuntimeError): production.read_disclosed_evidence_source(conn,SCOPE,'actor',grant.decision_id,request,markings=args['markings'])
        assert production.resolve_evidence_disclosure(SCOPE,'actor','derived-after-withdraw',request,markings=args['markings']).status.value=='blocked'


@pytest.mark.parametrize('problem',['missing_grant','duplicate','actor','metric','oversize','run','scope','markings','current_metric'])
def test_bad_inputs_write_no_derived_evidence(monkeypatch,problem):
    with disposable_database() as connect:
        args,_,_=seed(connect,monkeypatch)
        if problem=='missing_grant': args['source_grants']=[]
        elif problem=='duplicate': args['source_grants']*=2
        elif problem=='actor': args['actor']='other'
        elif problem=='metric': args['metric_ref'].content_hash='e'*64
        elif problem=='oversize': args['max_bytes']=1
        elif problem=='run': args['run_id']='absent'
        elif problem=='scope': args['scope']=type(SCOPE)('dev-org','dev-project')
        elif problem=='markings': args['markings']=['internal']
        elif problem=='current_metric':
            updated=metric().model_copy(update={'revision':2})
            updated.content_hash=canonical_hash(updated.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))
            AipEvalAuthorityStore(connect).create_metric_definition(SCOPE,updated,actor='actor')
        with connect(SCOPE) as conn:
            with pytest.raises((ValueError,RuntimeError)): record_metric_query_evidence(conn=conn,**args)
            assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE source_type='aip-metric-query'").fetchone()['n']==0


def test_caller_rollback_and_parallel_replay(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    with disposable_database() as connect:
        args,_,_=seed(connect,monkeypatch)
        with pytest.raises(RuntimeError,match='rollback'):
            with connect(SCOPE) as conn:
                record_metric_query_evidence(conn=conn,**args)
                raise RuntimeError('rollback')
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE source_type='aip-metric-query'").fetchone()['n']==0
        def write():
            with connect(SCOPE) as conn: return record_metric_query_evidence(conn=conn,**args)
        with ThreadPoolExecutor(max_workers=2) as pool:
            refs=list(pool.map(lambda _:write(),range(2)))
        assert refs[0]==refs[1]
        with connect(SCOPE) as conn:
            assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE source_type='aip-metric-query'").fetchone()['n']==1


def test_original_grant_expiry_propagates_before_derived_grant_expires(monkeypatch):
    import aos_api.aip_production_contract_store as module
    with disposable_database() as connect:
        args,production,raw_body=seed(connect,monkeypatch)
        with connect(SCOPE) as conn: ref=record_metric_query_evidence(conn=conn,**args)
        request=ResolveEvidenceDisclosureRequest(evidenceRef=ref.model_dump(mode='json',by_alias=True),purpose='source',requestedLevel='l3',taskId=raw_body.task_id)
        derived=production.resolve_evidence_disclosure(SCOPE,'actor','derived-expiry',request,markings=args['markings'])
        original=production.get_evidence_disclosure(SCOPE,args['source_grants'][0]['decisionId'])
        at=original.expires_at+timedelta(microseconds=1)
        assert at<derived.expires_at
        class Clock(datetime):
            @classmethod
            def now(cls,tz=None): return at.astimezone(tz) if tz else at.replace(tzinfo=None)
        monkeypatch.setattr(module,'datetime',Clock)
        with connect(SCOPE) as conn:
            with pytest.raises(RuntimeError): production.read_disclosed_evidence_source(conn,SCOPE,'actor',derived.decision_id,request,markings=args['markings'])
        renewal=production.resolve_evidence_disclosure(SCOPE,'actor','after-expiry-renewal',raw_body,markings=args['markings'])
        assert renewal.status.value=='allowed'
        with connect(SCOPE) as conn:
            restored=production.read_disclosed_evidence_source(conn,SCOPE,'actor',derived.decision_id,request,markings=args['markings'])
            assert restored['evidenceRef']['resourceId']==ref.resource_id


def test_produced_evidence_flows_through_bundle_into_portrait_reader(monkeypatch):
    from aos_api.aip_production_contracts import BuildEvidenceBundleRequest
    from aos_api.ecommerce_analyst_analysis_sources import AnalysisBundleSourceRequest
    from aos_api.ecommerce_analyst_portrait_query_sources import read_portrait_metric_query
    with disposable_database() as connect:
        args,production,raw_body=seed(connect,monkeypatch)
        with connect(SCOPE) as conn:
            ref=record_metric_query_evidence(conn=conn,**args)
            insert(conn,'aip_task_brief_head',brief_id='portrait-brief',task_id=raw_body.task_id,current_revision=1)
            insert(conn,'aip_task_brief_revision',brief_id='portrait-brief',task_id=raw_body.task_id,revision=1,brief_type='analysis',schema_ref=dict(resourceType='Schema',resourceId='fixture',revision='1',authority='postgresql'),spec={},content_hash='d'*64,lifecycle='frozen',created_by='actor')
        job=AipAnalystQueryStore(connect_factory=connect).get(SCOPE,args['result_ref'].resource_id)
        bundle=production.build_evidence_bundle(SCOPE,'actor','auto-bundle',BuildEvidenceBundleRequest(briefRef=dict(resourceType='TaskBriefRevision',resourceId='portrait-brief',revision=1,contentHash='d'*64),cutoffAt=job.query.cutoff_at,itemRefs=[ref.model_dump(mode='json',by_alias=True)],requiredFactIds=[args['metric_ref'].resource_id],marking=['internal']))
        request=ResolveEvidenceDisclosureRequest(evidenceRef=ref.model_dump(mode='json',by_alias=True),purpose='source',requestedLevel='l3',taskId=raw_body.task_id)
        grant=production.resolve_evidence_disclosure(SCOPE,'actor','auto-grant',request,markings=args['markings'])
        bundle_request=AnalysisBundleSourceRequest(bundleRef=dict(resourceType='EvidenceBundleRevision',resourceId=bundle.bundle_id,revision=1,contentHash=bundle.content_hash),grants=[dict(decisionId=grant.decision_id,request=request)])
        with connect(SCOPE) as conn:
            query,result,material=read_portrait_metric_query(conn=conn,scope=SCOPE,task_id=raw_body.task_id,actor='actor',request=bundle_request,markings=args['markings'],now=datetime.now(timezone.utc),max_source_age=timedelta(days=1),max_bytes=100000,metric_ref=args['metric_ref'],result_ref=args['result_ref'],window_start=job.query.window_start,window_end=job.query.window_end,cutoff_at=job.query.cutoff_at)
            assert result==job.latest_result and material['items'][0]['evidenceRef']['resourceId']==ref.resource_id


def test_renewed_original_authorization_preserves_evidence_identity(monkeypatch):
    with disposable_database() as connect:
        args,production,raw_body=seed(connect,monkeypatch)
        with connect(SCOPE) as conn: first=record_metric_query_evidence(conn=conn,**args)
        renewed=production.resolve_evidence_disclosure(SCOPE,'actor','raw-renewed',raw_body,markings=args['markings'])
        args['source_grants']=[dict(decisionId=renewed.decision_id,request=raw_body.model_dump(mode='json',by_alias=True))]
        with connect(SCOPE) as conn:
            second=record_metric_query_evidence(conn=conn,**args)
            assert first==second
            payload=conn.execute('SELECT payload FROM aip_evidence WHERE evidence_id=%s',(first.resource_id,)).fetchone()['payload']
            assert 'sourceGrants' not in payload and payload['sourceRequests']==[raw_body.model_dump(mode='json',by_alias=True)]
        request=ResolveEvidenceDisclosureRequest(evidenceRef=first.model_dump(mode='json',by_alias=True),purpose='source',requestedLevel='l3',taskId=raw_body.task_id)
        derived=production.resolve_evidence_disclosure(SCOPE,'actor','renewed-derived',request,markings=args['markings'])
        assert derived.status.value=='allowed'


@pytest.mark.parametrize('kind,freshness',[('DatasetRevision','fresh'),('Evidence','unknown')])
def test_unimplemented_source_authority_is_not_upgraded(monkeypatch,kind,freshness):
    with disposable_database() as connect:
        args,_,_=seed(connect,monkeypatch,source_kind=kind,source_freshness=freshness)
        with connect(SCOPE) as conn:
            with pytest.raises(ValueError): record_metric_query_evidence(conn=conn,**args)
            assert conn.execute("SELECT count(*) AS n FROM aip_evidence WHERE source_type='aip-metric-query'").fetchone()['n']==0
