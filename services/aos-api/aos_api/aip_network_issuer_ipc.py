"""Bounded private Unix transport for an isolated network approval issuer."""

from __future__ import annotations

import ctypes
import json
import os
import socket
import stat
import struct
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from aos_api.aip_network_issuer_contracts import (
    NetworkIssuerDecisionCommand, NetworkIssuerDecisionInquiry,
)
from aos_api.aip_network_issuer_service import dispatch_issuer_request, issue_decision_once
from aos_api.tenant_scope import TenantScope


MAX_ISSUER_FRAME_BYTES = 65_536


class IssuerProtocolBlocked(ValueError):
    pass


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise IssuerProtocolBlocked("ISSUER_WIRE_INVALID")
        result[key] = value
    return result


def _invalid_constant(_: str) -> None:
    raise IssuerProtocolBlocked("ISSUER_WIRE_INVALID")


def decode_issuer_request(raw: bytes):
    """Decode exactly one request; no caller-supplied role, path or DB credential."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_ISSUER_FRAME_BYTES:
        raise IssuerProtocolBlocked("ISSUER_WIRE_INVALID")
    try:
        message = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                             parse_constant=_invalid_constant)
        if (type(message) is not dict or set(message) != {"schemaVersion", "method", "payload"}
                or type(message["schemaVersion"]) is not int or message["schemaVersion"] != 1
                or type(message["payload"]) is not dict):
            raise IssuerProtocolBlocked("ISSUER_WIRE_INVALID")
        method = message["method"]
        if method == "inquiry":
            request = NetworkIssuerDecisionInquiry.model_validate(message["payload"])
        elif method == "decide_once":
            request = NetworkIssuerDecisionCommand.model_validate(message["payload"])
        else:
            raise IssuerProtocolBlocked("ISSUER_WIRE_INVALID")
        return method, request
    except (UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        raise IssuerProtocolBlocked("ISSUER_WIRE_INVALID") from None


def _require_unix_stream(conn: socket.socket) -> None:
    if (type(conn) is not socket.socket or conn.family != socket.AF_UNIX
            or conn.type & socket.SOCK_STREAM != socket.SOCK_STREAM):
        raise IssuerProtocolBlocked("ISSUER_UNIX_STREAM_REQUIRED")


def _peer_identity(conn: socket.socket) -> tuple[int, int]:
    """Read kernel peer UID/GID on macOS; never trust fields in the wire frame."""
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        getpeereid = libc.getpeereid
    except AttributeError:
        raise IssuerProtocolBlocked("ISSUER_PEER_CREDENTIAL_REQUIRED") from None
    getpeereid.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint),
                           ctypes.POINTER(ctypes.c_uint)]
    getpeereid.restype = ctypes.c_int
    uid = ctypes.c_uint()
    gid = ctypes.c_uint()
    if getpeereid(conn.fileno(), ctypes.byref(uid), ctypes.byref(gid)) != 0:
        raise IssuerProtocolBlocked("ISSUER_PEER_CREDENTIAL_REQUIRED")
    return uid.value, gid.value


def require_issuer_peer(conn: socket.socket, *, api_uid: int, issuer_uid: int) -> None:
    _require_unix_stream(conn)
    if (type(api_uid) is not int or type(issuer_uid) is not int
            or api_uid <= 0 or issuer_uid <= 0 or api_uid == issuer_uid
            or os.geteuid() != issuer_uid):
        raise IssuerProtocolBlocked("ISSUER_OS_IDENTITY_NOT_ISOLATED")
    peer_uid, peer_gid = _peer_identity(conn)
    if peer_uid != api_uid or peer_gid < 0:
        raise IssuerProtocolBlocked("ISSUER_PEER_IDENTITY_INVALID")


def open_private_issuer_listener(
    socket_path: str | Path,
    *,
    api_uid: int,
    issuer_uid: int,
    ipc_gid: int,
    credential_file: str | Path,
) -> socket.socket:
    """Bind only after distinct OS identities and private credential paths exist."""
    if (type(api_uid) is not int or type(issuer_uid) is not int or type(ipc_gid) is not int
            or api_uid <= 0 or issuer_uid <= 0 or api_uid == issuer_uid or ipc_gid <= 0
            or os.geteuid() != issuer_uid or os.getegid() != ipc_gid):
        raise IssuerProtocolBlocked("ISSUER_OS_IDENTITY_NOT_ISOLATED")
    path = Path(socket_path)
    secret = Path(credential_file)
    try:
        socket_dir = path.parent.lstat()
        secret_dir = secret.parent.lstat()
        secret_file = secret.lstat()
        if (not stat.S_ISDIR(socket_dir.st_mode)
                or socket_dir.st_uid != issuer_uid or socket_dir.st_gid != ipc_gid
                or stat.S_IMODE(socket_dir.st_mode) != 0o750
                or not stat.S_ISDIR(secret_dir.st_mode)
                or secret_dir.st_uid != issuer_uid
                or stat.S_IMODE(secret_dir.st_mode) != 0o700
                or not stat.S_ISREG(secret_file.st_mode)
                or secret_file.st_uid != issuer_uid
                or stat.S_IMODE(secret_file.st_mode) != 0o600):
            raise IssuerProtocolBlocked("ISSUER_PRIVATE_PATHS_REQUIRED")
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise IssuerProtocolBlocked("ISSUER_SOCKET_PATH_OCCUPIED")
    except OSError as exc:
        raise IssuerProtocolBlocked("ISSUER_PRIVATE_PATHS_REQUIRED") from exc
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        listener.bind(str(path))
        os.chmod(path, 0o660)
        bound = path.lstat()
        if (not stat.S_ISSOCK(bound.st_mode) or bound.st_uid != issuer_uid
                or bound.st_gid != ipc_gid or stat.S_IMODE(bound.st_mode) != 0o660):
            raise IssuerProtocolBlocked("ISSUER_SOCKET_PATH_UNTRUSTED")
        listener.listen(8)
        return listener
    except (OSError, IssuerProtocolBlocked) as exc:
        listener.close()
        raise IssuerProtocolBlocked("ISSUER_LISTENER_START_FAILED") from exc


def read_issuer_frame(conn: socket.socket) -> bytes:
    _require_unix_stream(conn)
    previous_timeout = conn.gettimeout()
    deadline = time.monotonic() + 5
    try:
        def exact(size: int) -> bytes:
            parts = []
            remaining = size
            while remaining:
                time_left = deadline - time.monotonic()
                if time_left <= 0:
                    raise IssuerProtocolBlocked("ISSUER_WIRE_DEADLINE_EXCEEDED")
                conn.settimeout(time_left)
                chunk = conn.recv(remaining)
                if time.monotonic() >= deadline:
                    raise IssuerProtocolBlocked("ISSUER_WIRE_DEADLINE_EXCEEDED")
                if not chunk:
                    raise IssuerProtocolBlocked("ISSUER_WIRE_TRUNCATED")
                parts.append(chunk)
                remaining -= len(chunk)
            return b"".join(parts)
        size = struct.unpack(">I", exact(4))[0]
        if not 0 < size <= MAX_ISSUER_FRAME_BYTES:
            raise IssuerProtocolBlocked("ISSUER_WIRE_SIZE_INVALID")
        return exact(size)
    except (OSError, struct.error):
        raise IssuerProtocolBlocked("ISSUER_WIRE_TRUNCATED") from None
    finally:
        conn.settimeout(previous_timeout)


def serve_one_issuer_connection(
    conn: socket.socket,
    *,
    api_uid: int,
    issuer_uid: int,
    attempt_directory: str | Path,
    expected_database: str,
    read_connect_factory: Callable[[], AbstractContextManager[Any]],
    decision_connect_factory: Callable[..., AbstractContextManager[Any]],
    expected_scope: TenantScope | None = None,
) -> bool:
    """Handle one private request; caller supplies trusted OS and DB configuration."""
    try:
        require_issuer_peer(conn, api_uid=api_uid, issuer_uid=issuer_uid)
    except IssuerProtocolBlocked:
        conn.close()
        return False
    processed = False
    response: dict[str, str | int | None] = {
        "schemaVersion": 1, "status": "blocked", "code": "ISSUER_REQUEST_BLOCKED",
    }
    try:
        method, request = decode_issuer_request(read_issuer_frame(conn))
        if expected_scope is not None and (type(expected_scope) is not TenantScope
                or (request.org_id, request.project_id) != expected_scope.key):
            raise IssuerProtocolBlocked('ISSUER_PROCESS_SCOPE_REQUIRED')
        if method == "inquiry":
            result = dispatch_issuer_request(
                request, read_connect_factory=read_connect_factory,
                expected_database=expected_database,
            )
        else:
            result = issue_decision_once(
                request, attempt_directory=attempt_directory,
                decision_connect_factory=decision_connect_factory,
                read_connect_factory=read_connect_factory,
                expected_database=expected_database,
            )
        response = {"schemaVersion": 1, "status": result.status.value,
                    "eventId": result.event_id, "decision": result.decision}
        processed = True
    except Exception:
        # No JWT, tenant, exception text or DB detail crosses the socket.
        pass
    try:
        body = json.dumps(response, sort_keys=True, separators=(",", ":")).encode()
        conn.settimeout(5)
        conn.sendall(struct.pack(">I", len(body)) + body)
    except OSError:
        processed = False
    finally:
        conn.close()
    return processed
