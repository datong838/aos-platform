"""Fixed joint source-row quality query; never a business fulfillment authority."""
from datetime import timedelta
import json

from aos_api.aip_analyst_contracts import (
    CreateQueryJobRequest, MetricQueryRequest, QueryResultRevision, RecordQueryResultRequest,
)
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_contracts import ResourceRef
from aos_api.ecommerce_fixed_metric import fixed_metric
from aos_api.aip_eval_contracts import MetricDefinitionRevision
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_joint_quality import ProductJointQualityReader, _RULE
from aos_api.tenant_scope import TenantScope

_FIELDS = (("identity", "商品身份"), ("title", "标题"), ("availability", "上架与删除状态"),
    ("category", "分类值"), ("price", "价格"), ("stock", "库存"), ("createdAt", "创建时间"), ("updatedAt", "修改时间"))
_UNCERTAINTIES = ["仅度量公开源行结构，不证明完整Product事实覆盖", "历史快照与规范库一致性未经证明", "Category关联、源新鲜度与连接身份未经证明"]
_CONFIDENCE = {"status": "not_applicable", "score": None, "basis": ["公开源行字段计量，不作业务质量评分"]}
_COLUMNS = [dict(key=key, label=label, valueType=kind) for key, label, kind in (
    ("field", "字段", "string"), ("observed", "观察行数", "number"), ("excluded", "范围外行数", "number"),
    ("duplicate", "重复隔离行数", "number"), ("eligible", "有效性分母", "number"),
    ("population", "不同商品数", "number"), ("jointValid", "联合字段有效行数", "number"),
    ("fieldValid", "该组字段有效行数", "number"))]


def _definition():
    body = dict(metricId="niushop.product-public-row-quality-counts", revision=1, name="商品公开字段联合计量",
        unit="count", source="configured-product-quality-observation", window="source-read-interval",
        aggregation="public-fields-joint/v1", acceptedQuality=["measured"])
    return MetricDefinitionRevision(**body, contentHash=canonical_hash(body))


def _rule():
    return dict(identity=_RULE[0], revision=_RULE[1], contentHash=_RULE[2])


def _resource(ref, authority):
    return ResourceRef(resource_type=ref.resource_type,resource_id=ref.resource_id,
        revision=str(ref.revision),authority=authority)


def _result_ref(result):
    return InvestigationExactRef(resource_type="QueryResultRevision",resource_id=result.query_id,
        revision=result.revision,content_hash="sha256:"+result.content_hash)


class ProductJointQualityQueryService:
    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("product query requires HostTransaction and TenantScope")
        self._transaction,self._scope=transaction,scope
        self._connect=TransactionBoundConnectFactory(transaction,scope)
        self._evidence=ConfiguredObservationEvidenceStore(transaction,scope)

    def _metric(self, *, ensure=False):
        return fixed_metric(self._transaction, self._scope, _definition(),
            actor="system:product-joint-quality-query", ensure=ensure)

    def _request(self,saved,evidence_ref,selection):
        observed=saved.observation.observation
        if observed.spec_id!="niushop.product-quality-observation/v1":
            raise ValueError("joint quality observation specification unsupported")
        if observed.site_id!=1:
            raise ValueError("joint quality query shop unsupported")
        if observed.read_started_at>=observed.read_finished_at:
            raise ValueError("joint quality query requires a positive observation interval")
        if any(type(ref) is not InvestigationExactRef or type(ref.revision) not in {int, str} for ref in selection):
            raise ValueError("strict joint query selection required")
        for ref,kind in zip(selection,("ChannelRevision","BusinessEntityRevision","BusinessEntityChannelBindingRevision")):
            if ref.resource_type!=kind:
                raise ValueError("joint quality selection type drifted")
        return MetricQueryRequest(metric_ref=self._metric(),dimensions=[],selection_refs=[],
            filters=[dict(field=name,operator="eq",value=ref.model_dump(mode="json",by_alias=True))
                for name,ref in zip(("observationEvidence","channel","entity","binding"),(evidence_ref,*selection))]
                +[dict(field="qualityRule", operator="eq", value=_rule())],
            window_start=observed.read_started_at,window_end=observed.read_finished_at,cutoff_at=observed.read_finished_at)

    def execute(self,*,evidence_ref,rows,channel_ref,entity_ref,binding_ref,idempotency_key,actor):
        if (type(idempotency_key) is not str or not idempotency_key or idempotency_key.strip()!=idempotency_key
            or len(idempotency_key)>200 or type(actor) is not str or not actor or actor.strip()!=actor or len(actor)>200):
            raise ValueError("canonical query identity and actor required")
        self._transaction.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (json.dumps([*self._scope.key,"product-joint-quality-query",idempotency_key]),))
        saved=self._evidence.read_exact(evidence_ref)
        if saved is None:raise ValueError("configured observation unavailable")
        saved.observation.verify_rows(rows)
        self._metric(ensure=True)
        selection=(channel_ref,entity_ref,binding_ref)
        request=self._request(saved,evidence_ref,selection)
        now=self._transaction.execute("SELECT clock_timestamp() AS now").fetchone()["now"]
        store=AipAnalystQueryStore(connect_factory=self._connect,clock=lambda:now)
        created=store.create(self._scope,CreateQueryJobRequest(query=request,
            deadline_at=request.cutoff_at+timedelta(days=1)),idempotency_key=idempotency_key,actor=actor)
        current=store.get(self._scope,created.query_id)
        if current.latest_result is not None:
            ref=_result_ref(current.latest_result)
            if self.read_exact(ref) is None:raise ValueError("query replay unavailable")
            return ref
        if now>=current.deadline_at:raise ValueError("joint quality query deadline expired")
        counts=ProductJointQualityReader(self._transaction,self._scope).read(
            evidence_ref=evidence_ref,rows=rows,channel_ref=channel_ref,entity_ref=entity_ref,binding_ref=binding_ref)
        now=counts.measured_at
        if now>=current.deadline_at:raise ValueError("joint quality query deadline expired during measurement")
        values=dict(observed=counts.observed_count,excluded=counts.excluded_count,duplicate=counts.duplicate_count,
            eligible=counts.eligible_count,population=counts.distinct_population_count,jointValid=counts.joint_valid_count)
        sources=[dict(ref=_resource(evidence_ref,"postgres:aip_evidence"),content_hash=evidence_ref.content_hash[7:],
            cutoff_at=request.cutoff_at,freshness="unknown",markings=["internal"])]
        result=QueryResultRevision(tenant=dict(orgId=self._scope.org_id,projectId=self._scope.project_id),
            query_id=current.query_id,revision=1,kind="metric",status="partial",columns=_COLUMNS,
            rows=[dict(rowId=field,values=dict(field=label,**values,
                fieldValid=dict(counts.field_valid_counts)[field])) for field,label in _FIELDS],
            source_refs=sources,lineage_refs=[self._metric(),*[_resource(ref,"postgres:ecom_object") for ref in selection]],
            uncertainties=_UNCERTAINTIES,confidence=_CONFIDENCE,cutoff_at=request.cutoff_at,
            content_hash="0"*64,created_at=now)
        result=result.model_copy(update={"content_hash":store._result_hash(self._scope,request.model_dump(mode="json",by_alias=True),result)})
        recorded=store.record_result(self._scope,current.query_id,
            RecordQueryResultRequest(expected_sequence=current.latest_sequence,result=result),
            idempotency_key=idempotency_key,actor=actor)
        ref=_result_ref(recorded.latest_result)
        if self.read_exact(ref)!=result:raise ValueError("joint quality result persistence drifted")
        return ref

    def read_exact(self,ref):
        store=AipAnalystQueryStore(connect_factory=self._connect)
        result=store.read_result_exact(self._scope,ref)
        if result is None:return None
        job=store.get(self._scope,ref.resource_id)
        query=job.query
        raw=self._transaction.execute("""SELECT r.result_json,j.request_json
            FROM public.aip_analyst_query_result_revision r JOIN public.aip_analyst_query_job j
            ON (r.org_id,r.project_id,r.query_id)=(j.org_id,j.project_id,j.query_id)
            WHERE r.org_id=%s AND r.project_id=%s AND r.query_id=%s AND r.revision=%s""",
            (*self._scope.key,ref.resource_id,ref.revision)).fetchone()
        if (raw is None or canonical_hash(raw["result_json"])!=canonical_hash(result.model_dump(mode="json",by_alias=True))
            or canonical_hash(raw["request_json"])!=canonical_hash(query.model_dump(mode="json",by_alias=True))):
            raise ValueError("joint quality raw authority drifted")
        if not isinstance(query,MetricQueryRequest) or len(query.filters)!=5:
            raise ValueError("joint quality query manifest drifted")
        refs=tuple(InvestigationExactRef.model_validate(item.value) for item in query.filters[:4])
        saved=self._evidence.read_exact(refs[0])
        if saved is None:raise ValueError("joint quality observation unavailable")
        expected_request=self._request(saved,refs[0],refs[1:])
        if (query.model_dump()!=expected_request.model_dump()
            or job.deadline_at!=query.cutoff_at+timedelta(days=1) or result.created_at>=job.deadline_at):
            raise ValueError("joint quality query request drifted")
        if (result.status.value!="partial" or result.kind.value!="metric" or result.revision!=1
            or result.uncertainties!=_UNCERTAINTIES or result.confidence.model_dump()!=_CONFIDENCE
            or [c.model_dump(mode="json",by_alias=True,exclude_none=True) for c in result.columns]!=_COLUMNS
            or len(result.rows)!=8 or len(result.source_refs)!=1):
            raise ValueError("joint quality result shape drifted")
        expected_lineage=[self._metric(),*[_resource(r,"postgres:ecom_object") for r in refs[1:]]]
        if result.lineage_refs!=expected_lineage:raise ValueError("joint quality lineage drifted")
        first=result.source_refs[0]
        if first.ref!=_resource(refs[0],"postgres:aip_evidence") or first.content_hash!=refs[0].content_hash[7:]:
            raise ValueError("joint quality evidence source drifted")
        if first.freshness!="unknown" or first.cutoff_at!=query.cutoff_at or first.markings!=["internal"]:
            raise ValueError("joint quality source policy drifted")
        totals=None
        field_valid_counts=[]
        for row,(field,label) in zip(result.rows,_FIELDS):
            v=row.values
            if row.row_id!=field or set(v)!={c["key"] for c in _COLUMNS} or v["field"]!=label:
                raise ValueError("joint quality row shape drifted")
            if any(type(value) is not int or not 0<=value<=100 for key,value in v.items() if key!="field"):
                raise ValueError("joint quality count type drifted")
            current=tuple(v[key] for key in ("observed","excluded","duplicate","eligible","population","jointValid"))
            if (v["observed"]!=saved.observation.observation.fetched_count
                or v["observed"]!=v["excluded"]+v["duplicate"]+v["eligible"]
                or v["duplicate"]==1 or not v["jointValid"]<=v["fieldValid"]<=v["eligible"]
                or not v["jointValid"]<=v["population"]<=v["eligible"]
                or (field=="identity" and v["fieldValid"]!=v["population"])
                or (totals is not None and current!=totals)):
                raise ValueError("joint quality population partition drifted")
            totals=current
            field_valid_counts.append(v["fieldValid"])
        # Necessary intersection bound, not reconstruction of the actual AND.
        if v["jointValid"] < max(0, sum(field_valid_counts) - (len(_FIELDS)-1)*v["eligible"]):
            raise ValueError("joint intersection is impossible for saved field counts")
        return result
