"""112 · TA.3 ontology-rail snippets."""


def test_ontology_rail_has_snippets(client, auth_headers):
    r = client.get("/v1/analytics/ontology-rail", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "ta3-rail"
    assert "objectTypes" in body
    assert "datasets" in body
    types = body["objectTypes"]
    assert isinstance(types, list)
    # seed usually includes WorkOrder
    if types:
        ot = types[0]
        assert ot.get("kind") == "objectType"
        assert "aos.objects.list" in (ot.get("snippet") or "")
        assert "/v1/analytics/objects/list" in (ot.get("snippet") or "")
        for inst in ot.get("instances") or []:
            assert "aos.objects.get" in (inst.get("snippet") or "")


def test_ontology_rail_limits(client, auth_headers):
    r = client.get(
        "/v1/analytics/ontology-rail",
        headers=auth_headers,
        params={"typeLimit": 1, "instanceLimit": 0, "datasetLimit": 0},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["objectTypes"]) <= 1
    if body["objectTypes"]:
        assert body["objectTypes"][0].get("instances") == []
    assert body["datasets"] == []


def test_ontology_rail_requires_auth(client):
    r = client.get("/v1/analytics/ontology-rail")
    assert r.status_code in (401, 403)
