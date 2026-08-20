"""W2 canonical production contract API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import Field

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_production_contract_store import (
    AipProductionContractStore, ProductionContractConflict,
    ProductionContractDependencyBlocked, ProductionContractError,
    ProductionContractIdempotencyConflict, ProductionContractNotFound,
)
from aos_api.aip_production_start_service import AipProductionStartService
from aos_api.aip_responsibility_template_authority import resolve_responsibility_template
from aos_api.aip_stage_template_authority import resolve_stage_template_source
from aos_api.aip_production_contracts import (
    CreateBriefRequest, CreateEvidenceBundleRequest, BuildEvidenceBundleRequest,
    EvidenceBundleListResponse,
    EvidenceBundleRevision, ReviseBriefRequest, TaskBriefListResponse, TaskBriefRevision,
    CreateEvalContractRequest, ReviseEvalContractRequest, EvalContractRevision,
    EvalContractListResponse, EvalContractDiff, CreateResponsibilityPlanRequest,
    ReviseResponsibilityPlanRequest, ResponsibilityPlanRevision,
    ResponsibilityPlanListResponse,
    ArtifactRelation, ArtifactRelationListResponse, CompileStageTemplateRequest,
    CreateArtifactRelationRequest, CreateReviewIssueRequest,
    CreateStageTemplateRequest, ResolveReviewIssueRequest, ReturnDecision,
    ReturnDecisionListResponse,
    ReturnReviewIssueRequest, ReviseStageTemplateRequest, ReviewIssue,
    ReviewIssueListResponse, StageCompilationResult, StageTemplateListResponse,
    StageTemplateRevision,
    CreateImpactPreviewRequest, ReviseImpactPreviewRequest,
    ImpactPreviewRevision, ImpactPreviewListResponse,
    ProductionStartRequest, ProductionStartDecision,
    ProductionStartDecisionListResponse,
    RevokeEvidenceBundleRequest, ResolveEvidenceDisclosureRequest,
    EvidenceDisclosureDecision,
    FreezeProductionContextRequest, ProductionContextRevision,
    ProductionContextListResponse,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/production-contracts", tags=["aip-production-contracts"])
_STORE = AipProductionContractStore(
    responsibility_template_resolver=resolve_responsibility_template,
    stage_template_source_resolver=resolve_stage_template_source,
)
_START_SERVICE = AipProductionStartService(contract_store=_STORE)


class FreezeBriefRequest(AipContractModel):
    expected_version: int = Field(ge=1)


FreezeContractRequest = FreezeBriefRequest


def get_store() -> AipProductionContractStore:
    return _STORE


def get_start_service() -> AipProductionStartService:
    return _START_SERVICE


def _scope(principal: Principal) -> TenantScope:
    return TenantScope(principal.org_id, principal.project_id)


def _key(value: str) -> str:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 120:
        raise ApiError(code="AIP_INVALID_ARGUMENT", message="Idempotency-Key must be 1..120 characters", status_code=400)
    return cleaned


def _map(exc: ProductionContractError) -> ApiError:
    if isinstance(exc, ProductionContractNotFound): return ApiError(code=exc.code,message=str(exc),status_code=404)
    if isinstance(exc,(ProductionContractConflict,ProductionContractIdempotencyConflict)): return ApiError(code=exc.code,message=str(exc),status_code=409)
    if isinstance(exc,ProductionContractDependencyBlocked): return ApiError(code=exc.code,message=str(exc),status_code=422)
    return ApiError(code=exc.code,message="production contract persistence failed",status_code=503)


@router.post("/impact-previews", response_model=ImpactPreviewRevision, status_code=201)
def create_impact_preview(body: CreateImpactPreviewRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.create_impact_preview(_scope(principal), principal.subject, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/impact-previews", response_model=ImpactPreviewListResponse)
def list_impact_previews(principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.list_impact_previews(_scope(principal))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/impact-previews/{preview_id}", response_model=ImpactPreviewRevision)
def get_impact_preview(preview_id: str, revision: int | None = Query(default=None, ge=1), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.get_impact_preview(_scope(principal), preview_id, revision)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/impact-previews/{preview_id}/revisions", response_model=ImpactPreviewRevision, status_code=201)
def revise_impact_preview(preview_id: str, body: ReviseImpactPreviewRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.revise_impact_preview(_scope(principal), principal.subject, preview_id, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/impact-previews/{preview_id}/freeze", response_model=ImpactPreviewRevision)
def freeze_impact_preview(preview_id: str, body: FreezeContractRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.freeze_impact_preview(_scope(principal), principal.subject, preview_id, body.expected_version, _key(idempotency_key))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/production-contexts/freeze", response_model=ProductionContextRevision, status_code=201)
def freeze_production_context(body:FreezeProductionContextRequest,idempotency_key:str=Header(alias="Idempotency-Key"),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.freeze_production_context(_scope(principal),principal.subject,_key(idempotency_key),body)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.get("/production-contexts", response_model=ProductionContextListResponse)
def list_production_contexts(principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.list_production_contexts(_scope(principal))
    except ProductionContractError as exc:raise _map(exc) from exc


@router.get("/production-contexts/{context_id}", response_model=ProductionContextRevision)
def get_production_context(context_id:str,revision:int=Query(default=1,ge=1),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.get_production_context(_scope(principal),context_id,revision)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.post("/production-runs/start", response_model=ProductionStartDecision)
def start_production_run(body: ProductionStartRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), service: AipProductionStartService = Depends(get_start_service)):
    try: return service.start(_scope(principal), principal.subject, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/production-start-decisions", response_model=ProductionStartDecisionListResponse)
def list_production_start_decisions(principal: Principal = Depends(require_principal), service: AipProductionStartService = Depends(get_start_service)):
    try: return service.list(_scope(principal))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/production-start-decisions/{decision_id}", response_model=ProductionStartDecision)
def get_production_start_decision(decision_id: str, principal: Principal = Depends(require_principal), service: AipProductionStartService = Depends(get_start_service)):
    try: return service.get(_scope(principal), decision_id)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/task-briefs", response_model=TaskBriefRevision, status_code=status.HTTP_201_CREATED)
def create_brief(body: CreateBriefRequest, idempotency_key: str=Header(alias="Idempotency-Key"), principal:Principal=Depends(require_principal), store:AipProductionContractStore=Depends(get_store)):
    try:return store.create_brief(_scope(principal),principal.subject,_key(idempotency_key),body)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.get("/task-briefs", response_model=TaskBriefListResponse)
def list_briefs(principal:Principal=Depends(require_principal), store:AipProductionContractStore=Depends(get_store)):
    try:return store.list_briefs(_scope(principal))
    except ProductionContractError as exc:raise _map(exc) from exc


@router.get("/task-briefs/{brief_id}", response_model=TaskBriefRevision)
def get_brief(brief_id:str, revision:int|None=Query(default=None,ge=1), principal:Principal=Depends(require_principal), store:AipProductionContractStore=Depends(get_store)):
    try:return store.get_brief(_scope(principal),brief_id,revision)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.post("/task-briefs/{brief_id}/revisions", response_model=TaskBriefRevision, status_code=status.HTTP_201_CREATED)
def revise_brief(brief_id:str,body:ReviseBriefRequest,idempotency_key:str=Header(alias="Idempotency-Key"),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.revise_brief(_scope(principal),principal.subject,brief_id,_key(idempotency_key),body)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.post("/task-briefs/{brief_id}/freeze",response_model=TaskBriefRevision)
def freeze_brief(brief_id:str,body:FreezeBriefRequest,idempotency_key:str=Header(alias="Idempotency-Key"),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.freeze_brief(_scope(principal),principal.subject,brief_id,body.expected_version,_key(idempotency_key))
    except ProductionContractError as exc:raise _map(exc) from exc


@router.post("/evidence-bundles",response_model=EvidenceBundleRevision,status_code=status.HTTP_201_CREATED)
def create_bundle(body:CreateEvidenceBundleRequest,idempotency_key:str=Header(alias="Idempotency-Key"),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.create_evidence_bundle(_scope(principal),principal.subject,_key(idempotency_key),body)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.post("/evidence-bundles/build",response_model=EvidenceBundleRevision,status_code=status.HTTP_201_CREATED)
def build_bundle(body:BuildEvidenceBundleRequest,idempotency_key:str=Header(alias="Idempotency-Key"),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    """W-L9: server-owned required-facts coverage Build Job."""
    try:return store.build_evidence_bundle(_scope(principal),principal.subject,_key(idempotency_key),body)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.get("/evidence-bundles",response_model=EvidenceBundleListResponse)
def list_bundles(principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.list_evidence_bundles(_scope(principal), markings=principal.markings)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.get("/evidence-bundles/{bundle_id}",response_model=EvidenceBundleRevision)
def get_bundle(bundle_id:str,revision:int=Query(default=1,ge=1),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.get_evidence_bundle(_scope(principal),bundle_id,revision, markings=principal.markings)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.post("/evidence-bundles/{bundle_id}/revoke",response_model=EvidenceBundleRevision)
def revoke_bundle(bundle_id:str,body:RevokeEvidenceBundleRequest,idempotency_key:str=Header(alias="Idempotency-Key"),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.revoke_evidence_bundle(_scope(principal),principal.subject,bundle_id,_key(idempotency_key),body)
    except ProductionContractError as exc:raise _map(exc) from exc


@router.post("/eval-contracts", response_model=EvalContractRevision, status_code=201)
def create_eval_contract(body: CreateEvalContractRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.create_eval_contract(_scope(principal), principal.subject, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/eval-contracts", response_model=EvalContractListResponse)
def list_eval_contracts(principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.list_eval_contracts(_scope(principal))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/eval-contracts/{contract_id}", response_model=EvalContractRevision)
def get_eval_contract(contract_id: str, revision: int | None = Query(default=None, ge=1), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.get_eval_contract(_scope(principal), contract_id, revision)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/eval-contracts/{contract_id}/diff", response_model=EvalContractDiff)
def diff_eval_contract(
    contract_id: str,
    from_revision: int = Query(alias="fromRevision", ge=1),
    to_revision: int = Query(alias="toRevision", ge=1),
    principal: Principal = Depends(require_principal),
    store: AipProductionContractStore = Depends(get_store),
):
    try:
        return store.diff_eval_contract(
            _scope(principal), contract_id, from_revision, to_revision
        )
    except ProductionContractError as exc:
        raise _map(exc) from exc


@router.post("/eval-contracts/{contract_id}/revisions", response_model=EvalContractRevision, status_code=201)
def revise_eval_contract(contract_id: str, body: ReviseEvalContractRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.revise_eval_contract(_scope(principal), principal.subject, contract_id, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/eval-contracts/{contract_id}/freeze", response_model=EvalContractRevision)
def freeze_eval_contract(contract_id: str, body: FreezeContractRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.freeze_eval_contract(_scope(principal), principal.subject, contract_id, body.expected_version, _key(idempotency_key))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/responsibility-plans", response_model=ResponsibilityPlanRevision, status_code=201)
def create_responsibility_plan(body: CreateResponsibilityPlanRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.create_responsibility_plan(_scope(principal), principal.subject, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/responsibility-plans", response_model=ResponsibilityPlanListResponse)
def list_responsibility_plans(principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.list_responsibility_plans(_scope(principal))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/responsibility-plans/{plan_id}", response_model=ResponsibilityPlanRevision)
def get_responsibility_plan(plan_id: str, revision: int | None = Query(default=None, ge=1), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.get_responsibility_plan(_scope(principal), plan_id, revision)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/responsibility-plans/{plan_id}/revisions", response_model=ResponsibilityPlanRevision, status_code=201)
def revise_responsibility_plan(plan_id: str, body: ReviseResponsibilityPlanRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.revise_responsibility_plan(_scope(principal), principal.subject, plan_id, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/responsibility-plans/{plan_id}/freeze", response_model=ResponsibilityPlanRevision)
def freeze_responsibility_plan(plan_id: str, body: FreezeContractRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.freeze_responsibility_plan(_scope(principal), principal.subject, plan_id, body.expected_version, _key(idempotency_key))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/stage-templates", response_model=StageTemplateRevision, status_code=201)
def create_stage_template(body: CreateStageTemplateRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.create_stage_template(_scope(principal), principal.subject, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/stage-templates", response_model=StageTemplateListResponse)
def list_stage_templates(principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.list_stage_templates(_scope(principal))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/stage-templates/{template_id}", response_model=StageTemplateRevision)
def get_stage_template(template_id: str, revision: int | None = Query(default=None, ge=1), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.get_stage_template(_scope(principal), template_id, revision)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/stage-templates/{template_id}/revisions", response_model=StageTemplateRevision, status_code=201)
def revise_stage_template(template_id: str, body: ReviseStageTemplateRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.revise_stage_template(_scope(principal), principal.subject, template_id, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/stage-templates/{template_id}/freeze", response_model=StageTemplateRevision)
def freeze_stage_template(template_id: str, body: FreezeContractRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.freeze_stage_template(_scope(principal), principal.subject, template_id, body.expected_version, _key(idempotency_key))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/stage-templates/{template_id}/compile", response_model=StageCompilationResult, status_code=201)
def compile_stage_template(template_id: str, body: CompileStageTemplateRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.compile_stage_template(_scope(principal), principal.subject, template_id, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/artifact-relations", response_model=ArtifactRelation, status_code=201)
def create_artifact_relation(body: CreateArtifactRelationRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.create_artifact_relation(_scope(principal), principal.subject, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/artifact-relations", response_model=ArtifactRelationListResponse)
def list_artifact_relations(principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.list_artifact_relations(_scope(principal))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/review-issues", response_model=ReviewIssue, status_code=201)
def create_review_issue(body: CreateReviewIssueRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.create_review_issue(_scope(principal), principal.subject, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/review-issues", response_model=ReviewIssueListResponse)
def list_review_issues(principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.list_review_issues(_scope(principal))
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/review-issues/{issue_id}", response_model=ReviewIssue)
def get_review_issue(issue_id: str, principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.get_review_issue(_scope(principal), issue_id)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/review-issues/{issue_id}/resolve", response_model=ReviewIssue)
def resolve_review_issue(issue_id: str, body: ResolveReviewIssueRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.resolve_review_issue(_scope(principal), principal.subject, issue_id, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.post("/review-issues/{issue_id}/return", response_model=ReturnDecision, status_code=201)
def return_review_issue(issue_id: str, body: ReturnReviewIssueRequest, idempotency_key: str = Header(alias="Idempotency-Key"), principal: Principal = Depends(require_principal), store: AipProductionContractStore = Depends(get_store)):
    try: return store.return_review_issue(_scope(principal), principal.subject, issue_id, _key(idempotency_key), body)
    except ProductionContractError as exc: raise _map(exc) from exc


@router.get("/return-decisions", response_model=ReturnDecisionListResponse)
def list_return_decisions(
    issue_id: str | None = Query(default=None, alias="issueId"),
    principal: Principal = Depends(require_principal),
    store: AipProductionContractStore = Depends(get_store),
):
    try:
        return store.list_return_decisions(_scope(principal), issue_id=issue_id)
    except ProductionContractError as exc:
        raise _map(exc) from exc


@router.get("/return-decisions/{decision_id}", response_model=ReturnDecision)
def get_return_decision(
    decision_id: str,
    principal: Principal = Depends(require_principal),
    store: AipProductionContractStore = Depends(get_store),
):
    try:
        return store.get_return_decision(_scope(principal), decision_id)
    except ProductionContractError as exc:
        raise _map(exc) from exc
