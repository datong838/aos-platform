"""Internal metric-query evidence projection with live original disclosure lineage.

No new query, metric, license or dispatch authority is created. Transactions are
owned by the caller. Only one level of evidence-backed metric queries is supported.
"""
from contextlib import contextmanager
from datetime import datetime
import json

from psycopg.types.json import Jsonb

from aos_api.aip_analyst_contracts import MetricQueryRequest
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_production_contracts import ExactRevisionRef, ResolveEvidenceDisclosureRequest
from aos_api.business_investigation_shared_contracts import InvestigationExactRef

TYPE = 'aip-metric-query'
SCHEMA = 'aos.metric-query-evidence/v1'


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _factory(conn, scope):
    @contextmanager
    def bound(requested):
        if requested != scope:
            raise ValueError('metric query evidence transaction scope mismatch')
        yield conn
    return bound


def _body(conn, scope, *, run_id, actor, metric_ref, result_ref, source_grants, markings, max_bytes=2_000_000):
    from aos_api.aip_production_contract_store import AipProductionContractStore, canonical_hash
    if (conn is None or type(actor) is not str or not actor or actor.strip()!=actor
            or type(run_id) is not str or not run_id.strip()
            or not isinstance(source_grants,list) or not 1<=len(source_grants)<=100):
        raise ValueError('explicit run, actor and complete source grants required')
    metric_ref=ExactRevisionRef.model_validate(metric_ref.model_dump())
    result_ref=InvestigationExactRef.model_validate(result_ref.model_dump())
    if metric_ref.resource_type!='MetricDefinitionRevision':
        raise ValueError('exact metric definition required')
    bound=_factory(conn,scope)
    definition=AipEvalAuthorityStore(bound).get_metric_definition(scope,metric_ref.resource_id,metric_ref.revision)
    if (definition.content_hash!=metric_ref.content_hash
            or canonical_hash(definition.model_dump(mode='json',by_alias=True,exclude={'content_hash'}))!=metric_ref.content_hash):
        raise ValueError('metric query definition drifted')
    run=conn.execute('SELECT task_id FROM public.aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s',(*scope.key,run_id)).fetchone()
    if run is None: raise ValueError('metric query evidence task run unavailable')
    owner=AipAnalystQueryStore(connect_factory=bound)
    result=owner.read_result_exact(scope,result_ref)
    if result is None: raise ValueError('metric query exact result unavailable')
    job=owner.get(scope,result_ref.resource_id)
    query=job.query
    if (not isinstance(query,MetricQueryRequest) or job.created_by!=actor or job.status!='succeeded'
            or job.latest_result is None or job.latest_result.revision!=result.revision
            or result.kind!='metric' or result.status!='complete'
            or (query.metric_ref.resource_type,query.metric_ref.resource_id,query.metric_ref.revision,query.metric_ref.authority)
            != ('MetricDefinitionRevision',metric_ref.resource_id,str(metric_ref.revision),'postgres:aip_metric_definition_revision')):
        raise ValueError('completed same-actor metric query required')
    wanted={}
    for source in result.source_refs:
        ref=source.ref
        if (ref.resource_type!='Evidence' or ref.revision!='1' or ref.authority!='postgres:aip_evidence'
                or ref.resource_id in wanted or source.freshness!='fresh'
                or source.cutoff_at.utcoffset() is None or source.cutoff_at>result.cutoff_at):
            raise ValueError('unique original Evidence query sources required')
        wanted[ref.resource_id]=source.content_hash
    grants={}
    for raw in source_grants:
        if type(raw) is not dict or set(raw)!={'decisionId','request'} or not isinstance(raw['decisionId'],str) or not raw['decisionId'].strip():
            raise ValueError('original source grant required')
        request=ResolveEvidenceDisclosureRequest.model_validate(raw['request'])
        ref=request.evidence_ref
        if (ref.resource_id in grants or ref.resource_type!='Evidence' or ref.revision!=1
                or wanted.get(ref.resource_id)!=ref.content_hash or request.task_id!=run['task_id']
                or request.purpose!='source' or request.requested_level!='l3'):
            raise ValueError('query source disclosure inventory or task drifted')
        grants[ref.resource_id]=(raw['decisionId'],request)
    if set(grants)!=set(wanted): raise ValueError('every query source requires original disclosure')
    labels={'internal'}
    production=AipProductionContractStore(bound)
    source_bytes=0
    for source in result.source_refs:
        decision_id,request=grants[source.ref.resource_id]
        row=conn.execute('SELECT source_type,octet_length(payload::text) AS payload_bytes FROM public.aip_evidence WHERE org_id=%s AND project_id=%s AND evidence_id=%s',(*scope.key,source.ref.resource_id)).fetchone()
        # Check before materialization: no recursive derived-evidence grant graph.
        if row is None or row['source_type']==TYPE:
            raise ValueError('query evidence requires non-derived original sources')
        source_bytes+=row['payload_bytes'] or 0
        if source_bytes>max_bytes: raise ValueError('complete original query sources exceed limit')
        material=production.read_disclosed_evidence_source(conn,scope,actor,decision_id,request,markings=markings)
        parent_labels=material['payload'].get('marking',['public'])
        if (not isinstance(parent_labels,list) or not parent_labels
                or any(not isinstance(x,str) or not x.strip() for x in parent_labels)):
            raise ValueError('original evidence markings unavailable')
        labels.update(parent_labels)
        labels.update(source.markings)
    labels.update(column.marking for column in result.columns if column.marking is not None)
    if any(not label.strip() for label in labels) or not labels.issubset(set(markings)):
        raise ValueError('query evidence classification access denied')
    return dict(schemaVersion=SCHEMA,taskRunId=run_id,taskId=run['task_id'],actor=actor,
        metricDefinitionRef=metric_ref.model_dump(mode='json',by_alias=True),queryResultRef=result_ref.model_dump(mode='json',by_alias=True),
        queryRequest=query.model_dump(mode='json',by_alias=True),queryResult=result.model_dump(mode='json',by_alias=True),
        sourceRequests=[grants[source.ref.resource_id][1].model_dump(mode='json',by_alias=True) for source in result.source_refs],
        factIds=[definition.metric_id],marking=sorted(labels),license=dict(status='allowed',allowedPurposes=['source']))


def validate_metric_query_evidence(conn,scope,actor,task_id,payload,*,markings):
    if (type(payload) is not dict or payload.get('schemaVersion')!=SCHEMA
            or payload.get('actor')!=actor or payload.get('taskId')!=task_id):
        raise ValueError('derived query evidence actor, task or schema drifted')
    from aos_api.aip_production_contract_store import canonical_hash
    requests=payload.get('sourceRequests')
    if not isinstance(requests,list) or not 1<=len(requests)<=100:
        raise ValueError('complete original query source requests required')
    grants=[]
    for raw in requests:
        request=ResolveEvidenceDisclosureRequest.model_validate(raw)
        receipt=conn.execute("""SELECT d.decision_id FROM public.aip_production_contract_receipt r
            JOIN public.aip_evidence_disclosure_decision d ON d.org_id=r.org_id AND d.project_id=r.project_id
            AND d.decision_id=r.result_ref->>'resourceId' AND d.decision_hash=r.result_ref->>'contentHash'
            WHERE r.org_id=%s AND r.project_id=%s AND r.operation='evidence_disclosure.resolve'
            AND r.created_by=%s AND r.request_hash=%s AND d.actor=%s
            AND d.status='allowed' AND d.expires_at>clock_timestamp()
            ORDER BY d.created_at DESC,d.decision_id DESC LIMIT 1""",
            (*scope.key,actor,canonical_hash(request.model_dump(mode='json',by_alias=True)),actor)).fetchone()
        if receipt is None: raise ValueError('current original source authorization unavailable')
        grants.append(dict(decisionId=receipt['decision_id'],request=request.model_dump(mode='json',by_alias=True)))
    expected=_body(conn,scope,run_id=payload.get('taskRunId'),actor=actor,
        metric_ref=ExactRevisionRef.model_validate(payload.get('metricDefinitionRef')),
        result_ref=InvestigationExactRef.model_validate(payload.get('queryResultRef')),
        source_grants=grants,markings=markings)
    if _canonical(expected)!=_canonical(payload):
        raise ValueError('derived query evidence canonical content drifted')


def record_metric_query_evidence(*,conn,scope,run_id,actor,metric_ref,result_ref,source_grants,now,max_bytes,markings):
    from aos_api.aip_production_contract_store import canonical_hash
    if (not isinstance(now,datetime) or now.utcoffset() is None
            or type(max_bytes) is not int or not 1<=max_bytes<=2_000_000):
        raise ValueError('explicit aware clock and bounded evidence size required')
    body=_body(conn,scope,run_id=run_id,actor=actor,metric_ref=metric_ref,result_ref=result_ref,source_grants=source_grants,markings=markings,max_bytes=max_bytes)
    metric_ref=ExactRevisionRef.model_validate(body['metricDefinitionRef'])
    result_ref=InvestigationExactRef.model_validate(body['queryResultRef'])
    if len(_canonical(body).encode('utf-8'))>max_bytes: raise ValueError('complete query evidence exceeds limit')
    row=conn.execute('SELECT status FROM public.aip_task_run WHERE org_id=%s AND project_id=%s AND run_id=%s FOR SHARE',(*scope.key,run_id)).fetchone()
    latest=conn.execute('SELECT max(revision) AS revision FROM public.aip_metric_definition_revision WHERE org_id=%s AND project_id=%s AND metric_id=%s',(*scope.key,metric_ref.resource_id)).fetchone()
    observed=datetime.fromisoformat(body['queryResult']['createdAt'])
    cutoff=datetime.fromisoformat(body['queryResult']['cutoffAt'])
    if row is None or row['status']!='running' or latest['revision']!=metric_ref.revision or observed>now:
        raise ValueError('running task, current metric and completed query time required')
    digest=canonical_hash(body)
    ref=ExactRevisionRef(resourceType='Evidence',resourceId='evidence-metric-query-'+digest,revision=1,contentHash=digest)
    subject=body['queryResultRef']
    conn.execute('''INSERT INTO public.aip_evidence
        (org_id,project_id,evidence_id,run_id,evidence_type,subject_ref,source_type,source_ref,
        observed_at,freshness_at,content_hash,redaction,payload,created_by,created_at)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'{}'::jsonb,%s,%s,clock_timestamp())
        ON CONFLICT(org_id,project_id,evidence_id) DO NOTHING''',
        (*scope.key,ref.resource_id,run_id,TYPE,Jsonb(subject),TYPE,result_ref.resource_id,observed,cutoff,digest,Jsonb(body),actor))
    saved=conn.execute('''SELECT e.*,EXISTS(SELECT 1 FROM public.aip_evidence_revoke_event r
        WHERE r.org_id=e.org_id AND r.project_id=e.project_id AND r.evidence_id=e.evidence_id
        AND r.revision=1 AND r.content_hash=e.content_hash) AS revoked FROM public.aip_evidence e
        WHERE org_id=%s AND project_id=%s AND evidence_id=%s''',(*scope.key,ref.resource_id)).fetchone()
    expected=dict(org_id=scope.org_id,project_id=scope.project_id,evidence_id=ref.resource_id,run_id=run_id,
        evidence_type=TYPE,subject_ref=subject,source_type=TYPE,source_ref=result_ref.resource_id,
        observed_at=observed,freshness_at=cutoff,content_hash=digest,redaction={},payload=body,created_by=actor)
    if (saved is None or saved['revoked']
            or not isinstance(saved['created_at'],datetime) or saved['created_at'].utcoffset() is None
            or saved['created_at']<observed or any(saved[k]!=v for k,v in expected.items()) or canonical_hash(saved['payload'])!=digest):
        raise ValueError('metric query evidence persistence drifted or revoked')
    return ref
