"""Single-send client for the isolated guard policy approval issuer."""
from dataclasses import dataclass
import json
from pathlib import Path

from aos_api.aip_guard_policy_issuer_contracts import GuardIssuerDecisionCommand, GuardIssuerDecisionInquiry
from aos_api.aip_private_service_transport import exchange_private_frame, request_private_frame, validate_private_endpoint


class GuardIssuerClientBlocked(ValueError):
    pass


@dataclass(frozen=True)
class GuardIssuerEndpoint:
    socket_path: Path
    api_uid: int
    issuer_uid: int
    ipc_gid: int

    def __post_init__(self):
        try:
            path = validate_private_endpoint(self.socket_path, api_uid=self.api_uid,
                                             service_uid=self.issuer_uid, ipc_gid=self.ipc_gid)
            object.__setattr__(self, "socket_path", path)
        except Exception:
            raise GuardIssuerClientBlocked("GUARD_ISSUER_ENDPOINT_REQUIRED") from None


def _decode(raw, request):
    try:
        value = json.loads(raw.decode("utf-8"))
        if type(value) is not dict or value.get("schemaVersion") != 1:
            raise ValueError()
        status = value.get("status")
        if status == "unresolved":
            if set(value) != {"schemaVersion", "status"}:
                raise ValueError()
            return {"status": status, "activationAuthorized": False}
        if set(value) != {"schemaVersion", "status", "proposalId", "approvalEventId", "decision", "activationAuthorized"}:
            raise ValueError()
        if (status != "observed" or value["proposalId"] != request.proposal_id
                or value["decision"] != request.decision.decision.value
                or type(value["approvalEventId"]) is not str or not value["approvalEventId"]
                or value["activationAuthorized"] is not False):
            raise ValueError()
        return {key: item for key, item in value.items() if key != "schemaVersion"}
    except Exception:
        raise GuardIssuerClientBlocked("GUARD_ISSUER_RESPONSE_INVALID") from None


def request_guard_issuer(endpoint, request):
    if type(endpoint) is not GuardIssuerEndpoint or type(request) not in (GuardIssuerDecisionCommand, GuardIssuerDecisionInquiry):
        raise GuardIssuerClientBlocked("GUARD_ISSUER_CLIENT_EXACT_INPUT_REQUIRED")
    endpoint.__post_init__()
    method = "inquiry" if type(request) is GuardIssuerDecisionInquiry else "execute_once"
    try:
        return request_private_frame(endpoint.socket_path, api_uid=endpoint.api_uid,
            service_uid=endpoint.issuer_uid, ipc_gid=endpoint.ipc_gid,
            exchange=lambda conn: exchange_private_frame(conn, method, request,
                request_type=type(request), decode=_decode))
    except Exception:
        raise GuardIssuerClientBlocked("GUARD_ISSUER_CLIENT_CONNECTION_BLOCKED") from None
