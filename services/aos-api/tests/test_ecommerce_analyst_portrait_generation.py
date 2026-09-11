import json
from copy import deepcopy
from hashlib import sha256
import pytest
from aos_api.ecommerce_analyst_portrait_generation import portrait_prompt,insight_from_completed_generation
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.aip_agent_run_executor import AipAgentRunExecutor
from aos_api.aip_agent_run_execution_contracts import ExecuteAgentRunRequest
from test_ecommerce_analyst_portrait_method import inputs as method_inputs
from test_ecommerce_analyst_portrait_sources import setup,exact
from test_ecommerce_analyst_growth_plan_draft import generation


def fixture(monkeypatch):
    args=method_inputs(monkeypatch)
    with monkeypatch.context() as patch: _,state,_=setup(patch)
    args['contract']=state['contract'].model_copy(update={'created_at':args['now']})
    metric=args['metrics'][0];request,result=args['queries'][0]
    payload=dict(queryRequest=request.model_dump(mode='json',by_alias=True),queryResult=result.model_dump(mode='json',by_alias=True),
        metricDefinitionRef=exact('MetricDefinitionRevision',metric.metric_id,metric.content_hash).model_dump(mode='json',by_alias=True),marking=['internal'])
    args['materials']=[dict(bundleRef=exact('EvidenceBundleRevision','bundle','b'*64).model_dump(mode='json',by_alias=True),
        cutoffAt=args['cutoff_at'].isoformat(),items=[dict(evidenceRef=exact('Evidence','source',canonical_hash(payload)).model_dump(mode='json',by_alias=True),
        disclosureRef=exact('EvidenceDisclosureDecision','grant','c'*64).model_dump(mode='json',by_alias=True),expiresAt=args['now'].isoformat(),payload=payload)])]
    return args


def completed(args,source_indices=None):
    query,system=portrait_prompt(**args)
    _,attempt,_=generation()
    answer=json.dumps(dict(summary='观察到商品准备依据',assumptions=[],uncertainty='未证明经营增长',sourceIndices=source_indices or [0],metricIndices=[0]),ensure_ascii=False)
    artifact=attempt.output_artifact_ref.model_copy(update={'content_hash':sha256(answer.encode()).hexdigest()})
    attempt=attempt.model_copy(update={'output_artifact_ref':artifact,'tenant':args['method'].tenant,'completed_at':args['now']})
    request=ExecuteAgentRunRequest(expectedAgentRunVersion=attempt.agent_run_version,attemptId=attempt.attempt_id,attemptNo=attempt.attempt_no,
        budgetRef=attempt.budget_ref,capacityReservationRef=attempt.capacity_reservation_ref,query=query,systemPrompt=system,dataClassification=attempt.data_classification)
    return attempt.model_copy(update={'request_hash':AipAgentRunExecutor._request_hash(attempt.agent_run_id,request)}),answer


def test_stable_original_portrait_and_renewable_metadata(monkeypatch):
    args=fixture(monkeypatch);attempt,answer=completed(args)
    value=insight_from_completed_generation(attempt=attempt,answer=answer,actor='compiler',**args)
    assert value==insight_from_completed_generation(attempt=attempt,answer=answer,actor='compiler',**args)
    assert value.kind.value=='observation' and value.generation_artifact_ref.content_hash==sha256(answer.encode()).hexdigest()
    original=portrait_prompt(**args)
    args['materials'][0]['items'][0]['disclosureRef']['resourceId']='renewed'
    assert portrait_prompt(**args)==original


@pytest.mark.parametrize('fault',['missing','duplicate','body','query','oversize','eval','freshness'])
def test_drifted_inputs_rejected(monkeypatch,fault):
    args=fixture(monkeypatch);item=args['materials'][0]['items'][0]
    if fault=='missing': args['materials']=[]
    if fault=='duplicate': args['materials']*=2
    if fault=='body': item['payload']['extra']='drift'
    if fault=='query':
        item['payload'].pop('queryRequest');item['evidenceRef']['contentHash']=canonical_hash(item['payload'])
    if fault=='oversize':
        item['payload']['extra']='字'*16000;item['evidenceRef']['contentHash']=canonical_hash(item['payload'])
    if fault=='eval': args['contract']=args['contract'].model_copy(update={'lifecycle':'draft'})
    if fault=='freshness': args['queries'][0][1].source_refs[0].freshness='unknown'
    with pytest.raises(ValueError):portrait_prompt(**args)


@pytest.mark.parametrize('fault',['answer','request','receipt','actor','unknown','artifact'])
def test_unproven_attempt_rejected(monkeypatch,fault):
    args=fixture(monkeypatch);attempt,answer=completed(args);actor='compiler'
    if fault=='answer':answer+=' '
    if fault=='request':attempt=attempt.model_copy(update={'request_hash':'d'*64})
    if fault=='receipt':attempt=attempt.model_copy(update={'provider_receipt_id':None})
    if fault=='actor':actor='other'
    if fault=='unknown':attempt=attempt.model_copy(update={'status':'unknown'})
    if fault=='artifact':attempt=attempt.model_copy(update={'output_artifact_ref':None})
    with pytest.raises(ValueError):insight_from_completed_generation(attempt=attempt,answer=answer,actor=actor,**args)


def test_legacy_insight_serialization_unchanged():
    from test_ecommerce_analyst_authority_contracts import insight
    from aos_api.ecommerce_analyst_authority_contracts import InsightRevision
    value=InsightRevision.model_validate(insight())
    assert 'generationArtifactRef' not in value.model_dump(mode='json',by_alias=True)
    assert 'generation_artifact_ref' not in value.model_dump(mode='json')


def test_selected_metric_must_keep_its_supporting_bundle(monkeypatch):
    args=fixture(monkeypatch)
    other=deepcopy(args['materials'][0]);other['bundleRef']['resourceId']='unrelated-bundle'
    item=other['items'][0];item['payload']={'note':'unrelated source'}
    item['evidenceRef']['resourceId']='unrelated-source';item['evidenceRef']['contentHash']=canonical_hash(item['payload'])
    args['materials'].append(other)
    attempt,answer=completed(args,[1])
    with pytest.raises(ValueError,match='selected source support'):
        insight_from_completed_generation(attempt=attempt,answer=answer,actor='compiler',**args)


def test_completion_cannot_predate_sources(monkeypatch):
    from datetime import timedelta
    args=fixture(monkeypatch);attempt,answer=completed(args)
    attempt=attempt.model_copy(update={'completed_at':args['cutoff_at']-timedelta(seconds=1)})
    with pytest.raises(ValueError,match='predates'):
        insight_from_completed_generation(attempt=attempt,answer=answer,actor='compiler',**args)
