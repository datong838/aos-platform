"""Independent review of exact Source claims; approval never verifies or grants capacity."""
from datetime import UTC,datetime

from aos_api.aip_action_models import CreateActionProposalRequest,DecideActionProposalRequest
from aos_api.aip_action_policy import classify_action_risk
from aos_api.aip_action_store import AipActionStore,canonical_hash
from aos_api.aip_contracts import ActionRiskLevel
from aos_api.aip_provider_capacity_action import ProviderCapacityActionGuard,ProviderCapacityActionBlocked
from aos_api.aip_provider_capacity_source_contracts import (
    ProviderPhysicalAccountCandidate,ProviderCapacityBasisCandidate,ProviderCapacitySourceCandidate)
from aos_api.aip_provider_capacity_source_authority import ProviderCapacityCandidateStore,ProviderCapacityCandidateBlocked
from aos_api.aip_model_eval_request_store import ModelEvalRequestBlocked
from aos_api.aip_production_contract_store import ProductionContractError
from aos_api.auth import Principal
from aos_api.db import connect
from aos_api.openfga import openfga_api_url
from aos_api.tenant_scope import TenantScope

ACTION_ID='aip_review_provider_capacity_source'
OBJECT_ID='ProviderCapacitySourceReview'
ProviderCapacitySourceActionBlocked=ProviderCapacityActionBlocked


class ProviderCapacitySourceActionGuard(ProviderCapacityActionGuard):
    action_id=ACTION_ID
    object_id=OBJECT_ID
    object_snapshot=dict(id=OBJECT_ID,name='Provider容量来源审查',description='仅供独立审批的不可执行Source条款',
        published=True,properties=[],required_markings=[])
    action_snapshot=dict(id=ACTION_ID,name='审查Provider容量来源',objectType=OBJECT_ID,
        parameters=[],requiredMarkings=[],submissionCriteria=[])

    @staticmethod
    def _candidate(conn,scope,ref,kind,model,maker):
        row=conn.execute("SELECT *,encode(public.digest(convert_to(public.canonical_asset_registry_jsonb(request_json),'UTF8'),'sha256'),'hex') AS actual_hash "
            "FROM aip_provider_capacity_candidate WHERE org_id=%s AND project_id=%s AND candidate_id=%s AND revision=%s AND candidate_kind=%s",
            (*scope.key,ref.asset_id,ref.revision,kind)).fetchone()
        if (row is None or row['content_hash']!=ref.content_hash or row['actual_hash']!=ref.content_hash
            or row['authorization_mode']!='CANDIDATE_ONLY_NO_CAPACITY_NO_START'
            or row['basis_verified'] is not False or row['execution_allowed'] is not False
            or row['created_by']!=maker or set(row['request_json'])!={'candidateKind','candidate','makerSubject'}
            or row['request_json']['candidateKind']!=kind or row['request_json']['makerSubject']!=maker):
            raise ProviderCapacitySourceActionBlocked('SOURCE_EXACT_CANDIDATE_REQUIRED')
        value=model.model_validate(row['request_json']['candidate'])
        if (value.tenant.org_id,value.tenant.project_id)!=scope.key:
            raise ProviderCapacitySourceActionBlocked('SOURCE_CANDIDATE_TENANT_REQUIRED')
        return value

    @staticmethod
    def _allocation(conn,scope,source,maker):
        request,original_maker=ProviderCapacityActionGuard._request(conn,scope,
            source.allocation_request_ref.asset_id,source.allocation_request_ref.content_hash)
        ref=source.allocation_approval_ref
        event=conn.execute('SELECT * FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND approval_event_id=%s',
            (*scope.key,ref.asset_id)).fetchone()
        if event is None:
            raise ProviderCapacitySourceActionBlocked('SOURCE_ALLOCATION_APPROVAL_REQUIRED')
        row=conn.execute('SELECT * FROM aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE',
            (*scope.key,event['proposal_id'])).fetchone()
        events=conn.execute('SELECT approval_event_id FROM aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
            (*scope.key,event['proposal_id'])).fetchall()
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if (row is None or original_maker!=maker or row['created_by']!=maker
            or row['action_type_id']!='aip_request_provider_capacity' or row['status']!='approved'
            or row['payload']!={'requestId':source.allocation_request_ref.asset_id,'requestHash':source.allocation_request_ref.content_hash}
            or len(events)!=1 or event['decision']!='approved' or event['proposal_version']!=1 or row['version']!=2
            or event['proposal_hash']!=row['proposal_hash'] or event['action_binding_hash']!=row['action_binding_hash']
            or event['approval_policy_hash']!=row['approval_policy_hash'] or event['slot_id']!='checker.1'
            or event['expires_at'] is None or event['expires_at']<=now):
            raise ProviderCapacitySourceActionBlocked('SOURCE_ALLOCATION_APPROVAL_DRIFTED')
        guard=ProviderCapacityActionGuard()
        guard.check_proposal(conn,scope,event['actor_id'],row,checker=True)
        eligibility=canonical_hash(dict(tenant=dict(orgId=scope.org_id,projectId=scope.project_id),
            actorId=event['actor_id'],roles=['owner'],slotId='checker.1',approvalPolicyHash=row['approval_policy_hash']))
        snapshot=AipActionStore()._bundle(conn,scope,row['proposal_id']).approvals[0]
        if event['eligibility_snapshot_hash']!=eligibility or canonical_hash(snapshot.model_dump(mode='json',by_alias=True))!=ref.content_hash:
            raise ProviderCapacitySourceActionBlocked('SOURCE_ALLOCATION_EVENT_HASH_DRIFTED')
        return request,event['expires_at']

    def check_request(self,conn,scope,actor,body,action_snapshot,risk):
        if (type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
            or body.action_type_id!=ACTION_ID or action_snapshot!=self.read_metadata(conn)
            or body.purpose!='capacity-source-review' or body.task_id is not None or body.run_id is not None
            or body.object_ref is not None or body.impact_preview_ref is not None or body.diff or body.evidence_refs
            or body.risk_hint is not None or openfga_api_url() or set(body.payload)!={'sourceCandidate'}):
            raise ProviderCapacitySourceActionBlocked('SOURCE_PROPOSAL_SHAPE_REQUIRED')
        current=classify_action_risk(ACTION_ID,action_snapshot,body.payload,None)
        if (risk!=current or risk.level is not ActionRiskLevel.R2
            or risk.approval_policy.get('makerChecker') is not True
            or risk.approval_policy.get('executionAllowed') is not False or risk.approval_policy.get('draftOnly') is not False):
            raise ProviderCapacitySourceActionBlocked('SOURCE_REVIEW_POLICY_REQUIRED')
        identity=conn.execute("SELECT current_user AS role,current_setting('aos.org_id',true) AS org_id,current_setting('aos.project_id',true) AS project_id").fetchone()
        if (identity['role'],identity['org_id'],identity['project_id'])!=('aos_runtime',*scope.key):
            raise ProviderCapacitySourceActionBlocked('SOURCE_TENANT_ROLE_REQUIRED')
        self._role(conn,scope,actor)
        try:
            source=ProviderCapacitySourceCandidate.model_validate(body.payload['sourceCandidate'])
            if (source.tenant.org_id,source.tenant.project_id)!=scope.key:
                raise ProviderCapacitySourceActionBlocked('SOURCE_TENANT_REQUIRED')
            request,expiry=self._allocation(conn,scope,source,actor)
            account=self._candidate(conn,scope,source.physical_account_ref,'account',ProviderPhysicalAccountCandidate,actor)
            basis=self._candidate(conn,scope,source.basis_ref,'basis',ProviderCapacityBasisCandidate,actor)
            if (basis.physical_account_ref!=source.physical_account_ref
                or account.physical_account_id!=request.physical_account_id
                or request.provider_ref not in account.provider_refs or basis.max_concurrency>request.requested_max_concurrency):
                raise ProviderCapacitySourceActionBlocked('SOURCE_ACCOUNT_OR_CONCURRENCY_DRIFTED')
            ProviderCapacityCandidateStore._account_dependencies(conn,scope,account)
            ProviderCapacityCandidateStore._evidence(conn,scope,basis.evidence_ref)
            now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            if (not max(request.valid_from,basis.valid_from)<=source.valid_from<=now<source.valid_until
                or source.valid_until>min(request.valid_until,request.proposal_expires_at,basis.valid_until,expiry)
                or body.effective_expiry()>source.valid_until):
                raise ProviderCapacitySourceActionBlocked('SOURCE_REVIEW_WINDOW_DRIFTED')
        except (TypeError,ValueError,ProviderCapacityCandidateBlocked,ModelEvalRequestBlocked,ProductionContractError) as exc:
            raise ProviderCapacitySourceActionBlocked('SOURCE_STRICT_DEPENDENCIES_REQUIRED') from exc
        return canonical_hash(dict(sourceCandidate=source.model_dump(mode='json',by_alias=True),
            actionTypeRevisionHash=action_snapshot['revisionHash']))


def _principal(principal,key):
    if (type(principal) is not Principal or principal.token_kind!='oidc'
        or (principal.org_id,principal.project_id)!=('org-org','dev-project')
        or any(type(v) is not str or not 1<=len(v)<=200 or v!=v.strip() for v in (key,principal.subject))):
        raise ProviderCapacitySourceActionBlocked('SOURCE_NATIVE_OIDC_REQUIRED')
    return TenantScope(principal.org_id,principal.project_id)


def propose_provider_capacity_source(principal,candidate,idempotency_key,expires_at,*,connect_factory=None):
    scope=_principal(principal,idempotency_key)
    if (type(candidate) is not ProviderCapacitySourceCandidate or type(expires_at) is not datetime
        or expires_at.utcoffset() is None or expires_at<=datetime.now(UTC)):
        raise ProviderCapacitySourceActionBlocked('SOURCE_NATIVE_CANDIDATE_REQUIRED')
    try:candidate=ProviderCapacitySourceCandidate.model_validate(candidate.model_dump(mode='python',by_alias=True))
    except (TypeError,ValueError) as exc:raise ProviderCapacitySourceActionBlocked('SOURCE_STRICT_CANDIDATE_REQUIRED') from exc
    factory=connect_factory or connect;guard=ProviderCapacitySourceActionGuard()
    with factory(scope) as conn:snapshot=guard.read_metadata(conn)
    payload=dict(sourceCandidate=candidate.model_dump(mode='json',by_alias=True))
    body=CreateActionProposalRequest(actionTypeId=ACTION_ID,purpose='capacity-source-review',payload=payload,expiresAt=expires_at)
    return AipActionStore(factory,provider_capacity_source_guard=guard).create_proposal(scope,principal.subject,
        idempotency_key,body,snapshot,classify_action_risk(ACTION_ID,snapshot,payload,None))


def decide_provider_capacity_source(principal,proposal_id,idempotency_key,body,*,connect_factory=None):
    scope=_principal(principal,idempotency_key)
    if (type(proposal_id) is not str or not 1<=len(proposal_id)<=200 or proposal_id!=proposal_id.strip()
        or type(body) is not DecideActionProposalRequest
        or (body.approval_expires_at is not None and body.approval_expires_at.utcoffset() is None)):
        raise ProviderCapacitySourceActionBlocked('SOURCE_CHECKER_INPUT_REQUIRED')
    return AipActionStore(connect_factory or connect,provider_capacity_source_guard=ProviderCapacitySourceActionGuard()).decide(
        scope,principal.subject,proposal_id,idempotency_key,body)
