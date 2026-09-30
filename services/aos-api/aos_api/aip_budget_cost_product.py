"""Persist original budget-cost review requests before one private dispatch."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from aos_api.aip_contracts import AipContractModel
from aos_api.aip_budget_cost_client import BudgetCostEndpoint, request_budget
from aos_api.aip_budget_cost_issuer import BudgetCostIssuerCommand
from aos_api.aip_budget_activation_product import BudgetProductBlocked, _authenticated
from aos_api.aip_budget_store import canonical_hash
from aos_api.aip_network_consumer_config import _read_private_config
from aos_api.aip_network_issuer_attempt import _private_directory_fd, _read_marker
from aos_api.aip_private_request_file import create_private_request_file
from aos_api.auth import parse_bearer


class BudgetCostReviewRequest(AipContractModel):
    proposal_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    decision: Literal['approved', 'rejected'] | None = None
    reason: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode='after')
    def _shape(self):
        if (self.decision is None) == (self.reason is None):
            raise ValueError('one review operation required')
        if self.reason is not None and (self.reason!=self.reason.strip() or not self.reason.isprintable()):
            raise ValueError('canonical reason required')
        return self


@dataclass(frozen=True)
class BudgetCostProductConfig:
    endpoint: BudgetCostEndpoint
    request_directory: Path

    def __post_init__(self):
        try:
            if type(self.endpoint) is not BudgetCostEndpoint:
                raise ValueError()
            self.endpoint.__post_init__()
            path = Path(self.request_directory)
            if not path.is_absolute():
                raise ValueError()
            fd = _private_directory_fd(path)
            os.close(fd)
            object.__setattr__(self, 'request_directory', path)
        except Exception:
            raise BudgetProductBlocked('BUDGET_COST_PRODUCT_CONFIG_REQUIRED', 503) from None


def configured_budget_cost_product():
    try:
        path = os.environ.get('AOS_BUDGET_COST_API_CONFIG')
        if not path:
            raise ValueError()
        data = _read_private_config(path)
        if (type(data) is not dict or set(data) != {'schemaVersion','socketPath','apiUid','issuerUid','ipcGid','requestDirectory'}
                or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1):
            raise ValueError()
        return BudgetCostProductConfig(BudgetCostEndpoint(data['socketPath'],data['apiUid'],
            data['issuerUid'],data['ipcGid']), data['requestDirectory'])
    except Exception:
        raise BudgetProductBlocked('BUDGET_COST_PRODUCT_CONFIG_REQUIRED', 503) from None


def _slot(actor, proposal_id, operation):
    if (operation not in ('decide','revoke') or type(proposal_id) is not str
            or not 1 <= len(proposal_id) <= 160 or not proposal_id.isprintable()
            or proposal_id != proposal_id.strip()):
        raise BudgetProductBlocked('BUDGET_COST_PRODUCT_REF_INVALID', 422)
    return 'budget-cost-product-v1-'+canonical_hash([
        actor.org_id,actor.project_id,actor.subject,operation,proposal_id])


def _command(actor, proposal_id, operation, body, authorization):
    if type(body) is not BudgetCostReviewRequest:
        raise ValueError('exact review required')
    body = BudgetCostReviewRequest.model_validate(body.model_dump())
    return BudgetCostIssuerCommand(operation=operation, orgId=actor.org_id, projectId=actor.project_id,
        proposalId=proposal_id, idempotencyKey=_slot(actor,proposal_id,operation),
        bearerToken=parse_bearer(authorization), **body.model_dump(by_alias=True))


def _envelope(actor, proposal_id, operation, body):
    payload = body.model_dump(mode='json',by_alias=True)
    return dict(schemaVersion=1, state='ATTEMPTED', orgId=actor.org_id, projectId=actor.project_id,
        subject=actor.subject, proposalId=proposal_id, operation=operation,
        key=_slot(actor,proposal_id,operation), requestHash=canonical_hash(payload), request=payload)


def _read_original(fd, actor, proposal_id, operation, authorization):
    key = _slot(actor,proposal_id,operation)
    saved = _read_marker(fd,key+'.json',allow_missing=True)
    if saved is None:
        return None
    body = BudgetCostReviewRequest.model_validate(saved['request'])
    _command(actor,proposal_id,operation,body,authorization)
    if canonical_hash(saved) != canonical_hash(_envelope(actor,proposal_id,operation,body)):
        raise ValueError('untrusted original request')
    return body


def budget_cost_request(config, proposal_id, operation, body, principal, authorization):
    actor = _authenticated(principal, authorization)
    key = _slot(actor, proposal_id, operation)
    if type(config) is not BudgetCostProductConfig:
        raise BudgetProductBlocked('BUDGET_COST_PRODUCT_CONFIG_REQUIRED', 503)
    config.__post_init__()
    envelope = raw = None
    if body is not None:
        try:
            _command(actor,proposal_id,operation,body,authorization)
            envelope = _envelope(actor,proposal_id,operation,body)
            raw = json.dumps(envelope,ensure_ascii=False,separators=(',',':')).encode()
            if len(raw)>4096:
                raise ValueError()
        except Exception:
            raise BudgetProductBlocked('BUDGET_COST_PRODUCT_REQUEST_INVALID',422) from None
    reserved = False
    try:
        fd = _private_directory_fd(config.request_directory)
        try:
            original = _read_original(fd,actor,proposal_id,operation,authorization)
            if original is None and body is not None:
                reserved = create_private_request_file(fd,key+'.json',raw)
                if not reserved:
                    original = _read_original(fd,actor,proposal_id,operation,authorization)
                    if original is None:
                        raise ValueError('reservation disappeared')
            if original is not None:
                if envelope is not None and canonical_hash(envelope)!=canonical_hash(_envelope(actor,proposal_id,operation,original)):
                    raise BudgetProductBlocked('BUDGET_COST_PRODUCT_REQUEST_CONFLICT',409)
                body = original
        finally:
            os.close(fd)
    except BudgetProductBlocked:
        raise
    except Exception:
        raise BudgetProductBlocked('BUDGET_COST_PRODUCT_SAVED_REQUEST_UNTRUSTED',503) from None
    if body is None:
        return {'status':'not_attempted'}
    command = _command(actor,proposal_id,operation,body,authorization)
    if reserved:
        try:
            result = request_budget(config.endpoint,'execute_once',command)
            # FU returns an immutable Receipt inquiry, validated by the client.
            # A bounded one-connection issuer need not remain up for a second read.
            if result['status'] == 'observed':
                return result
        except Exception:
            # The durable request stays even if connection/response is lost.
            pass
    try:
        return request_budget(config.endpoint,'inquiry',command)
    except Exception:
        return {'status':'unresolved'}
