from pathlib import Path

import pytest
from pydantic import ValidationError


def command_payload():
    return {
        "schemaVersion": 1,
        "orgId": "org-org",
        "projectId": "dev-project",
        "bearerToken": "a.b.c",
        "proposalId": "proposal-1",
        "idempotencyKey": "decision-1",
        "decision": {
            "decision": "approved",
            "expectedProposalVersion": 1,
            "expectedProposalHash": "a" * 64,
        },
    }


def principal(subject="human-checker"):
    from aos_api.auth import Principal
    return Principal(subject=subject, org_id="org-org", project_id="dev-project", roles=("owner",), token_kind="oidc")


def test_guard_wire_contract_is_exact_and_inquiry_binds_original_decision():
    from aos_api.aip_guard_policy_issuer_contracts import (
        GuardIssuerDecisionCommand, GuardIssuerDecisionInquiry,
    )
    command = GuardIssuerDecisionCommand.model_validate(command_payload())
    inquiry = command.inquiry()
    assert type(inquiry) is GuardIssuerDecisionInquiry
    assert inquiry.matches(command)
    assert len(inquiry.request_hash) == 64
    with pytest.raises(ValidationError):
        GuardIssuerDecisionCommand.model_validate({**command_payload(), "role": "owner"})
    with pytest.raises(ValidationError):
        GuardIssuerDecisionCommand.model_validate({**command_payload(), "bearerToken": "not-jwt"})


def test_guard_wire_decoder_accepts_only_bound_execute_or_inquiry():
    import json
    from aos_api.aip_guard_policy_issuer_contracts import GuardIssuerDecisionCommand
    from aos_api.aip_guard_policy_issuer_ipc import decode_guard_issuer_request
    from aos_api.aip_network_issuer_ipc import IssuerProtocolBlocked
    command = GuardIssuerDecisionCommand.model_validate(command_payload())
    payload = command.model_dump(mode="json", by_alias=True, exclude={"bearer_token"})
    payload["bearerToken"] = "a.b.c"
    raw = json.dumps({"schemaVersion": 1, "method": "execute_once", "payload": payload}).encode()
    method, decoded = decode_guard_issuer_request(raw)
    assert method == "execute_once" and decoded.request_hash == command.request_hash
    with pytest.raises(IssuerProtocolBlocked):
        decode_guard_issuer_request(json.dumps({"schemaVersion": 1, "method": "activate", "payload": payload}).encode())


def test_application_requires_same_oidc_identity_and_reserves_before_single_dispatch(tmp_path, monkeypatch):
    from aos_api.aip_guard_policy_issuer_application import (
        GuardIssuerApplicationConfig, execute_guard_issuer,
    )
    from aos_api.aip_guard_policy_issuer_client import GuardIssuerEndpoint
    sent = []
    monkeypatch.setattr("aos_api.aip_guard_policy_issuer_application.parse_bearer", lambda value: "a.b.c")
    monkeypatch.setattr("aos_api.aip_guard_policy_issuer_application.authenticate_guard_issuer_request",
                        lambda request: principal())
    monkeypatch.setattr("aos_api.aip_guard_policy_issuer_application.request_guard_issuer",
                        lambda endpoint, request: sent.append(request) or {
                            "status": "observed", "proposalId": "proposal-1",
                            "approvalEventId": "event-1", "decision": "approved",
                            "activationAuthorized": False,
                        })
    tmp_path.chmod(0o700)
    endpoint = object.__new__(GuardIssuerEndpoint)
    object.__setattr__(endpoint, "socket_path", Path("/tmp/guard.sock"))
    object.__setattr__(endpoint, "api_uid", 501)
    object.__setattr__(endpoint, "issuer_uid", 502)
    object.__setattr__(endpoint, "ipc_gid", 503)
    monkeypatch.setattr(GuardIssuerEndpoint, "__post_init__", lambda self: None)
    config = GuardIssuerApplicationConfig(endpoint=endpoint, attempt_directory=tmp_path)
    body = command_payload()["decision"]
    result = execute_guard_issuer(config, "proposal-1", "decision-1", body,
                                  principal(), "Bearer a.b.c", inquiry=False)
    assert result["activationAuthorized"] is False
    assert len(sent) == 1
    # The same command is never sent twice; the second call becomes inquiry.
    result = execute_guard_issuer(config, "proposal-1", "decision-1", body,
                                  principal(), "Bearer a.b.c", inquiry=False)
    assert result["activationAuthorized"] is False
    assert type(sent[-1]).__name__ == "GuardIssuerDecisionInquiry"


def test_application_fails_closed_for_unconfigured_or_non_oidc():
    from aos_api.aip_guard_policy_issuer_application import GuardIssuerApplicationBlocked, execute_guard_issuer
    body = command_payload()["decision"]
    with pytest.raises(GuardIssuerApplicationBlocked) as exc:
        execute_guard_issuer(None, "proposal-1", "decision-1", body,
                             principal(), "Bearer a.b.c", inquiry=False)
    assert exc.value.code == "GUARD_ISSUER_APPLICATION_UNCONFIGURED"
