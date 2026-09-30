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
