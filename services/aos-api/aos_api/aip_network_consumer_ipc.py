"""Private consumer Unix boundary reusing the guarded issuer transport primitives."""
import json
import os
from pathlib import Path
import socket
import struct

from aos_api.aip_network_consumer_contracts import NetworkConsumerCommand, NetworkConsumerInquiry
from aos_api.aip_network_consumer_connection import ConsumerDatabaseConfig
from aos_api.aip_network_consumer_service import consume_network_once, inquire_network
from aos_api.aip_network_issuer_auth import _require_external_oidc_config
from aos_api.aip_network_issuer_attempt import _private_directory_fd
from aos_api.aip_network_issuer_ipc import (
    MAX_ISSUER_FRAME_BYTES, _unique_pairs, _invalid_constant,
    require_issuer_peer, read_issuer_frame, open_private_issuer_listener,
)


class ConsumerProtocolBlocked(ValueError):
    pass


def decode_consumer_request(raw: bytes):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_ISSUER_FRAME_BYTES:
        raise ConsumerProtocolBlocked('CONSUMER_WIRE_INVALID')
    try:
        message = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs,
                             parse_constant=_invalid_constant)
        if (type(message) is not dict or set(message) != {'schemaVersion', 'method', 'payload'}
                or type(message['schemaVersion']) is not int or message['schemaVersion'] != 1
                or type(message['payload']) is not dict):
            raise ConsumerProtocolBlocked('CONSUMER_WIRE_INVALID')
        method = message['method']
        if method == 'inquiry':
            request = NetworkConsumerInquiry.model_validate(message['payload'])
        elif method == 'consume_once':
            request = NetworkConsumerCommand.model_validate(message['payload'])
        else:
            raise ConsumerProtocolBlocked('CONSUMER_WIRE_INVALID')
        return method, request
    except (UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        raise ConsumerProtocolBlocked('CONSUMER_WIRE_INVALID') from None


def open_private_consumer_listener(socket_path: str | Path, *, api_uid: int, consumer_uid: int,
                                  ipc_gid: int, config: ConsumerDatabaseConfig,
                                  attempt_directory: str | Path) -> socket.socket:
    try:
        if (type(config) is not ConsumerDatabaseConfig or not Path(socket_path).is_absolute()
                or not Path(attempt_directory).is_absolute()):
            raise ConsumerProtocolBlocked('CONSUMER_START_CONFIG_REQUIRED')
        config.__post_init__()
        _require_external_oidc_config()
        fd = _private_directory_fd(Path(attempt_directory))
        os.close(fd)
        return open_private_issuer_listener(socket_path, api_uid=api_uid, issuer_uid=consumer_uid,
                                            ipc_gid=ipc_gid, credential_file=config.passfile)
    except Exception:
        raise ConsumerProtocolBlocked('CONSUMER_LISTENER_START_BLOCKED') from None


def serve_one_consumer_connection(conn: socket.socket, *, api_uid: int, consumer_uid: int,
                                 config: ConsumerDatabaseConfig,
                                 attempt_directory: str | Path) -> bool:
    try:
        require_issuer_peer(conn, api_uid=api_uid, issuer_uid=consumer_uid)
    except Exception:
        conn.close()
        return False
    processed = False
    response = {'schemaVersion': 1, 'status': 'blocked', 'code': 'CONSUMER_REQUEST_BLOCKED'}
    try:
        method, request = decode_consumer_request(read_issuer_frame(conn))
        result = (inquire_network(request, config) if method == 'inquiry'
                  else consume_network_once(request, config, attempt_directory))
        response = {'schemaVersion': 1, **result}
        processed = True
    except Exception:
        # No bearer, exception detail, DB config or credential path on the wire.
        pass
    try:
        body = json.dumps(response, sort_keys=True, separators=(',', ':')).encode()
        if len(body) > MAX_ISSUER_FRAME_BYTES:
            raise ConsumerProtocolBlocked('CONSUMER_RESPONSE_TOO_LARGE')
        conn.settimeout(5)
        conn.sendall(struct.pack('>I', len(body)) + body)
    except (OSError, ValueError):
        processed = False
    finally:
        conn.close()
    return processed
