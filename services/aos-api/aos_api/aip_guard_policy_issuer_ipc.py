"""Bounded Unix transport for the isolated guard policy approval issuer."""
import json
import struct

from aos_api.aip_guard_policy_issuer import GuardPolicyIssuer
from aos_api.aip_guard_policy_issuer_contracts import GuardIssuerDecisionCommand, GuardIssuerDecisionInquiry
from aos_api.aip_network_issuer_ipc import (
    MAX_ISSUER_FRAME_BYTES, IssuerProtocolBlocked, _invalid_constant, _unique_pairs,
    read_issuer_frame, require_issuer_peer,
)


def decode_guard_issuer_request(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_ISSUER_FRAME_BYTES:
        raise IssuerProtocolBlocked("GUARD_ISSUER_WIRE_INVALID")
    try:
        message = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                             parse_constant=_invalid_constant)
        if (type(message) is not dict or set(message) != {"schemaVersion", "method", "payload"}
                or message["schemaVersion"] != 1 or type(message["payload"]) is not dict):
            raise ValueError()
        model = {"execute_once": GuardIssuerDecisionCommand,
                 "inquiry": GuardIssuerDecisionInquiry}.get(message["method"])
        if model is None:
            raise ValueError()
        return message["method"], model.model_validate(message["payload"])
    except Exception:
        raise IssuerProtocolBlocked("GUARD_ISSUER_WIRE_INVALID") from None


def serve_one_guard_issuer_connection(conn, *, api_uid, issuer_uid, attempt_directory,
                                      expected_database, expected_scope, connect_factory):
    try:
        require_issuer_peer(conn, api_uid=api_uid, issuer_uid=issuer_uid)
    except Exception:
        conn.close()
        return False
    processed = False
    response = {"schemaVersion": 1, "status": "unresolved"}
    try:
        method, request = decode_guard_issuer_request(read_issuer_frame(conn))
        if (request.org_id, request.project_id) != expected_scope.key:
            raise ValueError()
        issuer = GuardPolicyIssuer(connect_factory, attempt_directory,
                                   expected_database=expected_database)
        result = issuer.inquire(request.command()) if method == "inquiry" else issuer.execute(request.command())
        if result.get("status") == "observed" and result.get("activationAuthorized") is False:
            response = {"schemaVersion": 1, **result}
        processed = True
    except Exception:
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
