"""Exact budget consumption responses over an authenticated private peer."""
from dataclasses import dataclass
import json
from pathlib import Path
import re

from aos_api.aip_budget_consumer_service import BudgetConsumerRequest
from aos_api.aip_network_issuer_ipc import MAX_ISSUER_FRAME_BYTES, _unique_pairs, _invalid_constant
from aos_api.aip_private_service_transport import validate_private_endpoint, exchange_private_frame, request_private_frame


class BudgetConsumerClientBlocked(ValueError):
    pass


@dataclass(frozen=True)
class BudgetConsumerEndpoint:
    socket_path: Path
    api_uid: int
    consumer_uid: int
    ipc_gid: int

    def __post_init__(self):
        try:
            path = validate_private_endpoint(self.socket_path, api_uid=self.api_uid,
                service_uid=self.consumer_uid, ipc_gid=self.ipc_gid)
            object.__setattr__(self, 'socket_path', path)
        except Exception:
            raise BudgetConsumerClientBlocked('BUDGET_CONSUMER_ENDPOINT_REQUIRED') from None


def decode_consumer_response(raw, request):
    try:
        if type(request) is not BudgetConsumerRequest or type(raw) is not bytes or not 0 < len(raw) <= MAX_ISSUER_FRAME_BYTES:
            raise ValueError()
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs, parse_constant=_invalid_constant)
        if type(value) is not dict or type(value.get('schemaVersion')) is not int or value['schemaVersion'] != 1:
            raise ValueError()
        status = value.get('status')
        if status == 'observed':
            if set(value) != {'schemaVersion', 'status', 'receipt', 'activationEligible'} or value['activationEligible'] is not False:
                raise ValueError()
            r = value['receipt']
            if (type(r) is not dict or set(r) != {'resourceType', 'resourceId', 'revision', 'contentHash',
                    'proposalId', 'proposalHash', 'decisionId', 'receiptId'}
                    or r['resourceType'] != 'BudgetRevision' or r['proposalId'] != request.proposal_id
                    or r['proposalHash'] != request.proposal_hash or r['decisionId'] != request.decision_id
                    or r['receiptId'] != 'budget-cost-consume-'+request.request_hash
                    or type(r['revision']) is not int or not 1 <= r['revision'] <= 9007199254740991
                    or type(r['contentHash']) is not str or re.fullmatch('[0-9a-f]{64}', r['contentHash']) is None
                    or type(r['resourceId']) is not str or not 1 <= len(r['resourceId']) <= 160
                    or not r['resourceId'].isprintable() or any(c.isspace() for c in r['resourceId'])):
                raise ValueError()
        elif status in ('unresolved', 'conflict'):
            if set(value) != {'schemaVersion', 'status'}:
                raise ValueError()
        elif status == 'blocked':
            if set(value) != {'schemaVersion', 'status', 'code'} or value['code'] != 'BUDGET_CONSUMER_REQUEST_BLOCKED':
                raise ValueError()
        else:
            raise ValueError()
        return {k:v for k,v in value.items() if k != 'schemaVersion'}
    except Exception:
        raise BudgetConsumerClientBlocked('BUDGET_CONSUMER_RESPONSE_INVALID') from None


def exchange_consumer(conn, method, request):
    return exchange_private_frame(conn, method, request,
        request_type=BudgetConsumerRequest, decode=decode_consumer_response)


def request_consumer(endpoint, method, request):
    if (type(endpoint) is not BudgetConsumerEndpoint or type(request) is not BudgetConsumerRequest
            or method not in ('execute_once', 'inquiry')):
        raise BudgetConsumerClientBlocked('BUDGET_CONSUMER_CLIENT_INPUT_REQUIRED')
    try:
        endpoint.__post_init__()
        return request_private_frame(endpoint.socket_path, api_uid=endpoint.api_uid,
            service_uid=endpoint.consumer_uid, ipc_gid=endpoint.ipc_gid,
            exchange=lambda conn: exchange_consumer(conn, method, request))
    except Exception:
        raise BudgetConsumerClientBlocked('BUDGET_CONSUMER_CONNECTION_BLOCKED') from None
