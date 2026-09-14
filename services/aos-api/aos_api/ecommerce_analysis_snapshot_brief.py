"""Frozen snapshot brief for the original paused analysis Task, never a new Task."""
from typing import Literal
from aos_api.aip_contracts import AipContractModel,ResourceRef
from aos_api.aip_business_investigation_runtime import BusinessInvestigationRuntimeBinding
from aos_api.aip_production_contracts import CreateBriefRequest
from aos_api.aip_production_contract_store import AipProductionContractStore,canonical_hash
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.data_requirement_contracts import DataRequirementRevisionRecord,DataRequirementTimeWindow
from aos_api.ecommerce_analysis_pending_data_context import AnalysisPendingDataContext
from aos_api.ecommerce_analysis_snapshot_business_evidence import AnalysisSnapshotBusinessEvidence
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory


class AnalysisSnapshotBriefSpec(AipContractModel):
    schema_version: Literal['aos.analysis-snapshot-brief/v1']='aos.analysis-snapshot-brief/v1'
    requirement_ref: InvestigationExactRef
    business_evidence_ref: InvestigationExactRef
    runtime: BusinessInvestigationRuntimeBinding
    time_window: DataRequirementTimeWindow
    required_fact_ids: list[str]
    covered_fact_ids: list[str]
    quality_reasons: list[str]
    objective: Literal['基于本次完整观察形成有来源的经营分析、缺口与下一步假设，不将订单数量等同成交或推断利润']='基于本次完整观察形成有来源的经营分析、缺口与下一步假设，不将订单数量等同成交或推断利润'
    external_effect_authorized: Literal[False]=False


def _schema():
    return ResourceRef(resource_type='AnalysisSnapshotBriefSchema',resource_id='aos:analysis-snapshot-brief/v1',
        revision=canonical_hash(AnalysisSnapshotBriefSpec.model_json_schema()),authority='aos_api.ecommerce_analysis_snapshot_brief.AnalysisSnapshotBriefSpec')


def _ref(brief):
    return InvestigationExactRef(resource_type='TaskBriefRevision',resource_id=brief.brief_id,revision=brief.revision,content_hash='sha256:'+brief.content_hash)


def _same(left,right):
    return (left.resource_type,left.resource_id,left.revision,left.content_hash)==(
        right.resource_type,right.resource_id,right.revision,'sha256:'+right.content_hash)


class AnalysisSnapshotBrief:
    def __init__(self,business):
        if type(business) is not AnalysisSnapshotBusinessEvidence:raise TypeError('original current business Evidence required')
        self.business=business;self.scope=business.scope
        self.pending=AnalysisPendingDataContext(business.source.analysis)

    def _during(self,conn,business_ref,execute):
        reference=InvestigationExactRef.model_validate(business_ref)
        with conn.transaction():
            recorded=self.business._record(conn,reference)
            source=self.business.source._record(conn,recorded['selection']['evidenceRef'])
            def consume_pending(pending):
                requirement=DataRequirementRevisionRecord.model_validate(pending['requirement'])
                runtime=BusinessInvestigationRuntimeBinding.model_validate(pending['runtime'])
                checkpoint=runtime.checkpoint_ref
                if (runtime.tenant!=requirement.tenant or runtime.task_run_status.value!='paused' or checkpoint is None
                    or not _same(requirement.case_ref,runtime.case_ref) or not _same(requirement.run_ref,runtime.business_investigation_run_ref)
                    or (requirement.checkpoint_ref.resource_id,requirement.checkpoint_ref.revision,requirement.checkpoint_ref.content_hash)
                        !=(checkpoint.resource_id,checkpoint.sequence,'sha256:'+checkpoint.state_hash)):
                    raise ValueError('original paused brief runtime differs')
                def consume(body):
                    if body['requirementRef']!=dict(resourceType='DataRequirementRevision',resourceId=requirement.requirement_id,
                        revision=requirement.revision,contentHash=requirement.content_hash):raise ValueError('brief requirement differs from business evidence')
                    tx=HostTransaction(conn)
                    row=tx.execute('SELECT version,status FROM public.aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s',
                        (*self.scope.key,runtime.task_ref.resource_id)).fetchone()
                    if row is None or row['version']!=runtime.task_ref.version or row['status']!='paused':
                        raise ValueError('original paused Task changed')
                    spec=AnalysisSnapshotBriefSpec(requirement_ref=body['requirementRef'],business_evidence_ref=reference,runtime=runtime,
                        time_window=requirement.time_window,required_fact_ids=requirement.required_facts,
                        covered_fact_ids=body['factIds'],quality_reasons=body['qualityReasons'])
                    request=CreateBriefRequest(task_id=runtime.task_ref.resource_id,brief_type='analysis_snapshot',schema_ref=_schema(),
                        spec=spec.model_dump(mode='json',by_alias=True))
                    store=AipProductionContractStore(TransactionBoundConnectFactory(tx,self.scope))
                    result=execute(tx,store,request,body['actor'])
                    after=tx.execute('SELECT version,status FROM public.aip_task WHERE org_id=%s AND project_id=%s AND task_id=%s',
                        (*self.scope.key,runtime.task_ref.resource_id)).fetchone()
                    if after!=row:raise ValueError('original Task changed during brief persistence')
                    return result
                return self.business.run_current(conn,reference=reference,execute=consume)
            return self.pending.run_current(conn,receipt_ref=source['selection']['receiptRef'],execute=consume_pending)

    def prepare_current(self,conn,*,business_ref):
        def execute(tx,store,request,actor):
            key='snapshot-brief-'+canonical_hash(dict(scope=self.scope.key,request=request.model_dump(mode='json',by_alias=True)))
            tx.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(key,))
            draft=store.create_brief(self.scope,actor,key,request)
            frozen=store.freeze_brief(self.scope,actor,draft.brief_id,1,key+'-freeze')
            reference=_ref(frozen);self._read(tx,store,request,actor,reference)
            return reference
        return self._during(conn,business_ref,execute)

    def read_current(self,conn,*,business_ref,brief_ref):
        reference=InvestigationExactRef.model_validate(brief_ref)
        return self._during(conn,business_ref,lambda tx,store,request,actor:self._read(tx,store,request,actor,reference))

    def _read(self,tx,store,request,actor,reference):
        if (reference.resource_type!='TaskBriefRevision' or type(reference.revision) is not int
            or reference.revision!=2 or reference.receipt_id is not None):raise ValueError('exact frozen snapshot brief required')
        brief=store.get_brief(self.scope,reference.resource_id,reference.revision)
        raw=tx.execute('''SELECT h.current_revision,r.schema_ref,r.spec FROM public.aip_task_brief_head h
            JOIN public.aip_task_brief_revision r USING(org_id,project_id,brief_id)
            WHERE h.org_id=%s AND h.project_id=%s AND h.brief_id=%s AND r.revision=%s''',
            (*self.scope.key,reference.resource_id,reference.revision)).fetchone()
        expected=dict(briefType=request.brief_type,schemaRef=request.schema_ref.model_dump(mode='json',by_alias=True),spec=request.spec)
        if (raw is None or raw['current_revision']!=reference.revision or _ref(brief)!=reference
            or brief.task_id!=request.task_id or brief.brief_type!=request.brief_type or brief.schema_ref!=request.schema_ref
            or brief.spec!=request.spec or brief.created_by!=actor or brief.lifecycle.value!='frozen'
            or canonical_hash(expected)!=brief.content_hash or canonical_hash(raw['spec'])!=canonical_hash(request.spec)
            or raw['schema_ref']!=expected['schemaRef']):raise ValueError('snapshot brief authority differs')
        return brief
