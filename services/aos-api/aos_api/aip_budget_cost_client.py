"""Single-send budget protocol over an authenticated private Unix peer."""
from dataclasses import dataclass
import json
from pathlib import Path

from aos_api.aip_budget_cost_issuer import BudgetCostIssuerCommand, BudgetCostIssuerBlocked
from aos_api.aip_network_issuer_ipc import MAX_ISSUER_FRAME_BYTES, _unique_pairs, _invalid_constant
from aos_api.aip_private_service_transport import validate_private_endpoint, exchange_private_frame, request_private_frame


@dataclass(frozen=True)
class BudgetCostEndpoint:
    socket_path: Path
    api_uid: int
    issuer_uid: int
    ipc_gid: int

    def __post_init__(self):
        try:
            path = validate_private_endpoint(self.socket_path, api_uid=self.api_uid,
                service_uid=self.issuer_uid, ipc_gid=self.ipc_gid)
            object.__setattr__(self, 'socket_path', path)
        except Exception:
            raise BudgetCostIssuerBlocked('BUDGET_COST_ENDPOINT_REQUIRED') from None


def decode_budget_response(raw, command):
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_ISSUER_FRAME_BYTES:
            raise ValueError()
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs, parse_constant=_invalid_constant)
        if type(value) is not dict or type(value.get('schemaVersion')) is not int or value['schemaVersion'] != 1:
            raise ValueError()
        status = value.get('status')
        if status == 'observed':
            if set(value) != {'schemaVersion', 'status', 'result', 'activationEligible'} or value['activationEligible'] is not False:
                raise ValueError()
            result = value['result']
            expected = ({'decisionId', 'decision', 'proposalHash', 'activationEligible'} if command.operation=='decide'
                        else {'revocationId', 'decisionId', 'activationEligible'})
            if type(result) is not dict or set(result) != expected or result['activationEligible'] is not False:
                raise ValueError()
            for key in ('decisionId', 'revocationId'):
                if key in result and (type(result[key]) is not str or not 1 <= len(result[key]) <= 160
                        or not result[key].isprintable() or any(c.isspace() for c in result[key])):
                    raise ValueError()
            if command.operation=='decide' and (result['decision']!=command.decision or result['proposalHash']!=command.proposal_hash):
                raise ValueError()
        elif status in ('unresolved', 'conflict'):
            if set(value) != {'schemaVersion','status'}:
                raise ValueError()
        elif status == 'blocked':
            if set(value) != {'schemaVersion','status','code'} or value['code'] != 'BUDGET_COST_REQUEST_BLOCKED':
                raise ValueError()
        else:
            raise ValueError()
        return {k:v for k,v in value.items() if k!='schemaVersion'}
    except Exception:
        raise BudgetCostIssuerBlocked('BUDGET_COST_RESPONSE_INVALID') from None


def exchange_budget(conn, method, command):
    """Transport only. Production caller must establish kernel peer first."""
    return exchange_private_frame(conn, method, command,
        request_type=BudgetCostIssuerCommand, decode=decode_budget_response)


def request_budget(endpoint, method, command):
    if (type(endpoint) is not BudgetCostEndpoint or type(command) is not BudgetCostIssuerCommand
            or method not in ('execute_once','inquiry')):
        raise BudgetCostIssuerBlocked('BUDGET_COST_CLIENT_INPUT_REQUIRED')
    try:
        endpoint.__post_init__()
        return request_private_frame(endpoint.socket_path, api_uid=endpoint.api_uid,
            service_uid=endpoint.issuer_uid, ipc_gid=endpoint.ipc_gid,
            exchange=lambda conn: exchange_budget(conn, method, command))
    except Exception:
        raise BudgetCostIssuerBlocked('BUDGET_COST_CLIENT_CONNECTION_BLOCKED') from None
