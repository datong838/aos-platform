"""Fixed observed/current-product query, persisted through existing owners."""
from datetime import timedelta
import json
import re

from aos_api.aip_analyst_contracts import (
    CreateQueryJobRequest, MetricQueryRequest, QueryResultRevision, RecordQueryResultRequest,
)
from aos_api.aip_analyst_query_store import AipAnalystQueryStore
from aos_api.aip_contracts import ResourceRef
from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import MetricDefinitionRevision
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.configured_source_observation_evidence import ConfiguredObservationEvidenceStore
from aos_api.data_requirement_store import canonical_hash
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
from aos_api.ecommerce_product_observation_comparison import ProductObservationComparisonReader
from aos_api.tenant_scope import TenantScope

_FIELDS = (("title","标题"),("price","价格"),("stock","库存"))
_UNCERTAINTIES = ["仅比较读取观察与当前规范库快照，不重建历史数据", "源快照与连接身份未经证明", "比较结果不代表业务事实覆盖或数据履约"]
_CONFIDENCE = {"status":"not_applicable","score":None,"basis":["固定计数，不作质量评分"]}
_COLUMNS = [dict(key=key,label=label,valueType=kind) for key,label,kind in (
    ("field","字段","string"),("sourceCount","源端商品数","number"),
    ("canonicalCount","规范商品数","number"),("commonCount","共同商品数","number"),
    ("onlySourceCount","仅源端存在","number"),("onlyCanonicalCount","仅规范库存在","number"),
    ("matched","一致","number"),("invalid","字段非法","number"),("mismatched","值不一致","number"))]


def _definition():
    body = dict(metricId="niushop.product-observation-comparison",revision=1,name="商品观察与规范数据比较",
        unit="count",source="configured-observation-and-current-canonical-products",
        window="read-interval-to-current-snapshot",aggregation="title-price-stock-partition/v1",
        acceptedQuality=["measured"])
    return MetricDefinitionRevision(**body,contentHash=canonical_hash(body))


def _resource(ref, authority):
    return ResourceRef(resource_type=ref.resource_type,resource_id=ref.resource_id,
        revision=str(ref.revision),authority=authority)


def _result_ref(result):
    return InvestigationExactRef(resource_type="QueryResultRevision",resource_id=result.query_id,
        revision=result.revision,content_hash="sha256:"+result.content_hash)


class ProductComparisonQueryService:
    def __init__(self, transaction: HostTransaction, scope: TenantScope):
        if type(transaction) is not HostTransaction or type(scope) is not TenantScope:
            raise TypeError("product query requires HostTransaction and TenantScope")
        self._transaction,self._scope=transaction,scope
        self._connect=TransactionBoundConnectFactory(transaction,scope)
        self._evidence=ConfiguredObservationEvidenceStore(transaction,scope)

    def _metric(self, *, ensure=False):
        expected=_definition()
        row=self._transaction.execute("""SELECT * FROM public.aip_metric_definition_revision
            WHERE org_id=%s AND project_id=%s AND metric_id=%s AND revision=1""",
            (*self._scope.key,expected.metric_id)).fetchone()
        if row is None and ensure:
            owner=AipEvalAuthorityStore(self._connect)
            owner._append_contract(self._scope,table="public.aip_metric_definition_revision",
                id_column="metric_id",identifier=expected.metric_id,
                columns=("metric_id","revision","content_hash","definition","actor"),
                values=(expected.metric_id,expected.revision,expected.content_hash,
                    owner._json(expected),"system:product-comparison-query"),
                expected=expected,parser=lambda row:MetricDefinitionRevision.model_validate(row["definition"]),
                extra_lookup=("revision",expected.revision))
            return self._metric()
        if row is None:
            raise ValueError("fixed comparison metric unavailable")
        body=expected.model_dump(mode="json",by_alias=True)
        if (row["definition"]!=body or canonical_hash(row["definition"])!=canonical_hash(body)
            or row["content_hash"]!=expected.content_hash or row["metric_id"]!=expected.metric_id
            or type(row["revision"]) is not int or row["revision"]!=1
            or (row["org_id"],row["project_id"])!=self._scope.key):
            raise ValueError("fixed comparison metric drifted")
        return ResourceRef(resource_type="MetricDefinitionRevision",resource_id=expected.metric_id,
            revision="1",authority="postgres:aip_metric_definition_revision")

    def _request(self,saved,evidence_ref,selection):
        observed=saved.observation.observation
        if observed.site_id!=1:
            raise ValueError("fixed comparison query shop unsupported")
        if observed.read_started_at>=observed.read_finished_at:
            raise ValueError("fixed comparison query requires a positive observation interval")
        for ref,kind in zip(selection,("ChannelRevision","BusinessEntityRevision","BusinessEntityChannelBindingRevision")):
            if ref.resource_type!=kind:
                raise ValueError("fixed comparison selection type drifted")
        return MetricQueryRequest(metric_ref=self._metric(),dimensions=[],selection_refs=[],
            filters=[dict(field=name,operator="eq",value=ref.model_dump(mode="json",by_alias=True))
                for name,ref in zip(("observationEvidence","channel","entity","binding"),(evidence_ref,*selection))],
            window_start=observed.read_started_at,window_end=observed.read_finished_at,cutoff_at=observed.read_finished_at)

    def execute(self,*,evidence_ref,rows,channel_ref,entity_ref,binding_ref,idempotency_key,actor):
        if (type(idempotency_key) is not str or not idempotency_key or idempotency_key.strip()!=idempotency_key
            or len(idempotency_key)>200 or type(actor) is not str or not actor or actor.strip()!=actor or len(actor)>200):
            raise ValueError("canonical query identity and actor required")
        self._transaction.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (json.dumps([*self._scope.key,"product-comparison-query",idempotency_key]),))
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
        if now>=current.deadline_at:raise ValueError("fixed comparison query deadline expired")
        comparison=ProductObservationComparisonReader(self._transaction,self._scope).compare(
            evidence_ref=evidence_ref,rows=rows,channel_ref=channel_ref,entity_ref=entity_ref,binding_ref=binding_ref)
        values=dict(sourceCount=comparison.source_count,canonicalCount=comparison.canonical_count,
            commonCount=comparison.common_count,onlySourceCount=comparison.only_source_count,
            onlyCanonicalCount=comparison.only_canonical_count)
        sources=[dict(ref=_resource(evidence_ref,"postgres:aip_evidence"),content_hash=evidence_ref.content_hash[7:],
            cutoff_at=request.cutoff_at,freshness="unknown",markings=["internal"])]
        sources.extend(dict(ref=ref,content_hash=ref.revision,cutoff_at=request.cutoff_at,
            freshness="unknown",markings=["internal"]) for ref in comparison.canonical_refs)
        result=QueryResultRevision(tenant=dict(orgId=self._scope.org_id,projectId=self._scope.project_id),
            query_id=current.query_id,revision=1,kind="metric",status="partial",columns=_COLUMNS,
            rows=[dict(rowId=field,values=dict(field=label,**values,
                matched=dict(comparison.match_counts)[field],invalid=dict(comparison.invalid_counts)[field],
                mismatched=dict(comparison.mismatch_counts)[field])) for field,label in _FIELDS],
            source_refs=sources,lineage_refs=[self._metric(),*[_resource(ref,"postgres:ecom_object") for ref in selection]],
            uncertainties=_UNCERTAINTIES,confidence=_CONFIDENCE,cutoff_at=request.cutoff_at,
            content_hash="0"*64,created_at=now)
        result=result.model_copy(update={"content_hash":store._result_hash(self._scope,request.model_dump(mode="json",by_alias=True),result)})
        recorded=store.record_result(self._scope,current.query_id,
            RecordQueryResultRequest(expected_sequence=current.latest_sequence,result=result),
            idempotency_key=idempotency_key,actor=actor)
        ref=_result_ref(recorded.latest_result)
        if self.read_exact(ref)!=result:raise ValueError("fixed comparison result persistence drifted")
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
            raise ValueError("fixed comparison raw authority drifted")
        if not isinstance(query,MetricQueryRequest) or len(query.filters)!=4:
            raise ValueError("fixed comparison query manifest drifted")
        refs=tuple(InvestigationExactRef.model_validate(item.value) for item in query.filters)
        saved=self._evidence.read_exact(refs[0])
        if saved is None:raise ValueError("fixed comparison observation unavailable")
        expected_request=self._request(saved,refs[0],refs[1:])
        if (query.model_dump()!=expected_request.model_dump()
            or job.deadline_at!=query.cutoff_at+timedelta(days=1) or result.created_at>=job.deadline_at):
            raise ValueError("fixed comparison query request drifted")
        if (result.status.value!="partial" or result.kind.value!="metric" or result.revision!=1
            or result.uncertainties!=_UNCERTAINTIES or result.confidence.model_dump()!=_CONFIDENCE
            or [c.model_dump(mode="json",by_alias=True,exclude_none=True) for c in result.columns]!=_COLUMNS
            or len(result.rows)!=3 or not result.source_refs):
            raise ValueError("fixed comparison result shape drifted")
        expected_lineage=[self._metric(),*[_resource(r,"postgres:ecom_object") for r in refs[1:]]]
        if result.lineage_refs!=expected_lineage:raise ValueError("fixed comparison lineage drifted")
        first=result.source_refs[0]
        if first.ref!=_resource(refs[0],"postgres:aip_evidence") or first.content_hash!=refs[0].content_hash[7:]:
            raise ValueError("fixed comparison evidence source drifted")
        canonical=result.source_refs[1:]
        identities=[]
        for source in result.source_refs:
            if source.freshness!="unknown" or source.cutoff_at!=query.cutoff_at or source.markings!=["internal"]:
                raise ValueError("fixed comparison source policy drifted")
        for source in canonical:
            r=source.ref
            if r.resource_type!="EcommerceObjectRevision" or r.authority!="postgres:ecom_object" or r.revision!=source.content_hash:
                raise ValueError("fixed comparison canonical source drifted")
            identity=json.loads(r.resource_id.removeprefix("ecom/v1:"))
            if identity[:5]!=[*self._scope.key,"niushop","1","Product"] or len(identity)!=6 or re.fullmatch(r"niushop:1:[1-9][0-9]*",identity[5]) is None:
                raise ValueError("fixed comparison canonical identity drifted")
            identities.append(r.resource_id)
        if identities!=sorted(set(identities)):raise ValueError("fixed comparison duplicate or unsorted source")
        totals=None
        for row,(field,label) in zip(result.rows,_FIELDS):
            v=row.values
            if row.row_id!=field or set(v)!={c["key"] for c in _COLUMNS} or v["field"]!=label:
                raise ValueError("fixed comparison row shape drifted")
            if any(type(value) is not int or not 0<=value<=100 for key,value in v.items() if key!="field"):
                raise ValueError("fixed comparison count type drifted")
            current=tuple(v[key] for key in ("sourceCount","canonicalCount","commonCount","onlySourceCount","onlyCanonicalCount"))
            if (v["sourceCount"]!=saved.observation.observation.retained_count or v["canonicalCount"]!=len(canonical)
                or v["sourceCount"]!=v["commonCount"]+v["onlySourceCount"]
                or v["canonicalCount"]!=v["commonCount"]+v["onlyCanonicalCount"]
                or v["matched"]+v["invalid"]+v["mismatched"]!=v["commonCount"] or (totals is not None and current!=totals)):
                raise ValueError("fixed comparison population partition drifted")
            totals=current
        return result
