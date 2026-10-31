"""Complete descriptive Model/Route execution manifest, never admission.

The original readonly snapshot, approvals and holds are presented inputs here.
An actual owner must independently verify their provenance/currentness and
causal Run transition before any effect. No connection or Provider is opened.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_budget_reservation_contracts import (
    BudgetExactRef, ReserveBudgetRequest, BudgetReservationRevision, BudgetReservationState,
)
from aos_api.aip_contracts import TenantContext
from aos_api.aip_eval_contracts import AssetType, EvalRunAuthorityRecord, EvalSuiteRevision, DatasetRevisionRef, EvalRunStatus
from aos_api.aip_eval_pack_registry import compute_eval_suite_hash
from aos_api.aip_model_eval_authorization import ModelEvalRequestCreate
from aos_api.aip_model_eval_judge_authorization import ModelJudgeRuleDefinition, ModelJudgeRuleSourceRef
from aos_api.aip_model_eval_execution_contracts import (
    _ModelExecutionContract, _plain_contract_input,
    ModelEvalTargetJudgeExecutionManifest, ModelEvalTargetJudgeSharedRiskManifest,
)
from aos_api.aip_model_route_eval_subject_binding import canonical_eval_subject_binding_bytes, _stored
from aos_api.aip_model_runtime_contracts import ModelEvalCandidate, RegisteredModelRevision, ModelRouteRevision, RuntimePolicyRevision, ModelRuntimeLifecycle
from aos_api.aip_model_runtime_store import canonical_hash
from aos_api.aip_production_contracts import CreateEvalContractRequest, EvalContractRevision
from aos_api.tenant_scope import TenantScope

SHA = r'^[0-9a-f]{64}$'
CONTEXT_DOMAIN = b'AOS-MODEL-ROUTE-EVAL-CONTEXT-v1\n'
MANIFEST_DOMAIN = b'AOS-GOVERNED-MODEL-ROUTE-EVAL-MANIFEST-v1\n'
ROUTE_OPERATIONS = {'target':'aip_route_eval_target_call','judge':'aip_route_eval_judge_call'}


def _canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


def _dump(value):
    return value.model_dump(mode='json',by_alias=True)


def _alias_input(value):
    """Preserve copied extras while honoring original alias-only contracts."""
    if isinstance(value,BaseModel):
        extra=value.model_extra or {}
        if set(value.__dict__)&set(extra):raise ValueError('colliding original model extra fields')
        fields=type(value).model_fields;result={}
        for name,item in {**value.__dict__,**extra}.items():
            field=fields.get(name)
            alias=(field.validation_alias if isinstance(field.validation_alias,str) else field.alias) if field else None
            key=alias or name
            if key in result:raise ValueError('colliding original field aliases')
            result[key]=_alias_input(item)
        return result
    if isinstance(value,dict):return {k:_alias_input(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [_alias_input(v) for v in value]
    return value


def _fresh(value, cls):
    raw = _plain_contract_input(value)
    item = cls.model_validate(raw)
    original = _dump(value) if isinstance(value,BaseModel) else value
    if _canonical(original) != _canonical(_dump(item)):
        raise ValueError('canonical complete input must not be normalized or lose fields')
    return item


def _aware(value):
    if type(value) is str:
        value = datetime.fromisoformat(value)
    if type(value) is not datetime or value.utcoffset() is None:
        raise ValueError('exact timezone-aware clock required')
    return value


class _RouteContract(_ModelExecutionContract):
    @model_validator(mode='before')
    @classmethod
    def _native_reference_numbers(cls,value):
        raw = _alias_input(value)
        def visit(item):
            if isinstance(item,dict):
                for name,child in item.items():
                    if name in {'revision','attempt','upperBoundMinor','upper_bound_minor','limitMinor','limit_minor'} and (type(child) is not int or child<1):
                        raise ValueError('native positive revision/attempt/amount required')
                    if name in {'heldMinor','held_minor','submittedMinor','submitted_minor','settledMinor','settled_minor','unknownMinor','unknown_minor'} and (type(child) is not int or child<0):
                        raise ValueError('native nonnegative budget bucket amount required')
                    visit(child)
            elif isinstance(item,(list,tuple)):
                for child in item:visit(child)
        visit(raw)
        return raw


class RouteEvalCallRecipe(_RouteContract):
    case_id: str = Field(strict=True,min_length=1,max_length=200)
    purpose: Literal['target','judge']
    model_ref: VersionedAssetRef
    provider_ref: VersionedAssetRef
    price_ref: VersionedAssetRef
    quota_policy_ref: VersionedAssetRef
    budget_policy_ref: VersionedAssetRef
    task_budget_ref: BudgetExactRef
    source_ref: VersionedAssetRef
    physical_account_ref: VersionedAssetRef
    identity_id: str = Field(strict=True,min_length=1,max_length=200)
    identity_key_hash: str = Field(strict=True,pattern=SHA)
    input_hash: str = Field(strict=True,pattern=SHA)
    expected_hash: str | None = Field(pattern=SHA,strict=True)
    wire_input_hash: str | None = Field(strict=True,pattern=SHA)
    target_call_key: str | None
    input_protocol: Literal['case-artifact-wire/v1','aos.model-eval-judge-input/v1']
    max_output_tokens: int = Field(strict=True,ge=1,le=1_000_000)
    upper_bound_minor: int = Field(strict=True,gt=0,le=100_000_000)
    attempt: Literal[1]

    @field_validator('case_id','identity_id')
    @classmethod
    def _identifier(cls,value):
        if value!=value.strip():raise ValueError('exact nonempty call identity required')
        return value

    @model_validator(mode='after')
    def _kinds(self):
        for name,kind in [('model_ref','RegisteredModelRevision'),('provider_ref','ProviderInstanceRevision'),
                          ('price_ref','ModelPriceSnapshotRevision'),('quota_policy_ref','QuotaPolicyRevision'),
                          ('budget_policy_ref','BudgetPolicyRevision'),('source_ref','ProviderCapacitySourceRevision'),
                          ('physical_account_ref','ProviderPhysicalAccountCandidateRevision')]:
            if getattr(self,name).asset_type!=kind:raise ValueError('exact Route call asset kinds required')
        if self.task_budget_ref.resource_type!='BudgetRevision':raise ValueError('original Task BudgetRevision required')
        if self.purpose=='target' and (self.wire_input_hash is None or self.target_call_key is not None or self.input_protocol!='case-artifact-wire/v1'):
            raise ValueError('Target preplanned wire hash and direct input protocol required')
        if self.purpose=='judge' and (self.wire_input_hash is not None or not self.target_call_key or self.input_protocol!='aos.model-eval-judge-input/v1'):
            raise ValueError('Judge input must derive from observed Target; future wire hash forbidden')
        return self


class RouteEvalApplication(_RouteContract):
    schema_version: Literal['aos.route-eval-application/v1'] = 'aos.route-eval-application/v1'
    purpose: Literal['route-eval'] = 'route-eval'
    tenant: TenantContext
    execution_id: str = Field(strict=True,min_length=1,max_length=200)
    task_ref: BudgetExactRef
    judge_model: RegisteredModelRevision
    judge_rule: ModelJudgeRuleDefinition
    judge_rule_source: ModelJudgeRuleSourceRef
    context_binding_hash: str = Field(strict=True,pattern=SHA)
    expires_at: datetime
    currency: Literal['CNY'] = 'CNY'
    upper_bound_minor: int = Field(strict=True,gt=0,le=100_000_000)
    calls: list[RouteEvalCallRecipe] = Field(min_length=2,max_length=20000)
    execution_allowed: Literal[False] = False

    @field_validator('execution_allowed',mode='before')
    @classmethod
    def _denied(cls,value):
        if type(value) is not bool or value is not False:raise ValueError('native false nonexecuting declaration required')
        return value

    @model_validator(mode='after')
    def _complete(self):
        if self.execution_id!=self.execution_id.strip() or self.task_ref.resource_type!='Task':raise ValueError('exact execution and original Task required')
        _aware(self.expires_at)
        _stored(TenantScope(self.tenant.org_id,self.tenant.project_id),self.judge_model)
        if self.judge_model.lifecycle is not ModelRuntimeLifecycle.ACTIVE:raise ValueError('active original Judge Model description required')
        rule,source=self.judge_rule,self.judge_rule_source
        if (rule.model_ref.asset_id,rule.model_ref.revision,rule.model_ref.content_hash)!=(self.judge_model.registered_model_id,self.judge_model.revision,self.judge_model.content_hash) or rule.template_digest!=source.template_artifact.digest or rule.implementation_digest!=source.implementation_artifact.digest:
            raise ValueError('complete original Judge model/rule/source binding required')
        if len({(c.case_id,c.purpose) for c in self.calls})!=len(self.calls) or sum(c.upper_bound_minor for c in self.calls)>self.upper_bound_minor:
            raise ValueError('unique calls within complete application upper bound required')
        for name in ('identity_id','identity_key_hash'):
            target={getattr(c,name) for c in self.calls if c.purpose=='target'}
            judge={getattr(c,name) for c in self.calls if c.purpose=='judge'}
            if target&judge:raise ValueError('independent Target/Judge execution identities required')
        return self


class RouteEvalBudgetBinding(_RouteContract):
    call_key: str = Field(strict=True,min_length=1,max_length=200)
    request: ReserveBudgetRequest
    reservation: BudgetReservationRevision


def _parse_context(raw):
    if type(raw) is not bytes or not raw.startswith(CONTEXT_DOMAIN):raise ValueError('original complete context bytes required')
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:raise ValueError('duplicate JSON key')
            out[key]=value
        return out
    def nonfinite(value):raise ValueError('nonfinite JSON constant')
    payload=json.loads(raw[len(CONTEXT_DOMAIN):],object_pairs_hook=unique,parse_constant=nonfinite)
    if (type(payload) is not dict or set(payload)!={'schemaVersion','subject','run','suite','dataset','contract','snapshotReadAt','executionAllowed'}
        or payload['schemaVersion']!='aos.model-route-eval-context/v1' or payload['executionAllowed'] is not False
        or CONTEXT_DOMAIN+_canonical(payload)!=raw):raise ValueError('exact canonical nonexecuting context required')
    subject=payload['subject']
    if (type(subject) is not dict or set(subject)!={'schemaVersion','tenant','candidate','source','models','runtimePolicy','executionAllowed'}
        or type(subject['models']) is not list):raise ValueError('complete original context subject shape required')
    claim=_fresh(subject['candidate'],ModelEvalCandidate)
    kind=claim.source_ref.asset_type
    if kind not in {'RegisteredModelRevision','ModelRouteRevision'}:raise ValueError('Model or complete Route subject required')
    source=_fresh(subject['source'],RegisteredModelRevision if kind=='RegisteredModelRevision' else ModelRouteRevision)
    models=[_fresh(m,RegisteredModelRevision) for m in subject['models']]
    policy=None if subject['runtimePolicy'] is None else _fresh(subject['runtimePolicy'],RuntimePolicyRevision)
    scope=TenantScope(source.tenant.org_id,source.tenant.project_id)
    bound=canonical_eval_subject_binding_bytes(scope,claim,source,models=models,runtime_policy=policy)
    if _canonical(subject)!=bound.split(b'\n',1)[1]:raise ValueError('complete original subject binding drifted')
    run=_fresh(payload['run'],EvalRunAuthorityRecord);suite=_fresh(payload['suite'],EvalSuiteRevision)
    dataset=_fresh(payload['dataset'],DatasetRevisionRef);contract=_fresh(payload['contract'],EvalContractRevision)
    target=claim.target_ref
    expected_kind=AssetType.REGISTERED_MODEL if kind=='RegisteredModelRevision' else AssetType.MODEL_ROUTE
    if (run.tenant!=source.tenant or contract.tenant!=source.tenant or run.target!=suite.target
        or (run.target.asset_type,run.target.asset_id,run.target.revision,run.target.content_hash)!=(expected_kind,target.asset_id,str(target.revision),target.content_hash)
        or run.suite_ref.asset_id!=suite.suite_id or run.suite_ref.revision!=str(suite.revision) or run.suite_ref.content_hash!=suite.content_hash
        or compute_eval_suite_hash(suite)!=suite.content_hash or run.dataset!=dataset or suite.dataset!=dataset or run.judge!=suite.judge
        or run.eval_contract_ref is None):raise ValueError('exact context Run/Suite/Dataset/Judge binding required')
    ref=run.eval_contract_ref;cs=contract.suite_ref
    contract_body=CreateEvalContractRequest.model_validate({n:getattr(contract,n) for n in CreateEvalContractRequest.model_fields})
    if ((contract.contract_id,contract.revision,contract.content_hash)!=(ref.resource_id,ref.revision,ref.content_hash)
        or canonical_hash(_dump(contract_body))!=ref.content_hash or contract.lifecycle.value!='frozen'
        or contract.readiness.value!='ready' or contract.blockers
        or (cs.resource_type,cs.resource_id,cs.revision,cs.content_hash)!=('EvalSuiteRevision',suite.suite_id,suite.revision,suite.content_hash)):
        raise ValueError('exact frozen ready context Contract required')
    _aware(payload['snapshotReadAt'])
    return payload,source,claim,run,suite,models


def eval_context_binding_hash(context_bytes: bytes) -> str:
    """Bind every origin semantic field, excluding only snapshot read clock."""
    payload,*_=_parse_context(context_bytes)
    semantic={k:v for k,v in payload.items() if k!='snapshotReadAt'}
    return hashlib.sha256(b'AOS-EVAL-CONTEXT-SEMANTICS-v1\n'+_canonical(semantic)).hexdigest()


def route_eval_call_key(execution_id,context_hash,case_id,purpose):
    if any(type(v) is not str or not v or v!=v.strip() for v in (execution_id,context_hash,case_id)) or purpose not in ROUTE_OPERATIONS:
        raise ValueError('exact Route execution/context/case/purpose required')
    return 'route-eval-call-v1:'+hashlib.sha256(_canonical([execution_id,context_hash,case_id,purpose])).hexdigest()


def route_eval_approval_payload(application,recipe):
    """Expected proposal payload only; never creates or approves an event."""
    app=RouteEvalApplication.model_validate(_alias_input(application))
    call=RouteEvalCallRecipe.model_validate(_alias_input(recipe))
    if not any(c==call for c in app.calls):raise ValueError('call outside complete Route application')
    return {'applicationHash':canonical_hash(_dump(app)),
            'callKey':route_eval_call_key(app.execution_id,app.context_binding_hash,call.case_id,call.purpose),
            'caseId':call.case_id,'purpose':call.purpose,'recipeHash':canonical_hash(_dump(call)),
            'budgetUpperBoundMinor':call.upper_bound_minor}


def _validate_route_application(app,source,claim,suite,models,checked_at,context_hash,execution_id):
    if type(source) is not ModelRouteRevision:
        raise ValueError('complete original Route context required')
    app=RouteEvalApplication.model_validate(_alias_input(app))
    if (app.execution_id!=execution_id or app.tenant!=source.tenant or app.context_binding_hash!=context_hash or app.expires_at<=checked_at):
        raise ValueError('exact current descriptive Route application required')
    expected=[(c.case_id,p) for c in suite.cases for p in ('target','judge')]
    if [(c.case_id,c.purpose) for c in app.calls]!=expected:raise ValueError('complete ordered Target/Judge Suite call set required')
    judge=suite.judge.model_route
    if judge is None or judge.asset_type is not AssetType.REGISTERED_MODEL:raise ValueError('exact original Judge RegisteredModel required')
    if (app.judge_rule.judge_id,app.judge_rule.revision,canonical_hash(_dump(app.judge_rule)))!=(suite.judge.judge_id,suite.judge.revision,suite.judge.content_hash):
        raise ValueError('original Suite Judge rule hash drifted')
    mapped={m.registered_model_id:m for m in models}
    eligible={c.model.asset_id for c in source.candidates if c.weight>0}
    for call,case in zip(app.calls,[c for c in suite.cases for _ in (0,1)]):
        if (call.input_hash!=case.input_artifact.content_hash or call.expected_hash!=(None if case.expected_artifact is None else case.expected_artifact.content_hash)):
            raise ValueError('exact original case Artifact input/expected hashes required')
        selected=mapped.get(call.model_ref.asset_id) if call.purpose=='target' else app.judge_model
        if (call.purpose=='target' and call.model_ref.asset_id not in eligible) or selected is None:
            raise ValueError('complete Route selected Model missing or zero weight')
        if (call.model_ref.revision,call.model_ref.content_hash)!=(selected.revision,selected.content_hash) or any(
            getattr(call,field)!=getattr(selected,attr) for field,attr in [('provider_ref','provider'),('price_ref','price_snapshot_ref'),('quota_policy_ref','quota_policy_ref'),('budget_policy_ref','budget_policy_ref')]):
            raise ValueError('selected Model exact governance drifted')
        if call.purpose=='judge' and (call.model_ref.asset_id,str(call.model_ref.revision),call.model_ref.content_hash)!=(judge.asset_id,judge.revision,judge.content_hash):
            raise ValueError('original Suite Judge Model drifted')
        if call.max_output_tokens>selected.context_window:raise ValueError('call output bound exceeds exact Model context window')
        if call.purpose=='judge' and call.target_call_key!=route_eval_call_key(execution_id,context_hash,case.case_id,'target'):
            raise ValueError('Judge must bind its same-case Target call')
    return app.model_copy(deep=True)


def validate_route_eval_application(context_bytes: bytes, *, application,
                                    checked_at: datetime) -> RouteEvalApplication:
    """Validate complete preapproval recipes; never approval or native authority.

    There are no approval, reservation, connection or execution inputs. The
    post-approval compiler retains all its original budget checks separately.
    """
    at=_aware(checked_at)
    context,source,claim,run,suite,models=_parse_context(context_bytes)
    if run.status not in {EvalRunStatus.QUEUED,EvalRunStatus.RUNNING}:
        raise ValueError('unknown or terminal Run cannot become a new execution intent')
    if _aware(context['snapshotReadAt'])>at:
        raise ValueError('origin snapshot cannot be in the future')
    app=RouteEvalApplication.model_validate(_alias_input(application))
    return _validate_route_application(app,source,claim,suite,models,at,
        eval_context_binding_hash(context_bytes),app.execution_id)


def _route_bindings(app,bindings,source,claim,suite,models,checked_at,context_hash,execution_id):
    app=_validate_route_application(app,source,claim,suite,models,checked_at,context_hash,execution_id)
    if type(bindings) not in {tuple,list} or len(bindings)!=len(app.calls):raise ValueError('complete original per-call budget facts required')
    indexed={};parsed=[]
    for value in bindings:
        item=RouteEvalBudgetBinding.model_validate(_alias_input(value))
        if item.call_key in indexed:raise ValueError('duplicate call budget binding')
        indexed[item.call_key]=item;parsed.append(item)
    used=set();authority_ids={'reservation':set(),'invocation':set(),'approval':set()}
    for call in app.calls:
        key=route_eval_call_key(execution_id,context_hash,call.case_id,call.purpose);item=indexed.get(key)
        if item is None:raise ValueError('missing exact call budget binding')
        request,res=item.request,item.reservation
        pricing=BudgetExactRef(resourceType='ModelPriceSnapshotRevision',resourceId=call.price_ref.asset_id,revision=call.price_ref.revision,contentHash='sha256:'+call.price_ref.content_hash)
        if (request.operation_id!=ROUTE_OPERATIONS[call.purpose] or request.invocation_key!=key or request.task_ref!=app.task_ref
            or request.policy_ref!=call.task_budget_ref or request.pricing_ref!=pricing or request.upper_bound_minor!=call.upper_bound_minor
            or request.currency!='CNY' or res.tenant!=app.tenant or res.state is not BudgetReservationState.HELD
            or res.request_hash!=request.request_hash() or any(getattr(res,f)!=getattr(request,f) for f in
                ('operation_id','invocation_key','task_ref','policy_ref','pricing_ref','approval_ref','currency','upper_bound_minor'))):
            raise ValueError('exact original Task budget request and HELD reservation required')
        for label,ref in [('reservation',res.reservation_ref),('invocation',res.invocation_ref),('approval',res.approval_ref)]:
            if ref.resource_id in authority_ids[label]:raise ValueError('per-call independent reservation/invocation/approval required')
            authority_ids[label].add(ref.resource_id)
        if not _aware(res.created_at)<=_aware(res.updated_at)<=checked_at or any(not _aware(b.period_start)<=checked_at<_aware(b.period_end) for b in res.buckets):
            raise ValueError('budget snapshot clock/period drifted')
        used.add(key)
    if used!=set(indexed):raise ValueError('extra call budget facts')
    return _dump(app),[_dump(indexed[route_eval_call_key(execution_id,context_hash,c.case_id,c.purpose)]) for c in app.calls]


def compile_eval_execution_manifest(context_bytes: bytes, *, execution_id: str, checked_at: datetime,
                                    model_plan=None, route_application=None, route_budget_bindings=()) -> bytes:
    """Compile complete origin/plan bindings; every authority remains unverified."""
    at=_aware(checked_at)
    if type(execution_id) is not str or not 1<=len(execution_id)<=200 or execution_id!=execution_id.strip():raise ValueError('exact execution identity required')
    context,source,claim,run,suite,models=_parse_context(context_bytes)
    if run.status not in {EvalRunStatus.QUEUED,EvalRunStatus.RUNNING}:raise ValueError('unknown or terminal Run cannot become a new execution intent')
    if _aware(context['snapshotReadAt'])>at:raise ValueError('origin snapshot cannot be in the future')
    context_hash=eval_context_binding_hash(context_bytes)
    body={'schemaVersion':'aos.governed-model-route-eval-manifest/v1','tenant':_dump(source.tenant),
          'executionId':execution_id,'compiledAt':at.isoformat(),'context':context,'contextBindingHash':context_hash,'executionAllowed':False}
    if type(source) is RegisteredModelRevision:
        if route_application is not None or route_budget_bindings or model_plan is None:raise ValueError('complete original Model plan only')
        plain=_plain_contract_input(model_plan)
        def native_legacy_numbers(value):
            if isinstance(value,dict):
                asset_type=value.get('assetType',value.get('asset_type'))
                numeric_ref=(type(asset_type) is str and asset_type.endswith('Revision')) or 'resourceType' in value or 'resource_type' in value or 'judgeId' in value or 'judge_id' in value
                for key,item in value.items():
                    if (key=='revision' and numeric_ref or key in {'expectedHeadVersion','expected_head_version','upperBoundMinor','upper_bound_minor','allocationUpperBoundMinor','allocation_upper_bound_minor','attempt'}) and (type(item) is not int or item<1):
                        raise ValueError('native original Model reference/head/amount/attempt required')
                    native_legacy_numbers(item)
            elif isinstance(value,(list,tuple)):
                for item in value:native_legacy_numbers(item)
        native_legacy_numbers(plain)
        version=plain.get('schema_version',plain.get('schemaVersion'))
        cls={'aos.model-eval-target-judge-manifest/v2':ModelEvalTargetJudgeExecutionManifest,
             'aos.model-eval-target-judge-shared-risk-manifest/v3':ModelEvalTargetJudgeSharedRiskManifest}.get(version)
        if cls is None:raise ValueError('original whole Target/Judge v2 or v3 required')
        plan=cls.model_validate(plain);request=ModelEvalRequestCreate.model_validate(plan.judge_request['targetApplication']['request'])
        if (plan.execution_id!=execution_id or plan.tenant!=source.tenant or request.source_ref!=claim.source_ref or request.target_ref!=claim.target_ref
            or any(getattr(request,field)!=getattr(source,attr) for field,attr in [('provider_ref','provider'),('price_ref','price_snapshot_ref'),('quota_policy_ref','quota_policy_ref'),('budget_policy_ref','budget_policy_ref')])
            or request.expected_head_version!=claim.expected_head_version or (request.suite_ref.asset_id,request.suite_ref.revision,request.suite_ref.content_hash)!=(suite.suite_id,suite.revision,suite.content_hash)
            or (request.eval_contract_ref.asset_id,request.eval_contract_ref.revision,request.eval_contract_ref.content_hash)!=(run.eval_contract_ref.resource_id,run.eval_contract_ref.revision,run.eval_contract_ref.content_hash)
            or plan.judge_request['judgeRef']!=_dump(suite.judge) or _aware(plan.judge_request['expiresAt'])<=at):
            raise ValueError('complete original Model request/context binding drifted')
        expected=[(c.case_id,c.input_artifact.content_hash,None if c.expected_artifact is None else c.expected_artifact.content_hash) for c in suite.cases]
        if [(c.case_id,c.input_hash,c.expected_hash) for c in plan.cases]!=expected:raise ValueError('complete ordered original Model Suite required')
        for name in ('identity_id','identity_key_hash'):
            if {getattr(c.target,name) for c in plan.cases}&{getattr(c.judge,name) for c in plan.cases}:raise ValueError('independent original Target/Judge identities across complete case set required')
        body['modelPlan']=_dump(plan)
    else:
        if model_plan is not None or route_application is None:raise ValueError('Route cannot borrow Model purpose')
        app,budgets=_route_bindings(route_application,route_budget_bindings,source,claim,suite,models,at,context_hash,execution_id)
        body.update(routeApplication=app,routeBudgetBindings=budgets)
    return MANIFEST_DOMAIN+_canonical(body)
