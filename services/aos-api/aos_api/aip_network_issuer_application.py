"""Authenticated API dispatch to an isolated issuer, with durable no-resend gate."""
from dataclasses import dataclass
import os
from pathlib import Path

from aos_api.auth import Principal, parse_bearer
from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_network_issuer_auth import authenticate_issuer_request
from aos_api.aip_network_issuer_attempt import _private_directory_fd, reserve_decision_attempt, AttemptConflict
from aos_api.aip_network_issuer_client import IssuerEndpoint, request_issuer
from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionCommand
from aos_api.aip_private_dispatch import dispatch_once_or_inquire, DispatchReservationBlocked


class IssuerApplicationBlocked(ValueError):
    def __init__(self, code, status_code):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class IssuerApplicationConfig:
    endpoint: IssuerEndpoint
    attempt_directory: Path

    def __post_init__(self):
        if type(self.endpoint) is not IssuerEndpoint:
            raise ValueError('ISSUER_APPLICATION_CONFIG_REQUIRED')
        self.endpoint.__post_init__()
        path = Path(self.attempt_directory)
        if not path.is_absolute():
            raise ValueError('ISSUER_APPLICATION_CONFIG_REQUIRED')
        fd = _private_directory_fd(path)
        os.close(fd)
        object.__setattr__(self, 'attempt_directory', path)


def execute_issuer(config, proposal_id, idempotency_key, decision, principal, authorization, *, inquiry):
    if type(config) is not IssuerApplicationConfig:
        raise IssuerApplicationBlocked('ISSUER_APPLICATION_UNCONFIGURED', 503)
    try:
        config.__post_init__()
    except Exception:
        raise IssuerApplicationBlocked('ISSUER_APPLICATION_CONFIG_BLOCKED', 503) from None
    try:
        if (type(decision) is not DecideActionProposalRequest or type(principal) is not Principal
                or principal.token_kind != 'oidc' or type(inquiry) is not bool):
            raise ValueError()
        command = NetworkIssuerDecisionCommand.model_validate({
            'schema_version': 1, 'proposal_id': proposal_id, 'idempotency_key': idempotency_key,
            'decision': decision, 'org_id': principal.org_id, 'project_id': principal.project_id,
            'bearer_token': parse_bearer(authorization)})
        verified = authenticate_issuer_request(command.inquiry() if inquiry else command)
        if (verified.subject, verified.org_id, verified.project_id) != (
                principal.subject, principal.org_id, principal.project_id):
            raise ValueError()
    except Exception:
        raise IssuerApplicationBlocked('ISSUER_APPLICATION_IDENTITY_BLOCKED', 403) from None
    try:
        return dispatch_once_or_inquire(command, inquiry=inquiry,
            reserve=lambda: reserve_decision_attempt(config.attempt_directory, command, verified),
            send=lambda request: request_issuer(config.endpoint, request))
    except AttemptConflict:
        raise IssuerApplicationBlocked('ISSUER_APPLICATION_REQUEST_CONFLICT', 409) from None
    except DispatchReservationBlocked:
        raise IssuerApplicationBlocked('ISSUER_APPLICATION_ATTEMPT_BLOCKED', 503) from None
