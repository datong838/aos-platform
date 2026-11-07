"""Bind a metric query to complete disclosed evidence, without deriving values.

The caller must also read current portrait authorities in this transaction.
This internal reader is neither metric-card readiness nor Provider authority.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta
import json

from aos_api.aip_analyst_contracts import MetricQueryRequest, QueryResultRevision
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_analyst_analysis_sources import read_analysis_bundle
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def read_portrait_metric_query(*, conn, scope, task_id, actor, request, markings,
                               now, max_source_age, max_bytes, metric_ref,
                               result_ref, window_start, window_end, cutoff_at):
    metric_ref = AnalystExactRef.model_validate(metric_ref.model_dump())
    result_ref = InvestigationExactRef.model_validate(result_ref.model_dump())
    times = (now, window_start, window_end, cutoff_at)
    if (conn is None or any(not isinstance(t, datetime) or t.utcoffset() is None for t in times)
            or not isinstance(max_source_age, timedelta) or max_source_age <= timedelta(0)
            or not window_start < window_end <= cutoff_at <= now
            or now - cutoff_at > max_source_age
            or metric_ref.resource_type != 'MetricDefinitionRevision'
            or result_ref.resource_type != 'QueryResultRevision'
            or type(result_ref.revision) is not int or result_ref.receipt_id is not None):
        raise ValueError('exact metric query, aware frozen window and current lifetime required')
    # Authorize the entire source bundle before fetching any extra query body.
    material = read_analysis_bundle(conn=conn, scope=scope, task_id=task_id, actor=actor,
        request=request, markings=markings, now=now, max_source_age=max_source_age, max_bytes=max_bytes)
    if datetime.fromisoformat(material['cutoffAt']) != cutoff_at:
        raise ValueError('portrait query and evidence must share the frozen cutoff')

    @contextmanager
    def bound(requested_scope):
        if requested_scope != scope:
            raise ValueError('portrait query transaction scope mismatch')
        yield conn

    owner = AipAnalystQueryStore(connect_factory=bound)
    result = owner.read_result_exact(scope, result_ref)
    if result is None:
        raise ValueError('exact portrait query result unavailable')
    result = QueryResultRevision.model_validate(result.model_dump())
    job = owner.get(scope, result_ref.resource_id)
    query = job.query
    if (not isinstance(query, MetricQueryRequest)
            or (job.tenant.org_id, job.tenant.project_id) != scope.key
            or job.query_id != result_ref.resource_id or job.status != 'succeeded'
            or job.latest_result is None or job.latest_result.revision != result_ref.revision
            or (result.tenant.org_id, result.tenant.project_id) != scope.key
            or result.query_id != result_ref.resource_id or result.revision != result_ref.revision
            or 'sha256:' + result.content_hash != result_ref.content_hash
            or result.kind != 'metric' or result.status != 'complete'
            or result.cutoff_at != cutoff_at or result.created_at > now
            or query.cutoff_at != cutoff_at or query.window_start != window_start or query.window_end != window_end
            or (query.metric_ref.resource_type, query.metric_ref.resource_id, query.metric_ref.revision, query.metric_ref.authority)
                != ('MetricDefinitionRevision', metric_ref.resource_id, str(metric_ref.revision), 'postgres:aip_metric_definition_revision')):
        raise ValueError('portrait metric query identity, completion or frozen window mismatch')
    for source in result.source_refs:
        if (source.freshness != 'fresh' or source.cutoff_at.utcoffset() is None
                or source.cutoff_at > cutoff_at or now - source.cutoff_at > max_source_age):
            raise ValueError('portrait query has stale or unknown source material')
    expected = _json(result.model_dump(mode='json', by_alias=True))
    matches = []
    for item in material['items']:
        payload = item['payload']
        if (isinstance(payload, dict) and _json(payload.get('metricDefinitionRef')) == _json(metric_ref.model_dump(mode='json', by_alias=True))
                and _json(payload.get('queryResult')) == expected
                and _json(payload.get('queryRequest')) == _json(query.model_dump(mode='json', by_alias=True))):
            matches.append(payload)
    if len(matches) != 1:
        raise ValueError('one complete disclosed query snapshot with exact metric definition required')
    labels = matches[0].get('marking')
    if not isinstance(labels, list) or not labels or any(not isinstance(x, str) or not x.strip() for x in labels):
        raise ValueError('explicit disclosed query markings required')
    required = {label for source in result.source_refs for label in source.markings}
    required.update(column.marking for column in result.columns if column.marking is not None)
    if any(not label.strip() for label in required) or not required.issubset(set(labels)):
        raise ValueError('query source and column markings cannot be downgraded')
    return query, result, material
