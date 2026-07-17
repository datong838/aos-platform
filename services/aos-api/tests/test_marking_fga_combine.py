"""OpenFGA marking#bearer ∪ JWT markings — scheme 63."""

from aos_api.db import ensure_inherit_openfga_seed, init_schema


def _headers(client, *, subject: str, markings: list[str], roles: list[str] | None = None):
    tok = client.post(
        "/v1/auth/token",
        json={
            "grantType": "dev",
            "subject": subject,
            "roles": roles or ["developer"],
            "markings": markings,
        },
    )
    assert tok.status_code == 200
    return {
        "Authorization": f"Bearer {tok.json()['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_jwt_restricted_still_allows_wo1003(client):
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="restricted-user", markings=["public", "restricted"])
    r = client.get("/v1/objects/WorkOrder/wo-1003", headers=h)
    assert r.status_code == 200


def test_public_without_bearer_denied(client, monkeypatch):
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "1")
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="public-user", markings=["public"])
    r = client.get("/v1/objects/WorkOrder/wo-1003", headers=h)
    assert r.status_code == 403


def test_bearer_only_allows_wo1003(client, monkeypatch):
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "1")
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="bearer-only", markings=["public"])
    r = client.get("/v1/objects/WorkOrder/wo-1003", headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == "wo-1003"


def test_bearer_disabled_ignores_fga(client, monkeypatch):
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "0")
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="bearer-only", markings=["public"])
    r = client.get("/v1/objects/WorkOrder/wo-1003", headers=h)
    assert r.status_code == 403


def test_fga_demo_still_needs_viewer(client, monkeypatch):
    """AND: marking ok via bearer does not skip object viewer tuples."""
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "1")
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(
        client,
        subject="bearer-only",
        markings=["public", "restricted", "secret"],
    )
    r = client.get("/v1/objects/WorkOrder/wo-fga-demo", headers=h)
    assert r.status_code == 403


def test_authz_status_marking_bearer(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_AUTHZ_MARKING_BEARER", "1")
    r = client.get("/v1/authz/status", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["markingBearer"] is True
