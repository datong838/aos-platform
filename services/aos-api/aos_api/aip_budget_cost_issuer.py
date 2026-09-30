"""Independent signed-identity budget risk review core; no runtime activation.

The caller must supply a separately provisioned issuer connection factory.
There is deliberately no shared-API/owner connection or credential fallback.
"""
from __future__ import annotations

import json
from typing import Literal
from uuid import uuid4
from pydantic import Field, SecretStr, field_validator, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal, DevelopmentRiskProposal
from aos_api.aip_budget_cost_proposal_store import _view as proposal_view
from aos_api.aip_budget_activation_store import _member, read_initial_budget_target, BudgetActivationDenied
from aos_api.aip_model_runtime_contracts import ProviderInstanceRevision
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.auth import resolve_principal
from aos_api.tenant_scope import TenantScope


class BudgetCostIssuerBlocked(ValueError):
    pass


class BudgetCostIssuerCommand(AipContractModel):
    operation: Literal['decide','revoke']
    org_id: str = Field(min_length=1,max_length=120)
    project_id: str = Field(min_length=1,max_length=120)
    bearer_token: SecretStr
    proposal_id: str = Field(min_length=1,max_length=160)
    proposal_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    idempotency_key: str = Field(min_length=1,max_length=160)
    decision: Literal['approved','rejected'] | None = None
    reason: str | None = Field(default=None,min_length=1,max_length=500)

    @field_validator('org_id','project_id','proposal_id','idempotency_key','reason')
    @classmethod
    def _canonical(cls,value):
        if value is not None and (value != value.strip() or not value.isprintable()):
            raise ValueError('canonical text required')
        return value

    @model_validator(mode='after')
    def _operation(self):
        if ((self.operation=='decide' and (self.decision is None or self.reason is not None))
                or (self.operation=='revoke' and (self.reason is None or self.decision is not None))):
            raise ValueError('operation fields must match')
        return self

    @property
    def request_hash(self):
        return canonical_hash({'domain':'aos.budget-cost-issuer/v1',
            **self.model_dump(mode='json',by_alias=True,exclude={'bearer_token','idempotency_key'})})


def _authenticate(command):
    try:
        c=BudgetCostIssuerCommand.model_validate(command.model_dump())
        _require_external_oidc_config()
        p=resolve_principal(token=c.bearer_token.get_secret_value(),header_org=c.org_id,header_project=c.project_id)
        if (p.token_kind!='oidc' or not p.subject or p.subject=='unknown' or p.subject!=p.subject.strip()
                or not p.subject.isprintable() or (p.org_id,p.project_id)!=(c.org_id,c.project_id)):
            raise ValueError('formal identity required')
        return c,p,TenantScope(p.org_id,p.project_id)
    except Exception:
        raise BudgetCostIssuerBlocked('BUDGET_COST_EXTERNAL_IDENTITY_REQUIRED') from None


def _db(conn,scope,read_only):
    row=conn.execute("""SELECT session_user AS login,current_user AS role,
      current_setting('aos.org_id',true) AS org,current_setting('aos.project_id',true) AS project,
      current_setting('transaction_isolation') AS isolation,
      EXISTS(SELECT 1 FROM pg_roles WHERE rolname=session_user AND
        (NOT rolcanlogin OR rolinherit OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) AS unsafe,
      EXISTS(SELECT 1 FROM pg_auth_members WHERE roleid=session_user::regrole
        OR (member=session_user::regrole AND (roleid<>'aos_runtime'::regrole OR admin_option))) AS extra_roles""").fetchone()
    if (row is None or row['login']!='aos_budget_cost_issuer' or row['role']!='aos_runtime'
            or (row['org'],row['project'])!=scope.key or row['unsafe'] or row['extra_roles']
            or conn.read_only is not read_only
            or row['isolation']!=('repeatable read' if read_only else 'serializable')):
        raise BudgetCostIssuerBlocked('BUDGET_COST_DATABASE_IDENTITY_REQUIRED')


def _proposal(conn,scope,c):
    row=conn.execute('SELECT * FROM aip_budget_cost_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
        (*scope.key,c.proposal_id)).fetchone()
    if row is None or row['proposal_hash']!=c.proposal_hash:
        raise BudgetCostIssuerBlocked('BUDGET_COST_PROPOSAL_DRIFT')
    try:return row,BudgetCostBasisProposal.from_canonical_payload(proposal_view(row,scope)['proposal'])
    except ValueError:raise BudgetCostIssuerBlocked('BUDGET_COST_PROPOSAL_DRIFT') from None


def _receipt(conn,scope,actor,c):
    return conn.execute('SELECT request_hash,result FROM aip_budget_cost_issuer_receipt '
        'WHERE org_id=%s AND project_id=%s AND actor_subject=%s AND operation=%s AND idempotency_key=%s',
        (*scope.key,actor,c.operation,c.idempotency_key)).fetchone()


def _provider(conn,scope,p):
    if not isinstance(p.basis,DevelopmentRiskProposal):
        raise BudgetCostIssuerBlocked('BUDGET_COST_SOURCE_AUTHORITY_UNWIRED')
    ref=p.basis.provider
    row=conn.execute('''SELECT r.payload,r.content_hash,r.revision,r.lifecycle FROM aip_provider_instance_head h
      JOIN aip_provider_instance_revision r USING(org_id,project_id,provider_instance_id)
      WHERE h.org_id=%s AND h.project_id=%s AND h.provider_instance_id=%s AND r.revision=h.current_revision
      FOR SHARE OF h''',(*scope.key,ref.asset_id)).fetchone()
    try:
        if row is None:raise ValueError('missing')
        provider=ProviderInstanceRevision.model_validate(row['payload'])
        content={k:v for k,v in provider.model_dump(mode='json',by_alias=True).items()
                 if k not in {'tenant','revision','contentHash','createdBy','createdAt'}}
        if ((provider.tenant.org_id,provider.tenant.project_id)!=scope.key
                or provider.provider_instance_id!=ref.asset_id
                or provider.revision!=ref.revision or row['revision']!=ref.revision
                or provider.content_hash!=ref.content_hash or row['content_hash']!=ref.content_hash
                or canonical_hash(content)!=ref.content_hash or provider.lifecycle.value!='active' or row['lifecycle']!='active'):
            raise ValueError('drift')
    except (ValueError,TypeError,KeyError):
        raise BudgetCostIssuerBlocked('BUDGET_COST_PROVIDER_AUTHORITY_REQUIRED') from None
    return ref.model_dump(mode='json',by_alias=True)


def _historical_result(conn,scope,actor,c,receipt):
    result=receipt['result']
    if receipt['request_hash']!=c.request_hash or type(result) is not dict or result.get('activationEligible') is not False:
        raise BudgetCostIssuerBlocked('BUDGET_COST_IDEMPOTENCY_DRIFT')
    if c.operation=='decide':
        row=conn.execute('SELECT * FROM aip_budget_cost_decision WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*scope.key,c.proposal_id)).fetchone()
        if row is None or row['actor_subject']!=actor or row['proposal_hash']!=c.proposal_hash or row['decision']!=c.decision or result!={'decisionId':row['decision_id'],'decision':row['decision'],'proposalHash':row['proposal_hash'],'activationEligible':False}:
            raise BudgetCostIssuerBlocked('BUDGET_COST_RECEIPT_DRIFT')
    else:
        row=conn.execute('''SELECT r.*,d.proposal_hash FROM aip_budget_cost_revocation r
            JOIN aip_budget_cost_decision d USING(org_id,project_id,decision_id)
            WHERE r.org_id=%s AND r.project_id=%s AND d.proposal_id=%s''',(*scope.key,c.proposal_id)).fetchone()
        if row is None or row['actor_subject']!=actor or row['reason']!=c.reason or row['proposal_hash']!=c.proposal_hash or result!={'revocationId':row['revocation_id'],'decisionId':row['decision_id'],'activationEligible':False}:
            raise BudgetCostIssuerBlocked('BUDGET_COST_RECEIPT_DRIFT')
    return result


class BudgetCostIssuer:
    def __init__(self,connect_factory):
        self._connect=connect_factory

    def execute(self,command:BudgetCostIssuerCommand)->dict:
        c,principal,scope=_authenticate(command);actor=principal.subject
        try:
            with self._connect(scope,False) as conn:
                _db(conn,scope,False)
                _member(conn,scope,actor,label='REVIEWER')
                conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                    (f'budget-cost-review:{scope.org_id}:{scope.project_id}:{c.proposal_id}',))
                row,p=_proposal(conn,scope,c)
                if actor not in {p.maker_subject,p.checker_subject} or (c.operation=='decide' and actor!=p.checker_subject):
                    raise BudgetCostIssuerBlocked('BUDGET_COST_REVIEWER_REQUIRED')
                receipt=_receipt(conn,scope,actor,c)
                if receipt is not None:return _historical_result(conn,scope,actor,c,receipt)
                if c.operation=='decide':
                    _member(conn,scope,p.maker_subject,label='MAKER')
                    _member(conn,scope,p.checker_subject,label='CHECKER')
                    now=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
                    if row['expires_at']<=now:raise BudgetCostIssuerBlocked('BUDGET_COST_PROPOSAL_EXPIRED')
                    ledger,target=read_initial_budget_target(conn,scope,p.target,p.expected_head_version)
                    if ledger.current_revision!=p.draft_revision or BudgetRevisionCreate.model_validate(target)!=p.target:
                        raise BudgetCostIssuerBlocked('BUDGET_COST_TARGET_DRIFT')
                    source=_provider(conn,scope,p) if c.decision=='approved' else None
                    # Head/source locks can wait. The earlier timestamp must not
                    # authorize a decision after that wait has crossed expiry.
                    if row['expires_at']<=conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']:
                        raise BudgetCostIssuerBlocked('BUDGET_COST_PROPOSAL_EXPIRED')
                    if conn.execute('SELECT 1 FROM aip_budget_cost_decision WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*scope.key,c.proposal_id)).fetchone():
                        raise BudgetCostIssuerBlocked('BUDGET_COST_ALREADY_DECIDED')
                    decision_id='budget-cost-decision-'+uuid4().hex
                    conn.execute('''INSERT INTO aip_budget_cost_decision(org_id,project_id,decision_id,proposal_id,
                      proposal_hash,actor_subject,decision,source_ref,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)''',
                        (*scope.key,decision_id,c.proposal_id,c.proposal_hash,actor,c.decision,json.dumps(source) if source else None,row['expires_at']))
                    result=dict(decisionId=decision_id,decision=c.decision,proposalHash=c.proposal_hash,activationEligible=False)
                else:
                    decision=conn.execute('SELECT * FROM aip_budget_cost_decision WHERE org_id=%s AND project_id=%s AND proposal_id=%s',(*scope.key,c.proposal_id)).fetchone()
                    if decision is None or decision['decision']!='approved' or decision['proposal_hash']!=c.proposal_hash:
                        raise BudgetCostIssuerBlocked('BUDGET_COST_APPROVED_DECISION_REQUIRED')
                    if conn.execute('SELECT 1 FROM aip_budget_cost_revocation WHERE org_id=%s AND project_id=%s AND decision_id=%s',(*scope.key,decision['decision_id'])).fetchone():
                        raise BudgetCostIssuerBlocked('BUDGET_COST_ALREADY_REVOKED')
                    revocation_id='budget-cost-revoke-'+uuid4().hex
                    conn.execute('INSERT INTO aip_budget_cost_revocation(org_id,project_id,revocation_id,decision_id,actor_subject,reason) VALUES(%s,%s,%s,%s,%s,%s)',
                        (*scope.key,revocation_id,decision['decision_id'],actor,c.reason))
                    result=dict(revocationId=revocation_id,decisionId=decision['decision_id'],activationEligible=False)
                conn.execute('INSERT INTO aip_budget_cost_issuer_receipt(org_id,project_id,actor_subject,operation,idempotency_key,request_hash,result) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb)',
                    (*scope.key,actor,c.operation,c.idempotency_key,c.request_hash,json.dumps(result)))
                conn.commit();return result
        except BudgetActivationDenied as exc:
            raise BudgetCostIssuerBlocked(str(exc)) from None

    def inquire(self,command:BudgetCostIssuerCommand)->dict:
        c,principal,scope=_authenticate(command);actor=principal.subject
        try:
            with self._connect(scope,True) as conn:
                _db(conn,scope,True);_member(conn,scope,actor,label='REVIEWER',lock=False)
                receipt=_receipt(conn,scope,actor,c)
                if receipt is None:return {'status':'unresolved'}
                try:
                    _proposal(conn,scope,c)
                    result=_historical_result(conn,scope,actor,c,receipt)
                except BudgetCostIssuerBlocked:return {'status':'conflict'}
                return dict(status='observed',result=result,activationEligible=False)
        except BudgetCostIssuerBlocked:raise
        except BudgetActivationDenied as exc:raise BudgetCostIssuerBlocked(str(exc)) from None
        except Exception:raise BudgetCostIssuerBlocked('BUDGET_COST_INQUIRY_UNAVAILABLE') from None
