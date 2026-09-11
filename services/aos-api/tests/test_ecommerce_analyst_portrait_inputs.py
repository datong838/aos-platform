from datetime import timedelta
from types import SimpleNamespace
import pytest
import aos_api.ecommerce_analyst_portrait_inputs as module
from aos_api.ecommerce_analyst_portrait_generation import portrait_prompt
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from test_ecommerce_analyst_portrait_generation import fixture


def setup(monkeypatch):
    inputs=fixture(monkeypatch);method=inputs['method'];metric=inputs['metrics'][0];contract=inputs['contract'];query,result=inputs['queries'][0]
    def ref(kind,key,rev,digest):return AnalystExactRef(resourceType=kind,resourceId=key,revision=rev,contentHash=digest)
    source=inputs['materials'][0]
    item=module.PortraitMetricSourceRequest(metric_ref=ref('MetricDefinitionRevision',metric.metric_id,metric.revision,metric.content_hash),
        result_ref=InvestigationExactRef(resourceType='QueryResultRevision',resourceId=result.query_id,revision=1,contentHash='sha256:'+result.content_hash),
        source_request=dict(bundleRef=source['bundleRef'],grants=[dict(decisionId='grant',request=dict(evidenceRef=source['items'][0]['evidenceRef'],purpose='source',requestedLevel='l3',taskId='task'))]),
        window_start=query.window_start,window_end=query.window_end)
    method_ref=ref('MethodRevision',method.method_id,method.revision,method.content_hash)
    eval_ref=ref('EvalContractRevision',contract.contract_id,contract.revision,contract.content_hash)
    run=SimpleNamespace(tenant=method.tenant,task_id='task',request=SimpleNamespace(skill=SimpleNamespace(asset_type='SkillTemplate',asset_id='ecommerce.skill.D01'),
        input_refs=[SimpleNamespace(resource_type=r.resource_type,resource_id=r.resource_id,revision=str(r.revision),authority='postgresql')
            for r in [method_ref,eval_ref,item.metric_ref,item.result_ref,item.source_request.bundle_ref]]))
    conn=object();calls=[]
    def authorities(**args):
        assert args['conn'] is conn;calls.append('authorities')
        return method,[metric],contract
    def read_query(**args):
        assert args['conn'] is conn and args['task_id']=='task';calls.append('query')
        return query,result,source
    monkeypatch.setattr(module,'read_portrait_authorities',authorities)
    monkeypatch.setattr(module,'read_portrait_metric_query',read_query)
    return dict(conn=conn,scope=inputs['scope'],run=run,actor='actor',method_ref=method_ref,eval_ref=eval_ref,metric_sources=[item],
        cutoff_at=inputs['cutoff_at'],markings=['internal','secret'],now=inputs['now'],max_source_age=timedelta(days=1),max_bytes=2_000_000),inputs,calls


def test_same_transaction_complete_prompt_inputs(monkeypatch):
    args,original,calls=setup(monkeypatch)
    actual=module.read_portrait_inputs(**args)
    assert portrait_prompt(**actual)==portrait_prompt(**original)
    assert calls==['authorities','query']


@pytest.mark.parametrize('fault',['missing','revision','authority','scope','skill','duplicate','empty','bytes','clock','limit'])
def test_invalid_declarations_and_limits_rejected(monkeypatch,fault):
    args,_,calls=setup(monkeypatch)
    if fault=='missing':args['run'].request.input_refs.pop()
    if fault=='revision':args['run'].request.input_refs[0].revision='99'
    if fault=='authority':args['run'].request.input_refs[0].authority='untrusted'
    if fault=='scope':args['run'].tenant=args['run'].tenant.model_copy(update={'org_id':'dev-org'})
    if fault=='skill':args['run'].request.skill.asset_id='ecommerce.skill.D02'
    if fault=='duplicate':args['metric_sources']*=2
    if fault=='empty':args['metric_sources']=[]
    if fault=='bytes':args['max_bytes']=1
    if fault=='clock':args['now']=args['now'].replace(tzinfo=None)
    if fault=='limit':args['max_bytes']=True
    with pytest.raises(ValueError):module.read_portrait_inputs(**args)
    if fault!='bytes':assert not calls


def test_same_bundle_conflicting_material_rejected(monkeypatch):
    from copy import deepcopy
    args,_,_=setup(monkeypatch)
    second=args['metric_sources'][0].model_copy(deep=True)
    second.metric_ref.resource_id='second-metric'
    second.result_ref.resource_id='second-query'
    args['metric_sources'].append(second)
    for ref in (second.metric_ref,second.result_ref):
        args['run'].request.input_refs.append(SimpleNamespace(resource_type=ref.resource_type,resource_id=ref.resource_id,revision=str(ref.revision),authority='postgresql'))
    original=module.read_portrait_metric_query
    calls=0
    def conflict(**kwargs):
        nonlocal calls
        calls+=1
        query,result,material=original(**kwargs)
        material=deepcopy(material)
        if calls==2: material['items'][0]['payload']['unexpected']='changed'
        return query,result,material
    monkeypatch.setattr(module,'read_portrait_metric_query',conflict)
    with pytest.raises(ValueError,match='conflicting material'):
        module.read_portrait_inputs(**args)
