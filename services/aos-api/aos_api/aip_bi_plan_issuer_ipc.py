"""One-command private Unix wire for the isolated BI Plan issuer."""

from __future__ import annotations

import json
import socket
import struct
from collections.abc import Callable

from aos_api.aip_bi_plan_issuer_contracts import (
    BIIssuerPrepareCommand, BIIssuerRebindCommand,
)
from aos_api.aip_bi_plan_issuer_service import BIIssuerOutcome
from aos_api.aip_network_issuer_ipc import (
    MAX_ISSUER_FRAME_BYTES, IssuerProtocolBlocked, _invalid_constant,
    _unique_pairs, read_issuer_frame, require_issuer_peer,
)
from aos_api.tenant_scope import TenantScope


class BIIssuerProtocolBlocked(ValueError):
    pass


def decode_bi_issuer_request(raw: bytes):
    """Client controls only a strict command, never actor, paths or DB login."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_ISSUER_FRAME_BYTES:
        raise BIIssuerProtocolBlocked("BI_ISSUER_WIRE_INVALID")
    try:
        message = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                             parse_constant=_invalid_constant)
        if (type(message) is not dict
                or set(message) != {"schemaVersion", "method", "payload"}
                or type(message["schemaVersion"]) is not int
                or message["schemaVersion"] != 1
                or type(message["payload"]) is not dict):
            raise BIIssuerProtocolBlocked("BI_ISSUER_WIRE_INVALID")
        method = message["method"]
        if method == "prepare":
            command = BIIssuerPrepareCommand.model_validate(message["payload"])
        elif method == "rebind":
            command = BIIssuerRebindCommand.model_validate(message["payload"])
        else:
            raise BIIssuerProtocolBlocked("BI_ISSUER_WIRE_INVALID")
        return method, command
    except (UnicodeError, ValueError, TypeError, KeyError, RecursionError):
        raise BIIssuerProtocolBlocked("BI_ISSUER_WIRE_INVALID") from None


def serve_one_bi_issuer_connection(
    conn: socket.socket, *, api_uid: int, issuer_uid: int,
    expected_scope: TenantScope,
    dispatch: Callable[[BIIssuerPrepareCommand | BIIssuerRebindCommand], BIIssuerOutcome],
) -> bool:
    """A future process supplies the real auth/Receipt dispatcher; no retry here."""
    try:
        require_issuer_peer(conn, api_uid=api_uid, issuer_uid=issuer_uid)
    except IssuerProtocolBlocked:
        conn.close()
        return False
    processed = False
    response = {"schemaVersion": 1, "status": "blocked",
                "code": "BI_ISSUER_REQUEST_BLOCKED"}
    try:
        if type(expected_scope) is not TenantScope or not callable(dispatch):
            raise BIIssuerProtocolBlocked("BI_ISSUER_PROCESS_CONFIG_REQUIRED")
        _, command = decode_bi_issuer_request(read_issuer_frame(conn))
        if (command.org_id, command.project_id) != expected_scope.key:
            raise BIIssuerProtocolBlocked("BI_ISSUER_PROCESS_SCOPE_REQUIRED")
        outcome = dispatch(command)
        if type(outcome) is not BIIssuerOutcome or outcome.status not in {
                "observed", "unresolved", "conflict"}:
            raise BIIssuerProtocolBlocked("BI_ISSUER_RESULT_INVALID")
        response = {"schemaVersion": 1, "status": outcome.status}
        processed = True
    except Exception:
        # JWT, actor, receipt and database errors never cross the socket.
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
