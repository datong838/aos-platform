"""Current D01 input composition, not a Provider or full quality authorization."""
from datetime import datetime,timedelta
import json
from aos_api.aip_contracts import AipContractModel
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analyst_analysis_sources import AnalysisBundleSourceRequest
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_portrait_sources import read_portrait_authorities
from aos_api.ecommerce_analyst_portrait_query_sources import read_portrait_metric_query
from aos_api.ecommerce_analyst_portrait_generation import portrait_prompt


class PortraitMetricSourceRequest(AipContractModel):
    metric_ref: AnalystExactRef
    result_ref: InvestigationExactRef
    source_request: AnalysisBundleSourceRequest
    window_start: datetime
    window_end: datetime


def read_portrait_inputs(*,conn,scope,run,actor,method_ref,eval_ref,metric_sources,cutoff_at,
                         markings,now,max_source_age,max_bytes):
    if (conn is None or type(actor) is not str or not actor or actor.strip()!=actor
        or type(max_bytes) is not int or not 1<=max_bytes<=2_000_000
        or not isinstance(max_source_age,timedelta) or max_source_age<=timedelta(0)
        or any(not isinstance(t,datetime) or t.utcoffset() is None for t in (now,cutoff_at))
        or not isinstance(metric_sources,list) or not 1<=len(metric_sources)<=100):
        raise ValueError('explicit bounded portrait input context required')
    if ((run.tenant.org_id,run.tenant.project_id)!=scope.key or run.request.skill.asset_type!='SkillTemplate'
        or run.request.skill.asset_id!='ecommerce.skill.D01'):
        raise ValueError('scoped D01 run required')
    items=[PortraitMetricSourceRequest.model_validate(item.model_dump() if isinstance(item,PortraitMetricSourceRequest) else item) for item in metric_sources]
    if len({item.metric_ref.resource_id for item in items})!=len(items):
        raise ValueError('unique D01 metric inventory required')
    refs=[method_ref,eval_ref,*[item.metric_ref for item in items],*[item.result_ref for item in items],
        *[item.source_request.bundle_ref for item in items]]
    declared={(r.resource_type,r.resource_id,r.revision,r.authority) for r in run.request.input_refs}
    required={(r.resource_type,r.resource_id,str(r.revision),'postgresql') for r in refs}
    if not required.issubset(declared):
        raise ValueError('D01 run did not declare complete exact input inventory')
    method,metrics,contract=read_portrait_authorities(conn=conn,scope=scope,method_ref=method_ref,
        metric_refs=[item.metric_ref for item in items],eval_ref=eval_ref,now=now)
    queries=[];materials=[];bundles={}
    for item in items:
        query,result,material=read_portrait_metric_query(conn=conn,scope=scope,task_id=run.task_id,actor=actor,
            request=item.source_request,markings=markings,now=now,max_source_age=max_source_age,max_bytes=max_bytes,
            metric_ref=item.metric_ref,result_ref=item.result_ref,window_start=item.window_start,window_end=item.window_end,cutoff_at=cutoff_at)
        queries.append((query,result))
        key=canonical_hash(item.source_request.bundle_ref.model_dump(mode='json',by_alias=True))
        if key in bundles and canonical_hash(bundles[key])!=canonical_hash(material):
            raise ValueError('same portrait bundle returned conflicting material')
        if key not in bundles:
            bundles[key]=material;materials.append(material)
        if len(json.dumps(materials,ensure_ascii=False,allow_nan=False,default=str).encode('utf-8'))>max_bytes:
            raise ValueError('complete portrait material exceeds byte limit')
    inputs=dict(scope=scope,method=method,metrics=metrics,queries=queries,contract=contract,materials=materials,cutoff_at=cutoff_at,now=now)
    portrait_prompt(**inputs)
    return inputs
