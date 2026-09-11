"""Pure descriptive-method applicability, never full metric quality readiness.

Inputs must first be read through current scoped authorities and disclosure.
Passing this check does not establish quality, reconciliation, denominators,
source ownership, Eval readiness or permission to dispatch a model.
"""
from datetime import datetime,timedelta

from aos_api.aip_analyst_contracts import MetricQueryRequest,QueryResultRevision
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_eval_contracts import MetricDefinitionRevision
from aos_api.ecommerce_analyst_authority_contracts import MethodRevision
from aos_api.ecommerce_analyst_authority_store import canonical_hash


def require_portrait_method_applicable(*,scope,method,metrics,queries,cutoff_at,now):
    if (any(not isinstance(t,datetime) or t.utcoffset() is None for t in (cutoff_at,now))
            or cutoff_at>now or not isinstance(metrics,list) or not 1<=len(metrics)<=100
            or not isinstance(queries,list) or len(queries)!=len(metrics)):
        raise ValueError('complete metric query inventory and aware frozen time required')
    method=MethodRevision.model_validate(method.model_dump())
    if ((method.tenant.org_id,method.tenant.project_id)!=scope.key or method.created_at>now
            or canonical_hash(method.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))!=method.content_hash):
        raise ValueError('descriptive method scope or content drifted')
    definitions=[MetricDefinitionRevision.model_validate(item.model_dump()) for item in metrics]
    if len({item.metric_id for item in definitions})!=len(definitions):
        raise ValueError('unique metric definitions required')
    age=timedelta(seconds=method.max_source_age_seconds)
    if now-cutoff_at>age: raise ValueError('frozen portrait cutoff exceeds method age')
    sources={}
    for definition,pair in zip(definitions,queries):
        if not isinstance(pair,(tuple,list)) or len(pair)!=2: raise ValueError('original metric request and result required')
        query=MetricQueryRequest.model_validate(pair[0].model_dump())
        result=QueryResultRevision.model_validate(pair[1].model_dump())
        if (canonical_hash(definition.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))!=definition.content_hash
                or (query.metric_ref.resource_type,query.metric_ref.resource_id,query.metric_ref.revision,query.metric_ref.authority)
                != ('MetricDefinitionRevision',definition.metric_id,str(definition.revision),'postgres:aip_metric_definition_revision')
                or (result.tenant.org_id,result.tenant.project_id)!=scope.key or result.kind!='metric' or result.status!='complete'
                or any(t.utcoffset() is None for t in (query.window_start,query.window_end,query.cutoff_at,result.created_at,result.cutoff_at))
                or query.cutoff_at!=cutoff_at or result.cutoff_at!=cutoff_at or result.created_at>now
                or result.content_hash!=AipAnalystQueryStore._result_hash(scope,query.model_dump(mode='json',by_alias=True),result)):
            raise ValueError('portrait metric query or definition content drifted')
        for source in result.source_refs:
            if (source.freshness!='fresh' or source.cutoff_at.utcoffset() is None
                    or source.cutoff_at>cutoff_at or now-source.cutoff_at>age):
                raise ValueError('original source exceeds descriptive method freshness')
            identity=(source.ref.resource_type,source.ref.resource_id,source.ref.authority)
            version=(source.ref.revision,source.content_hash)
            if identity in sources and sources[identity]!=version:
                raise ValueError('conflicting revisions of the same portrait source')
            sources[identity]=version
    if len(sources)<method.min_source_items:
        raise ValueError('distinct original sources do not meet method minimum')
