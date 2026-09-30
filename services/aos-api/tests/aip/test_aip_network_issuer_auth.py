"""Fail-closed boundary before a separate network approval issuer uses its DB role."""

import pytest

from aos_api.auth import Principal
from aos_api.aip_network_issuer_contracts import NetworkIssuerDecisionCommand


def _command(**changes):
    raw = {
        "schemaVersion": 1, "bearerToken": "header.payload.signature",
        "orgId": "org-org", "projectId": "dev-project",
        "proposalId": "proposal-1", "idempotencyKey": "decision-1",
        "decision": {"expectedProposalVersion": 1,
                     "expectedProposalHash": "a" * 64,
                     "decision": "approved", "reason": "reviewed"},
    }
    raw.update(changes)
    return NetworkIssuerDecisionCommand.model_validate(raw)


def _external_config(monkeypatch):
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")
    monkeypatch.setenv("AOS_AUTH_EXTERNAL_ONLY", "1")
    monkeypatch.setenv("AOS_OIDC_ISSUER", "https://id.example.test/realm")
    monkeypatch.delenv("AOS_OIDC_ISSUERS", raising=False)
    monkeypatch.setenv("AOS_OIDC_AUDIENCE", "aos-api-formal")
    monkeypatch.setenv("AOS_OIDC_JWKS_URL", "https://id.example.test/jwks")
    monkeypatch.delenv("AOS_OIDC_JWKS_URLS", raising=False)


@pytest.mark.parametrize("name,value", [
    ("AOS_AUTH_ALLOW_DEV", "1"),
    ("AOS_AUTH_EXTERNAL_ONLY", "0"),
    ("AOS_OIDC_ISSUER", "http://localhost/realm"),
    ("AOS_OIDC_ISSUER", ""),
    ("AOS_OIDC_AUDIENCE", ""),
    ("AOS_OIDC_JWKS_URL", "http://127.0.0.1/jwks"),
    ("AOS_OIDC_JWKS_URL", ""),
])
def test_issuer_rejects_incomplete_or_development_auth(monkeypatch, name, value):
    _external_config(monkeypatch)
    monkeypatch.setenv(name, value)
    from aos_api.aip_network_issuer_auth import authenticate_issuer_request, IssuerAuthBlocked

    with pytest.raises(IssuerAuthBlocked) as error:
        authenticate_issuer_request(_command())
    assert "header.payload.signature" not in str(error.value)


def test_issuer_rejects_dev_signed_jwt_without_fallback(monkeypatch):
    _external_config(monkeypatch)
    from aos_api.oidc import issue_dev_token
    from aos_api.aip_network_issuer_auth import authenticate_issuer_request, IssuerAuthBlocked

    token = issue_dev_token(subject="checker", org_id="org-org", project_id="dev-project")["accessToken"]
    with pytest.raises(IssuerAuthBlocked) as error:
        authenticate_issuer_request(_command(bearerToken=token))
    assert token not in str(error.value)


@pytest.mark.parametrize("principal", [
    Principal(subject="checker", org_id="dev-org", project_id="dev-project", token_kind="oidc"),
    Principal(subject="", org_id="org-org", project_id="dev-project", token_kind="oidc"),
    Principal(subject="unknown", org_id="org-org", project_id="dev-project", token_kind="oidc"),
    Principal(subject="checker", org_id="org-org", project_id="dev-project", token_kind="dev"),
])
def test_issuer_rejects_unbound_principal(monkeypatch, principal):
    _external_config(monkeypatch)
    from aos_api import aip_network_issuer_auth as module

    monkeypatch.setattr(module, "resolve_principal", lambda **kwargs: principal)
    with pytest.raises(module.IssuerAuthBlocked):
        module.authenticate_issuer_request(_command())


def test_issuer_reauthenticates_command_and_inquiry_with_exact_tenant(monkeypatch):
    _external_config(monkeypatch)
    from aos_api import aip_network_issuer_auth as module

    calls = []
    def verified(**kwargs):
        calls.append(kwargs)
        return Principal(subject="checker", org_id="org-org", project_id="dev-project", token_kind="oidc")

    monkeypatch.setattr(module, "resolve_principal", verified)
    command = _command()
    assert module.authenticate_issuer_request(command).subject == "checker"
    assert module.authenticate_issuer_request(command.inquiry()).subject == "checker"
    assert calls == [{"token": "header.payload.signature", "header_org": "org-org", "header_project": "dev-project"}] * 2
