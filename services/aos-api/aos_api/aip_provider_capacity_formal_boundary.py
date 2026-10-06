"""Private issuer may recheck approved claims; this module issues no capacity."""
from dataclasses import dataclass,field
from typing import Literal
import hashlib

import psycopg

from aos_api.aip_binding_formal_evaluator_contracts import FormalExactRef
from aos_api.aip_action_store import AipActionStore,canonical_hash
from aos_api.aip_provider_capacity_source_contracts import ProviderCapacitySourceCandidate
from aos_api.tenant_scope import TenantScope

ISSUER='aos_provider_capacity_issuer'
SCOPED=('meta_membership','aip_provider_capacity_request','aip_provider_capacity_candidate',
    'aip_provider_instance_head','aip_provider_instance_revision','aip_evidence_bundle_revision',
    'aip_evidence_bundle_build_provenance','aip_evidence_bundle_revoke_event',
    'aip_production_contract_receipt','aip_action_withdrawal_event')
LOCKS={'meta_membership':'subject','aip_provider_instance_head':'provider_instance_id',
    'meta_object_type':'id','meta_action_type':'id','aip_action_proposal':'proposal_id'}
TABLES=(*SCOPED,'meta_object_type','meta_action_type','aip_action_proposal','aip_action_draft','aip_action_approval_event')
GUARD_HASH='a1a7dfea408cd95dce80933704f19b0c458ff25af90b66477f3cf201f08262a7'
TENANT_EXPR="((org_id = 'org-org'::text) AND (project_id = 'dev-project'::text) AND (org_id = NULLIF(current_setting('aos.org_id'::text, true), ''::text)) AND (project_id = NULLIF(current_setting('aos.project_id'::text, true), ''::text)))"


class ProviderCapacityFormalBoundaryBlocked(ValueError):
    pass


def _normalized(value):
    return ' '.join(value.split())


def _policy_expression(table):
    if table in SCOPED:return TENANT_EXPR
    tenant=TENANT_EXPR[1:-1]
    if table=='aip_action_proposal':
        return "("+tenant+" AND (action_type_id = ANY (ARRAY['aip_request_provider_capacity'::text, 'aip_review_provider_capacity_source'::text])) AND ((action_type_snapshot ->> 'id'::text) = action_type_id))"
    return "("+tenant+f" AND (EXISTS ( SELECT 1 FROM aip_action_proposal p WHERE ((p.org_id = {table}.org_id) AND (p.project_id = {table}.project_id) AND (p.proposal_id = {table}.proposal_id)))))"


def _require_read_boundary(conn):
    # Match native relation identities, never a bare name in another schema.
    identities=conn.execute("SELECT name,to_regclass('public.'||name)::oid AS oid FROM unnest(%s::text[]) AS name",(list(TABLES),)).fetchall()
    allowed={r['oid'] for r in identities}
    lock_columns={(r['oid'],LOCKS[r['name']]) for r in identities if r['name'] in LOCKS}
    if None in allowed or len(allowed)!=len(TABLES):
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_TABLE_IDENTITY_DRIFTED')
    grants=conn.execute("SELECT c.oid,a.privilege_type,a.is_grantable FROM pg_class c,LATERAL aclexplode(c.relacl) a "
        "WHERE a.grantee=%s::regrole",(ISSUER,)).fetchall()
    if ({r['oid'] for r in grants}!=allowed or any(r['oid'] not in allowed
        or r['privilege_type']!='SELECT' or r['is_grantable'] for r in grants)):
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_TABLE_ACL_DRIFTED')
    columns=conn.execute("SELECT c.oid,x.attname,a.privilege_type,a.is_grantable FROM pg_class c "
        "JOIN pg_attribute x ON x.attrelid=c.oid,LATERAL aclexplode(x.attacl) a WHERE a.grantee=%s::regrole",(ISSUER,)).fetchall()
    if ({(r['oid'],r['attname']) for r in columns}!=lock_columns or any(
        (r['oid'],r['attname']) not in lock_columns or r['privilege_type']!='UPDATE' or r['is_grantable'] for r in columns)):
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_COLUMN_ACL_DRIFTED')
    if conn.execute("SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' "
        "AND c.relkind IN('r','v','m','p','f') AND (has_table_privilege(%s,c.oid,'INSERT,UPDATE,DELETE,TRUNCATE,TRIGGER,REFERENCES') "
        "OR (NOT(c.oid=ANY(%s::oid[])) AND (has_table_privilege(%s,c.oid,'SELECT') "
        "OR has_any_column_privilege(%s,c.oid,'SELECT,INSERT,UPDATE,REFERENCES')))) LIMIT 1",(ISSUER,list(allowed),ISSUER,ISSUER)).fetchone():
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_EFFECTIVE_TABLE_PERMISSION_DRIFTED')
    effective_columns=conn.execute("SELECT c.oid,x.attname,has_column_privilege(%s,c.oid,x.attnum,'INSERT,REFERENCES') AS extra "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute x ON x.attrelid=c.oid "
        "WHERE n.nspname !~ '^pg_' AND n.nspname<>'information_schema' AND c.relkind IN('r','v','m','p','f') "
        "AND x.attnum>0 AND NOT x.attisdropped AND (has_column_privilege(%s,c.oid,x.attnum,'INSERT,REFERENCES') "
        "OR has_column_privilege(%s,c.oid,x.attnum,'UPDATE'))",(ISSUER,ISSUER,ISSUER)).fetchall()
    if any(r['extra'] or (r['oid'],r['attname']) not in lock_columns for r in effective_columns):
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_EFFECTIVE_COLUMN_PERMISSION_DRIFTED')
    from aos_api.aip_capacity_withdrawal_fence import require_withdrawal_fence
    require_withdrawal_fence(conn)
    functions=conn.execute("SELECT p.oid FROM pg_proc p WHERE p.prosecdef AND has_function_privilege(%s,p.oid,'EXECUTE') "
        "AND p.oid NOT IN ('public.aos_capacity_evidence_epoch_issuer_lock(text,text,text)'::regprocedure,'public.aos_capacity_withdrawal_epoch_lock(text,text,text)'::regprocedure) LIMIT 1",(ISSUER,)).fetchone()
    if functions:raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_EFFECTIVE_DEFINER_PERMISSION_DRIFTED')
    explicit=conn.execute("SELECT p.oid,a.privilege_type,a.is_grantable FROM pg_proc p,LATERAL aclexplode(p.proacl) a "
        "WHERE a.grantee=%s::regrole AND (p.oid NOT IN ('public.aos_capacity_evidence_epoch_issuer_lock(text,text,text)'::regprocedure,'public.aos_capacity_withdrawal_epoch_lock(text,text,text)'::regprocedure) "
        "OR a.privilege_type<>'EXECUTE' OR a.is_grantable)",(ISSUER,)).fetchone()
    schemas=conn.execute("SELECT n.nspname,a.privilege_type,a.is_grantable FROM pg_namespace n,LATERAL aclexplode(n.nspacl) a "
        "WHERE a.grantee=%s::regrole",(ISSUER,)).fetchall()
    if (explicit or schemas!=[{'nspname':'public','privilege_type':'USAGE','is_grantable':False}]
        or conn.execute("SELECT 1 FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname NOT IN('public','information_schema') "
            "AND has_schema_privilege(%s,oid,'USAGE') LIMIT 1",(ISSUER,)).fetchone()
        or conn.execute("SELECT 1 FROM pg_namespace WHERE has_schema_privilege(%s,oid,'CREATE') LIMIT 1",(ISSUER,)).fetchone()
        or conn.execute("SELECT 1 FROM pg_database WHERE datname=current_database() AND has_database_privilege(%s,oid,'CREATE')",(ISSUER,)).fetchone()):
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_SCHEMA_OR_FUNCTION_PERMISSION_DRIFTED')
    for table in (*SCOPED,'aip_action_proposal','aip_action_draft','aip_action_approval_event'):
        row=conn.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',('public.'+table,)).fetchone()
        policies=conn.execute("SELECT polname,polcmd,polpermissive,polroles,pg_get_expr(polqual,polrelid) AS us,"
            "pg_get_expr(polwithcheck,polrelid) AS wc FROM pg_policy WHERE polrelid=%s::regclass "
            "AND %s::regrole::oid=ANY(polroles)",('public.'+table,ISSUER)).fetchall()
        name='capacity_issuer_scope_a0v150' if table in SCOPED else ('capacity_issuer_proposal_a0v150' if table=='aip_action_proposal' else 'capacity_issuer_related_a0v150')
        expected={name:True,name.replace('_a0v150','_restrict_a0v150'):False}
        if (not row or not all(row.values()) or len(policies)!=2 or {p['polname'] for p in policies}!=set(expected)
            or any(p['polcmd']!='*' or p['polpermissive'] is not expected[p['polname']]
                or len(p['polroles'])!=1 or any(_normalized(p[key] or '')!=_normalized(_policy_expression(table)) for key in ('us','wc')) for p in policies)):
            raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_RLS_POLICY_DRIFTED:'+table)
    guard=conn.execute("SELECT oid,prosrc,prosecdef,proconfig,proowner=(SELECT datdba FROM pg_database WHERE datname=current_database()) AS owner "
        "FROM pg_proc WHERE oid='public.capacity_issuer_read_lock_only_a0v150()'::regprocedure").fetchone()
    if (not guard or guard['prosecdef'] or guard['proconfig']!=['search_path=pg_catalog'] or not guard['owner']
        or hashlib.sha256(guard['prosrc'].encode()).hexdigest()!=GUARD_HASH
        or conn.execute("SELECT 1 FROM pg_proc p,LATERAL aclexplode(p.proacl) a WHERE p.oid=%s AND a.grantee<>p.proowner",(guard['oid'],)).fetchone()):
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_READ_GUARD_DRIFTED')
    triggers=conn.execute("SELECT t.tgrelid,t.tgfoid,t.tgenabled,t.tgtype,t.tgqual,t.tgargs,t.tgnargs,cardinality(t.tgattr::smallint[]) AS column_count FROM pg_trigger t "
        "JOIN pg_class c ON c.oid=t.tgrelid WHERE t.tgname='capacity_issuer_read_lock_only_a0v150'").fetchall()
    if ({t['tgrelid'] for t in triggers}!={oid for oid,_ in lock_columns} or len(triggers)!=len(LOCKS) or any(t['tgfoid']!=guard['oid']
        or t['tgenabled']!='O' or t['tgtype']!=31 or t['tgqual'] is not None or bytes(t['tgargs'])!=b''
        or t['tgnargs']!=0 or t['column_count']!=0 for t in triggers)):
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_READ_TRIGGER_DRIFTED')


def require_capacity_issuer_identity(conn,scope):
    if (type(conn) is not psycopg.Connection or type(scope) is not TenantScope or scope.key!=('org-org','dev-project')
        or conn.autocommit or conn.info.transaction_status!=psycopg.pq.TransactionStatus.INTRANS):
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_NATIVE_CALLER_REQUIRED')
    row=conn.execute("""SELECT session_user AS login,current_user AS role,
      current_setting('transaction_isolation') AS isolation,current_setting('transaction_read_only') AS read_only,
      current_setting('search_path') AS path,current_setting('session_replication_role') AS replication,
      current_setting('TimeZone') AS time_zone,
      current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
      r.rolcanlogin,r.rolinherit,r.rolsuper,r.rolcreatedb,r.rolcreaterole,r.rolreplication,r.rolbypassrls,
      EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=r.oid OR member=r.oid) AS members,
      EXISTS(SELECT 1 FROM pg_class WHERE relowner=r.oid) OR EXISTS(SELECT 1 FROM pg_proc WHERE proowner=r.oid)
        OR EXISTS(SELECT 1 FROM pg_namespace WHERE nspowner=r.oid) OR EXISTS(SELECT 1 FROM pg_database WHERE datdba=r.oid) AS owned
      FROM pg_roles r WHERE rolname=current_user""").fetchone()
    if (not row or (row['login'],row['role'],row['isolation'],row['read_only'],row['path'],row['replication'],row['org'],row['project'])
        !=(ISSUER,ISSUER,'serializable','off','pg_catalog, public, pg_temp','origin',*scope.key) or row['rolcanlogin'] is not True
        or row['time_zone']!='UTC'
        or any(row[k] for k in ('rolinherit','rolsuper','rolcreatedb','rolcreaterole','rolreplication','rolbypassrls','members','owned'))):
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ISSUER_PRIVATE_IDENTITY_REQUIRED')
    _require_read_boundary(conn)
    from aos_api.aip_provider_capacity_evidence_fence import _require_boundary
    _require_boundary(conn)


@dataclass(frozen=True,slots=True)
class ProviderCapacityApprovedClaims:
    maker: str
    source: ProviderCapacitySourceCandidate
    approved_proposal: FormalExactRef
    approval_event: FormalExactRef
    supplier_verified: Literal[False]=field(default=False,init=False)
    execution_allowed: Literal[False]=field(default=False,init=False)
    authorization: Literal['APPROVED_CLAIMS_ONLY_NO_CAPACITY_NO_START']=field(default='APPROVED_CLAIMS_ONLY_NO_CAPACITY_NO_START',init=False)


def read_capacity_approved_claims(conn,command):
    from aos_api.aip_provider_capacity_source_issuer import authenticate_capacity_issuance_command
    from aos_api.aip_provider_capacity_source_action import ProviderCapacitySourceActionGuard,ACTION_ID
    try:
        from aos_api.aip_provider_capacity_source_contracts import ProviderCapacityIssuanceCommand
        if type(command) is not ProviderCapacityIssuanceCommand:raise ValueError('native original command required')
        command=ProviderCapacityIssuanceCommand.model_validate(command.model_dump(mode='python',by_alias=True))
        principal=authenticate_capacity_issuance_command(command)
        scope=TenantScope(principal.org_id,principal.project_id)
        require_capacity_issuer_identity(conn,scope)
        ref=command.approved_proposal
        row=conn.execute('SELECT * FROM public.aip_action_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s FOR SHARE',
            (*scope.key,ref.asset_id)).fetchone()
        if (not row or row['action_type_id']!=ACTION_ID or row['created_by']!=principal.subject
            or row['status']!='approved' or row['version']!=ref.revision or row['proposal_hash']!=ref.content_hash):
            raise ValueError('original Source approval required')
        events=conn.execute('SELECT * FROM public.aip_action_approval_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
            (*scope.key,ref.asset_id)).fetchall()
        event=events[0] if len(events)==1 else None
        now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        if (not event or event['approval_event_id']!=command.approval_event.asset_id or event['decision']!='approved'
            or event['proposal_version']!=1 or event['slot_id']!='checker.1' or event['proposal_hash']!=row['proposal_hash']
            or event['action_binding_hash']!=row['action_binding_hash'] or event['approval_policy_hash']!=row['approval_policy_hash']
            or event['expires_at'] is None or event['expires_at']<=now or row['expires_at']<=now):
            raise ValueError('original unique approved event required')
        if conn.execute('SELECT 1 FROM public.aip_action_withdrawal_event WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*scope.key,ref.asset_id)).fetchone():
            raise ValueError('proposal withdrawn')
        guard=ProviderCapacitySourceActionGuard()
        guard.check_proposal(conn,scope,event['actor_id'],row,checker=True)
        bundle=AipActionStore()._bundle(conn,scope,ref.asset_id)
        expected=canonical_hash(dict(tenant=dict(orgId=scope.org_id,projectId=scope.project_id),actorId=event['actor_id'],
            roles=['owner'],slotId='checker.1',approvalPolicyHash=row['approval_policy_hash']))
        if (bundle.draft.status!='approved' or event['eligibility_snapshot_hash']!=expected
            or canonical_hash(bundle.approvals[0].model_dump(mode='json',by_alias=True))!=command.approval_event.content_hash):
            raise ValueError('approved snapshot hash drifted')
        return ProviderCapacityApprovedClaims(principal.subject,ProviderCapacitySourceCandidate.model_validate(row['payload']['sourceCandidate']),
            ref,command.approval_event)
    except Exception:
        raise ProviderCapacityFormalBoundaryBlocked('CAPACITY_ORIGINAL_APPROVED_CLAIMS_REQUIRED') from None
