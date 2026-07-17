import os

from aos_api.oidc import issue_dev_token, public_config


def test_oidc_public_config(client):
    r = client.get("/v1/auth/oidc")
    assert r.status_code == 200
    body = r.json()
    assert body["issuer"]
    assert body["clientIdRef"].startswith("vault:")
    assert "allowDevToken" in body
    # no secrets
    blob = str(body)
    assert "aos_dev_oidc_hs256" not in blob


def test_jwt_login_non_dev_token(client):
    tok = issue_dev_token(subject="bob", org_id="org-b", project_id="prj-b")
    assert tok["tokenKind"] == "oidc"
    r = client.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {tok['accessToken']}"},
    )
    assert r.status_code == 200
    me = r.json()
    assert me["subject"] == "bob"
    assert me["orgId"] == "org-b"
    assert me["tokenKind"] == "oidc"
    assert "restricted" in me["markings"]


def test_auth_token_endpoint(client):
    r = client.post(
        "/v1/auth/token",
        json={"grantType": "dev", "subject": "carol"},
    )
    assert r.status_code == 200
    assert r.json()["accessToken"].count(".") == 2


def test_dev_token_can_be_disabled(client, monkeypatch):
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")
    # force reload of allow_dev via env at call time — oidc.allow_dev reads env live
    r = client.get("/v1/me", headers={"Authorization": "Bearer dev"})
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_DEV_DISABLED"


def test_bearer_dev_still_works_by_default(client, auth_headers):
    r = client.get("/v1/me", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["tokenKind"] == "dev"
