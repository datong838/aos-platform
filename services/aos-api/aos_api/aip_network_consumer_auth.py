"""Reverify external identity before entering the independent consumer boundary."""
from aos_api.auth import Principal, resolve_principal
from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand, NetworkConsumerInquiry
from aos_api.aip_network_issuer_auth import _require_external_oidc_config


class ConsumerAuthBlocked(ValueError):
    pass


def authenticate_consumer_request(
    request: NetworkConsumerCommand | NetworkConsumerInquiry,
) -> Principal:
    if type(request) not in {NetworkConsumerCommand, NetworkConsumerInquiry}:
        raise ConsumerAuthBlocked('CONSUMER_REQUEST_CONTRACT_REQUIRED')
    try:
        _require_external_oidc_config()
        principal = resolve_principal(
            token=request.bearer_token.get_secret_value(),
            header_org=request.org_id, header_project=request.project_id,
        )
    except Exception:
        raise ConsumerAuthBlocked('CONSUMER_EXTERNAL_OIDC_REQUIRED') from None
    if (type(principal) is not Principal or principal.token_kind != 'oidc'
            or principal.org_id != request.org_id or principal.project_id != request.project_id
            or not principal.subject or principal.subject == 'unknown'
            or principal.subject != principal.subject.strip()
            or not principal.subject.isprintable()):
        raise ConsumerAuthBlocked('CONSUMER_PRINCIPAL_TENANT_INVALID')
    return principal
