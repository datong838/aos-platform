"""Durable consumer attempt, separate from issuer decisions and business receipts."""
from pathlib import Path
from aos_api.auth import Principal
from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand
from aos_api.aip_network_issuer_attempt import AttemptBlocked, AttemptReceipt, _reserve_attempt_receipt


def reserve_consumer_attempt(
    private_directory: str | Path,
    command: NetworkConsumerCommand,
    principal: Principal,
) -> AttemptReceipt:
    if (type(command) is not NetworkConsumerCommand or type(principal) is not Principal
            or principal.token_kind != 'oidc' or principal.org_id != command.org_id
            or principal.project_id != command.project_id or not principal.subject
            or principal.subject == 'unknown' or principal.subject != principal.subject.strip()
            or not principal.subject.isprintable()):
        raise AttemptBlocked('CONSUMER_ATTEMPT_AUTHENTICATED_SCOPE_REQUIRED')
    receipt = AttemptReceipt(command.org_id, command.project_id, command.proposal_id,
                             command.idempotency_key, command.request_hash, principal.subject)
    return _reserve_attempt_receipt(private_directory, receipt, namespace='network-policy-consumer/v1')
