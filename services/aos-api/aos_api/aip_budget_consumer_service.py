"""Private budget consumption and historical inquiry; never retries a write."""
from typing import Literal
from pydantic import ConfigDict, Field, SecretStr, field_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_budget_consumer_connection import BudgetConsumerConfig, connect_budget_consumer
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_issuer_attempt import (
    AttemptReceipt, AttemptAlreadyRecorded, AttemptUnknown, AttemptConflict, _reserve_attempt_receipt,
)
from aos_api.aip_network_consumer_contracts import NetworkConsumerReferences, _ConsumerRequest
from aos_api.auth import Principal, resolve_principal
from aos_api.tenant_scope import TenantScope


class BudgetConsumerServiceBlocked(RuntimeError):
    pass


class BudgetConsumerRequest(AipContractModel):
    model_config = ConfigDict(strict=True, frozen=True)
    schema_version: Literal[1]
    org_id: Literal['org-org']
    project_id: Literal['dev-project']
    proposal_id: str = Field(min_length=1, max_length=160)
    proposal_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    decision_id: str = Field(min_length=1, max_length=160)
    bearer_token: SecretStr

    @field_validator('schema_version', mode='before')
    @classmethod
    def _version(cls, value):
        return NetworkConsumerReferences._version(value)

    @field_validator('proposal_id', 'decision_id')
    @classmethod
    def _identifier(cls, value):
        return NetworkConsumerReferences._identifier(value)

    @field_validator('bearer_token')
    @classmethod
    def _jwt(cls, value):
        return _ConsumerRequest._jwt_shape(value)

    @property
    def request_hash(self):
        return canonical_hash(dict(domain='aos.budget-cost-consume/v1',
            tenant=dict(orgId=self.org_id, projectId=self.project_id), proposalId=self.proposal_id,
            proposalHash=self.proposal_hash, decisionId=self.decision_id))


def _authenticate(request, config):
    try:
        if type(request) is not BudgetConsumerRequest or type(config) is not BudgetConsumerConfig:
            raise ValueError()
        request = BudgetConsumerRequest.model_validate(request.model_dump())
        _require_external_oidc_config()
        principal = resolve_principal(token=request.bearer_token.get_secret_value(),
            header_org=request.org_id, header_project=request.project_id)
        if (type(principal) is not Principal or principal.token_kind != 'oidc'
                or (principal.org_id, principal.project_id) != (request.org_id, request.project_id)
                or not principal.subject or principal.subject == 'unknown'
                or principal.subject != principal.subject.strip() or not principal.subject.isprintable()):
            raise ValueError()
        return request, principal
    except Exception:
        raise BudgetConsumerServiceBlocked('BUDGET_CONSUMER_EXTERNAL_IDENTITY_REQUIRED') from None


def _call(conn, request, subject, *, read_only):
    name = 'reconcile' if read_only else 'consume'
    return conn.execute(f'SELECT public.aip_{name}_budget_as_actor_a0v_127(%s,%s,%s,%s,%s,%s) AS result',
        (request.org_id, request.project_id, request.proposal_id, request.decision_id,
         subject, request.proposal_hash)).fetchone()['result']


def _observe(request, config, subject):
    with connect_budget_consumer(config, TenantScope(request.org_id, request.project_id), read_only=True) as conn:
        result = _call(conn, request, subject, read_only=True)
    if type(result) is not dict or result.get('status') not in {'observed', 'unresolved', 'conflict'}:
        raise BudgetConsumerServiceBlocked('BUDGET_CONSUMER_OBSERVATION_INVALID')
    if result['status'] == 'observed':
        receipt = result.get('receipt')
        if (set(result) != {'status', 'receipt', 'activationEligible'} or result['activationEligible'] is not False
                or type(receipt) is not dict or receipt.get('proposalId') != request.proposal_id
                or receipt.get('proposalHash') != request.proposal_hash or receipt.get('decisionId') != request.decision_id
                or receipt.get('resourceType') != 'BudgetRevision'
                or receipt.get('receiptId') != 'budget-cost-consume-'+request.request_hash):
            raise BudgetConsumerServiceBlocked('BUDGET_CONSUMER_OBSERVATION_INVALID')
    elif set(result) != {'status'}:
        raise BudgetConsumerServiceBlocked('BUDGET_CONSUMER_OBSERVATION_INVALID')
    return result


def inquire_budget(request, config):
    request, principal = _authenticate(request, config)
    return _observe(request, config, principal.subject)


def consume_budget_once(request, config, attempt_directory):
    request, principal = _authenticate(request, config)
    prior = _observe(request, config, principal.subject)
    if prior['status'] != 'unresolved':
        return prior
    try:
        _reserve_attempt_receipt(attempt_directory, AttemptReceipt(request.org_id, request.project_id,
            request.proposal_id, request.proposal_id, request.request_hash, principal.subject),
            namespace='budget-cost-consumer/v1')
    except AttemptConflict:
        return {'status': 'conflict'}
    except (AttemptAlreadyRecorded, AttemptUnknown):
        pass
    else:
        try:
            with connect_budget_consumer(config, TenantScope(request.org_id, request.project_id)) as conn:
                _call(conn, request, principal.subject, read_only=False)
        except Exception:
            # A failed commit acknowledgement never authorizes another write.
            pass
    try:
        return _observe(request, config, principal.subject)
    except Exception:
        return {'status': 'unresolved'}
