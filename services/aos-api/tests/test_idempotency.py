def test_idempotent_create_module(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "mod-create-1"}
    r1 = client.post(
        "/v1/modules",
        headers=headers,
        json={"name": "Idem Module"},
    )
    assert r1.status_code == 201
    id1 = r1.json()["id"]

    r2 = client.post(
        "/v1/modules",
        headers=headers,
        json={"name": "Idem Module"},
    )
    assert r2.status_code == 201
    assert r2.json()["id"] == id1
    assert r2.json().get("idempotentReplay") is True


def test_buddy_idempotent_replay(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "ask-1"}
    a = client.post("/v1/buddy/ask", headers=headers, json={"query": "one"})
    b = client.post("/v1/buddy/ask", headers=headers, json={"query": "two"})
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["answer"] == b.json()["answer"]
