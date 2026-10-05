"""Current request facts for the original source-specific Owner Proposal.

These reads mint no license, approval, installation or runtime-start authority.
The original Proposal/Approval producer and issuer remain separate commands.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import ValidationError

from aos_api.aip_agent_registry_contracts import VersionedAssetRef
from aos_api.aip_license_source_authority import _require_scope, LicenseSourceUnavailable, lock_license_source_initialization
from aos_api.aip_license_source_policy import SignedLicensePolicyFact, SignedLicensePolicyUnavailable, read_license_source_policy
from aos_api.aip_license_source_proposal_contracts import SourceLicenseProposalRequest, source_license_request_binding
from aos_api.aip_production_contracts import ExactRevisionRef
from aos_api.asset_registry.manifest_loader import ManifestLoader
from aos_api.asset_registry.release_policy import ReleasePolicy
from aos_api.evidence_bundle_provenance import BuildProvenanceUnavailable, read_build_provenance
from aos_api.extension_runtime.current_installation_release_evidence import SelectedReleaseEvidence
from aos_api.openfga import openfga_api_url
from aos_api.tenant_scope import TenantScope


class SourceLicenseProposalBlocked(ValueError):
    pass


def require_source_approval_identity(conn, scope):
    """Dedicated login keeps its own ACL/RLS identity, never SET ROLE runtime."""
    _require_source_dedicated_identity(conn, scope, 'aos_source_license_approval_issuer')


def require_source_issuer_identity(conn, scope):
    _require_source_dedicated_identity(conn, scope, 'aos_source_license_issuer')


def _require_source_dedicated_identity(conn, scope, expected_role):
    if expected_role not in {'aos_source_license_approval_issuer', 'aos_source_license_issuer'}:
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_INDEPENDENT_APPROVAL_IDENTITY_REQUIRED')
    _require_scope(conn,scope)
    row=conn.execute("""SELECT session_user AS login,current_user AS role,
      pg_catalog.current_setting('transaction_isolation') AS isolation,
      pg_catalog.current_setting('search_path') AS path,
      pg_catalog.current_setting('aos.org_id',true) AS org_id,
      pg_catalog.current_setting('aos.project_id',true) AS project_id,
      r.rolcanlogin,r.rolinherit,r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,r.rolbypassrls,
      EXISTS(SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.roleid=r.oid OR m.member=r.oid) AS has_members
      FROM pg_catalog.pg_roles r WHERE r.rolname=current_user""").fetchone()
    if (not row or row['login']!=expected_role
        or row['role']!=expected_role or row['isolation']!='serializable'
        or row['path']!='pg_catalog, public, pg_temp'
        or (row['org_id'],row['project_id'])!=scope.key
        or row['rolcanlogin'] is not True
        or any(row[key] for key in ('rolinherit','rolsuper','rolcreatedb','rolcreaterole',
                                    'rolreplication','rolbypassrls','has_members'))):
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_INDEPENDENT_APPROVAL_IDENTITY_REQUIRED')


@dataclass(frozen=True, slots=True)
class SourceLicenseRequestFacts:
    binding_hash: str
    source_request_hash: str
    initialization_epoch: int
    policy: SignedLicensePolicyFact
    checked_at: datetime
    authorization: Literal['SOURCE_REQUEST_FACTS_ONLY_NO_START'] = field(
        default='SOURCE_REQUEST_FACTS_ONLY_NO_START', init=False)


def read_source_license_request_facts(*, conn: Any, scope: TenantScope, maker: str,
    request: SourceLicenseProposalRequest, loader: ManifestLoader,
    release_policy: ReleasePolicy) -> SourceLicenseRequestFacts:
    try:
        _require_scope(conn, scope)
    except LicenseSourceUnavailable as exc:
        reason='SCOPE_MISMATCH' if str(exc)=='LICENSE_SOURCE_SCOPE_MISMATCH' else 'CALLER_TRANSACTION_REQUIRED'
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_'+reason) from None
    identity=conn.execute("SELECT current_user AS role, current_setting('transaction_isolation') AS isolation").fetchone()
    if identity != {'role':'aos_runtime','isolation':'serializable'}:
        if identity and identity['role']=='aos_source_license_approval_issuer':
            require_source_approval_identity(conn,scope)
        elif identity and identity['role']=='aos_source_license_issuer':
            require_source_issuer_identity(conn,scope)
        else:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_RUNTIME_SERIALIZABLE_REQUIRED')
    return _read_source_request_content_facts(conn=conn, scope=scope, maker=maker,
        request=request, loader=loader, release_policy=release_policy)


def _read_source_request_content_facts(*, conn: Any, scope: TenantScope, maker: str,
    request: SourceLicenseProposalRequest, loader: ManifestLoader,
    release_policy: ReleasePolicy) -> SourceLicenseRequestFacts:
    """Internal content verification; the admitting caller owns identity checks.

    This function supplies neither an issuance nor a start permission. Actual
    database identity, rather than a caller flag, chooses the original lock mode.
    """
    try:
        _require_scope(conn, scope)
    except LicenseSourceUnavailable as exc:
        reason='SCOPE_MISMATCH' if str(exc)=='LICENSE_SOURCE_SCOPE_MISMATCH' else 'CALLER_TRANSACTION_REQUIRED'
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_'+reason) from None
    identity=conn.execute('SELECT current_user AS role').fetchone()
    if not identity or not identity.get('role'):
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_RUNTIME_SERIALIZABLE_REQUIRED')
    try:
        binding=source_license_request_binding(scope, maker, request)
        checked=SourceLicenseProposalRequest.model_validate(request.model_dump(mode='python', by_alias=True))
    except (ValidationError,ValueError,TypeError,AttributeError):
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_REQUEST_INVALID') from None
    if openfga_api_url():
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_CURRENT_REMOTE_OWNER_ADAPTER_REQUIRED')
    members=conn.execute('SELECT role FROM meta_membership WHERE org_id=%s AND project_id=%s '
        'AND subject=%s FOR SHARE', (*scope.key,maker)).fetchall()
    # Installation admin/control permissions do not imply a source licensing grant.
    if len(members)!=1 or members[0]['role'].lower()!='owner':
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_CURRENT_OWNER_REQUIRED')
    installed=conn.execute('SELECT current_revision,active_revision,etag_version FROM public.bundle_installation '
        'WHERE org_id=%s AND project_id=%s AND installation_id=%s FOR SHARE',
        (*scope.key,checked.installation_id)).fetchone()
    if (not installed
        or installed['current_revision']!=checked.installation_revision
        or installed['active_revision']!=checked.installation_revision
        or installed['etag_version']!=checked.installation_etag):
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_INSTALLATION_DRIFT')
    ref=ExactRevisionRef.model_validate(checked.source.model_dump(mode='python', by_alias=True))
    try:
        epoch=lock_license_source_initialization(conn,scope,ref,
            shared=identity['role']!='aos_source_license_issuer')
        provenance=read_build_provenance(conn,scope,ref)
    except (LicenseSourceUnavailable,BuildProvenanceUnavailable) as exc:
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_SOURCE_PROVENANCE_UNAVAILABLE') from exc
    if provenance.request_hash!=checked.source_request_hash:
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_PROVENANCE_DRIFT')
    source=conn.execute('SELECT coverage,freshness FROM public.aip_evidence_bundle_revision '
        'WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s AND content_hash=%s',
        (*scope.key,ref.resource_id,ref.revision,ref.content_hash)).fetchone()
    revoked=conn.execute('SELECT 1 FROM public.aip_evidence_bundle_revoke_event '
        'WHERE org_id=%s AND project_id=%s AND bundle_id=%s AND revision=%s AND content_hash=%s',
        (*scope.key,ref.resource_id,ref.revision,ref.content_hash)).fetchone()
    if not source or source['coverage']!='complete' or source['freshness']!='fresh' or revoked:
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_SOURCE_INELIGIBLE')
    release=SelectedReleaseEvidence(**checked.release_ref.model_dump(mode='python'))
    policy_ref=VersionedAssetRef.model_validate(checked.policy_ref.model_dump(mode='python', by_alias=True))
    try:
        policy=read_license_source_policy(conn=conn,scope=scope,
            installation_id=checked.installation_id,expected_etag=checked.installation_etag,
            release_ref=release,policy_ref=policy_ref,release_policy=release_policy,loader=loader)
    except SignedLicensePolicyUnavailable as exc:
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_CURRENT_SIGNED_POLICY_UNAVAILABLE') from exc
    # Sample live DB time after every potentially blocking lock, never NOW().
    now=conn.execute('SELECT clock_timestamp() AS checked_at').fetchone()['checked_at']
    if not (checked.valid_from<=now<checked.proposal_expires_at<=checked.valid_until
            and checked.proposal_expires_at<=now+timedelta(minutes=15)):
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_REQUEST_WINDOW_EXPIRED_OR_UNSUPPORTED')
    return SourceLicenseRequestFacts(binding.content_hash,provenance.request_hash,epoch,policy,now)


class SourceLicenseProposalGuard:
    """Exact maker guard bound to one native/Store transaction pair."""

    def __init__(self, *, conn, factory, principal, request, loader, release_policy):
        import psycopg
        from aos_api.auth import Principal
        from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
        if (type(conn) is not psycopg.Connection or type(factory) is not TransactionBoundConnectFactory
            or type(principal) is not Principal or principal.token_kind!='oidc'
            or type(request) is not SourceLicenseProposalRequest
            or type(loader) is not ManifestLoader or type(release_policy) is not ReleasePolicy):
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_PRIVATE_MAKER_CONTEXT_REQUIRED')
        self.scope=TenantScope(principal.org_id,principal.project_id)
        self.actor=principal.subject
        source_license_request_binding(self.scope,self.actor,request)
        self.native=conn
        conn.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
        try:
            _require_scope(conn,self.scope)
        except LicenseSourceUnavailable as exc:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_MAKER_SCOPE_OR_TRANSACTION_DRIFT') from exc
        self.bound=factory._connection
        if self.bound.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']!=conn.info.backend_pid:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_CALLER_TRANSACTION_DRIFT')
        self.requested=SourceLicenseProposalRequest.model_validate(request.model_dump(mode='python',by_alias=True))
        self.loader,self.release_policy=loader,release_policy

    def read_metadata(self):
        from aos_api.aip_action_store import canonical_hash
        from aos_api.aip_license_source_action import SOURCE_LICENSE_ISSUANCE_ACTION
        obj=self.native.execute('SELECT id,name,description,published,properties,required_markings '
            'FROM meta_object_type WHERE id=%s FOR SHARE',('SourceLicenseRequest',)).fetchone()
        if obj!={'id':'SourceLicenseRequest','name':'来源许可请求',
                 'description':'原Proposal内的精确来源许可声明','published':True,
                 'properties':[],'required_markings':[]}:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_OBJECT_METADATA_DRIFT')
        action=self.native.execute('SELECT id,name,object_type,parameters,required_markings,submission_criteria '
            'FROM meta_action_type WHERE id=%s FOR SHARE',(SOURCE_LICENSE_ISSUANCE_ACTION,)).fetchone()
        if action!={'id':SOURCE_LICENSE_ISSUANCE_ACTION,'name':'申请精确来源许可',
                    'object_type':'SourceLicenseRequest','parameters':[],
                    'required_markings':[],'submission_criteria':[]}:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_ACTION_METADATA_DRIFT')
        snapshot={'id':SOURCE_LICENSE_ISSUANCE_ACTION,'name':action['name'],
                  'objectType':action['object_type'],'parameters':[],
                  'requiredMarkings':[],'submissionCriteria':[]}
        return {**snapshot,'revisionHash':canonical_hash(snapshot)}

    def request(self):
        from aos_api.aip_action_models import CreateActionProposalRequest
        from aos_api.aip_license_source_action import SOURCE_LICENSE_ISSUANCE_ACTION
        facts=read_source_license_request_facts(conn=self.native,scope=self.scope,maker=self.actor,
            request=self.requested,loader=self.loader,release_policy=self.release_policy)
        return CreateActionProposalRequest(actionTypeId=SOURCE_LICENSE_ISSUANCE_ACTION,
            purpose='申请精确来源许可，等待独立Owner批准',
            payload={'requestedGrant':self.requested.model_dump(mode='json',by_alias=True),
                     'bindingHash':facts.binding_hash},expiresAt=self.requested.proposal_expires_at)

    def check_request(self,conn,scope,actor,body,snapshot,risk):
        from aos_api.aip_action_policy import classify_action_risk
        if conn is not self.bound or scope!=self.scope or actor!=self.actor:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_MAKER_TRANSACTION_DRIFT')
        current_snapshot=self.read_metadata()
        expected=self.request()
        expected_risk=classify_action_risk(expected.action_type_id,current_snapshot,expected.payload,None)
        if snapshot!=current_snapshot or body!=expected or risk!=expected_risk:
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_MAKER_REQUEST_DRIFT')
        return expected.payload['bindingHash']

    def check_replay(self,conn,scope,actor,row):
        from aos_api.aip_action_policy import classify_action_risk
        from aos_api.aip_action_store import canonical_hash, AipActionStore, proposal_request_hash
        if (row['created_by']!=actor or row['status'] not in {'drafted','approved'}
            or row['task_id'] is not None or row['run_id'] is not None
            or row['object_ref'] is not None or row['impact_preview_id'] is not None
            or row['source_draft_id'] is not None or row['client_risk_hint'] is not None
            or row['diff']!={} or row['evidence_refs']!=[]):
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_ORIGINAL_PROPOSAL_DRIFT')
        expected=self.request()
        snapshot=self.read_metadata()
        risk=classify_action_risk(expected.action_type_id,snapshot,expected.payload,None)
        binding=self.check_request(conn,scope,actor,expected,snapshot,risk)
        policy={'floor':risk.floor.value,'reasons':list(risk.reasons),**risk.approval_policy}
        if (row['payload']!=expected.payload or row['purpose']!=expected.purpose
            or row['expires_at']!=expected.expires_at or row['action_type_id']!=expected.action_type_id
            or row['action_type_snapshot']!=snapshot or row['action_type_revision_hash']!=snapshot['revisionHash']
            or row['risk_level']!=risk.level.value
            or row['policy_snapshot']!=policy or row['approval_policy_hash']!=canonical_hash(policy)
            or row['action_binding_hash']!=binding
            or row['request_hash']!=proposal_request_hash(expected,snapshot['revisionHash'],risk.level.value,policy)):
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_ORIGINAL_PROPOSAL_DRIFT')
        stable,_=AipActionStore(source_license_guard=self)._proposal_stable(
            conn,scope,actor,expected,snapshot,risk,source_draft_ref=None)
        # The original direct-creation envelope predates draft submission's
        # explicit null sourceDraftRef. Reuse its builder and preserve that form.
        stable.pop('sourceDraftRef')
        draft=self.native.execute('SELECT snapshot,proposal_hash,proposal_version,created_by,diff,evidence_refs,approval_policy FROM aip_action_draft '
            'WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE',
            (*scope.key,row['proposal_id'])).fetchone()
        if (not draft or draft['proposal_version']!=1 or draft['created_by']!=actor
            or draft['proposal_hash']!=row['proposal_hash']
            or canonical_hash(draft['snapshot'])!=row['proposal_hash']
            or draft['snapshot']!=stable or draft['diff']!={} or draft['evidence_refs']!=[]
            or draft['approval_policy']!=policy):
            raise SourceLicenseProposalBlocked('SOURCE_LICENSE_ORIGINAL_DRAFT_DRIFT')
        return None


def propose_source_license_in_transaction(*,conn,principal,request,idempotency_key,loader,release_policy):
    """Private authenticated maker service; caller owns the only commit.

    External adapters must validate the bearer token before supplying Principal.
    This internal function registers no public route and accepts no callback.
    """
    from aos_api.aip_action_policy import classify_action_risk
    from aos_api.aip_action_store import AipActionStore
    from aos_api.ecommerce_growth_host_ports import HostTransaction
    from aos_api.ecommerce_growth_runtime_adapters import TransactionBoundConnectFactory
    if (type(idempotency_key) is not str or not 1<=len(idempotency_key)<=120
        or idempotency_key!=idempotency_key.strip() or not idempotency_key.isprintable()):
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_IDEMPOTENCY_KEY_INVALID')
    # Exact context validation is performed by the guard before any Store write.
    from aos_api.auth import Principal
    if type(principal) is not Principal:
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_PRIVATE_MAKER_CONTEXT_REQUIRED')
    scope=TenantScope(principal.org_id,principal.project_id)
    factory=TransactionBoundConnectFactory(HostTransaction(conn),scope)
    guard=SourceLicenseProposalGuard(conn=conn,factory=factory,principal=principal,
        request=request,loader=loader,release_policy=release_policy)
    AipActionStore._idempotency_lock(conn,scope,'proposal',idempotency_key)
    snapshot=guard.read_metadata()
    body=guard.request()
    risk=classify_action_risk(body.action_type_id,snapshot,body.payload,None)
    result=AipActionStore(factory,source_license_guard=guard).create_proposal(
        scope,principal.subject,idempotency_key,body,snapshot,risk)
    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
    if result.proposal.expires_at<=now:
        raise SourceLicenseProposalBlocked('SOURCE_LICENSE_PROPOSAL_EXPIRED_BEFORE_COMMIT')
    return result
