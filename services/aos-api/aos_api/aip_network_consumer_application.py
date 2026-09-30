"""API-owned identity and durable dispatch gate; no automatic retry of commands."""
from dataclasses import dataclass
from pathlib import Path
import os

from aos_api.auth import Principal, parse_bearer
from aos_api.aip_network_consumer_auth import authenticate_consumer_request
from aos_api.aip_network_consumer_attempt import reserve_consumer_attempt
from aos_api.aip_network_consumer_client import ConsumerEndpoint, request_consumer
from aos_api.aip_network_consumer_contracts import NetworkConsumerReferences, NetworkConsumerCommand
from aos_api.aip_network_issuer_attempt import (
    _private_directory_fd, AttemptAlreadyRecorded, AttemptUnknown, AttemptConflict,
)


class ConsumerApplicationBlocked(ValueError):
    def __init__(self, code, status_code):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class ConsumerApplicationConfig:
    endpoint: ConsumerEndpoint
    attempt_directory: Path

    def __post_init__(self):
        if type(self.endpoint) is not ConsumerEndpoint:
            raise ValueError('CONSUMER_APPLICATION_CONFIG_REQUIRED')
        self.endpoint.__post_init__()
        path = Path(self.attempt_directory)
        if not path.is_absolute():
            raise ValueError('CONSUMER_APPLICATION_CONFIG_REQUIRED')
        fd = _private_directory_fd(path)
        os.close(fd)
        object.__setattr__(self, 'attempt_directory', path)


def execute_consumer(config, references, principal, authorization, *, inquiry):
    if type(config) is not ConsumerApplicationConfig:
        raise ConsumerApplicationBlocked('CONSUMER_APPLICATION_UNCONFIGURED', 503)
    try:
        config.__post_init__()
        if (type(references) is not NetworkConsumerReferences or type(principal) is not Principal
                or principal.token_kind != 'oidc' or type(inquiry) is not bool):
            raise ValueError()
        command = NetworkConsumerCommand.model_validate({**references.model_dump(),
            'org_id': principal.org_id, 'project_id': principal.project_id,
            'bearer_token': parse_bearer(authorization)})
        verified = authenticate_consumer_request(command.inquiry() if inquiry else command)
        if (verified.subject, verified.org_id, verified.project_id) != (
                principal.subject, principal.org_id, principal.project_id):
            raise ValueError()
    except Exception:
        raise ConsumerApplicationBlocked('CONSUMER_APPLICATION_IDENTITY_BLOCKED', 403) from None
    request = command.inquiry() if inquiry else command
    if not inquiry:
        try:
            reserve_consumer_attempt(config.attempt_directory, command, verified)
        except (AttemptAlreadyRecorded, AttemptUnknown):
            request = command.inquiry()
        except AttemptConflict:
            raise ConsumerApplicationBlocked('CONSUMER_APPLICATION_REQUEST_CONFLICT', 409) from None
        except Exception:
            raise ConsumerApplicationBlocked('CONSUMER_APPLICATION_ATTEMPT_BLOCKED', 503) from None
    try:
        return request_consumer(config.endpoint, request)
    except Exception:
        # Reservation stays durable even when the client could not confirm a send.
        return {'status': 'unresolved'}
