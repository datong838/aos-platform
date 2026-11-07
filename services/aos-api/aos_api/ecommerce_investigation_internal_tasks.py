"""Read original child TaskGraph results without deriving business completion."""
import hashlib
import re
from datetime import datetime,UTC
from typing import Literal
from aos_api.aip_contracts import AipContractModel,TenantContext,ArtifactRef,ResourceRef
from aos_api.db import connect_read_only
from aos_api.errors import ApiError
from aos_api.ecommerce_analyst_authority_contracts import AnalystExactRef,TaskGraphRevision
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_canonical_tasks import task_creation_ref
from aos_api.ecommerce_business_investigation_projection import BusinessInvestigationProjectionBuilder,CanonicalBusinessInvestigationProjectionReader
from aos_api.business_investigation_shared_contracts import InvestigationExactRef
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory

def _current_memo_refs(steps):
    memo=next((s for s in steps if s['step_key']=='research_memo'),None)
    if memo is None or memo['status']!='succeeded':
        return {}
    refs=memo.get('output_refs')
    try:
        if not isinstance(refs,list) or not refs:
            raise ValueError('successful memo requires output references')
        result={}
        for raw in refs:
            ref=ResourceRef.model_validate(raw)
            if (set(raw)!={'resourceType','resourceId','revision','authority'} or ref.resource_type!='aip.artifact' or ref.authority!='aos.artifact'
                or not isinstance(ref.revision,str) or not re.fullmatch('[0-9a-f]{64}',ref.revision) or ref.resource_id in result):
                raise ValueError('exact unique memo output required')
            result[ref.resource_id]=ref.revision
        return result
    except (ValueError,TypeError) as exc:
        raise ApiError(code='INTERNAL_MEMO_OUTPUT_DRIFT',message='当前研究步骤的成果引用不一致',status_code=409) from exc

class InternalMemoView(AipContractModel):
    artifact_id:str
    content_hash:str
    can_preview:bool

class InternalReviewView(AipContractModel):
    issue_id:str
    status:str
    version:int

class InternalCandidateView(AipContractModel):
    candidate_id:str
    status:str

class InvestigationInternalTaskView(AipContractModel):
    graph_ref:AnalystExactRef
    task_ref:AnalystExactRef
    title:str
    task_type:str
    status:str
    task_version:int
    run_id:str|None
    run_status:str|None
    completed_steps:int
    total_steps:int
    artifacts:list[InternalMemoView]
    reviews:list[InternalReviewView]
    effect_maturity:str|None
    memory_candidates:list[InternalCandidateView]
    sample_only:bool|None
    data_label:str|None

class InvestigationInternalTasksResponse(AipContractModel):
    schema_version:Literal['aos.investigation-internal-tasks/v1']='aos.investigation-internal-tasks/v1'
    tenant:TenantContext
    run_ref:InvestigationExactRef
    items:list[InvestigationInternalTaskView]
    external_effects_allowed:Literal[False]=False

class InvestigationInternalMemoResponse(AipContractModel):
    tenant:TenantContext
    run_id:str
    task_id:str
    artifact_ref:ArtifactRef
    body:str
    sample_only:bool|None

class InvestigationInternalTaskReader:
    def __init__(self,connect_factory=None,*,artifact_resolver=None):
        self._connect=connect_factory or connect_read_only
        self._resolve=artifact_resolver

    def list(self,scope,run_id):
        with self._connect(scope) as conn:
            factory=TransactionBoundConnectFactory(HostTransaction(conn),scope)
            parent=BusinessInvestigationProjectionBuilder(CanonicalBusinessInvestigationProjectionReader(factory)).build(scope,run_id,observed_at=datetime.now(UTC))
            rows=conn.execute("""SELECT g.payload,t.* FROM ecommerce_analyst_task_graph_head h
                JOIN ecommerce_analyst_task_graph_revision g ON g.org_id=h.org_id AND g.project_id=h.project_id AND g.graph_id=h.graph_id AND g.revision=h.current_revision
                CROSS JOIN LATERAL jsonb_array_elements(g.payload->'mappings') m(item)
                JOIN aip_task t ON t.org_id=g.org_id AND t.project_id=g.project_id AND t.task_id=m.item->'taskRef'->>'resourceId'
                WHERE g.org_id=%s AND g.project_id=%s AND t.goal->'materialization'->'runRef'->>'resourceId'=%s
                ORDER BY g.graph_id,t.task_id""",(*scope.key,run_id)).fetchall()
            items=[]
            for row in rows:
                graph=TaskGraphRevision.model_validate(row['payload']);creation=task_creation_ref(row)
                expected_hash=canonical_hash(dict(graphId=graph.graph_id,planRef=graph.plan_ref.model_dump(mode='json',by_alias=True),mappings=[m.model_dump(mode='json',by_alias=True) for m in graph.mappings]))
                if graph.content_hash!=expected_hash:
                    raise ApiError(code='INTERNAL_TASK_GRAPH_DRIFT',message='内部任务图引用已变化',status_code=409)
                if not any(m.task_ref==creation for m in graph.mappings):
                    raise ApiError(code='INTERNAL_TASK_MAPPING_DRIFT',message='内部任务引用已变化',status_code=409)
                run=conn.execute('SELECT run_id,status,plan_revision_id FROM aip_task_run WHERE org_id=%s AND project_id=%s AND task_id=%s AND plan_revision_id=%s ORDER BY created_at DESC,run_id DESC LIMIT 1',(*scope.key,row['task_id'],row['current_plan_revision_id'])).fetchone()
                artifacts=[];reviews=[];candidates=[];effect=None;done=total=0
                if run:
                    plan=conn.execute('SELECT steps FROM aip_plan_revision WHERE org_id=%s AND project_id=%s AND plan_revision_id=%s',(*scope.key,run['plan_revision_id'])).fetchone()
                    keys={s['stepKey'] for s in plan['steps']};total=len(keys)
                    steps=conn.execute('SELECT DISTINCT ON(step_key) step_key,status,output_refs FROM aip_step_run WHERE org_id=%s AND project_id=%s AND run_id=%s ORDER BY step_key,attempt DESC',(*scope.key,run['run_id'])).fetchall()
                    done=sum(s['step_key'] in keys and s['status']=='succeeded' for s in steps)
                    current=_current_memo_refs(steps)
                    outputs=conn.execute("""SELECT a.artifact_id,a.content_hash,r.content_hash AS receipt_hash FROM aip_artifact a
                        JOIN aip_research_artifact_receipt r USING(org_id,project_id,artifact_id)
                        JOIN LATERAL (SELECT status,artifact_ids FROM aip_research_delivery_receipt WHERE org_id=r.org_id AND project_id=r.project_id AND job_id=r.job_id ORDER BY created_at DESC,receipt_id DESC LIMIT 1) d ON d.status='succeeded' AND d.artifact_ids ? a.artifact_id
                        WHERE a.org_id=%s AND a.project_id=%s AND a.run_id=%s AND a.artifact_type='internal_research_memo' AND a.artifact_id=ANY(%s) ORDER BY a.artifact_id""",(*scope.key,run['run_id'],list(current))).fetchall() if current else []
                    if len(outputs)!=len(current):
                        raise ApiError(code='INTERNAL_MEMO_DELIVERY_DRIFT',message='当前研究成果尚无匹配交付记录',status_code=409)
                    for a in outputs:
                        if a['content_hash']!=a['receipt_hash'] or a['content_hash']!=current[a['artifact_id']]:
                            raise ApiError(code='INTERNAL_MEMO_HASH_DRIFT',message='研究成果引用已变化',status_code=409)
                        artifacts.append(InternalMemoView(artifactId=a['artifact_id'],contentHash=a['content_hash'],canPreview=self._resolve is not None))
                    artifact_ids=[a.artifact_id for a in artifacts]
                    review_rows=conn.execute('SELECT issue_id,status,version FROM aip_review_issue WHERE org_id=%s AND project_id=%s AND artifact_id=ANY(%s) ORDER BY created_at,issue_id',(*scope.key,artifact_ids)).fetchall() if artifact_ids else []
                    reviews=[InternalReviewView.model_validate(r) for r in review_rows]
                    issue_ids=[r.issue_id for r in reviews]
                    if issue_ids:
                        effect_row=conn.execute("""SELECT r.maturity_status FROM aip_effect_review_revision r JOIN aip_effect_review_head h USING(org_id,project_id,subject_id)
                            WHERE r.org_id=%s AND r.project_id=%s AND r.revision=h.current_revision AND r.subject_ref->>'resourceType'='ReviewIssue' AND r.subject_ref->>'resourceId'=ANY(%s) ORDER BY r.created_at DESC LIMIT 1""",(*scope.key,issue_ids)).fetchone()
                        effect=effect_row['maturity_status'] if effect_row else None
                    candidates=[InternalCandidateView.model_validate(r) for r in conn.execute('SELECT candidate_id,status FROM aip_memory_candidate WHERE org_id=%s AND project_id=%s AND task_id=%s AND run_id=%s ORDER BY created_at,candidate_id',(*scope.key,row['task_id'],run['run_id'])).fetchall()]
                brief=conn.execute('SELECT b.spec FROM aip_task_brief_head h JOIN aip_task_brief_revision b USING(org_id,project_id,brief_id) WHERE h.org_id=%s AND h.project_id=%s AND h.task_id=%s AND b.revision=h.current_revision ORDER BY b.created_at DESC LIMIT 1',(*scope.key,row['task_id'])).fetchone()
                spec=brief['spec'] if brief else {};sample=spec.get('sampleOnly') if type(spec.get('sampleOnly')) is bool else None
                label=spec.get('historyLabel') if isinstance(spec.get('historyLabel'),str) else None
                items.append(InvestigationInternalTaskView(graphRef=AnalystExactRef(resourceType='TaskGraphRevision',resourceId=graph.graph_id,revision=graph.revision,contentHash=graph.content_hash),taskRef=creation,title=row['title'],taskType=row['task_type'],status=row['status'],taskVersion=row['version'],runId=run['run_id'] if run else None,runStatus=run['status'] if run else None,completedSteps=done,totalSteps=total,artifacts=artifacts,reviews=reviews,effectMaturity=effect,memoryCandidates=candidates,sampleOnly=sample,dataLabel=label))
            return InvestigationInternalTasksResponse(tenant=parent.tenant,runRef=parent.run_ref,items=items)

    def memo(self,scope,run_id,task_id,artifact_id):
        if self._resolve is None:
            raise ApiError(code='INTERNAL_MEMO_READER_UNAVAILABLE',message='成果正文读取尚未配置',status_code=409)
        view=self.list(scope,run_id)
        task=next((t for t in view.items if t.task_ref.resource_id==task_id),None)
        memo=next((a for a in task.artifacts if a.artifact_id==artifact_id),None) if task else None
        if memo is None:
            raise ApiError(code='INTERNAL_MEMO_NOT_FOUND',message='当前任务下没有该研究成果',status_code=404)
        ref=ArtifactRef(artifactId=artifact_id,artifactType='internal_research_memo',revision='1',contentHash=memo.content_hash)
        resolved=self._resolve(scope,ref)
        if resolved.reference!=ref or not isinstance(resolved.value,str) or len(resolved.value.encode('utf-8'))>2097152 or hashlib.sha256(resolved.value.encode('utf-8')).hexdigest()!=memo.content_hash:
            raise ApiError(code='INTERNAL_MEMO_CONTENT_DRIFT',message='研究成果正文与记录不一致',status_code=409)
        return InvestigationInternalMemoResponse(tenant=view.tenant,runId=run_id,taskId=task_id,artifactRef=ref,body=resolved.value,sampleOnly=task.sample_only)
