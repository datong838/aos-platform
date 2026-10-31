"""Authenticated API dispatch to the isolated guard policy issuer."""
from dataclasses import dataclass
import os
from pathlib import Path

from aos_api.aip_action_models import DecideActionProposalRequest
from aos_api.aip_guard_policy_issuer_client import GuardIssuerEndpoint, request_guard_issuer
from aos_api.aip_guard_policy_issuer_contracts import GuardIssuerDecisionCommand, authenticate_guard_issuer_request
from aos_api.aip_network_issuer_attempt import AttemptConflict, AttemptReceipt, _private_directory_fd, _reserve_attempt_receipt
from aos_api.aip_private_dispatch import DispatchReservationBlocked, dispatch_once_or_inquire
from aos_api.auth import Principal, parse_bearer


class GuardIssuerApplicationBlocked(ValueError):
    def __init__(self, code, status_code):
        super().__init__(code)
        self.code, self.status_code = code, status_code


@dataclass(frozen=True)
class GuardIssuerApplicationConfig:
    endpoint: GuardIssuerEndpoint
    attempt_directory: Path

    def __post_init__(self):
        if type(self.endpoint) is not GuardIssuerEndpoint:
            raise ValueError("GUARD_ISSUER_APPLICATION_CONFIG_REQUIRED")
        self.endpoint.__post_init__()
        path = Path(self.attempt_directory)
        if not path.is_absolute():
            raise ValueError("GUARD_ISSUER_APPLICATION_CONFIG_REQUIRED")
        fd = _private_directory_fd(path)
        os.close(fd)
        object.__setattr__(self, "attempt_directory", path)


def execute_guard_issuer(config, proposal_id, idempotency_key, decision, principal, authorization, *, inquiry):
    if type(config) is not GuardIssuerApplicationConfig:
        raise GuardIssuerApplicationBlocked("GUARD_ISSUER_APPLICATION_UNCONFIGURED", 503)
    try:
        config.__post_init__()
        body = decision if type(decision) is DecideActionProposalRequest else DecideActionProposalRequest.model_validate(decision)
        if type(principal) is not Principal or principal.token_kind != "oidc" or type(inquiry) is not bool:
            raise ValueError()
        command = GuardIssuerDecisionCommand(schemaVersion=1, orgId=principal.org_id,
            projectId=principal.project_id, bearerToken=parse_bearer(authorization),
            proposalId=proposal_id, idempotencyKey=idempotency_key, decision=body)
        verified = authenticate_guard_issuer_request(command.inquiry() if inquiry else command)
        if (verified.subject, verified.org_id, verified.project_id) != (principal.subject, principal.org_id, principal.project_id):
            raise ValueError()
    except Exception:
        raise GuardIssuerApplicationBlocked("GUARD_ISSUER_APPLICATION_IDENTITY_BLOCKED", 403) from None

    receipt = AttemptReceipt(command.org_id, command.project_id, command.proposal_id,
                             command.idempotency_key, command.request_hash, principal.subject)
    try:
        result = dispatch_once_or_inquire(command, inquiry=inquiry,
            reserve=lambda: _reserve_attempt_receipt(config.attempt_directory, receipt,
                                                       namespace="guard-policy-api/v1"),
            send=lambda request: request_guard_issuer(config.endpoint, request))
        if result.get("activationAuthorized") is not False:
            result = {**result, "activationAuthorized": False}
        return result
    except AttemptConflict:
        raise GuardIssuerApplicationBlocked("GUARD_ISSUER_APPLICATION_REQUEST_CONFLICT", 409) from None
    except DispatchReservationBlocked:
        raise GuardIssuerApplicationBlocked("GUARD_ISSUER_APPLICATION_ATTEMPT_BLOCKED", 503) from None
