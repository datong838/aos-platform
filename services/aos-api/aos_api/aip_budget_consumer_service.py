"""Private budget consumption and historical inquiry; never retries a write."""
import re
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
    operation: Literal['consume', 'configure'] = 'consume'
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
        domain = 'aos.budget-cost-consume/v1' if self.operation == 'consume' else 'aos.budget-cost-configuration/v1'
        return canonical_hash(dict(domain=domain,
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
    if request.operation == 'configure':
        name = 'aip_reconcile_cost_configuration_a0v_128' if read_only else 'aip_configure_budget_cost_a0v_128'
    else:
        name = 'aip_reconcile_budget_as_actor_a0v_127' if read_only else 'aip_consume_budget_as_actor_a0v_127'
    return conn.execute(f'SELECT public.{name}(%s,%s,%s,%s,%s,%s) AS result',
        (request.org_id, request.project_id, request.proposal_id, request.decision_id,
         subject, request.proposal_hash)).fetchone()['result']


def _observe(request, config, subject):
    with connect_budget_consumer(config, TenantScope(request.org_id, request.project_id), read_only=True) as conn:
        result = _call(conn, request, subject, read_only=True)
    return validate_consumer_result(result, request)


def validate_consumer_result(result, request):
    """Same immutable result contract at SQL and IPC boundaries."""
    try:
        if type(request) is not BudgetConsumerRequest:
            raise ValueError()
        request = BudgetConsumerRequest.model_validate(request.model_dump())
        if type(result) is not dict or result.get('status') not in {'observed', 'unresolved', 'conflict'}:
            raise ValueError()
        if result['status'] != 'observed':
            if set(result) != {'status'}:
                raise ValueError()
            return result
        if set(result) != {'status', 'receipt', 'activationEligible'} or result['activationEligible'] is not False:
            raise ValueError()
        r = result['receipt']
        common = {'proposalId', 'proposalHash', 'decisionId', 'receiptId'}
        fields = ({'resourceType', 'resourceId', 'revision', 'contentHash'} if request.operation == 'consume'
                  else {'budgetRef', 'priceRef', 'policyRef'})
        prefix = 'budget-cost-consume-' if request.operation == 'consume' else 'cost-configuration-'
        if (type(r) is not dict or set(r) != common | fields
                or r['proposalId'] != request.proposal_id or r['proposalHash'] != request.proposal_hash
                or r['decisionId'] != request.decision_id or r['receiptId'] != prefix + request.request_hash):
            raise ValueError()
        def reference(value, kind):
            if (type(value) is not dict or set(value) != {'assetType', 'assetId', 'revision', 'contentHash'}
                    or value['assetType'] != kind or type(value['revision']) is not int
                    or not 1 <= value['revision'] <= 9007199254740991
                    or type(value['contentHash']) is not str or re.fullmatch('[0-9a-f]{64}', value['contentHash']) is None
                    or type(value['assetId']) is not str or not 1 <= len(value['assetId']) <= 160
                    or not value['assetId'].isprintable() or any(c.isspace() for c in value['assetId'])):
                raise ValueError()
        if request.operation == 'consume':
            reference(dict(assetType=r['resourceType'], assetId=r['resourceId'],
                           revision=r['revision'], contentHash=r['contentHash']), 'BudgetRevision')
        else:
            reference(r['budgetRef'], 'BudgetRevision')
            for key, kind, asset_prefix in [('priceRef', 'ModelPriceSnapshotRevision', 'cost-price-'),
                                            ('policyRef', 'BudgetPolicyRevision', 'cost-policy-')]:
                reference(r[key], kind)
                if r[key]['revision'] != 1 or r[key]['assetId'] != asset_prefix + request.request_hash:
                    raise ValueError()
        return result
    except Exception:
        raise BudgetConsumerServiceBlocked('BUDGET_CONSUMER_OBSERVATION_INVALID') from None


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
            namespace=('budget-cost-consumer/v1' if request.operation == 'consume'
                       else 'budget-cost-configuration/v1'))
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
