"""Descriptive Route material and original per-operation Action/budget inputs.

These constructors do not publish Action metadata, classify risk, connect,
write drafts, approve, reserve money or grant authority. A native dedicated
guard must recheck the original material/current context and actual independent
approval before any write or budget use. In particular an arbitrary supplied
ActionApprovalEvent reference is only a claim, never verified approval.
"""
from __future__ import annotations

import json
import re
from contextlib import nullcontext
from datetime import datetime
from typing import Literal

from pydantic import Field,field_validator
import psycopg

from aos_api.aip_action_models import CreateActionDraftRequest,CreateActionProposalRequest
from aos_api.aip_budget_reservation_contracts import BudgetExactRef,ReserveBudgetRequest
from aos_api.aip_contracts import TenantContext
from aos_api.aip_model_route_eval_manifest import (
    SHA,ROUTE_OPERATIONS,RouteEvalCallRecipe,_RouteContract,_alias_input,
    eval_context_binding_hash,validate_route_eval_application,route_eval_approval_payload,
)

ROUTE_MATERIAL_ACTION_ID='aip_prepare_route_eval_application'
MATERIAL_READBACK_DOMAIN=b'AOS-ROUTE-EVAL-MATERIAL-READBACK-v1\n'
_ROUTE_OBJECT=dict(id='RouteEvalApplication',name='路由评测申请',
    description='仅存材料与独立调用申请，不授执行权限',published=True,properties=[],required_markings=[])
_MATERIAL_ACTION=dict(id=ROUTE_MATERIAL_ACTION_ID,name='准备路由评测材料',objectType='RouteEvalApplication',
    parameters=[],requiredMarkings=[],submissionCriteria=[])


class RouteEvalMaterialRejected(ValueError):
    """Safe material-readback category, never underlying values or authority."""


class RouteEvalMaterialRef(_RouteContract):
    """Presented original draft identity; native provenance remains unverified."""
    tenant: TenantContext
    resource_type: Literal['ActionDraftRevision']
    resource_id: str=Field(strict=True,min_length=1,max_length=200)
    revision: int=Field(strict=True,ge=1)
    head_version: int=Field(strict=True,ge=1)
    content_hash: str=Field(strict=True,pattern=SHA)

    @field_validator('resource_id')
    @classmethod
    def _identity(cls,value):
        if value!=value.strip():raise ValueError('exact original draft identity required')
        return value


def _call_inputs(context_bytes,application,recipe,checked_at):
    app=validate_route_eval_application(context_bytes,application=application,checked_at=checked_at)
    call=RouteEvalCallRecipe.model_validate(_alias_input(recipe))
    if sum(c==call for c in app.calls)!=1:
        raise ValueError('one exact recipe from the complete Route application required')
    return app,call


def build_route_eval_material_draft(context_bytes: bytes,*,application,
                                    checked_at: datetime) -> CreateActionDraftRequest:
    """Construct one full material request; no draft is persisted or trusted."""
    app=validate_route_eval_application(context_bytes,application=application,checked_at=checked_at)
    context=json.loads(context_bytes.split(b'\n',1)[1])
    return CreateActionDraftRequest(actionTypeId=ROUTE_MATERIAL_ACTION_ID,
        taskId=app.task_ref.resource_id,purpose='route-eval-material',expiresAt=app.expires_at,
        payload={'schemaVersion':'aos.route-eval-material/v1','context':context,
                 'application':app.model_dump(mode='json',by_alias=True)})


def build_route_eval_call_proposal(context_bytes: bytes,*,application,recipe,material_ref,
                                   checked_at: datetime) -> CreateActionProposalRequest:
    """Construct one original per-operation proposal, without approving it."""
    app,call=_call_inputs(context_bytes,application,recipe,checked_at)
    ref=RouteEvalMaterialRef.model_validate(_alias_input(material_ref))
    if ref.tenant!=app.tenant:raise ValueError('same tenant original material draft required')
    payload=route_eval_approval_payload(app,call)
    payload['materialRef']=ref.model_dump(mode='json',by_alias=True)
    return CreateActionProposalRequest(actionTypeId=ROUTE_OPERATIONS[call.purpose],
        taskId=app.task_ref.resource_id,purpose='route-eval',payload=payload,expiresAt=app.expires_at)


def build_route_eval_call_budget_request(context_bytes: bytes,*,application,recipe,approval_ref,
                                         checked_at: datetime) -> ReserveBudgetRequest:
    """Construct an original Task request; the presented event is unverified.

    Native Owner must read the current original event and exact proposal
    payload for THIS recipe, then call the unchanged original budget authority.
    This function never creates approval/reservation/invocation facts.
    """
    app,call=_call_inputs(context_bytes,application,recipe,checked_at)
    raw=_alias_input(approval_ref)
    if type(raw) is not dict or type(raw.get('revision')) is not int or raw['revision']<1:
        raise ValueError('native original approval event revision required')
    approval=BudgetExactRef.model_validate(raw)
    if approval.resource_type!='ActionApprovalEvent':
        raise ValueError('original independent ActionApprovalEvent reference required')
    payload=route_eval_approval_payload(app,call)
    return ReserveBudgetRequest(operationId=ROUTE_OPERATIONS[call.purpose],
        invocationKey=payload['callKey'],taskRef=app.task_ref,policyRef=call.task_budget_ref,
        pricingRef=BudgetExactRef(resourceType='ModelPriceSnapshotRevision',resourceId=call.price_ref.asset_id,
            revision=call.price_ref.revision,contentHash='sha256:'+call.price_ref.content_hash),
        approvalRef=approval,currency='CNY',upperBoundMinor=call.upper_bound_minor)


def validate_route_eval_call_proposal(context_bytes: bytes,*,application,recipe,
                                      material_ref,request,checked_at: datetime
                                      ) -> CreateActionProposalRequest:
    """Match one whole direct request to its complete application and material.

    This is a semantic check for the dedicated native guard, not a provenance
    check. The guard must separately read the original current material and
    context, verify Source/authentication and the independent original approval,
    and use the unchanged budget authority on the same retained transaction.
    A supplied request or approval reference never establishes those facts.
    No SQL, transaction completion, authentication or effect occurs here.
    """
    from aos_api.aip_model_route_eval_manifest import _canonical
    try:
        # Draft is a subclass of this DTO but is not an original direct leaf.
        if type(request) is not CreateActionProposalRequest:
            raise ValueError('exact original direct call request required')
        # model_copy() can retain unvalidated fields which model_dump() hides.
        # Validate the preserved raw attributes, then compare the original
        # envelope too so normalization cannot conceal a changed request.
        CreateActionProposalRequest.model_validate(_alias_input(request))
        expected=build_route_eval_call_proposal(context_bytes,application=application,
            recipe=recipe,material_ref=material_ref,checked_at=checked_at)
        # Compare the entire envelope, including optional fields and every raw
        # payload key. JSON equality also distinguishes true from numeric 1.
        if _canonical(request.model_dump(mode='json',by_alias=True))!=_canonical(
                expected.model_dump(mode='json',by_alias=True)):
            raise ValueError('whole Route call request must match')
        return expected
    except (ValueError,TypeError,KeyError,AttributeError,RuntimeError):
        raise RouteEvalMaterialRejected('ROUTE_EVAL_EXACT_CALL_REQUEST_REQUIRED') from None


class RouteEvalActionGuard:
    """Fail-closed bridge into the original Action transaction.

    The configured G2a slice locks original Source, material and current Eval
    context on one caller. It still cannot create a proposal: original Rule and
    human checker authority remain mandatory before a binding can be returned.
    An unconfigured instance is the safe default and performs no Source call.
    """
    _CALL_IDS=frozenset(ROUTE_OPERATIONS.values())
    _PAYLOAD_KEYS=frozenset({'applicationHash','callKey','caseId','purpose',
        'recipeHash','budgetUpperBoundMinor','materialRef'})
    _SOURCE_DOMAIN=b'AOS-ROUTE-EVAL-NATIVE-SOURCE-PREFIX-v1\n'

    def __init__(self,*,expected_database=None,context_bytes=None,application=None,
                 candidate=None,run_id=None,expected_run_version=None,
                 expected_run_status=None,source_commands=None,release_policy=None,
                 artifact_bytes=None):
        """Freeze server-owned native inputs; an empty guard remains closed."""
        values=(expected_database,context_bytes,application,candidate,run_id,
            expected_run_version,expected_run_status,source_commands)
        self._native=None
        self._rule=None
        if all(value is None for value in values):
            if release_policy is None and artifact_bytes is None:return
            raise TypeError('exact Route Eval native guard inputs required')
        try:
            from aos_api.aip_eval_contracts import EvalRunStatus
            from aos_api.aip_model_runtime_contracts import ModelEvalCandidate
            from aos_api.aip_model_route_eval_manifest import RouteEvalApplication,_parse_context
            from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityConsumptionCommand
            if (any(value is None for value in values)
                or type(expected_database) is not str
                or re.fullmatch(r'[a-z][a-z0-9_]{0,62}',expected_database) is None
                or type(context_bytes) is not bytes
                or type(application) is not RouteEvalApplication
                or type(candidate) is not ModelEvalCandidate
                or type(run_id) is not str or not 1<=len(run_id)<=200 or run_id!=run_id.strip()
                or type(expected_run_version) is not int or expected_run_version<1
                or type(expected_run_status) is not EvalRunStatus
                or expected_run_status not in {EvalRunStatus.QUEUED,EvalRunStatus.RUNNING}
                or type(source_commands) is not tuple or not source_commands
                or any(type(item) is not ProviderCapacityConsumptionCommand for item in source_commands)):
                raise ValueError('complete exact native input types required')
            context,_,context_candidate,run,_,_=_parse_context(context_bytes)
            app=RouteEvalApplication.model_validate(_alias_input(application)).model_copy(deep=True)
            claim=ModelEvalCandidate.model_validate(candidate.model_dump(mode='python',by_alias=True)).model_copy(deep=True)
            commands=tuple(ProviderCapacityConsumptionCommand.model_validate(item).model_copy(deep=True)
                for item in source_commands)
            if (context_candidate!=claim or run.run_id!=run_id or run.version!=expected_run_version
                or run.status is not expected_run_status
                or (app.tenant.org_id,app.tenant.project_id)!=('org-org','dev-project')
                or app.context_binding_hash!=eval_context_binding_hash(context_bytes)):
                raise ValueError('native input package must bind one original context')
            self._native={'expected_database':expected_database,'context_bytes':bytes(context_bytes),
                'application':app,'candidate':claim,'run_id':run_id,
                'expected_run_version':expected_run_version,'expected_run_status':expected_run_status,
                'source_commands':commands}
            if release_policy is None and artifact_bytes is None:return
            from aos_api.asset_registry.release_policy import ReleasePolicy
            paths={item.relative_path for item in (app.judge_rule_source.rule_artifact,
                app.judge_rule_source.template_artifact,app.judge_rule_source.implementation_artifact)}
            if (type(release_policy) is not ReleasePolicy or type(artifact_bytes) is not dict
                or set(artifact_bytes)!=paths
                or any(type(key) is not str or type(value) is not bytes
                    for key,value in artifact_bytes.items())):
                raise ValueError('complete exact Rule inputs required')
            try:policy=release_policy.snapshot()
            except Exception:raise ValueError('stable Rule release policy snapshot required') from None
            self._rule={'release_policy':policy,
                'artifact_bytes':{key:bytes(value) for key,value in artifact_bytes.items()}}
        except (TypeError,ValueError,KeyError,AttributeError,RuntimeError):
            raise TypeError('exact Route Eval native guard inputs required') from None

    @staticmethod
    def _blocked(message):
        from aos_api.aip_action_store import AipActionTransitionBlocked
        raise AipActionTransitionBlocked(message)

    @staticmethod
    def _proposal_fingerprint(row):
        from aos_api.aip_action_store import canonical_hash
        names=('proposal_id','version','proposal_hash','status','action_type_id',
            'action_type_revision_hash','action_type_snapshot','task_id','run_id','object_ref',
            'purpose','client_risk_hint','risk_level','policy_snapshot','payload','diff',
            'evidence_refs','impact_preview_id','impact_preview_revision','impact_preview_hash',
            'action_binding_hash','approval_policy_hash','created_by','expires_at',
            'source_draft_id','source_draft_revision','source_draft_hash')
        return canonical_hash({name:row.get(name) for name in names})

    @classmethod
    def _packet(cls,raw,domain,keys):
        from aos_api.aip_model_route_eval_manifest import _canonical
        try:
            if type(raw) is not bytes or not raw.startswith(domain):raise ValueError
            def unique(pairs):
                result={}
                for key,value in pairs:
                    if key in result:raise ValueError
                    result[key]=value
                return result
            body=json.loads(raw[len(domain):],object_pairs_hook=unique,
                parse_constant=lambda value:(_ for _ in ()).throw(ValueError()))
            if type(body) is not dict or set(body)!=set(keys) or domain+_canonical(body)!=raw:
                raise ValueError
            return body
        except (TypeError,ValueError,KeyError,AttributeError,json.JSONDecodeError):
            cls._blocked('ROUTE_EVAL_NATIVE_INPUT_REQUIRED')

    def _rule_facts(self,conn,scope):
        from aos_api.aip_action_store import canonical_hash
        from aos_api.aip_model_eval_judge_request_store import ModelJudgeCallRequestStore
        if self._rule is None:return None
        app=self._native['application']
        try:
            facts=ModelJudgeCallRequestStore().read_published_rule(conn,scope,app.judge_rule_source,
                release_policy=self._rule['release_policy'],artifact_bytes=self._rule['artifact_bytes'])
            expected_keys={'source','rule','rootRevision','validUntil','ruleHash','signatureFingerprint',
                'releaseEvidenceRevision','approvalAllowed','executionAllowed'}
            rule=app.judge_rule.model_dump(mode='json',by_alias=True)
            source=app.judge_rule_source.model_dump(mode='json',by_alias=True)
            if (type(facts) is not dict or set(facts)!=expected_keys or facts['source']!=source
                or facts['rule']!=rule or facts['ruleHash']!=canonical_hash(rule)
                or facts['approvalAllowed'] is not False or facts['executionAllowed'] is not False
                or type(facts['signatureFingerprint']) is not str
                or re.fullmatch(r'sha256:[0-9a-f]{64}',facts['signatureFingerprint']) is None
                or type(facts['releaseEvidenceRevision']) is not str
                or re.fullmatch(r'sha256:[0-9a-f]{64}',facts['releaseEvidenceRevision']) is None):
                raise ValueError('exact original Rule facts required')
            if facts['validUntil'] is not None:
                until=datetime.fromisoformat(facts['validUntil'])
                if until.utcoffset() is None or app.expires_at>until:
                    raise ValueError('Rule window must cover the complete application')
            return facts
        except Exception:
            self._blocked('ROUTE_EVAL_NATIVE_RULE_GUARD_REQUIRED')

    def _binding(self,scope,body,action_snapshot):
        from aos_api.aip_action_store import canonical_hash
        if self._native is None or self._rule is None:
            self._blocked('ROUTE_EVAL_NATIVE_RULE_GUARD_REQUIRED')
        app=self._native['application']
        return canonical_hash({'schemaVersion':'aos.route-eval-action-binding/v1',
            'tenant':{'orgId':scope.org_id,'projectId':scope.project_id},
            'taskId':body.task_id,'actionTypeId':body.action_type_id,
            'actionTypeRevisionHash':action_snapshot['revisionHash'],'payload':body.payload,
            'contextBindingHash':app.context_binding_hash,
            'judgeRuleSource':app.judge_rule_source.model_dump(mode='json',by_alias=True),
            'judgeRuleHash':canonical_hash(app.judge_rule.model_dump(mode='json',by_alias=True)),
            'executionAllowed':False})

    def _native_inputs(self,conn,scope,actor,body,ref):
        from aos_api import aip_model_route_eval_owner as owner
        from aos_api.aip_model_route_eval_manifest import route_eval_approval_payload
        if self._native is None:self._blocked('ROUTE_EVAL_NATIVE_SOURCE_GUARD_REQUIRED')
        native=self._native;app=native['application']
        first_rule=self._rule_facts(conn,scope)
        try:
            source_raw=owner.prepare_route_eval_native_sources(conn,
                expected_database=native['expected_database'],context_bytes=native['context_bytes'],
                application=app,actor_id=actor,commands=native['source_commands'])
            source=self._packet(source_raw,self._SOURCE_DOMAIN,{'schemaVersion','applicationHash',
                'contextBindingHash','database','databaseOid','callerXid','callerPid','checkedAt',
                'sources','executionAllowed'})
            material_raw=read_route_eval_material_draft(conn,expected_database=native['expected_database'],
                scope=scope,material_ref=ref,expected_maker=actor)
            material=self._packet(material_raw,MATERIAL_READBACK_DOMAIN,{'schemaVersion','tenant',
                'materialRef','makerId','context','application','actionTypeRevisionHash','database',
                'databaseOid','callerXid','callerPid','observedAt','approvalAllowed','executionAllowed'})
            current=read_native_eval_subject_context_bytes(conn,expected_database=native['expected_database'],
                scope=scope,candidate=native['candidate'],run_id=native['run_id'],
                expected_run_version=native['expected_run_version'],
                expected_run_status=native['expected_run_status'],expires_at=app.expires_at)
            second_rule=self._rule_facts(conn,scope)
            if first_rule!=second_rule:
                self._blocked('ROUTE_EVAL_NATIVE_RULE_GUARD_REQUIRED')
            final=_native_eval_context_boundary(conn,native['expected_database'],scope)
            context=json.loads(native['context_bytes'].split(b'\n',1)[1])
            application=app.model_dump(mode='json',by_alias=True)
            ref_json=ref.model_dump(mode='json',by_alias=True)
            source_at=datetime.fromisoformat(source['checkedAt'])
            material_at=datetime.fromisoformat(material['observedAt'])
            identities={(source['database'],source['databaseOid'],source['callerXid'],source['callerPid']),
                (material['database'],material['databaseOid'],material['callerXid'],material['callerPid']),
                (final['database'],final['database_oid'],final['xid'],final['pid'])}
            if (source['schemaVersion']!='aos.route-eval-preapproval-source-prefix/v1'
                or source['applicationHash']!=body.payload['applicationHash']
                or source['contextBindingHash']!=app.context_binding_hash
                or source['executionAllowed'] is not False or type(source['sources']) is not list
                or material['schemaVersion']!='aos.route-eval-material-readback/v1'
                or material['tenant']!={'orgId':scope.org_id,'projectId':scope.project_id}
                or material['materialRef']!=ref_json or material['makerId']!=actor
                or material['context']!=context or material['application']!=application
                or material['approvalAllowed'] is not False or material['executionAllowed'] is not False
                or current!=native['context_bytes'] or len(identities)!=1
                or type(final['now']) is not datetime or final['now'].utcoffset() is None
                or source_at.utcoffset() is None or material_at.utcoffset() is None
                or not source_at<=material_at<=final['now']
                or final['now']>=app.expires_at or final['now']>=body.effective_expiry()):
                raise ValueError('same complete native Source/material/context caller required')
            matches=[recipe for recipe in app.calls
                if route_eval_approval_payload(app,recipe)=={key:value for key,value in body.payload.items()
                    if key!='materialRef'}]
            if len(matches)!=1:raise ValueError('one exact current Route recipe required')
            validate_route_eval_call_proposal(current,application=app,recipe=matches[0],
                material_ref=ref,request=body,checked_at=final['now'])
        except Exception as exc:
            from aos_api.aip_action_store import AipActionTransitionBlocked
            if isinstance(exc,AipActionTransitionBlocked):raise
            self._blocked('ROUTE_EVAL_NATIVE_INPUT_REQUIRED')
        if self._rule is None:self._blocked('ROUTE_EVAL_NATIVE_RULE_GUARD_REQUIRED')
        return final['now']

    @classmethod
    def _exact_leaf(cls,scope,actor,body,action_snapshot,risk):
        from aos_api.aip_action_models import CreateActionProposalRequest
        from aos_api.aip_action_policy import (ROUTE_EVAL_MATERIAL_ACTION_ID,
            classify_action_risk)
        from aos_api.aip_contracts import ActionRiskLevel
        from aos_api.tenant_scope import TenantScope
        if type(body) is not CreateActionProposalRequest or type(action_snapshot) is not dict:
            cls._blocked('ROUTE_EVAL_DIRECT_CALL_REQUIRED')
        ids={body.action_type_id,action_snapshot.get('id')}
        if ROUTE_EVAL_MATERIAL_ACTION_ID in ids:
            cls._blocked('ROUTE_EVAL_MATERIAL_NATIVE_GUARD_REQUIRED')
        payload=body.payload
        try:
            purpose=payload['purpose']
            ref=RouteEvalMaterialRef.model_validate(_alias_input(payload['materialRef']))
        except (TypeError,ValueError,KeyError,AttributeError):
            cls._blocked('ROUTE_EVAL_DIRECT_CALL_REQUIRED')
        native_strings=(payload.get('applicationHash'),payload.get('recipeHash'))
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or type(actor) is not str or not 1<=len(actor)<=200 or actor!=actor.strip()
            or type(body) is not CreateActionProposalRequest
            or body.action_type_id not in cls._CALL_IDS
            or action_snapshot.get('id')!=body.action_type_id
            or type(action_snapshot.get('revisionHash')) is not str
            or re.fullmatch(SHA,action_snapshot['revisionHash']) is None
            or body.action_type_id!=ROUTE_OPERATIONS.get(purpose)
            or body.purpose!='route-eval'
            or type(body.task_id) is not str or not 1<=len(body.task_id)<=200 or body.task_id!=body.task_id.strip()
            or body.run_id is not None or body.object_ref is not None or body.impact_preview_ref is not None
            or body.diff or body.evidence_refs or body.risk_hint is not None
            or body.expires_at is None or body.expires_at.utcoffset() is None
            or set(payload)!=cls._PAYLOAD_KEYS
            or any(type(value) is not str or re.fullmatch(SHA,value) is None for value in native_strings)
            or any(type(payload.get(name)) is not str or not payload[name] or payload[name]!=payload[name].strip()
                   for name in ('callKey','caseId'))
            or purpose not in ROUTE_OPERATIONS
            or type(payload.get('budgetUpperBoundMinor')) is not int or payload['budgetUpperBoundMinor']<1
            or (ref.tenant.org_id,ref.tenant.project_id)!=scope.key):
            cls._blocked('ROUTE_EVAL_DIRECT_CALL_REQUIRED')
        expected=classify_action_risk(body.action_type_id,action_snapshot,payload,None)
        if (risk!=expected or risk.level is not ActionRiskLevel.R2 or risk.floor is not ActionRiskLevel.R2
            or risk.approval_policy.get('makerChecker') is not True
            or risk.approval_policy.get('executionAllowed') is not False
            or risk.approval_policy.get('draftOnly') is not False):
            cls._blocked('ROUTE_EVAL_DIRECT_CALL_REQUIRED')
        return ref

    def check_request(self,conn,scope,actor,body,action_snapshot,risk):
        ref=self._exact_leaf(scope,actor,body,action_snapshot,risk)
        self._native_inputs(conn,scope,actor,body,ref)
        return self._binding(scope,body,action_snapshot)

    def check_proposal(self,conn,scope,actor,row,*,checker):
        from aos_api.aip_action_models import CreateActionProposalRequest
        from aos_api.aip_action_policy import classify_action_risk
        from aos_api.aip_action_store import _proposal_stable_envelope,canonical_hash
        from aos_api.aip_model_eval_action import ModelEvalActionGuard
        try:
            if type(row) is not dict or row.get('source_draft_id') is not None:
                self._blocked('ROUTE_EVAL_DIRECT_CALL_REQUIRED')
            body=CreateActionProposalRequest(actionTypeId=row['action_type_id'],taskId=row['task_id'],
                purpose=row['purpose'],payload=row['payload'],expiresAt=row['expires_at'])
            risk=classify_action_risk(row['action_type_id'],row['action_type_snapshot'],row['payload'],None)
        except (TypeError,ValueError,KeyError,AttributeError):
            self._blocked('ROUTE_EVAL_DIRECT_CALL_REQUIRED')
        self._exact_leaf(scope,row.get('created_by'),body,row['action_type_snapshot'],risk)
        binding=self._binding(scope,body,row['action_type_snapshot'])
        stable,_=_proposal_stable_envelope(scope,row['created_by'],body,row['action_type_snapshot'],risk,
            action_binding_hash=binding,source_draft_ref=None,expires_at=row['expires_at'])
        try:
            if (type(row.get('version')) is not int or row['version']<1
                or row.get('action_type_revision_hash')!=row['action_type_snapshot']['revisionHash']
                or row.get('run_id') is not None or row.get('object_ref') is not None
                or row.get('client_risk_hint') is not None or row.get('risk_level')!=risk.level.value
                or row.get('policy_snapshot')!=stable['policy'] or row.get('payload')!=body.payload
                or row.get('diff')!={} or row.get('evidence_refs')!=[]
                or any(row.get(name) is not None for name in ('impact_preview_id','impact_preview_revision',
                    'impact_preview_hash','source_draft_id','source_draft_revision','source_draft_hash'))
                or row.get('action_binding_hash')!=binding
                or row.get('approval_policy_hash')!=stable['approvalPolicyHash']
                or row.get('proposal_hash')!=canonical_hash(stable)
                or row.get('status') not in {'drafted','approved'}):
                raise ValueError('complete original proposal row required')
            draft=conn.execute('SELECT snapshot FROM aip_action_draft WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
                (*scope.key,row['proposal_id'])).fetchone()
            if type(draft) is not dict or draft.get('snapshot')!=stable:
                raise ValueError('complete original stable draft required')
        except (TypeError,ValueError,KeyError,AttributeError):
            self._blocked('ROUTE_EVAL_PROPOSAL_DRIFTED')
        if not checker:
            if actor!=row['created_by']:self._blocked('ROUTE_EVAL_REPLAY_MAKER_REQUIRED')
            return None
        if actor==row['created_by']:self._blocked('ROUTE_EVAL_INDEPENDENT_CHECKER_REQUIRED')
        try:return (ModelEvalActionGuard._role(conn,scope,actor),)
        except (TypeError,ValueError,RuntimeError):
            self._blocked('ROUTE_EVAL_CURRENT_CHECKER_REQUIRED')

    def prelock_decision(self,conn,scope,actor,proposal_id):
        from aos_api.aip_action_models import CreateActionProposalRequest
        from aos_api.aip_action_policy import classify_action_risk
        from aos_api.aip_action_policy import is_route_eval_action,ROUTE_EVAL_MATERIAL_ACTION_ID
        row=conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
            (*scope.key,proposal_id)).fetchone()
        if row is None or not is_route_eval_action(row.get('action_type_id'),row.get('action_type_snapshot') or {}):
            return None
        if ROUTE_EVAL_MATERIAL_ACTION_ID in {row.get('action_type_id'),(row.get('action_type_snapshot') or {}).get('id')}:
            self._blocked('ROUTE_EVAL_MATERIAL_NATIVE_GUARD_REQUIRED')
        try:
            if row.get('proposal_id')!=proposal_id:raise ValueError
            body=CreateActionProposalRequest(actionTypeId=row['action_type_id'],taskId=row['task_id'],
                purpose=row['purpose'],payload=row['payload'],expiresAt=row['expires_at'])
            risk=classify_action_risk(row['action_type_id'],row['action_type_snapshot'],row['payload'],None)
            ref=self._exact_leaf(scope,row['created_by'],body,row['action_type_snapshot'],risk)
        except (TypeError,ValueError,KeyError,AttributeError):
            self._blocked('ROUTE_EVAL_DIRECT_CALL_REQUIRED')
        self.check_proposal(conn,scope,actor,row,checker=True)
        checked_at=self._native_inputs(conn,scope,row['created_by'],body,ref)
        self.check_proposal(conn,scope,actor,row,checker=True)
        if row['status'] not in {'drafted','approved'} or row['expires_at']<=checked_at:
            self._blocked('ROUTE_EVAL_CURRENT_PROPOSAL_REQUIRED')
        return self._proposal_fingerprint(row)

    def assert_prelocked_proposal(self,row,fingerprint):
        from aos_api.aip_action_policy import is_route_eval_action
        if fingerprint is None:
            if is_route_eval_action(row.get('action_type_id'),row.get('action_type_snapshot') or {}):
                self._blocked('ROUTE_EVAL_PRELOCK_REQUIRED')
            return
        if self._proposal_fingerprint(row)!=fingerprint:
            self._blocked('ROUTE_EVAL_PRELOCK_PROPOSAL_DRIFTED')

    def _current_call_budget_request(self,conn,scope,approval_event_id):
        """Recheck one original Route approval and return its exact budget request.

        This performs no reservation write. The caller decides whether it is
        creating a new hold or proving an already-held manifest binding.
        """
        from aos_api.aip_action_store import canonical_hash
        from aos_api.aip_budget_reservation_store import (
            AipBudgetReservationStore,canonical_hash as budget_hash,
        )
        from aos_api.tenant_scope import TenantScope
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or type(approval_event_id) is not str or not 1<=len(approval_event_id)<=200
            or approval_event_id!=approval_event_id.strip()):
            self._blocked('ROUTE_EVAL_APPROVAL_EXACT_IDENTITY_REQUIRED')
        approval=conn.execute('SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
            (*scope.key,approval_event_id)).fetchone()
        try:
            if (type(approval) is not dict or approval['approval_event_id']!=approval_event_id
                or approval['decision']!='approved'
                or any(type(approval[name]) is not str or not approval[name]
                    for name in ('proposal_id','actor_id'))):
                raise ValueError
        except (TypeError,ValueError,KeyError,AttributeError):
            self._blocked('ROUTE_EVAL_DEDICATED_APPROVAL_REQUIRED')
        fingerprint=self.prelock_decision(conn,scope,approval['actor_id'],approval['proposal_id'])
        if fingerprint is None:self._blocked('ROUTE_EVAL_DEDICATED_APPROVAL_REQUIRED')
        row=conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE',
            (*scope.key,approval['proposal_id'])).fetchone()
        if type(row) is not dict:self._blocked('ROUTE_EVAL_DEDICATED_APPROVAL_REQUIRED')
        self.assert_prelocked_proposal(row,fingerprint)
        roles=self.check_proposal(conn,scope,approval['actor_id'],row,checker=True)
        events=conn.execute("SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s AND decision='approved' ORDER BY created_at,approval_event_id FOR SHARE",
            (*scope.key,row['proposal_id'])).fetchall()
        eligibility={'tenant':{'orgId':scope.org_id,'projectId':scope.project_id},
            'actorId':approval['actor_id'],'roles':sorted(role.lower() for role in roles),
            'slotId':'checker.1','approvalPolicyHash':row['approval_policy_hash']}
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        try:
            if (type(events) is not list or len(events)!=1 or dict(events[0])!=dict(approval)
                or row['status']!='approved' or row['purpose']!='route-eval'
                or approval['proposal_hash']!=row['proposal_hash']
                or approval['proposal_version']!=row['version']-1
                or approval['action_binding_hash']!=row['action_binding_hash']
                or approval['approval_policy_hash']!=row['approval_policy_hash']
                or approval['slot_id']!='checker.1'
                or approval['eligibility_snapshot_hash']!=canonical_hash(eligibility)
                or approval['actor_id']==row['created_by']
                or type(now) is not datetime or now.utcoffset() is None
                or approval['expires_at'] is None or approval['expires_at']<=now
                or row['expires_at']<=now or self._native['application'].expires_at<=now):
                raise ValueError
        except (TypeError,ValueError,KeyError,AttributeError):
            self._blocked('ROUTE_EVAL_CURRENT_UNIQUE_APPROVAL_REQUIRED')
        projection={key:approval[key] for key in ('approval_event_id','proposal_id',
            'proposal_version','proposal_hash','decision','actor_id','reason','expires_at',
            'created_at','action_binding_hash')}
        approval_ref=BudgetExactRef(resourceType='ActionApprovalEvent',
            resourceId=approval_event_id,revision=approval['proposal_version'],
            contentHash=budget_hash(projection,prefixed=True))
        app=self._native['application'];payload=row['payload']
        matches=[recipe for recipe in app.calls
            if route_eval_approval_payload(app,recipe)=={key:value for key,value in payload.items()
                if key!='materialRef'}]
        if len(matches)!=1:self._blocked('ROUTE_EVAL_APPROVAL_CALL_BINDING_REQUIRED')
        recipe=matches[0]
        request=build_route_eval_call_budget_request(self._native['context_bytes'],application=app,
            recipe=recipe,approval_ref=approval_ref,checked_at=now)
        expected_price=BudgetExactRef(resourceType='ModelPriceSnapshotRevision',
            resourceId=recipe.price_ref.asset_id,revision=recipe.price_ref.revision,
            contentHash='sha256:'+recipe.price_ref.content_hash)
        if (type(request) is not ReserveBudgetRequest
            or request.operation_id!=row['action_type_id'] or request.task_ref!=app.task_ref
            or request.task_ref.resource_id!=row['task_id']
            or request.invocation_key!=payload.get('callKey')
            or request.upper_bound_minor!=payload.get('budgetUpperBoundMinor')
            or request.policy_ref!=recipe.task_budget_ref or request.pricing_ref!=expected_price
            or request.approval_ref!=approval_ref or request.currency!='CNY'):
            self._blocked('ROUTE_EVAL_BUDGET_REQUEST_BINDING_REQUIRED')
        return request,row['created_by']

    def reserve_current_call_budget(self,conn,scope,approval_event_id):
        """Recheck one original Route approval, then use the unchanged budget Store.

        This retains the caller transaction, creates no Provider request and
        does not turn an approval reference into authority without readback.
        """
        from aos_api.aip_budget_reservation_store import AipBudgetReservationStore
        request,actor=self._current_call_budget_request(
            conn,scope,approval_event_id)
        return AipBudgetReservationStore().reserve_in_transaction(
            conn,scope,request,actor=actor)


def _material_context(conn,expected_database,scope):
    from aos_api.aip_model_route_eval_owner import _require_native_connection
    _require_native_connection(conn)
    row=conn.execute("""SELECT pg_catalog.current_database() AS database,
        (SELECT oid FROM pg_catalog.pg_database WHERE datname=pg_catalog.current_database()) AS database_oid,
        session_user AS login,current_user AS role,
        pg_catalog.current_setting('aos.org_id',true) AS org_id,pg_catalog.current_setting('aos.project_id',true) AS project_id,
        pg_catalog.current_setting('transaction_isolation') AS isolation,
        pg_catalog.current_setting('transaction_read_only') AS readonly,
        pg_catalog.pg_current_xact_id()::text AS xid,pg_catalog.pg_backend_pid() AS pid,pg_catalog.clock_timestamp() AS now,
        ARRAY[
          pg_catalog.to_regclass('meta_object_type')=pg_catalog.to_regclass('public.meta_object_type'),
          pg_catalog.to_regclass('meta_action_type')=pg_catalog.to_regclass('public.meta_action_type'),
          pg_catalog.to_regclass('meta_membership')=pg_catalog.to_regclass('public.meta_membership'),
          pg_catalog.to_regclass('aip_action_draft_head')=pg_catalog.to_regclass('public.aip_action_draft_head'),
          pg_catalog.to_regclass('aip_action_draft_revision')=pg_catalog.to_regclass('public.aip_action_draft_revision')
        ] AS original_relations,
        ARRAY[
          pg_catalog.has_table_privilege(current_user,'public.aip_action_draft_revision','SELECT'),
          NOT pg_catalog.has_any_column_privilege(current_user,'public.aip_action_draft_revision','UPDATE'),
          NOT pg_catalog.has_table_privilege(current_user,'public.aip_action_draft_revision','DELETE'),
          NOT pg_catalog.has_table_privilege(current_user,'public.aip_action_draft_revision','TRUNCATE')
        ] AS append_only_revision""").fetchone()
    if (type(row) is not dict or row.get('database')!=expected_database
        or type(row.get('database_oid')) is not int or row['database_oid']<1
        or type(row.get('login')) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}',row['login']) is None
        or (row.get('role'),row.get('org_id'),row.get('project_id'),row.get('isolation'),row.get('readonly'))
           !=('aos_runtime',*scope.key,'serializable','off')
        or type(row.get('xid')) is not str or re.fullmatch(r'[1-9][0-9]*',row['xid']) is None
        or type(row.get('pid')) is not int or row['pid']<1
        or type(row.get('now')) is not datetime or row['now'].utcoffset() is None
        or type(row.get('original_relations')) is not list or len(row['original_relations'])!=5
        or any(value is not True for value in row['original_relations'])
        or type(row.get('append_only_revision')) is not list or len(row['append_only_revision'])!=4
        or any(value is not True for value in row['append_only_revision'])):
        raise ValueError('same native runtime material caller required')
    return row


def _material_metadata(conn,scope):
    from aos_api.aip_action_store import AipActionStore
    from aos_api.aip_model_route_eval_manifest import _canonical
    obj=conn.execute("""SELECT id,name,description,published,properties,required_markings
        FROM public.meta_object_type WHERE id=%s FOR SHARE""",(_ROUTE_OBJECT['id'],)).fetchone()
    if type(obj) is not dict or _canonical(obj)!=_canonical(_ROUTE_OBJECT):
        raise ValueError('exact original material object metadata required')
    row=conn.execute('SELECT id FROM public.meta_action_type WHERE id=%s FOR SHARE',(ROUTE_MATERIAL_ACTION_ID,)).fetchone()
    if row is None:raise ValueError('original material action metadata required')
    def same_caller(requested_scope):
        if type(requested_scope) is not type(scope) or requested_scope!=scope:
            raise ValueError('original metadata store changed scope')
        return nullcontext(conn)
    snapshot=AipActionStore(connect_factory=same_caller).action_type_snapshot(scope,ROUTE_MATERIAL_ACTION_ID)
    action={k:v for k,v in snapshot.items() if k!='revisionHash'}
    if _canonical(action)!=_canonical(_MATERIAL_ACTION):
        raise ValueError('exact original material action metadata required')
    return snapshot


def read_route_eval_material_draft(conn,*,expected_database: str,scope,material_ref,
                                  expected_maker: str) -> bytes:
    """Read/recompute original current material, without approval or execution.

    Native material provenance is only a necessary input: the complete locked
    current context, Source/Rule and independent original approval still need
    their own actual caller checks. This reader creates no connection or writes.
    Metadata, membership and the original draft head locks stay with the caller.
    Revisions retain their original append-only permissions: the locked head
    prevents a legitimate revision switch, so no UPDATE privilege is needed
    just to read the immutable current revision.
    """
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_contracts import ActionRiskLevel
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_action_store import AipActionStore,canonical_hash
    from aos_api.aip_model_eval_action import ModelEvalActionGuard
    from aos_api.aip_model_route_eval_manifest import _canonical
    try:
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or type(expected_database) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}',expected_database) is None
            or type(expected_maker) is not str or not 1<=len(expected_maker)<=200
            or expected_maker!=expected_maker.strip() or expected_maker=='unknown'):
            raise ValueError('exact material caller scope, database and maker required')
        ref=RouteEvalMaterialRef.model_validate(_alias_input(material_ref))
        if (ref.tenant.org_id,ref.tenant.project_id)!=scope.key:
            raise ValueError('same tenant material reference required')
        before=_material_context(conn,expected_database,scope)
        snapshot=_material_metadata(conn,scope)
        ModelEvalActionGuard._role(conn,scope,expected_maker)
        head=conn.execute("""SELECT * FROM public.aip_action_draft_head
            WHERE org_id=%s AND project_id=%s AND draft_id=%s FOR SHARE""",(*scope.key,ref.resource_id)).fetchone()
        if (type(head) is not dict or (head.get('org_id'),head.get('project_id'),head.get('draft_id'))!=(*scope.key,ref.resource_id)
            or type(head.get('current_revision')) is not int or head['current_revision']!=ref.revision
            or type(head.get('version')) is not int or head['version']!=ref.head_version
            or head.get('lifecycle')!='editable' or head.get('submitted_proposal_id') is not None
            or head.get('created_by')!=expected_maker):
            raise ValueError('exact current original material head required')
        row=conn.execute("""SELECT * FROM public.aip_action_draft_revision
            WHERE org_id=%s AND project_id=%s AND draft_id=%s AND revision=%s""",
            (*scope.key,ref.resource_id,ref.revision)).fetchone()
        if (type(row) is not dict or (row.get('org_id'),row.get('project_id'),row.get('draft_id'))!=(*scope.key,ref.resource_id)
            or type(row.get('revision')) is not int or row['revision']!=ref.revision
            or row.get('lifecycle')!='editable' or row.get('created_by')!=expected_maker
            or row.get('content_hash')!=ref.content_hash):
            raise ValueError('exact original material revision required')
        request=CreateActionDraftRequest.model_validate(row['request_payload'])
        if _canonical(row['request_payload'])!=_canonical(request.model_dump(mode='json',by_alias=True)):
            raise ValueError('original complete request must not be normalized')
        payload=request.payload
        if (set(payload)!={'schemaVersion','context','application'}
            or payload['schemaVersion']!='aos.route-eval-material/v1'
            or _canonical(row['action_type_snapshot'])!=_canonical(snapshot)):
            raise ValueError('complete original material schema and metadata required')
        raw=b'AOS-MODEL-ROUTE-EVAL-CONTEXT-v1\n'+_canonical(payload['context'])
        risk=classify_action_risk(request.action_type_id,snapshot,payload,None)
        if (risk.level is not ActionRiskLevel.R1 or risk.floor is not ActionRiskLevel.R1
            or risk.approval_policy.get('draftOnly') is not True or risk.approval_policy.get('makerChecker') is not False
            or _canonical(row['risk_snapshot'])!=_canonical(AipActionStore._risk_snapshot(risk))
            or row['approval_policy_hash']!=canonical_hash({'floor':risk.floor.value,'reasons':list(risk.reasons),**risk.approval_policy})
            or canonical_hash({'request':row['request_payload'],'actionType':row['action_type_snapshot'],
                'risk':row['risk_snapshot'],'lifecycle':'editable'})!=ref.content_hash):
            raise ValueError('original material risk and complete content hash required')
        after=_material_context(conn,expected_database,scope);at=after['now']
        clocks=[head.get('created_at'),row.get('created_at'),head.get('updated_at')]
        if (any(after[k]!=v for k,v in before.items() if k!='now') or at<before['now']
            or any(type(t) is not datetime or t.utcoffset() is None for t in clocks)
            or not clocks[0]<=clocks[1]<=clocks[2]<=at):
            raise ValueError('same material caller and original record clocks required')
        expected=build_route_eval_material_draft(raw,application=payload['application'],checked_at=at)
        if _canonical(row['request_payload'])!=_canonical(expected.model_dump(mode='json',by_alias=True)):
            raise ValueError('original material request must bind the whole application')
        result={'schemaVersion':'aos.route-eval-material-readback/v1','tenant':ref.tenant.model_dump(mode='json',by_alias=True),
            'materialRef':ref.model_dump(mode='json',by_alias=True),'makerId':expected_maker,
            'context':payload['context'],'application':expected.payload['application'],
            'actionTypeRevisionHash':snapshot['revisionHash'],'database':after['database'],'databaseOid':after['database_oid'],
            'callerXid':after['xid'],'callerPid':after['pid'],'observedAt':at.isoformat(),
            'approvalAllowed':False,'executionAllowed':False}
        return MATERIAL_READBACK_DOMAIN+_canonical(result)
    except (ValueError,TypeError,KeyError,AttributeError,RuntimeError,psycopg.Error):
        raise RouteEvalMaterialRejected('ROUTE_EVAL_ORIGINAL_MATERIAL_REQUIRED') from None


_EVAL_CONTEXT_RELATIONS=(
    'aip_registered_model_head','aip_registered_model_revision',
    'aip_model_route_head','aip_model_route_revision',
    'aip_runtime_policy_head','aip_runtime_policy_revision',
    'aip_eval_run','aip_eval_suite_revision','aip_eval_dataset_revision',
    'aip_eval_contract_head','aip_eval_contract_revision',
    'aip_publication_event','aip_release_gate_decision','aip_publication_epoch',
)


def _native_eval_context_boundary(conn,expected_database,scope):
    from aos_api.aip_model_route_eval_owner import _require_native_connection
    _require_native_connection(conn)
    row=conn.execute("""SELECT TRUE AS native_eval_context,
        pg_catalog.current_database() AS database,
        (SELECT oid FROM pg_catalog.pg_database WHERE datname=pg_catalog.current_database()) AS database_oid,
        session_user AS login,current_user AS role,
        pg_catalog.current_setting('aos.org_id',true) AS org_id,
        pg_catalog.current_setting('aos.project_id',true) AS project_id,
        pg_catalog.current_setting('transaction_isolation') AS isolation,
        pg_catalog.current_setting('transaction_read_only') AS readonly,
        pg_catalog.pg_current_xact_id()::text AS xid,
        pg_catalog.pg_backend_pid() AS pid,pg_catalog.clock_timestamp() AS now,
        (SELECT pg_catalog.array_agg(
            pg_catalog.to_regclass(name)=pg_catalog.to_regclass('public.'||name) ORDER BY name)
         FROM pg_catalog.unnest(%s::text[]) AS original(name)) AS original_relations""",
        (list(_EVAL_CONTEXT_RELATIONS),)).fetchone()
    if (type(row) is not dict or row.get('database')!=expected_database
        or type(row.get('database_oid')) is not int or row['database_oid']<1
        or type(row.get('login')) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}',row['login']) is None
        or (row.get('role'),row.get('org_id'),row.get('project_id'),row.get('isolation'),row.get('readonly'))
           !=('aos_runtime',*scope.key,'serializable','off')
        or type(row.get('xid')) is not str or re.fullmatch(r'[1-9][0-9]*',row['xid']) is None
        or type(row.get('pid')) is not int or row['pid']<1
        or type(row.get('now')) is not datetime or row['now'].utcoffset() is None
        or type(row.get('original_relations')) is not list
        or len(row['original_relations'])!=len(_EVAL_CONTEXT_RELATIONS)
        or any(value is not True for value in row['original_relations'])):
        raise ValueError('same native runtime Eval context caller required')
    return row


def read_native_eval_subject_context_bytes(
    conn,*,expected_database: str,scope,candidate,run_id: str,
    expected_run_version: int,expected_run_status,expires_at: datetime,
) -> bytes:
    """Read an original locked descriptive snapshot on the native caller.

    Locks remain with the caller; no connection or transaction is ended here.
    Original published-row SHARE precedes the audited original epoch SHARE.
    A bump after this SERIAL snapshot propagates native serialization failure;
    locks remain with this caller. Real native concurrency still needs its own
    qualification. These bytes NEVER prove Source/approval or execution rights.
    """
    from aos_api.tenant_scope import TenantScope
    from aos_api.aip_eval_contracts import EvalRunStatus
    from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
    from aos_api.aip_model_runtime_contracts import ModelEvalCandidate
    from aos_api.aip_model_runtime_store import AipModelRuntimeStore
    from aos_api.aip_model_route_eval_subject_binding import _fresh
    from aos_api.aip_model_route_eval_context_reader import (
        _read_original_eval_context_payload,_encode_eval_context_payload,
    )
    if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
        or type(expected_database) is not str or re.fullmatch(r'[a-z][a-z0-9_]{0,62}',expected_database) is None
        or type(candidate) is not ModelEvalCandidate or candidate.execution_allowed is not False
        or type(run_id) is not str or not 1<=len(run_id)<=200 or run_id!=run_id.strip()
        or type(expected_run_version) is not int or expected_run_version<1
        or type(expected_run_status) is not EvalRunStatus
        or expected_run_status not in {EvalRunStatus.QUEUED,EvalRunStatus.RUNNING}
        or type(expires_at) is not datetime or expires_at.utcoffset() is None):
        raise ValueError('exact descriptive native Eval context inputs required')
    claim=_fresh(candidate,ModelEvalCandidate)
    before=_native_eval_context_boundary(conn,expected_database,scope)
    if before['now']>=expires_at:raise ValueError('native Eval context deadline elapsed')

    def same_caller(requested_scope):
        if type(requested_scope) is not TenantScope or requested_scope!=scope:
            raise ValueError('original context store changed scope')
        return nullcontext(conn)

    models=AipModelRuntimeStore(connect_factory=same_caller)
    method=(models.require_current_route_eval_candidate_for_update
            if claim.source_ref.asset_type=='ModelRouteRevision'
            else models.require_current_model_eval_candidate_for_update)
    current=method(conn,scope,claim.source_ref,claim.target_ref,
                   expected_head_version=claim.expected_head_version)
    if current!=claim:raise ValueError('original current Eval candidate drifted')
    if claim.source_ref.asset_type=='ModelRouteRevision':
        source=models.get_route(scope,claim.source_ref.asset_id)
        for identifier in sorted({item.model.asset_id for item in source.candidates}):
            row=conn.execute("""SELECT current_revision FROM public.aip_registered_model_head
                WHERE org_id=%s AND project_id=%s AND registered_model_id=%s FOR SHARE""",
                (*scope.key,identifier)).fetchone()
            if row is None:raise ValueError('original Route model head unavailable')
        row=conn.execute("""SELECT current_revision FROM public.aip_runtime_policy_head
            WHERE org_id=%s AND project_id=%s AND runtime_policy_id=%s FOR SHARE""",
            (*scope.key,source.runtime_policy_ref.asset_id)).fetchone()
        if row is None:raise ValueError('original Route policy head unavailable')
    authority=AipEvalAuthorityStore(connect_factory=same_caller)
    run_row=authority._run_row(conn,scope,run_id,for_update=True)
    if run_row is None:raise ValueError('original Eval Run unavailable')
    run=authority._run_from_row(run_row)
    if run.eval_contract_ref is None:raise ValueError('original Eval Contract required')
    ref=run.eval_contract_ref
    row=conn.execute("""SELECT current_revision FROM public.aip_eval_contract_head
        WHERE org_id=%s AND project_id=%s AND contract_id=%s FOR SHARE""",
        (*scope.key,ref.resource_id)).fetchone()
    if row is None or row['current_revision']!=ref.revision:
        raise ValueError('current original Eval Contract required')
    # Obtain original references only; readiness/raw JSON/hash stay in the DAO body.
    contract=conn.execute("""SELECT publication_ref,release_gate_ref FROM public.aip_eval_contract_revision
        WHERE org_id=%s AND project_id=%s AND contract_id=%s AND revision=%s""",
        (*scope.key,ref.resource_id,ref.revision)).fetchone()
    if contract is None:raise ValueError('original Eval Contract revision unavailable')
    from aos_api.aip_production_contracts import ExactRevisionRef
    publication=ExactRevisionRef.model_validate(contract['publication_ref'])
    gate=ExactRevisionRef.model_validate(contract['release_gate_ref'])
    row=conn.execute("""SELECT p.event_id,p.publication_id FROM public.aip_publication_event p
        WHERE p.org_id=%s AND p.project_id=%s AND p.event_type='published'
          AND p.publication_id=(SELECT b.publication_id FROM public.aip_publication_event b
            WHERE b.org_id=%s AND b.project_id=%s AND b.event_id=%s)
        ORDER BY p.occurred_at,p.event_id LIMIT 1 FOR SHARE OF p""",
        (*scope.key,*scope.key,publication.resource_id)).fetchone()
    if row is None:raise ValueError('original published event lock unavailable')
    from aos_api.aip_model_route_eval_publication_epoch import lock_eval_publication_epoch
    lock_eval_publication_epoch(conn,scope,row['publication_id'])
    row=conn.execute("""SELECT decision_id FROM public.aip_release_gate_decision
        WHERE org_id=%s AND project_id=%s AND decision_id=%s FOR SHARE""",
        (*scope.key,gate.resource_id)).fetchone()
    if row is None:raise ValueError('original release gate lock unavailable')
    payload=_read_original_eval_context_payload(conn,scope=scope,claim=claim,run_id=run_id,
        expected_run_version=expected_run_version,expected_run_status=expected_run_status,
        evaluated_at=before['now'])
    after=_native_eval_context_boundary(conn,expected_database,scope)
    if ({k:v for k,v in before.items() if k!='now'}!={k:v for k,v in after.items() if k!='now'}
        or after['now']<before['now'] or after['now']>=expires_at):
        raise ValueError('native Eval caller or deadline changed after dependency locks')
    return _encode_eval_context_payload(payload)
