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
from aos_api.aip_production_contracts import (
    CreateBriefRequest, CreateEvidenceBundleRequest, EvidenceBundleListResponse,
    EvidenceBundleRevision, ReviseBriefRequest, TaskBriefListResponse, TaskBriefRevision,
    CreateEvalContractRequest, ReviseEvalContractRequest, EvalContractRevision,
    EvalContractListResponse, CreateResponsibilityPlanRequest,
    ReviseResponsibilityPlanRequest, ResponsibilityPlanRevision,
    ResponsibilityPlanListResponse,
    ArtifactRelation, ArtifactRelationListResponse, CompileStageTemplateRequest,
    CreateArtifactRelationRequest, CreateReviewIssueRequest,
    CreateStageTemplateRequest, ResolveReviewIssueRequest, ReturnDecision,
    ReturnReviewIssueRequest, ReviseStageTemplateRequest, ReviewIssue,
    ReviewIssueListResponse, StageCompilationResult, StageTemplateListResponse,
    StageTemplateRevision,
)
from aos_api.auth import Principal, require_principal
from aos_api.errors import ApiError
from aos_api.tenant_scope import TenantScope

router = APIRouter(prefix="/v1/aip/production-contracts", tags=["aip-production-contracts"])
_STORE = AipProductionContractStore()


class FreezeBriefRequest(AipContractModel):
    expected_version: int = Field(ge=1)


FreezeContractRequest = FreezeBriefRequest


def get_store() -> AipProductionContractStore:
    return _STORE


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


@router.get("/evidence-bundles",response_model=EvidenceBundleListResponse)
def list_bundles(principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.list_evidence_bundles(_scope(principal))
    except ProductionContractError as exc:raise _map(exc) from exc


@router.get("/evidence-bundles/{bundle_id}",response_model=EvidenceBundleRevision)
def get_bundle(bundle_id:str,revision:int=Query(default=1,ge=1),principal:Principal=Depends(require_principal),store:AipProductionContractStore=Depends(get_store)):
    try:return store.get_evidence_bundle(_scope(principal),bundle_id,revision)
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
