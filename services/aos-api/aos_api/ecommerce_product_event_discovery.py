"""Bounded routing candidates; never a source read or execution authorization."""
from uuid import UUID
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.pipeline_runtime_control_contracts import PipelineExactRef
from aos_api.tenant_scope import TenantScope
from aos_api.automation_occurrence_store import ClaimedOccurrence
from aos_api.ecommerce_product_event_origin import ProductEventOriginStore

_QUERY = '''SELECT h.schedule_policy_id AS policy_id,c.run_id,c.actor,
    sb.control_id,sb.control_revision,sb.control_hash
FROM ecommerce_investigation_schedule_policy_head h
JOIN automation_schedule_binding b ON b.org_id=h.org_id AND b.project_id=h.project_id
 AND b.policy_id=h.schedule_policy_id AND b.policy_revision=h.current_revision
 AND b.policy_hash=h.authority_data->>'contentHash'
JOIN pipeline_source_selection_revision s ON s.org_id=h.org_id AND s.project_id=h.project_id
 AND s.installation_id=b.installation_id AND s.generation=b.generation
 AND 'source-selection-'||s.selection_id::text=h.authority_data->'sourceSelectionRef'->>'resourceId'
 AND to_jsonb(s.revision)=h.authority_data->'sourceSelectionRef'->'revision'
 AND s.content_hash=h.authority_data->'sourceSelectionRef'->>'contentHash'
JOIN pipeline_controlled_source_claim c ON c.org_id=s.org_id AND c.project_id=s.project_id
 AND c.installation_id=s.installation_id AND c.generation=s.generation AND c.pipeline_id=s.pipeline_id
JOIN meta_schedule_run r ON r.org_id=c.org_id AND r.project_id=c.project_id AND r.id=c.run_id
JOIN meta_schedule m ON m.org_id=r.org_id AND m.project_id=r.project_id AND m.id=r.schedule_id
JOIN pipeline_schedule_control_binding sb ON sb.org_id=m.org_id AND sb.project_id=m.project_id
 AND sb.schedule_id=m.id AND sb.pipeline_id=c.pipeline_id AND sb.installation_id=c.installation_id
 AND sb.generation=c.generation AND sb.actor=c.actor
WHERE h.org_id=%s AND h.project_id=%s AND b.installation_id=%s AND b.generation=%s
 AND b.cadence='event' AND b.enabled AND b.approved
 AND b.effective_from<=clock_timestamp() AND b.effective_until>clock_timestamp()
 AND h.authority_data->>'schemaVersion'='aos.ecommerce.product-event-schedule-policy/v1'
 AND r.status='succeeded' AND r.executor_stopped AND r.executor_id='ec-live-v1' AND r.finished_at IS NOT NULL
 AND m.enabled AND m.pipeline_id=c.pipeline_id AND m.ingest->>'kind'='pipeline-live-v1'
 AND m.ingest->>'pipelineId'=c.pipeline_id
 AND NOT EXISTS(SELECT 1 FROM pipeline_schedule_control_binding newer
   WHERE newer.org_id=sb.org_id AND newer.project_id=sb.project_id
    AND newer.schedule_id=sb.schedule_id AND newer.revision>sb.revision)
 AND EXISTS(SELECT 1 FROM ecommerce_ingress_command i WHERE i.org_id=c.org_id AND i.project_id=c.project_id AND i.run_id=c.run_id)
 AND EXISTS(SELECT 1 FROM ecommerce_ingress_derived_command d WHERE d.org_id=c.org_id AND d.project_id=c.project_id AND d.run_id=c.run_id)
 AND EXISTS(SELECT 1 FROM ecommerce_ingress_dataset_receipt d WHERE d.org_id=c.org_id AND d.project_id=c.project_id AND d.run_id=c.run_id)
 AND (h.schedule_policy_id,c.run_id)>(%s,%s)
ORDER BY h.schedule_policy_id,c.run_id LIMIT %s'''


def _query_candidates(tx,scope,installation_id,generation,*,after=None,limit=100,exact=None):
    if type(scope) is not TenantScope or type(limit) is not int or not 1<=limit<=100:
        raise ValueError('bounded scoped event discovery required')
    if after is not None and (type(after) is not tuple or len(after)!=2 or any(
            type(value) is not str or not 1<=len(value)<=200 or value!=value.strip() or not value.isprintable() for value in after)):
        raise ValueError('event discovery cursor invalid')
    installation_id,generation=UUID(str(installation_id)),UUID(str(generation))
    if exact is not None and (type(exact) is not tuple or len(exact)!=3 or any(
            type(value) is not str or not 1<=len(value)<=240 or value!=value.strip() or not value.isprintable() for value in exact)):
        raise ValueError('exact original event route invalid')
    query=_QUERY if exact is None else _QUERY.replace('ORDER BY h.schedule_policy_id,c.run_id',
        'AND (h.schedule_policy_id,c.run_id,c.actor)=(%s,%s,%s) ORDER BY h.schedule_policy_id,c.run_id')
    rows=tx.execute(query,(*scope.key,installation_id,generation,*(after or ('','')),*(exact or ()),limit)).fetchall()
    results=[];seen=set()
    for row in rows:
        key=(row['policy_id'],row['run_id'])
        if key in seen or any(type(v) is not str or not 1<=len(v)<=200 or v!=v.strip() or not v.isprintable() for v in key):
            raise ValueError('event discovery identity is ambiguous')
        if type(row['actor']) is not str or not 1<=len(row['actor'])<=240 or row['actor']!=row['actor'].strip() or not row['actor'].isprintable():
            raise ValueError('event discovery actor invalid')
        seen.add(key)
        ref=PipelineExactRef(resource_type='PipelineRuntimeControlRevision',
            resource_id='pipeline-control-'+str(row['control_id']),revision=row['control_revision'],content_hash=row['control_hash'])
        results.append(dict(policyId=key[0],runId=key[1],actor=row['actor'],controlRef=ref.model_dump(mode='json',by_alias=True)))
    return tuple(results)


def discover_event_candidates(transaction,scope,installation_id,generation,*,after=None,limit=100):
    if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
        raise TypeError('exact scoped Host transaction required')
    identity=transaction.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,"
        "current_setting('aos.project_id',true) AS project_id").fetchone()
    if identity is None or (identity['role'],identity['org_id'],identity['project_id'])!=('aos_runtime',*scope.key):
        raise PermissionError('current event discovery runtime scope required')
    return _query_candidates(transaction,scope,installation_id,generation,after=after,limit=limit)


def discover_claim_origin(transaction,scope,claimed):
    if type(claimed) is not ClaimedOccurrence or claimed.operation_id!='ecommerce_growth_analysis_advance':
        raise ValueError('exact analysis claim required for origin routing')
    origin=ProductEventOriginStore(transaction,scope).read(claimed.occurrence_id)
    if origin is None:
        raise ValueError('claimed event has no original batch origin')
    rows=_query_candidates(transaction,scope,claimed.installation_id,claimed.generation,
        exact=(claimed.policy_id,origin['runId'],origin['actor']),limit=2)
    if len(rows)!=1:
        raise PermissionError('original event batch is not uniquely current')
    return rows[0]
