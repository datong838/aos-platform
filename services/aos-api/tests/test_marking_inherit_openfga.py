"""TX.4 marking inheritance + OpenFGA facade — scheme 55."""

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


def test_wo1001_field_redact_still_works(client):
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="public-user", markings=["public"])
    r = client.get("/v1/objects/WorkOrder/wo-1001", headers=h)
    assert r.status_code == 200
    assert "internalCost" not in r.json()
    assert "internalCost" in (r.json().get("_redactedFields") or [])


def test_inherit_blocks_wo1003_without_restricted(client):
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="public-user", markings=["public"])
    r = client.get("/v1/objects/WorkOrder/wo-1003", headers=h)
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN"


def test_inherit_allows_wo1003_with_restricted(client):
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="restricted-user", markings=["public", "restricted"])
    r = client.get("/v1/objects/WorkOrder/wo-1003", headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == "wo-1003"


def test_list_filters_inherited(client):
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="public-user", markings=["public"])
    r = client.get("/v1/objects/WorkOrder", headers=h)
    assert r.status_code == 200
    ids = {it["id"] for it in r.json()["items"]}
    assert "wo-1001" in ids
    assert "wo-1003" not in ids


def test_openfga_blocks_without_viewer(client):
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="public-user", markings=["public", "restricted", "secret"])
    r = client.get("/v1/objects/WorkOrder/wo-fga-demo", headers=h)
    assert r.status_code == 403
    assert r.json()["code"] == "FORBIDDEN"


def test_openfga_allows_secret_user(client):
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(
        client,
        subject="secret-user",
        markings=["public", "restricted", "secret"],
    )
    r = client.get("/v1/objects/WorkOrder/wo-fga-demo", headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == "wo-fga-demo"


def test_authz_check_endpoint(client):
    init_schema()
    ensure_inherit_openfga_seed()
    h = _headers(client, subject="secret-user", markings=["public"])
    ok = client.post(
        "/v1/authz/check",
        headers=h,
        json={
            "relation": "viewer",
            "object": "object:WorkOrder:wo-fga-demo",
        },
    )
    assert ok.status_code == 200
    assert ok.json()["allowed"] is True

    h2 = _headers(client, subject="other", markings=["public"])
    no = client.post(
        "/v1/authz/check",
        headers=h2,
        json={
            "relation": "viewer",
            "object": "object:WorkOrder:wo-fga-demo",
        },
    )
    assert no.status_code == 200
    assert no.json()["allowed"] is False
