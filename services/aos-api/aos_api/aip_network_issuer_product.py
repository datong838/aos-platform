"""Stable product request identity and saved-attempt inquiry; no approval authority."""
from aos_api.aip_action_store import canonical_hash
from aos_api.aip_network_issuer_application import (
    IssuerApplicationBlocked, IssuerApplicationConfig, execute_issuer,
)
from aos_api.aip_network_issuer_attempt import read_decision_attempt
from aos_api.aip_network_issuer_auth import authenticate_issuer_request
from aos_api.aip_network_issuer_client import request_issuer
from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionInquiry
from aos_api.auth import Principal, parse_bearer


def _product_key(principal, proposal_id, version):
    if (type(principal) is not Principal or principal.token_kind != 'oidc'
            or type(version) is not int or version < 1 or type(proposal_id) is not str
            or not proposal_id or proposal_id != proposal_id.strip()):
        raise IssuerApplicationBlocked('ISSUER_PRODUCT_IDENTITY_REQUIRED', 403)
    # Request identity only. Membership, version and approval remain issuer/DB decisions.
    return 'network-product-v1-'+canonical_hash([
        principal.org_id, principal.project_id, principal.subject, proposal_id, version])


def decide_product(config, proposal_id, decision, principal, authorization):
    key = _product_key(principal, proposal_id, decision.expected_proposal_version)
    return execute_issuer(config, proposal_id, key, decision, principal, authorization, inquiry=False)


def inquire_product_decision(config, proposal_id, version, principal, authorization):
    if type(config) is not IssuerApplicationConfig:
        raise IssuerApplicationBlocked('ISSUER_APPLICATION_UNCONFIGURED', 503)
    try:
        config.__post_init__()
    except Exception:
        raise IssuerApplicationBlocked('ISSUER_APPLICATION_CONFIG_BLOCKED', 503) from None
    key = _product_key(principal, proposal_id, version)
    try:
        inquiry = NetworkIssuerDecisionInquiry(schema_version=1,
            bearer_token=parse_bearer(authorization), org_id=principal.org_id,
            project_id=principal.project_id, proposal_id=proposal_id,
            idempotency_key=key, request_hash='0'*64)
        verified = authenticate_issuer_request(inquiry)
        if (verified.subject, verified.org_id, verified.project_id) != (
                principal.subject, principal.org_id, principal.project_id):
            raise ValueError()
    except Exception:
        raise IssuerApplicationBlocked('ISSUER_APPLICATION_IDENTITY_BLOCKED', 403) from None
    try:
        request_hash = read_decision_attempt(config.attempt_directory,
            org_id=verified.org_id, project_id=verified.project_id, proposal_id=proposal_id,
            idempotency_key=key, principal_subject=verified.subject)
    except Exception:
        raise IssuerApplicationBlocked('ISSUER_PRODUCT_SAVED_ATTEMPT_UNTRUSTED', 503) from None
    if request_hash is None:
        return {'status': 'not_attempted'}
    try:
        return request_issuer(config.endpoint, inquiry.model_copy(update={'request_hash': request_hash}))
    except Exception:
        return {'status': 'unresolved'}
