"""159 · BI subset deepen (needs PG for contour/vertex roundtrip)."""

from __future__ import annotations


def test_contour_share_and_options(client, auth_headers):
    client.post("/v1/demo/ensure-seed", headers=auth_headers)
    r = client.get(
        "/v1/analytics/contour/explore",
        headers=auth_headers,
        params={"objectType": "WorkOrder", "groupBy": "status", "limit": 200},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "ta8-contour-subset"
    assert body.get("scheme") == "159"
    assert isinstance(body.get("groupByOptions"), list)
    assert body["groupByOptions"]
    assert body["buckets"]
    assert "share" in body["buckets"][0]
    assert abs(sum(float(b["share"]) for b in body["buckets"]) - 1.0) < 0.02


def test_quiver_fill_gaps_length(client, auth_headers):
    client.post("/v1/demo/ensure-seed", headers=auth_headers)
    r = client.get(
        "/v1/analytics/quiver/series",
        headers=auth_headers,
        params={"objectType": "WorkOrder", "limitDays": 7, "fillGaps": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "ta8-quiver-subset"
    assert body.get("scheme") == "159"
    assert body.get("fillGaps") is True
    assert len(body.get("points") or []) == 7


def test_vertex_media_rid(client, auth_headers):
    created = client.post(
        "/v1/analytics/vertex/experiments",
        headers=auth_headers,
        json={
            "name": "bi-159-media",
            "objectType": "WorkOrder",
            "params": {"model": "heuristic"},
            "metrics": {"score": 0.91},
            "mediaRid": "ri.media.main.set.demo",
            "note": "159",
        },
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert row.get("scheme") == "159"
    assert row.get("mediaRid") == "ri.media.main.set.demo"
    assert row["productionWritten"] is False
