def test_me_requires_auth(client):
    r = client.get("/v1/me")
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == "AUTH_REQUIRED"
    assert "traceId" in body


def test_me_with_dev_token(client, auth_headers):
    r = client.get("/v1/me", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["orgId"] == "dev-org"
    assert body["projectId"] == "dev-project"
    assert "admin" in body["roles"]
    assert "restricted" in body["markings"]


def test_buddy_ask_unauthorized_error_shape(client):
    r = client.post("/v1/buddy/ask", json={"query": "hi"})
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_REQUIRED"


def test_buddy_ask_ok(client, auth_headers):
    r = client.post(
        "/v1/buddy/ask",
        headers=auth_headers,
        json={"query": "ping"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "ping" in body["answer"]
    assert body["traceId"] == "test-trace-1"
