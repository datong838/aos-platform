"""Persist a maker's original approved-budget request before private dispatch."""
from dataclasses import dataclass
from datetime import datetime, UTC
import os
from pathlib import Path

from pydantic import ConfigDict, Field, field_validator
from aos_api.aip_contracts import AipContractModel
from aos_api.aip_budget_activation_product import BudgetProductBlocked, _authenticated
from aos_api.aip_budget_consumer_client import BudgetConsumerEndpoint, request_consumer
from aos_api.aip_budget_consumer_service import BudgetConsumerRequest
from aos_api.aip_budget_cost_proposal_store import BudgetCostProposalStore
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_network_consumer_config import _read_private_config
from aos_api.aip_network_consumer_contracts import NetworkConsumerReferences
from aos_api.aip_network_issuer_attempt import _private_directory_fd, _read_marker
from aos_api.aip_private_product_request import recover_private_product_request
from aos_api.auth import parse_bearer


class BudgetConsumptionRequest(AipContractModel):
    model_config = ConfigDict(strict=True, frozen=True)
    proposal_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    decision_id: str = Field(min_length=1, max_length=160)

    @field_validator('decision_id')
    @classmethod
    def _identifier(cls, value):
        return NetworkConsumerReferences._identifier(value)


@dataclass(frozen=True)
class BudgetConsumerProductConfig:
    endpoint: BudgetConsumerEndpoint
    request_directory: Path

    def __post_init__(self):
        try:
            if type(self.endpoint) is not BudgetConsumerEndpoint:
                raise ValueError()
            self.endpoint.__post_init__()
            path = Path(self.request_directory)
            if not path.is_absolute():
                raise ValueError()
            fd = _private_directory_fd(path)
            os.close(fd)
            object.__setattr__(self, 'request_directory', path)
        except Exception:
            raise BudgetProductBlocked('BUDGET_CONSUMER_PRODUCT_CONFIG_REQUIRED', 503) from None


def configured_budget_consumer_product():
    try:
        path = os.environ.get('AOS_BUDGET_CONSUMER_API_CONFIG')
        if not path:
            raise ValueError()
        data = _read_private_config(path)
        if (type(data) is not dict or set(data) != {'schemaVersion', 'socketPath', 'apiUid', 'consumerUid', 'ipcGid', 'requestDirectory'}
                or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1):
            raise ValueError()
        return BudgetConsumerProductConfig(BudgetConsumerEndpoint(data['socketPath'], data['apiUid'],
            data['consumerUid'], data['ipcGid']), data['requestDirectory'])
    except Exception:
        raise BudgetProductBlocked('BUDGET_CONSUMER_PRODUCT_CONFIG_REQUIRED', 503) from None


def budget_consumption_request(config, proposal_id, body, principal, authorization):
    actor = _authenticated(principal, authorization)
    try:
        if type(proposal_id) is not str or not 1 <= len(proposal_id) <= 160:
            raise ValueError()
        NetworkConsumerReferences._identifier(proposal_id)
        if (actor.org_id, actor.project_id) != ('org-org', 'dev-project'):
            raise ValueError()
    except Exception:
        raise BudgetProductBlocked('BUDGET_CONSUMER_PRODUCT_REF_INVALID', 422) from None
    if type(config) is not BudgetConsumerProductConfig:
        raise BudgetProductBlocked('BUDGET_CONSUMER_PRODUCT_CONFIG_REQUIRED', 503)
    config.__post_init__()
    store = BudgetCostProposalStore()
    review = store.review(actor, proposal_id)
    if review['proposal']['proposal']['makerSubject'] != actor.subject:
        raise BudgetProductBlocked('BUDGET_CONSUMER_ORIGINAL_MAKER_REQUIRED', 403)
    key = 'budget-consumer-product-v1-'+canonical_hash([actor.org_id, actor.project_id, actor.subject, proposal_id])

    def make_command(value):
        if type(value) is not BudgetConsumptionRequest:
            raise ValueError()
        value = BudgetConsumptionRequest.model_validate(value.model_dump())
        return BudgetConsumerRequest(schemaVersion=1, orgId=actor.org_id, projectId=actor.project_id,
            proposalId=proposal_id, proposalHash=value.proposal_hash, decisionId=value.decision_id,
            bearerToken=parse_bearer(authorization))

    def envelope(value):
        request = value.model_dump(mode='json', by_alias=True)
        return dict(schemaVersion=1, state='ATTEMPTED', orgId=actor.org_id, projectId=actor.project_id,
            subject=actor.subject, proposalId=proposal_id, key=key, requestHash=canonical_hash(request), request=request)

    def original(fd):
        saved = _read_marker(fd, key+'.json', allow_missing=True)
        if saved is None:
            return None
        value = BudgetConsumptionRequest.model_validate(saved['request'])
        make_command(value)
        if canonical_hash(saved) != canonical_hash(envelope(value)):
            raise ValueError('untrusted original request')
        return value

    def before_reserve(value):
        current = store.review(actor, proposal_id)
        d = current['decision']
        if (current['proposal']['proposal']['makerSubject'] != actor.subject
                or current['proposal']['proposalHash'] != value.proposal_hash
                or d is None or d['decision'] != 'approved' or d['decisionId'] != value.decision_id
                or d['proposalHash'] != value.proposal_hash or current['revocation'] is not None
                or datetime.now(UTC) >= datetime.fromisoformat(d['expiresAt'])):
            raise BudgetProductBlocked('BUDGET_CONSUMER_CURRENT_APPROVAL_REQUIRED', 409)

    return recover_private_product_request(config.request_directory, key, body,
        make_command=make_command, make_envelope=envelope, read_original=original,
        send=lambda method, request: request_consumer(config.endpoint, method, request),
        code_prefix='BUDGET_CONSUMER_PRODUCT', before_reserve=before_reserve)
