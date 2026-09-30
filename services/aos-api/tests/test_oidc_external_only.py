"""Formal API mode must never accept a locally issued development identity."""

import pytest

from aos_api import oidc


def test_external_only_rejects_dev_hs256_even_with_allow_dev_off(monkeypatch):
    token = oidc.issue_dev_token(subject="test-only", org_id="org-org",
                                 project_id="dev-project")["accessToken"]
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")
    monkeypatch.setenv("AOS_AUTH_EXTERNAL_ONLY", "1")
    monkeypatch.setenv("AOS_OIDC_JWKS_URL", "https://id.example.test/jwks")
    with pytest.raises(ValueError, match="external"):
        oidc.verify_access_token(token)


def test_external_only_jwks_failure_never_uses_local_rsa(monkeypatch):
    token = oidc.issue_dev_token(subject="test-only", alg="RS256")["accessToken"]
    monkeypatch.setenv("AOS_AUTH_EXTERNAL_ONLY", "1")
    monkeypatch.setenv("AOS_OIDC_JWKS_URL", "https://id.example.test/jwks")
    monkeypatch.setattr(oidc, "_verify_jwks", lambda *_: (_ for _ in ()).throw(ValueError("JWKS_DOWN")))
    monkeypatch.setattr(oidc, "_verify_local_rs256", lambda *_: pytest.fail("local RSA fallback"))
    with pytest.raises(ValueError, match="JWKS_DOWN"):
        oidc.verify_access_token(token)


def test_external_only_accepts_external_jwks_result(monkeypatch):
    token = oidc.issue_dev_token(subject="test-only", alg="RS256")["accessToken"]
    monkeypatch.setenv("AOS_AUTH_EXTERNAL_ONLY", "1")
    monkeypatch.setenv("AOS_OIDC_JWKS_URL", "https://id.example.test/jwks")
    expected = {"sub": "external-user", "org_id": "org-org", "project_id": "dev-project"}
    monkeypatch.setattr(oidc, "_verify_jwks", lambda *_: expected)
    assert oidc.verify_access_token(token) is expected


def test_external_only_disables_dev_grant_and_literal_dev(monkeypatch):
    monkeypatch.setenv("AOS_AUTH_EXTERNAL_ONLY", "1")
    monkeypatch.delenv("AOS_AUTH_ALLOW_DEV", raising=False)
    monkeypatch.delenv("AOS_OIDC_JWKS_URL", raising=False)
    monkeypatch.delenv("AOS_OIDC_JWKS_URLS", raising=False)
    assert oidc.allow_dev() is False
    config = oidc.public_config()
    assert "dev" not in config["grantTypes"]
    assert config["jwksConfigured"] is False
