"""Module PG store + Dev JWKS RS256."""


def test_modules_from_postgres(client, auth_headers):
    r = client.get("/v1/modules", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body.get("store") == "postgres"
    assert any(i["id"] == "mod-ops-inbox" for i in body["items"])
    rt = client.get("/v1/modules/mod-ops-inbox/runtime", headers=auth_headers)
    assert rt.status_code == 200
    assert rt.json().get("store") == "postgres"


def test_module_create_persists(client, auth_headers):
    c = client.post(
        "/v1/modules",
        headers=auth_headers,
        json={"name": "pg-mod", "entryPath": "/workshop/inbox"},
    )
    assert c.status_code == 201
    mid = c.json()["id"]
    g = client.get(f"/v1/modules/{mid}", headers=auth_headers)
    assert g.status_code == 200
    assert g.json()["name"] == "pg-mod"


def test_jwks_and_rs256_me(client):
    jwks = client.get("/v1/auth/jwks")
    assert jwks.status_code == 200
    assert jwks.json()["keys"]
    assert jwks.json()["keys"][0]["alg"] == "RS256"

    tok = client.post(
        "/v1/auth/token",
        json={"grantType": "dev", "subject": "jwks-user", "alg": "RS256"},
    )
    assert tok.status_code == 200
    assert tok.json()["alg"] == "RS256"
    access = tok.json()["accessToken"]
    me = client.get(
        "/v1/me",
        headers={
            "Authorization": f"Bearer {access}",
            "X-Org-Id": "dev-org",
            "X-Project-Id": "dev-project",
        },
    )
    assert me.status_code == 200
    body = me.json()
    assert body["subject"] == "jwks-user"
    assert body["tokenKind"] == "oidc"
