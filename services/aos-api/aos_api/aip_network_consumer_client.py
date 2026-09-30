"""One-send private consumer transport; unknown outcomes never authorize resend."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import struct

from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand, NetworkConsumerInquiry
from aos_api.aip_network_issuer_ipc import (
    MAX_ISSUER_FRAME_BYTES, _unique_pairs, _invalid_constant,
    read_issuer_frame,
)
from aos_api.aip_private_service_transport import open_private_service, require_private_peer


class ConsumerClientBlocked(ValueError):
    pass


@dataclass(frozen=True)
class ConsumerEndpoint:
    socket_path: Path
    api_uid: int
    consumer_uid: int
    ipc_gid: int

    def __post_init__(self):
        try:
            path = Path(self.socket_path)
            if (not path.is_absolute() or any(type(v) is not int or v <= 0 for v in
                    (self.api_uid, self.consumer_uid, self.ipc_gid))
                    or self.api_uid == self.consumer_uid or self.api_uid != os.geteuid()):
                raise ValueError()
            object.__setattr__(self, 'socket_path', path)
        except Exception:
            raise ConsumerClientBlocked('CONSUMER_ENDPOINT_REQUIRED') from None


def _require_server(conn, endpoint):
    try:
        endpoint.__post_init__()
        require_private_peer(conn, api_uid=endpoint.api_uid,
                             service_uid=endpoint.consumer_uid, ipc_gid=endpoint.ipc_gid)
    except Exception:
        raise ConsumerClientBlocked('CONSUMER_SERVER_IDENTITY_REQUIRED') from None


def _decode_response(raw, request):
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs,
                           parse_constant=_invalid_constant)
        if (type(value) is not dict or type(value.get('schemaVersion')) is not int
                or value['schemaVersion'] != 1):
            raise ValueError()
        status = value.get('status')
        if status in ('unresolved', 'conflict'):
            if set(value) != {'schemaVersion', 'status'}:
                raise ValueError()
        elif status == 'blocked':
            if (set(value) != {'schemaVersion', 'status', 'code'}
                    or value['code'] != 'CONSUMER_REQUEST_BLOCKED'):
                raise ValueError()
        elif status == 'observed':
            r = value.get('receipt')
            if (set(value) != {'schemaVersion', 'status', 'receipt'} or type(r) is not dict
                    or set(r) != {'resourceType', 'resourceId', 'revision', 'proposalId',
                                  'approvalEventId', 'contentHash', 'receiptId'}
                    or r['resourceType'] != 'NetworkPolicyRevision'
                    or r['proposalId'] != request.proposal_id
                    or r['approvalEventId'] != request.approval_event_id
                    or r['contentHash'] != request.target_content_hash
                    or type(r['revision']) is not int or r['revision'] < 1
                    or any(type(r[k]) is not str or not 0 < len(r[k]) <= 160
                           or not r[k].isprintable() or any(c.isspace() for c in r[k])
                           for k in ('resourceId', 'receiptId'))):
                raise ValueError()
        else:
            raise ValueError()
        return {key: val for key, val in value.items() if key != 'schemaVersion'}
    except Exception:
        raise ConsumerClientBlocked('CONSUMER_RESPONSE_INVALID') from None


def _exchange(conn, request):
    """Internal transport only. Caller must validate the connected server first."""
    try:
        if type(request) not in (NetworkConsumerCommand, NetworkConsumerInquiry):
            raise ValueError()
        payload = request.model_dump(mode='json', by_alias=True, exclude={'bearer_token'})
        payload['bearerToken'] = request.bearer_token.get_secret_value()
        method = 'consume_once' if type(request) is NetworkConsumerCommand else 'inquiry'
        body = json.dumps({'schemaVersion': 1, 'method': method, 'payload': payload},
                          separators=(',', ':')).encode('utf-8')
        if not 0 < len(body) <= MAX_ISSUER_FRAME_BYTES:
            raise ValueError()
        conn.settimeout(5)
        conn.sendall(struct.pack('>I', len(body)) + body)
        return _decode_response(read_issuer_frame(conn), request)
    except Exception:
        # Includes partial sends, response loss and malformed replies. No reconnect.
        return {'status': 'unresolved'}


def request_consumer(endpoint: ConsumerEndpoint, request):
    if (type(endpoint) is not ConsumerEndpoint
            or type(request) not in (NetworkConsumerCommand, NetworkConsumerInquiry)):
        raise ConsumerClientBlocked('CONSUMER_CLIENT_EXACT_INPUT_REQUIRED')
    dispatched = False
    try:
        endpoint.__post_init__()
        with open_private_service(endpoint.socket_path, api_uid=endpoint.api_uid,
                                  service_uid=endpoint.consumer_uid, ipc_gid=endpoint.ipc_gid) as conn:
            dispatched = True
            return _exchange(conn, request)
    except Exception:
        if dispatched:
            return {'status': 'unresolved'}
        raise ConsumerClientBlocked('CONSUMER_CLIENT_CONNECTION_BLOCKED') from None
