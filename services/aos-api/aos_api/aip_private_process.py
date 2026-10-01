"""Shared finite private transport lifecycle; business dispatch remains domain-owned."""
import json
import math
import os
from pathlib import Path
import struct
from aos_api.tenant_scope import TenantScope
from aos_api.aip_network_issuer_ipc import (
    MAX_ISSUER_FRAME_BYTES, _unique_pairs, _invalid_constant, require_issuer_peer, read_issuer_frame,
)


def validate_private_process(config, *, database_type, service_uid, blocked, error_code):
    try:
        if (type(config.database) is not database_type or type(config.scope) is not TenantScope
                or any(type(v) is not int or v <= 0 for v in (config.api_uid, service_uid, config.ipc_gid))
                or config.api_uid == service_uid or service_uid != os.geteuid()
                or config.ipc_gid != os.getegid()
                or type(config.max_connections) is not int or not 1 <= config.max_connections <= 64
                or type(config.accept_timeout) not in (int, float)
                or not math.isfinite(config.accept_timeout) or not 0 < config.accept_timeout <= 30):
            raise ValueError()
        for name in ('socket_path', 'attempt_directory'):
            value = Path(getattr(config, name))
            if not value.is_absolute():
                raise ValueError()
            if name == 'socket_path' and (len(os.fsencode(value)) > 103 or '\0' in str(value)):
                raise ValueError('macOS Unix socket path exceeds kernel limit')
            object.__setattr__(config, name, value)
        config.database.__post_init__()
        config.scope.__post_init__()
    except Exception:
        raise blocked(error_code) from None


def decode_private_request(raw, *, request_type, blocked, error_code):
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_ISSUER_FRAME_BYTES:
            raise ValueError()
        frame = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_pairs,
                           parse_constant=_invalid_constant)
        if (type(frame) is not dict or set(frame) != {'schemaVersion', 'method', 'payload'}
                or type(frame['schemaVersion']) is not int or frame['schemaVersion'] != 1
                or frame['method'] not in ('execute_once', 'inquiry') or type(frame['payload']) is not dict):
            raise ValueError()
        command = request_type.model_validate(frame['payload'])
        return frame['method'], command
    except Exception:
        raise blocked(error_code) from None


def serve_private_connection(conn, *, api_uid, service_uid, scope, decode, dispatch, error_code):
    response = {'schemaVersion': 1, 'status': 'blocked', 'code': error_code}
    processed = False
    try:
        require_issuer_peer(conn, api_uid=api_uid, issuer_uid=service_uid)
        method, command = decode(read_issuer_frame(conn))
        if (command.org_id, command.project_id) != scope.key:
            raise ValueError('private process scope mismatch')
        response = {'schemaVersion': 1, **dispatch(method, command)}
        processed = True
    except Exception:
        # Never return bearer tokens, raw SQL, tenant data or exception text.
        pass
    try:
        body = json.dumps(response, separators=(',', ':')).encode()
        conn.settimeout(5)
        conn.sendall(struct.pack('>I', len(body)) + body)
    except OSError:
        processed = False
    finally:
        conn.close()
    return processed


def run_private_process(config, *, listener_factory, serve):
    accepted = processed = 0
    with listener_factory(config) as listener:
        listener.settimeout(config.accept_timeout)
        for _ in range(config.max_connections):
            try:
                conn, _ = listener.accept()
            except TimeoutError:
                break
            accepted += 1
            try:
                processed += int(serve(conn, config))
            finally:
                conn.close()
    return {'accepted': accepted, 'processed': processed}
