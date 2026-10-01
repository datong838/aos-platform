"""Shared private Unix connection gate. No business authority or request retry."""
from contextlib import contextmanager
import os
from pathlib import Path
import socket
import stat

from aos_api.aip_network_issuer_ipc import _peer_identity, _require_unix_stream


def require_private_identity(*, api_uid, service_uid, ipc_gid):
    if (any(type(v) is not int or v <= 0 for v in (api_uid, service_uid, ipc_gid))
            or api_uid == service_uid or api_uid != os.geteuid()):
        raise ValueError('PRIVATE_SERVICE_IDENTITY_REQUIRED')


def validate_private_endpoint(path, *, api_uid, service_uid, ipc_gid):
    path = Path(path)
    if not path.is_absolute() or len(os.fsencode(path)) > 103 or '\0' in str(path):
        raise ValueError('PRIVATE_SERVICE_PATH_REQUIRED')
    require_private_identity(api_uid=api_uid, service_uid=service_uid, ipc_gid=ipc_gid)
    return path


def require_private_peer(conn, *, api_uid, service_uid, ipc_gid):
    require_private_identity(api_uid=api_uid, service_uid=service_uid, ipc_gid=ipc_gid)
    _require_unix_stream(conn)
    if _peer_identity(conn) != (service_uid, ipc_gid):
        raise ValueError('PRIVATE_SERVICE_PEER_REQUIRED')


@contextmanager
def open_private_service(path, *, api_uid, service_uid, ipc_gid):
    require_private_identity(api_uid=api_uid, service_uid=service_uid, ipc_gid=ipc_gid)
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('PRIVATE_SERVICE_PATH_REQUIRED')
    parent, target = path.parent.lstat(), path.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or not stat.S_ISSOCK(target.st_mode)
            or stat.S_IMODE(parent.st_mode) != 0o750 or stat.S_IMODE(target.st_mode) != 0o660
            or any((s.st_uid, s.st_gid) != (service_uid, ipc_gid) for s in (parent, target))):
        raise ValueError('PRIVATE_SERVICE_PATH_REQUIRED')
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.settimeout(5)
        conn.connect(str(path))
        require_private_peer(conn, api_uid=api_uid, service_uid=service_uid, ipc_gid=ipc_gid)
        yield conn


def exchange_private_frame(conn, method, command, *, request_type, decode):
    """One send and one reply only; caller must establish the private peer first."""
    import json
    import struct
    from aos_api.aip_network_issuer_ipc import MAX_ISSUER_FRAME_BYTES, read_issuer_frame
    try:
        if type(command) is not request_type or method not in ('execute_once','inquiry'):
            raise ValueError()
        command = request_type.model_validate(command.model_dump())
        payload = command.model_dump(mode='json', by_alias=True, exclude={'bearer_token'})
        payload['bearerToken'] = command.bearer_token.get_secret_value()
        raw = json.dumps(dict(schemaVersion=1, method=method, payload=payload), separators=(',',':')).encode()
        if not 0 < len(raw) <= MAX_ISSUER_FRAME_BYTES:
            raise ValueError()
        conn.settimeout(5)
        conn.sendall(struct.pack('>I',len(raw))+raw)
        return decode(read_issuer_frame(conn), command)
    except Exception:
        return {'status':'unresolved'}


def request_private_frame(path, *, api_uid, service_uid, ipc_gid, exchange):
    dispatched = False
    try:
        with open_private_service(path, api_uid=api_uid, service_uid=service_uid, ipc_gid=ipc_gid) as conn:
            dispatched = True
            return exchange(conn)
    except Exception:
        if dispatched:
            return {'status': 'unresolved'}
        raise ValueError('PRIVATE_SERVICE_CONNECTION_BLOCKED') from None
