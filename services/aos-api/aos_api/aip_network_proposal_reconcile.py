"""Observe a maker's original Proposal after response loss, never authorize resend."""
from datetime import datetime

from aos_api.aip_action_store import proposal_request_hash
from aos_api.aip_network_policy_action_producer import (
    ACTION_ID, NetworkActivationProposalRequest, build_network_proposal_request,
)
from aos_api.auth import Principal
from aos_api.db import connect_read_only as db_connect_read_only
from aos_api.tenant_scope import TenantScope


class ProposalInquiryBlocked(ValueError):
    def __init__(self, code: str, status_code: int):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def inquire_network_proposal(principal: Principal, body: NetworkActivationProposalRequest, *,
                             expected_version: int, idempotency_key: str,
                             connect_factory=None) -> dict[str, str]:
    if type(principal) is not Principal or principal.token_kind != 'oidc':
        raise ProposalInquiryBlocked('OIDC_POLICY_MAKER_REQUIRED', 403)
    try:
        if (type(body) is not NetworkActivationProposalRequest
                or type(body.expires_at) is not datetime or body.expires_at.tzinfo is None
                or type(idempotency_key) is not str or not 1 <= len(idempotency_key) <= 120
                or idempotency_key != idempotency_key.strip() or not idempotency_key.isprintable()
                or type(principal.subject) is not str or not principal.subject
                or principal.subject != principal.subject.strip() or not principal.subject.isprintable()):
            raise ValueError()
        scope = TenantScope(principal.org_id, principal.project_id)
        request = build_network_proposal_request(scope, body.candidate, expected_version, body.expires_at)
    except (TypeError, ValueError, AttributeError):
        raise ProposalInquiryBlocked('NETWORK_PROPOSAL_INQUIRY_INPUT_INVALID', 422) from None
    try:
        with (connect_factory or db_connect_read_only)(scope) as conn:
            identity = conn.execute("SELECT current_user AS role,"
                "current_setting('aos.org_id',true) AS org_id,"
                "current_setting('aos.project_id',true) AS project_id,"
                "current_setting('transaction_read_only') AS readonly").fetchone()
            if (conn.read_only is not True or identity is None
                    or (identity['role'], identity['org_id'], identity['project_id'], identity['readonly'])
                    != ('aos_runtime', *scope.key, 'on')):
                raise ProposalInquiryBlocked('NETWORK_PROPOSAL_READ_IDENTITY_REQUIRED', 503)
            rows = conn.execute(
                "SELECT proposal_id,action_type_id,action_type_revision_hash,risk_level,policy_snapshot,request_hash "
                "FROM public.aip_action_proposal WHERE org_id=%s AND project_id=%s "
                "AND idempotency_key=%s AND created_by=%s",
                (*scope.key, idempotency_key, principal.subject),
            ).fetchall()
            if not rows:
                return {'status': 'unresolved'}
            if len(rows) != 1:
                return {'status': 'conflict'}
            row = rows[0]
            if (row['action_type_id'] != ACTION_ID or row['request_hash'] != proposal_request_hash(
                    request, row['action_type_revision_hash'], row['risk_level'], row['policy_snapshot'])):
                return {'status': 'conflict'}
            return {'status': 'observed', 'proposalId': row['proposal_id']}
    except ProposalInquiryBlocked:
        raise
    except Exception:
        # A read failure must never become evidence of an absent write.
        raise ProposalInquiryBlocked('NETWORK_PROPOSAL_INQUIRY_UNAVAILABLE', 503) from None
