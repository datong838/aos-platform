"""G-ALIGN-03/04 — link-types · datasets · syncs."""


def test_list_seed_link_types(client, auth_headers):
    r = client.get("/v1/ontology/link-types", headers=auth_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(x["id"] == "lt-related-to" and x["rel"] == "related_to" for x in items)


def test_create_link_type_and_get(client, auth_headers):
    body = {
        "id": "lt-owns",
        "name": "拥有",
        "srcType": "WorkOrder",
        "dstType": "WorkOrder",
        "rel": "owns",
        "expectedEdges": 10,
        "published": True,
    }
    created = client.post("/v1/ontology/link-types", headers=auth_headers, json=body)
    assert created.status_code == 200, created.text
    got = client.get("/v1/ontology/link-types/lt-owns", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["rel"] == "owns"
    deleted = client.delete("/v1/ontology/link-types/lt-owns", headers=auth_headers)
    assert deleted.status_code == 200


def test_link_scale_blocked(client, auth_headers):
    r = client.post(
        "/v1/ontology/link-types",
        headers=auth_headers,
        json={
            "id": "lt-huge",
            "name": "超大规模",
            "srcType": "WorkOrder",
            "dstType": "WorkOrder",
            "rel": "huge",
            "expectedEdges": 1_000_001,
            "mdoApproved": False,
        },
    )
    assert r.status_code == 422
    assert r.json()["code"] == "LINK_SCALE_BLOCKED"


def test_link_scale_ok_with_mdo(client, auth_headers):
    r = client.post(
        "/v1/ontology/link-types",
        headers=auth_headers,
        json={
            "id": "lt-huge-ok",
            "name": "超大规模已批",
            "srcType": "WorkOrder",
            "dstType": "WorkOrder",
            "rel": "huge_ok",
            "expectedEdges": 2_000_000,
            "mdoApproved": True,
            "published": True,
        },
    )
    assert r.status_code == 200, r.text
    client.delete("/v1/ontology/link-types/lt-huge-ok", headers=auth_headers)


def test_syncs_and_datasets(client, auth_headers):
    src = client.post(
        "/v1/sources",
        headers=auth_headers,
        json={"id": "src-align-04", "type": "file"},
    )
    assert src.status_code == 200
    pipe = client.post(
        "/v1/pipelines",
        headers=auth_headers,
        json={"id": "pipe-align-04", "sourceId": "src-align-04"},
    )
    assert pipe.status_code == 200
    rid = pipe.json()["datasetRid"]
    assert rid.startswith("ri.dataset.")

    ds = client.get(f"/v1/datasets/{rid}", headers=auth_headers)
    assert ds.status_code == 200
    assert ds.json()["pipelineId"] == "pipe-align-04"

    hist = client.get(f"/v1/datasets/{rid}/history", headers=auth_headers)
    assert hist.status_code == 200
    assert len(hist.json()["items"]) >= 1

    sync = client.post(
        "/v1/syncs",
        headers=auth_headers,
        json={"sourceId": "src-align-04"},
    )
    assert sync.status_code == 200
    assert sync.json()["status"] == "SUCCEEDED"

    listed = client.get("/v1/syncs", headers=auth_headers)
    assert listed.status_code == 200
    assert any(s["sourceId"] == "src-align-04" for s in listed.json()["items"])

    hist2 = client.get(f"/v1/datasets/{rid}/history", headers=auth_headers)
    assert len(hist2.json()["items"]) >= 2
