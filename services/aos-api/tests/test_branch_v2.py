"""89 v2 · object-level branch overlay: filter / diff / merge / checkout."""


def test_branch_overlay_checkout_diff_merge(client, auth_headers):
    bid = "feature89v2"
    # cleanup if prior run
    client.post(
        f"/v1/ontology/branches/{bid}/merge",
        headers=auth_headers,
        json={},
    )
    # create (ignore if exists)
    r = client.post(
        "/v1/ontology/branches",
        headers=auth_headers,
        json={"id": bid, "name": "89v2", "baseRef": "main"},
    )
    if r.status_code >= 400 and "exists" not in (r.json().get("message") or ""):
        # recreate path: delete not available — use unique id
        bid = "feature89v2b"
        r = client.post(
            "/v1/ontology/branches",
            headers=auth_headers,
            json={"id": bid, "name": "89v2b", "baseRef": "main"},
        )
        assert r.status_code == 200, r.text

    # production put rejected
    bad = client.put(
        "/v1/objects/WorkOrder/wo-1001?branch=main",
        headers=auth_headers,
        json={"props": {"title": "nope"}},
    )
    assert bad.status_code == 400

    # checkout with patch
    c = client.post(
        f"/v1/ontology/branches/{bid}/checkout",
        headers=auth_headers,
        json={
            "objectType": "WorkOrder",
            "objectId": "wo-1001",
            "patch": {"title": f"[{bid}] branch title"},
        },
    )
    assert c.status_code == 200, c.text

    listed = client.get("/v1/ontology/branches", headers=auth_headers)
    assert listed.status_code == 200
    row = next(i for i in listed.json()["items"] if i["id"] == bid)
    assert row["changeCount"] >= 1

    d = client.get(f"/v1/ontology/branches/{bid}/diff", headers=auth_headers)
    assert d.status_code == 200, d.text
    kinds = {i["kind"] for i in d.json()["items"]}
    assert "modified" in kinds or "added" in kinds

    br = client.get(f"/v1/objects/WorkOrder/wo-1001?branch={bid}", headers=auth_headers)
    assert br.status_code == 200
    assert br.json().get("title") == f"[{bid}] branch title"

    main = client.get("/v1/objects/WorkOrder/wo-1001?branch=main", headers=auth_headers)
    assert main.status_code == 200
    assert main.json().get("title") != br.json().get("title")

    m = client.post(f"/v1/ontology/branches/{bid}/merge", headers=auth_headers, json={})
    assert m.status_code == 200, m.text
    assert m.json()["merged"] >= 1

    after = client.get("/v1/objects/WorkOrder/wo-1001?branch=main", headers=auth_headers)
    assert after.status_code == 200
    assert after.json().get("title") == f"[{bid}] branch title"

    listed2 = client.get("/v1/ontology/branches", headers=auth_headers)
    row2 = next(i for i in listed2.json()["items"] if i["id"] == bid)
    assert row2["changeCount"] == 0
