from datetime import timedelta
from copy import deepcopy
import pytest

from aos_api.ecommerce_analyst_portrait_method import require_portrait_method_applicable
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from test_ecommerce_analyst_portrait_query_sources import setup,SCOPE
from test_ecommerce_analyst_portrait_sources import metric
from test_ecommerce_analyst_method_authority import method,hashed


def inputs(monkeypatch):
    with monkeypatch.context() as patch: args,state=setup(patch)
    definition=metric(); revision=method()
    query=state['query'];query.metric_ref.resource_id=definition.metric_id
    result=state['result'];result.content_hash=AipAnalystQueryStore._result_hash(SCOPE,query.model_dump(mode='json',by_alias=True),result)
    return dict(scope=SCOPE,method=revision,metrics=[definition],queries=[(query,result)],cutoff_at=args['cutoff_at'],now=revision.created_at+timedelta(seconds=1))


def rehash(args):
    for query,result in args['queries']:
        result.content_hash=AipAnalystQueryStore._result_hash(SCOPE,query.model_dump(mode='json',by_alias=True),result)


def test_method_applicability_does_not_return_quality_ready_or_values(monkeypatch):
    args=inputs(monkeypatch)
    assert require_portrait_method_applicable(**args) is None


@pytest.mark.parametrize('problem',['method_hash','method_scope','metric_hash','empty','duplicate_metric','missing_query','wrong_metric','result_scope','result_hash','cutoff','future_result','unknown_source','old_source','future_source','clock'])
def test_inapplicable_or_drifted_inputs_fail(monkeypatch,problem):
    args=inputs(monkeypatch);query,result=args['queries'][0]
    if problem=='method_hash': args['method'].content_hash='d'*64
    elif problem=='method_scope': args['method']=hashed(args['method'].model_copy(update={'tenant':args['method'].tenant.model_copy(update={'org_id':'dev-org'})}))
    elif problem=='metric_hash': args['metrics'][0].content_hash='d'*64
    elif problem=='empty': args['metrics']=[];args['queries']=[]
    elif problem=='duplicate_metric': args['metrics']*=2;args['queries']*=2
    elif problem=='missing_query': args['queries']=[]
    elif problem=='wrong_metric': query.metric_ref.resource_id='other';rehash(args)
    elif problem=='result_scope': result.tenant.org_id='dev-org'
    elif problem=='result_hash': result.content_hash='f'*64
    elif problem=='cutoff': args['cutoff_at']-=timedelta(seconds=1)
    elif problem=='future_result': result.created_at=args['now']+timedelta(seconds=1)
    elif problem=='unknown_source': result.source_refs[0].freshness='unknown';rehash(args)
    elif problem=='old_source': result.source_refs[0].cutoff_at=args['now']-timedelta(seconds=86401);rehash(args)
    elif problem=='future_source': result.source_refs[0].cutoff_at=args['cutoff_at']+timedelta(seconds=1);rehash(args)
    elif problem=='clock': args['now']=args['now'].replace(tzinfo=None)
    with pytest.raises(ValueError): require_portrait_method_applicable(**args)


@pytest.mark.parametrize('conflict',[False,True])
def test_reused_source_does_not_inflate_minimum_and_conflicting_revision_is_rejected(monkeypatch,conflict):
    args=inputs(monkeypatch)
    args['method']=hashed(args['method'].model_copy(update={'min_source_items':2}))
    second=hashed(args['metrics'][0].model_copy(update={'metric_id':'second-metric'}))
    query,result=deepcopy(args['queries'][0]);query.metric_ref.resource_id=second.metric_id;result.query_id='second-query'
    if conflict: result.source_refs[0].ref.revision='2'
    args['metrics'].append(second);args['queries'].append((query,result));rehash(args)
    with pytest.raises(ValueError): require_portrait_method_applicable(**args)
    if not conflict:
        result.source_refs[0].ref.resource_id='different-source';rehash(args)
        assert require_portrait_method_applicable(**args) is None


def test_oldest_source_exact_age_boundary(monkeypatch):
    args=inputs(monkeypatch)
    source=args['queries'][0][1].source_refs[0]
    source.cutoff_at=args['now']-timedelta(seconds=86400);rehash(args)
    assert require_portrait_method_applicable(**args) is None
    args['now']+=timedelta(microseconds=1)
    with pytest.raises(ValueError): require_portrait_method_applicable(**args)
