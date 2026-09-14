"""Fixed structural fact counts from a currently authenticated complete snapshot."""
from datetime import datetime
import json

from aos_api.aip_analyst_contracts import CreateQueryJobRequest,MetricQueryRequest,QueryResultRevision,RecordQueryResultRequest
from aos_api.aip_analyst_query_store import AipAnalystQueryStore, _hash
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_eval_contracts import MetricDefinitionRevision
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_analysis_snapshot_source_evidence import AnalysisSnapshotSourceEvidence, _subject
from aos_api.ecommerce_fixed_metric import fixed_metric
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory

_VERSION='snapshot-fact-structure-and-reference-counts/v1'
_UNCERTAINTIES=['仅计量字段结构、业务窗口与引用覆盖，不证明成交、利润或金额对账',
    '逐类事实独立计数；空分母及未知行保留，不能据此判定经营质量通过']
_CONFIDENCE=dict(status='not_applicable',score=None,basis=['固定结构计数，不作经营评分'])
_COLUMNS=[dict(key=k,label=label,valueType=kind) for k,label,kind in (
    ('fact','事实类型','string'),('observedCount','观察行数','number'),('eligibleCount','范围内分母','number'),
    ('validCount','联合有效行数','number'),('excludedCount','排除行数','number'),('duplicateCount','重复行数','number'),
    ('unknownRows','范围未知行数','number'),('fieldIssues','字段缺口','string'),('relationshipIssues','关系缺口','string'))]


def _definition():
    body=dict(metricId='ecommerce.snapshot-fact-structure-counts',revision=1,name='完整快照逐类事实结构计数',
        unit='count',source='analysis-snapshot-fact-source',window='original-data-requirement',
        aggregation=_VERSION,acceptedQuality=['measured'])
    return MetricDefinitionRevision(**body,contentHash=canonical_hash(body))


def _resource(ref):
    return ResourceRef(resource_type='Evidence',resource_id=ref.resource_id,revision=str(ref.revision),authority='postgres:aip_evidence')


def _ref(result):
    return InvestigationExactRef(resource_type='QueryResultRevision',resource_id=result.query_id,
        revision=result.revision,content_hash='sha256:'+result.content_hash)


class AnalysisSnapshotFactQuery:
    def __init__(self, source):
        if type(source) is not AnalysisSnapshotSourceEvidence:raise TypeError('original snapshot source Owner required')
        self.source=source
        self.scope=source.analysis.scope

    def _prepare(self,tx,body,evidence,*,ensure=False):
        now=tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        requirement=body['fieldContext']['requirement']
        deadline=datetime.fromisoformat(requirement['expiresAt'])
        if deadline.utcoffset() is None or now>=deadline:raise ValueError('snapshot query requirement expired')
        metric=fixed_metric(tx,self.scope,_definition(),actor=body['actor'],ensure=ensure)
        query=MetricQueryRequest(metric_ref=metric,dimensions=[],selection_refs=[],
            filters=[dict(field='snapshotEvidence',operator='eq',value=evidence.model_dump(mode='json',by_alias=True,exclude_none=True)),
                dict(field='requirement',operator='eq',value=_subject(body)),
                dict(field='rule',operator='eq',value=_VERSION)],
            window_start=requirement['timeWindow']['startAt'],window_end=requirement['timeWindow']['endAt'],cutoff_at=requirement['cutoffAt'])
        request=CreateQueryJobRequest(query=query,deadline_at=deadline)
        key='snapshot-fact-query-'+canonical_hash(dict(tenant=self.scope.key,evidence=query.filters[0].value,rule=_VERSION))
        store=AipAnalystQueryStore(connect_factory=TransactionBoundConnectFactory(tx,self.scope),clock=lambda:now)
        return store,request,key,now

    def _result(self,store,request,body,evidence,query_id,created_at):
        facts=body['fieldContext']['measurement']['facts']
        rows=[dict(rowId=fact,values=dict(fact=fact,**value['counts'],unknownRows=value['unknownRows'],
            fieldIssues=json.dumps(value['fieldIssues'],ensure_ascii=False,sort_keys=True,separators=(',',':')),
            relationshipIssues=json.dumps(value['relationshipIssues'],ensure_ascii=False,sort_keys=True,separators=(',',':'))))
            for fact,value in sorted(facts.items())]
        result=QueryResultRevision(tenant=body['tenant'],query_id=query_id,revision=1,kind='metric',status='partial',
            columns=_COLUMNS,rows=rows,source_refs=[dict(ref=_resource(evidence),content_hash=evidence.content_hash[7:],
                cutoff_at=request.query.cutoff_at,freshness='unknown',markings=['internal'])],
            lineage_refs=[request.query.metric_ref],uncertainties=_UNCERTAINTIES,confidence=_CONFIDENCE,
            cutoff_at=request.query.cutoff_at,created_at=created_at,content_hash='0'*64)
        return result.model_copy(update={'content_hash':store._result_hash(self.scope,request.query.model_dump(mode='json',by_alias=True),result)})

    def execute_current(self,conn,*,evidence_ref):
        evidence=InvestigationExactRef.model_validate(evidence_ref)
        def execute(body):
            tx=HostTransaction(conn)
            store,request,key,now=self._prepare(tx,body,evidence,ensure=True)
            tx.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(json.dumps([*self.scope.key,key]),))
            job=store.create(self.scope,request,idempotency_key=key,actor=body['actor'])
            job=store.get(self.scope,job.query_id)
            if job.latest_result is None:
                result=self._result(store,request,body,evidence,job.query_id,now)
                job=store.record_result(self.scope,job.query_id,RecordQueryResultRequest(expected_sequence=job.latest_sequence,result=result),
                    idempotency_key=key,actor=body['actor'])
            ref=_ref(job.latest_result)
            self._read(tx,body,evidence,ref)
            return ref
        return self.source.run_current(conn,evidence_ref=evidence,execute=execute)

    def read_current(self,conn,*,result_ref,evidence_ref):
        evidence=InvestigationExactRef.model_validate(evidence_ref)
        ref=InvestigationExactRef.model_validate(result_ref)
        return self.source.run_current(conn,evidence_ref=evidence,
            execute=lambda body:self._read(HostTransaction(conn),body,evidence,ref))

    def _read(self,tx,body,evidence,ref):
        store,request,key,now=self._prepare(tx,body,evidence)
        result=store.read_result_exact(self.scope,ref)
        if result is None:raise LookupError('snapshot query result unavailable')
        job=store.get(self.scope,ref.resource_id)
        raw=tx.execute('''SELECT r.result_json,j.request_json,j.idempotency_key FROM public.aip_analyst_query_result_revision r
            JOIN public.aip_analyst_query_job j ON (r.org_id,r.project_id,r.query_id)=(j.org_id,j.project_id,j.query_id)
            WHERE r.org_id=%s AND r.project_id=%s AND r.query_id=%s AND r.revision=%s''',
            (*self.scope.key,ref.resource_id,ref.revision)).fetchone()
        expected=self._result(store,request,body,evidence,result.query_id,result.created_at)
        if (raw is None or raw['idempotency_key']!=key
            or canonical_hash(raw['result_json'])!=canonical_hash(expected.model_dump(mode='json',by_alias=True))
            or canonical_hash(raw['request_json'])!=canonical_hash(request.query.model_dump(mode='json',by_alias=True))
            or result!=expected or job.query!=request.query or job.deadline_at!=request.deadline_at
            or job.created_by!=body['actor'] or job.status.value!='succeeded' or job.latest_result!=result
            or job.request_hash!=_hash(dict(scope=self.scope.key,request=request.model_dump(mode='json',by_alias=True),actor=body['actor']))
            or not job.created_at<=result.created_at<request.deadline_at or result.created_at>now):
            raise ValueError('snapshot query exact request or result drifted')
        return result
