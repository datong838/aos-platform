"""Reverify external OIDC at the isolated BI issuer, never trust API actor."""

import pytest

from aos_api.auth import Principal
from aos_api.aip_bi_plan_issuer_contracts import BIIssuerPrepareCommand, BIIssuerRebindCommand


def _command(token="header.payload.signature"):
    return BIIssuerPrepareCommand.model_validate({
        "schemaVersion": 1, "bearerToken": token,
        "orgId": "org-org", "projectId": "dev-project",
        "installationId": "42785d78-5914-4a54-a078-e5d2c7f48481",
        "expectedETagVersion": 3, "idempotencyKey": "bi-prepare-1",
    })


def _external_config(monkeypatch):
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")
    monkeypatch.setenv("AOS_AUTH_EXTERNAL_ONLY", "1")
    monkeypatch.setenv("AOS_OIDC_ISSUER", "https://id.example.test/realm")
    monkeypatch.delenv("AOS_OIDC_ISSUERS", raising=False)
    monkeypatch.setenv("AOS_OIDC_AUDIENCE", "aos-api-formal")
    monkeypatch.setenv("AOS_OIDC_JWKS_URL", "https://id.example.test/jwks")
    monkeypatch.delenv("AOS_OIDC_JWKS_URLS", raising=False)


@pytest.mark.parametrize("name,value", [
    ("AOS_AUTH_ALLOW_DEV", "1"), ("AOS_AUTH_EXTERNAL_ONLY", "0"),
    ("AOS_OIDC_ISSUER", "http://localhost/realm"),
    ("AOS_OIDC_JWKS_URL", ""), ("AOS_OIDC_AUDIENCE", ""),
])
def test_bi_issuer_rejects_development_or_incomplete_oidc(monkeypatch, name, value):
    _external_config(monkeypatch)
    monkeypatch.setenv(name, value)
    from aos_api.aip_bi_plan_issuer_auth import authenticate_bi_issuer_request, BIIssuerAuthBlocked
    with pytest.raises(BIIssuerAuthBlocked) as error:
        authenticate_bi_issuer_request(_command())
    assert "header.payload.signature" not in str(error.value)


@pytest.mark.parametrize("principal", [
    Principal(subject="checker", org_id="dev-org", project_id="dev-project", token_kind="oidc"),
    Principal(subject="checker", org_id="org-org", project_id="dev-project", token_kind="dev"),
    Principal(subject="", org_id="org-org", project_id="dev-project", token_kind="oidc"),
    Principal(subject="unknown", org_id="org-org", project_id="dev-project", token_kind="oidc"),
])
def test_bi_issuer_rejects_nonmatching_principal(monkeypatch, principal):
    _external_config(monkeypatch)
    from aos_api import aip_bi_plan_issuer_auth as module
    monkeypatch.setattr(module, "resolve_principal", lambda **_: principal)
    with pytest.raises(module.BIIssuerAuthBlocked):
        module.authenticate_bi_issuer_request(_command())


def test_bi_issuer_rejects_dev_signed_jwt_without_fallback(monkeypatch):
    _external_config(monkeypatch)
    from aos_api.oidc import issue_dev_token
    from aos_api.aip_bi_plan_issuer_auth import authenticate_bi_issuer_request, BIIssuerAuthBlocked

    token = issue_dev_token(subject="checker", org_id="org-org", project_id="dev-project")["accessToken"]
    command = _command(token)
    with pytest.raises(BIIssuerAuthBlocked) as error:
        authenticate_bi_issuer_request(command)
    assert token not in str(error.value)


def test_bi_issuer_rechecks_jwt_on_every_command(monkeypatch):
    _external_config(monkeypatch)
    from aos_api import aip_bi_plan_issuer_auth as module
    calls = []
    def verified(**kwargs):
        calls.append(kwargs)
        return Principal(subject="checker", org_id="org-org", project_id="dev-project", token_kind="oidc")
    monkeypatch.setattr(module, "resolve_principal", verified)
    command = _command()
    assert module.authenticate_bi_issuer_request(command).subject == "checker"
    assert module.authenticate_bi_issuer_request(command).subject == "checker"
    assert calls == [{"token": "header.payload.signature", "header_org": "org-org",
                      "header_project": "dev-project"}] * 2


def test_rebind_rechecks_jwt_and_rejects_plain_principal(monkeypatch):
    _external_config(monkeypatch)
    from aos_api import aip_bi_plan_issuer_auth as module
    calls = []
    monkeypatch.setattr(module, "resolve_principal", lambda **kwargs: (
        calls.append(kwargs) or Principal(
            subject="checker", org_id="org-org", project_id="dev-project", token_kind="oidc")))
    command = BIIssuerRebindCommand.model_validate({
        "schemaVersion": 1, "bearerToken": "header.payload.signature",
        "orgId": "org-org", "projectId": "dev-project",
        "installationId": "42785d78-5914-4a54-a078-e5d2c7f48481",
        "expectedETagVersion": 4, "idempotencyKey": "bi-rebind-1",
        "planId": "responsibility-plan-original",
        "prepareIdempotencyKey": "bi-prepare-1", "expectedPlanVersion": 2,
    })
    assert module.authenticate_bi_issuer_request(command).subject == "checker"
    assert len(calls) == 1
    with pytest.raises(module.BIIssuerAuthBlocked):
        module.authenticate_bi_issuer_request(Principal(
            subject="checker", org_id="org-org", project_id="dev-project", token_kind="oidc"))
