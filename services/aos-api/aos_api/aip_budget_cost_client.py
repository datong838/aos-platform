"""Single-send budget protocol over an authenticated private Unix peer."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import struct

from aos_api.aip_budget_cost_issuer import BudgetCostIssuerCommand, BudgetCostIssuerBlocked
from aos_api.aip_network_issuer_ipc import MAX_ISSUER_FRAME_BYTES, _unique_pairs, _invalid_constant, read_issuer_frame
from aos_api.aip_private_service_transport import open_private_service, require_private_identity


@dataclass(frozen=True)
class BudgetCostEndpoint:
    socket_path: Path
    api_uid: int
    issuer_uid: int
    ipc_gid: int

    def __post_init__(self):
        try:
            path = Path(self.socket_path)
            if not path.is_absolute() or len(os.fsencode(path)) > 103 or '\0' in str(path):
                raise ValueError()
            require_private_identity(api_uid=self.api_uid, service_uid=self.issuer_uid, ipc_gid=self.ipc_gid)
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
    try:
        if type(command) is not BudgetCostIssuerCommand or method not in ('execute_once','inquiry'):
            raise ValueError()
        command = BudgetCostIssuerCommand.model_validate(command.model_dump())
        payload = command.model_dump(mode='json', by_alias=True, exclude={'bearer_token'})
        payload['bearerToken'] = command.bearer_token.get_secret_value()
        raw = json.dumps(dict(schemaVersion=1, method=method, payload=payload), separators=(',',':')).encode()
        if not 0 < len(raw) <= MAX_ISSUER_FRAME_BYTES:
            raise ValueError()
        conn.settimeout(5)
        conn.sendall(struct.pack('>I',len(raw))+raw)
        return decode_budget_response(read_issuer_frame(conn), command)
    except Exception:
        return {'status':'unresolved'}


def request_budget(endpoint, method, command):
    if (type(endpoint) is not BudgetCostEndpoint or type(command) is not BudgetCostIssuerCommand
            or method not in ('execute_once','inquiry')):
        raise BudgetCostIssuerBlocked('BUDGET_COST_CLIENT_INPUT_REQUIRED')
    dispatched = False
    try:
        endpoint.__post_init__()
        with open_private_service(endpoint.socket_path, api_uid=endpoint.api_uid,
                service_uid=endpoint.issuer_uid, ipc_gid=endpoint.ipc_gid) as conn:
            dispatched = True
            return exchange_budget(conn, method, command)
    except Exception:
        if dispatched:
            return {'status':'unresolved'}
        raise BudgetCostIssuerBlocked('BUDGET_COST_CLIENT_CONNECTION_BLOCKED') from None
