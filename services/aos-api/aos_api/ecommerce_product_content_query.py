"""Fixed preparation counts, explicitly partial until source readiness is proven."""
from datetime import timedelta
from aos_api.aip_analyst_contracts import CreateQueryJobRequest,MetricQueryRequest,QueryResultRevision,RecordQueryResultRequest
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_eval_contracts import MetricDefinitionRevision
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_fixed_metric import fixed_metric
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_content_evidence import ProductContentEvidenceStore
from aos_api.tenant_scope import TenantScope


def definition():
    body=dict(metricId='niushop.product-content-preparation-counts',revision=1,name='商品内容准备观察计数',
        unit='count',source='exact-product-content-evidence',window='source-read-interval',
        aggregation='observed-eligible-joint-valid-positive-stock/v1',acceptedQuality=['measured'])
    return MetricDefinitionRevision(**body,contentHash=canonical_hash(body))


class ProductContentQueryService:
    def __init__(self,transaction,scope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError('product query requires HostTransaction and TenantScope')
        self.tx,self.scope=transaction,scope
        self.connect=TransactionBoundConnectFactory(transaction,scope)
        self.evidence=ProductContentEvidenceStore(transaction,scope)

    def _request(self,ref,*,ensure=False):
        saved=self.evidence.read_exact(ref)
        original=saved.snapshot.quality.observation_ref
        observation=ConfiguredObservationEvidenceStore(self.tx,self.scope).read_exact(InvestigationExactRef(
            resource_type=original[0],resource_id=original[1],revision=original[2],content_hash=original[3])).observation.observation
        metric=fixed_metric(self.tx,self.scope,definition(),actor='system:product-content-query',ensure=ensure)
        request=MetricQueryRequest(metric_ref=metric,filters=[dict(field='productContentEvidence',operator='eq',value=ref.model_dump(mode='json',by_alias=True))],
            window_start=observation.read_started_at,window_end=observation.read_finished_at,cutoff_at=observation.read_finished_at)
        return saved,request

    def _result(self,ref,saved,request,query_id,now):
        quality=saved.snapshot.quality
        values=dict(observed=quality.observed_count,eligible=quality.eligible_count,jointValid=quality.joint_valid_count,
            preparable=saved.snapshot.preparable_product_count)
        result=QueryResultRevision(tenant=dict(orgId=self.scope.org_id,projectId=self.scope.project_id),query_id=query_id,
            revision=1,kind='metric',status='partial',columns=[dict(key=k,label=label,valueType='number',marking='internal')
                for k,label in [('observed','观察行数'),('eligible','质量检查行数'),('jointValid','全部字段合格商品数'),('preparable','有库存内容准备商品数')]],
            rows=[dict(rowId='observed-product-population',values=values)],source_refs=[dict(ref=ResourceRef(resource_type='Evidence',
                resource_id=ref.resource_id,revision='1',authority='postgres:aip_evidence'),content_hash=ref.content_hash,
                cutoff_at=request.cutoff_at,freshness='unknown',markings=['internal'])],lineage_refs=[request.metric_ref],
            uncertainties=[*saved.snapshot.limitations,'上游新鲜度和连接身份未经证明，不可用作ready经营事实'],
            confidence=dict(status='not_applicable',score=None,basis=['固定观察计数，不作经营收益或质量评分']),
            cutoff_at=request.cutoff_at,created_at=now,content_hash='0'*64)
        return result.model_copy(update={'content_hash':AipAnalystQueryStore._result_hash(self.scope,request.model_dump(mode='json',by_alias=True),result)})

    def execute(self,*,evidence_ref,idempotency_key,actor):
        if any(type(v) is not str or not v or v.strip()!=v or len(v)>200 for v in (idempotency_key,actor)):
            raise ValueError('canonical query identity required')
        self.tx.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
            (canonical_hash([*self.scope.key,'product-content-query',idempotency_key]),))
        saved,request=self._request(evidence_ref,ensure=True)
        now=self.tx.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        store=AipAnalystQueryStore(connect_factory=self.connect,clock=lambda:now)
        job=store.create(self.scope,CreateQueryJobRequest(query=request,deadline_at=request.cutoff_at+timedelta(days=1)),idempotency_key=idempotency_key,actor=actor)
        job=store.get(self.scope,job.query_id)
        if job.latest_result is None:
            if now>=job.deadline_at: raise ValueError('product preparation query deadline expired')
            result=self._result(evidence_ref,saved,request,job.query_id,now)
            job=store.record_result(self.scope,job.query_id,RecordQueryResultRequest(expected_sequence=job.latest_sequence,result=result),idempotency_key=idempotency_key,actor=actor)
        result=job.latest_result
        ref=InvestigationExactRef(resource_type='QueryResultRevision',resource_id=result.query_id,revision=result.revision,content_hash='sha256:'+result.content_hash)
        self.read_exact(ref)
        return ref

    def read_exact(self,ref):
        store=AipAnalystQueryStore(connect_factory=self.connect)
        result=store.read_result_exact(self.scope,ref)
        if result is None: raise ValueError('product preparation query unavailable')
        job=store.get(self.scope,ref.resource_id)
        if not isinstance(job.query,MetricQueryRequest) or len(job.query.filters)!=1:
            raise ValueError('product preparation request drifted')
        source=ExactRevisionRef.model_validate(job.query.filters[0].value)
        saved,request=self._request(source)
        expected=self._result(source,saved,request,result.query_id,result.created_at)
        if (canonical_hash(job.query.model_dump(mode='json',by_alias=True))!=canonical_hash(request.model_dump(mode='json',by_alias=True))
            or expected!=result or job.deadline_at!=request.cutoff_at+timedelta(days=1) or result.created_at>=job.deadline_at):
            raise ValueError('product preparation result drifted')
        return result
