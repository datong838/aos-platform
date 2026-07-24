"""117 · TA.8 Contour / Quiver / Vertex subset surfaces."""


def test_contour_explore_buckets(client, auth_headers):
    client.post("/v1/demo/ensure-seed", headers=auth_headers)
    r = client.get(
        "/v1/analytics/contour/explore",
        headers=auth_headers,
        params={"objectType": "WorkOrder", "groupBy": "status", "limit": 200},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "ta8-contour-subset"
    assert body["productionWritten"] is False
    assert "subset" in (body.get("disclaimer") or "")
    assert isinstance(body.get("buckets"), list)
    assert body["totalRows"] >= 1
    assert any(int(b.get("count") or 0) >= 1 for b in body["buckets"])


def test_quiver_series_shape(client, auth_headers):
    client.post("/v1/demo/ensure-seed", headers=auth_headers)
    client.post("/v1/demo/run-analytics-story", headers=auth_headers)
    r = client.get(
        "/v1/analytics/quiver/series",
        headers=auth_headers,
        params={"objectType": "WorkOrder", "limitDays": 14},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "ta8-quiver-subset"
    assert body["metric"] == "lineageEventsPerDay"
    assert isinstance(body.get("points"), list)
    assert body["productionWritten"] is False
    assert len(body["points"]) >= 1


def test_vertex_experiment_register_and_list(client, auth_headers):
    created = client.post(
        "/v1/analytics/vertex/experiments",
        headers=auth_headers,
        json={
            "name": "ta8-baseline",
            "objectType": "WorkOrder",
            "params": {"model": "heuristic"},
            "metrics": {"score": 0.77},
            "note": "unit",
        },
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["mode"] == "ta8-vertex-subset"
    assert row["productionWritten"] is False
    assert row["id"].startswith("exp-")
    assert row["name"] == "ta8-baseline"

    listed = client.get("/v1/analytics/vertex/experiments", headers=auth_headers)
    assert listed.status_code == 200
    items = listed.json().get("items") or []
    assert any(i.get("id") == row["id"] for i in items)


def test_demo_story_lists_ta8_step(client, auth_headers):
    s = client.get("/v1/demo/story", headers=auth_headers)
    assert s.status_code == 200
    story = s.json()
    assert any(st.get("id") == "TA.8" for st in (story.get("steps") or []))
    assert story["deferred"].get("analyticsFullBiMl") is True
