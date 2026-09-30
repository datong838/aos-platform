"""OIDC maker proposals and immutable request reconciliation, without approval."""
from datetime import timedelta
import json
from uuid import uuid4

from aos_api.aip_budget_activation_store import (
    BudgetActivationDenied, BudgetActivationConflict, BudgetActivationInquiryUnavailable,
    _identity, _key, _member, _require_inquiry_connection, _instant, read_initial_budget_target,
)
from aos_api.aip_budget_contracts import BudgetRevisionCreate
from aos_api.aip_budget_cost_basis import BudgetCostBasisProposal, DevelopmentRiskProposal
from aos_api.db import connect_read_only, connect_serializable


def _input(principal, proposal, key):
    scope, actor = _identity(principal)
    key = _key(key)
    p = BudgetCostBasisProposal.from_canonical_payload(proposal.canonical_payload())
    if scope.key != (p.tenant.org_id, p.tenant.project_id) or actor != p.maker_subject:
        raise BudgetActivationDenied('BUDGET_COST_MAKER_IDENTITY_REQUIRED')
    return scope, actor, p, key


def _view(row, scope):
    try:
        p = BudgetCostBasisProposal.from_canonical_payload(row['payload'])
        if (p.proposal_hash != row['proposal_hash'] or scope.key != (p.tenant.org_id,p.tenant.project_id)
                or p.maker_subject != row['maker_subject'] or p.checker_subject != row['checker_subject']
                or p.target.budget_id != row['budget_id'] or row['status'] != 'proposed'
                or row['source_verification'] != 'pending' or row['activation_eligible'] is not False
                or not p.target.effective_from <= row['created_at'] < p.target.effective_until
                or row['expires_at'] != min(row['created_at']+timedelta(minutes=30),p.target.effective_until)):
            raise ValueError('proposal row drifted')
    except (ValueError, TypeError, KeyError):
        raise BudgetActivationConflict('BUDGET_COST_PROPOSAL_DRIFT') from None
    return dict(proposalId=row['proposal_id'], proposalHash=row['proposal_hash'],
        proposal=p.canonical_payload(), status='proposed', sourceVerification='pending',
        activationEligible=False, createdAt=_instant(row['created_at']), expiresAt=_instant(row['expires_at']))


def _row(conn, scope, proposal_id):
    return conn.execute('SELECT * FROM aip_budget_cost_proposal WHERE org_id=%s AND project_id=%s AND proposal_id=%s',
        (*scope.key, proposal_id)).fetchone()


def _receipt(conn, scope, actor, key):
    return conn.execute('SELECT request_hash,proposal_id FROM aip_budget_cost_proposal_receipt '
        'WHERE org_id=%s AND project_id=%s AND actor_subject=%s AND idempotency_key=%s',
        (*scope.key, actor, key)).fetchone()


class BudgetCostProposalStore:
    def create(self, principal, proposal: BudgetCostBasisProposal, key: str) -> dict:
        scope, actor, p, key = _input(principal, proposal, key)
        if not isinstance(p.basis, DevelopmentRiskProposal):
            raise BudgetActivationDenied('BUDGET_COST_SOURCE_AUTHORITY_UNWIRED')
        with connect_serializable(scope) as conn:
            _member(conn,scope,actor,label='MAKER')
            _member(conn,scope,p.checker_subject,label='CHECKER')
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',
                (f'budget-cost:{scope.org_id}:{scope.project_id}:{actor}:{key}',))
            receipt = _receipt(conn,scope,actor,key)
            if receipt is not None:
                if receipt['request_hash'] != p.proposal_hash:
                    raise BudgetActivationConflict('BUDGET_COST_IDEMPOTENCY_DRIFT')
                row = _row(conn,scope,receipt['proposal_id'])
                if row is None or row['maker_subject'] != actor or row['proposal_hash'] != p.proposal_hash:
                    raise BudgetActivationConflict('BUDGET_COST_RECEIPT_DRIFT')
                return _view(row,scope)
            ledger, payload = read_initial_budget_target(conn,scope,p.target,p.expected_head_version)
            if ledger.current_revision != p.draft_revision or BudgetRevisionCreate.model_validate(payload) != p.target:
                raise BudgetActivationDenied('BUDGET_COST_TARGET_DRIFT')
            now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
            if not p.target.effective_from <= now < p.target.effective_until:
                raise BudgetActivationDenied('BUDGET_COST_WINDOW_INVALID')
            proposal_id = 'budget-cost-'+uuid4().hex
            expires = min(now+timedelta(minutes=30),p.target.effective_until)
            row = conn.execute('''INSERT INTO aip_budget_cost_proposal(
                org_id,project_id,proposal_id,budget_id,maker_subject,checker_subject,proposal_hash,payload,created_at,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s) RETURNING *''',
                (*scope.key,proposal_id,p.target.budget_id,actor,p.checker_subject,p.proposal_hash,
                 json.dumps(p.canonical_payload(),sort_keys=True),now,expires)).fetchone()
            conn.execute('''INSERT INTO aip_budget_cost_proposal_receipt
                (org_id,project_id,actor_subject,idempotency_key,request_hash,proposal_id)
                VALUES(%s,%s,%s,%s,%s,%s)''',(*scope.key,actor,key,p.proposal_hash,proposal_id))
            view = _view(row,scope)
            conn.commit()
            return view

    def get(self, principal, proposal_id: str) -> dict:
        scope, actor = _identity(principal)
        _key(proposal_id)
        try:
            with connect_read_only(scope) as conn:
                _require_inquiry_connection(conn,scope)
                _member(conn,scope,actor,label='REVIEWER',lock=False)
                row = _row(conn,scope,proposal_id)
                if row is None or actor not in {row['maker_subject'],row['checker_subject']}:
                    raise BudgetActivationDenied('BUDGET_COST_PROPOSAL_UNAVAILABLE')
                return _view(row,scope)
        except (BudgetActivationDenied,BudgetActivationConflict):
            raise
        except Exception:
            raise BudgetActivationInquiryUnavailable('BUDGET_COST_READ_UNAVAILABLE') from None

    def inquire(self, principal, proposal: BudgetCostBasisProposal, key: str) -> dict:
        scope, actor, p, key = _input(principal,proposal,key)
        try:
            with connect_read_only(scope) as conn:
                _require_inquiry_connection(conn,scope)
                _member(conn,scope,actor,label='MAKER',lock=False)
                receipt = _receipt(conn,scope,actor,key)
                if receipt is None:
                    return {'status':'unresolved'}
                if receipt['request_hash'] != p.proposal_hash:
                    return {'status':'conflict'}
                row = _row(conn,scope,receipt['proposal_id'])
                if row is None or row['maker_subject'] != actor or row['proposal_hash'] != p.proposal_hash:
                    return {'status':'conflict'}
                try:
                    view = _view(row,scope)
                except BudgetActivationConflict:
                    return {'status':'conflict'}
                return dict(status='observed',proposalId=view['proposalId'],
                    proposalHash=view['proposalHash'],activationEligible=False)
        except BudgetActivationDenied:
            raise
        except Exception:
            raise BudgetActivationInquiryUnavailable('BUDGET_COST_INQUIRY_UNAVAILABLE') from None
