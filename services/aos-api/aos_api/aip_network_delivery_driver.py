"""One authorized delivery step over private IPC; no poller or identity supplier."""
from datetime import UTC, datetime

from aos_api.auth import Principal, parse_bearer
from aos_api.aip_network_consumer_application import ConsumerApplicationConfig, ConsumerApplicationBlocked
from aos_api.aip_network_consumer_auth import authenticate_consumer_request
from aos_api.aip_network_consumer_client import request_consumer
from aos_api.aip_network_consumer_contracts import NetworkDeliveryClaim, NetworkDeliveryFinish, NetworkDeliveryLease
from aos_api.aip_network_approval_event_driver import process_network_approval_event


def process_network_delivery_once(config, principal, authorization):
    if type(config) is not ConsumerApplicationConfig:
        raise ConsumerApplicationBlocked('NETWORK_DELIVERY_UNCONFIGURED', 503)
    try:
        config.__post_init__()
        if type(principal) is not Principal or principal.token_kind != 'oidc':
            raise ValueError()
        request = NetworkDeliveryClaim(schema_version=1, org_id=principal.org_id,
            project_id=principal.project_id, bearer_token=parse_bearer(authorization))
        verified = authenticate_consumer_request(request)
        if (verified.subject, verified.org_id, verified.project_id) != (
                principal.subject, principal.org_id, principal.project_id):
            raise ValueError()
    except Exception:
        raise ConsumerApplicationBlocked('NETWORK_DELIVERY_CURRENT_IDENTITY_REQUIRED', 403) from None
    try:
        result = request_consumer(config.endpoint, request)
    except Exception:
        return {'status': 'unresolved'}
    if result.get('status') != 'claimed':
        return result
    try:
        lease = NetworkDeliveryLease.model_validate(result['delivery'])
    except Exception:
        return {'status': 'unresolved'}
    # Expired/unknown delivery must never depend on whether a local marker survived.
    inquiry = lease.mode == 'inquiry' or datetime.fromisoformat(lease.claim_until) <= datetime.now(UTC)
    try:
        process_network_approval_event(config, lease.proposal_id, lease.approval_event_id,
            verified, authorization, inquiry=inquiry)
    except Exception:
        # Exact PG receipt acknowledgement below is safe even after response loss.
        pass
    finish = NetworkDeliveryFinish.model_validate({**request.model_dump(),
        'approval_event_id': lease.approval_event_id, 'claim_token': lease.claim_token})
    try:
        return request_consumer(config.endpoint, finish)
    except Exception:
        return {'status': 'unresolved'}
