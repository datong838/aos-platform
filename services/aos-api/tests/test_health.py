def test_health_ok(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.headers.get("X-Trace-Id")


def test_ready_ok(client):
    r = client.get("/v1/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"
