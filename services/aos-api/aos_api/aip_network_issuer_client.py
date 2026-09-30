"""Single-send isolated issuer client. Unknown results permit inquiry only."""
from dataclasses import dataclass
import json
from pathlib import Path
import struct

from aos_api.aip_network_issuer_contracts import (
    NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry,
)
from aos_api.aip_network_issuer_ipc import (
    MAX_ISSUER_FRAME_BYTES, _unique_pairs, _invalid_constant, read_issuer_frame,
)
from aos_api.aip_private_service_transport import open_private_service, require_private_identity


class IssuerClientBlocked(ValueError):
    pass


@dataclass(frozen=True)
class IssuerEndpoint:
    socket_path: Path
    api_uid: int
    issuer_uid: int
    ipc_gid: int

    def __post_init__(self):
        try:
            path = Path(self.socket_path)
            if not path.is_absolute():
                raise ValueError()
            require_private_identity(api_uid=self.api_uid, service_uid=self.issuer_uid,
                                     ipc_gid=self.ipc_gid)
            object.__setattr__(self, 'socket_path', path)
        except Exception:
            raise IssuerClientBlocked('ISSUER_ENDPOINT_REQUIRED') from None


def _decode_response(raw, request):
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs,
                           parse_constant=_invalid_constant)
        if (type(value) is not dict or type(value.get('schemaVersion')) is not int
                or value['schemaVersion'] != 1):
            raise ValueError()
        status = value.get('status')
        if status == 'blocked':
            if (set(value) != {'schemaVersion', 'status', 'code'}
                    or value['code'] != 'ISSUER_REQUEST_BLOCKED'):
                raise ValueError()
        else:
            if set(value) != {'schemaVersion', 'status', 'eventId', 'decision'}:
                raise ValueError()
            if status == 'observed':
                event = value['eventId']
                if (type(event) is not str or not 0 < len(event) <= 160
                        or not event.isprintable() or any(c.isspace() for c in event)
                        or value['decision'] not in ('approved', 'rejected')
                        or (type(request) is NetworkIssuerDecisionCommand
                            and value['decision'] != request.decision.decision)):
                    raise ValueError()
            elif status in ('unresolved', 'conflict'):
                if value['eventId'] is not None or value['decision'] is not None:
                    raise ValueError()
            else:
                raise ValueError()
        return {key: val for key, val in value.items() if key != 'schemaVersion'}
    except Exception:
        raise IssuerClientBlocked('ISSUER_RESPONSE_INVALID') from None


def _exchange(conn, request):
    """Transport only; caller must establish the exact kernel peer before this."""
    try:
        if type(request) not in (NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry):
            raise ValueError()
        payload = request.model_dump(mode='json', by_alias=True, exclude={'bearer_token'})
        payload['bearerToken'] = request.bearer_token.get_secret_value()
        method = 'decide_once' if type(request) is NetworkIssuerDecisionCommand else 'inquiry'
        body = json.dumps({'schemaVersion': 1, 'method': method, 'payload': payload},
                          separators=(',', ':')).encode('utf-8')
        if not 0 < len(body) <= MAX_ISSUER_FRAME_BYTES:
            raise ValueError()
        conn.settimeout(5)
        conn.sendall(struct.pack('>I', len(body)) + body)
        return _decode_response(read_issuer_frame(conn), request)
    except Exception:
        return {'status': 'unresolved'}


def request_issuer(endpoint: IssuerEndpoint, request):
    if (type(endpoint) is not IssuerEndpoint
            or type(request) not in (NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry)):
        raise IssuerClientBlocked('ISSUER_CLIENT_EXACT_INPUT_REQUIRED')
    dispatched = False
    try:
        endpoint.__post_init__()
        with open_private_service(endpoint.socket_path, api_uid=endpoint.api_uid,
                                  service_uid=endpoint.issuer_uid, ipc_gid=endpoint.ipc_gid) as conn:
            dispatched = True
            return _exchange(conn, request)
    except Exception:
        if dispatched:
            return {'status': 'unresolved'}
        raise IssuerClientBlocked('ISSUER_CLIENT_CONNECTION_BLOCKED') from None
