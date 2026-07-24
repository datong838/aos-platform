"""160 · Apollo ops deepening HTTP (needs PG for promote health gate)."""

from __future__ import annotations

from aos_api.aip_kv_store import put_payload
from aos_api.db import connect, init_schema, seed_if_empty


def setup_function():
    put_payload("apollo_ops_changes", {"items": []})
    put_payload("apollo_ops_assets", {"items": []})


def test_changes_api_roundtrip(client, auth_headers):
    created = client.post(
        "/v1/apollo/changes",
        headers=auth_headers,
        json={"title": "ops-160", "kind": "hotfix", "summary": "unit"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["kind"] == "hotfix"
    assert body["status"] == "pending"
    cid = body["id"]

    ap = client.post(
        f"/v1/apollo/changes/{cid}/approve",
        headers=auth_headers,
        json={"note": "ok"},
    )
    assert ap.status_code == 200
    assert ap.json()["status"] == "approved"

    mg = client.post(f"/v1/apollo/changes/{cid}/merge-stable", headers=auth_headers)
    assert mg.status_code == 200
    assert mg.json()["status"] == "merged"

    listed = client.get("/v1/apollo/changes", headers=auth_headers)
    assert listed.status_code == 200
    assert any(i.get("id") == cid for i in listed.json().get("items") or [])


def test_promote_unhealthy_blocked(client, auth_headers):
    init_schema()
    seed_if_empty()
    with connect() as conn:
        conn.execute(
            "UPDATE apollo_spoke SET channel_id='dev', heartbeat_ok=FALSE WHERE kind='lite'"
        )
        conn.commit()
    r = client.post("/v1/apollo/channels/dev/promote", headers=auth_headers)
    assert r.status_code == 400
    assert r.json()["code"] == "CHANNEL_PROMOTE_UNHEALTHY"
    # restore
    with connect() as conn:
        conn.execute(
            "UPDATE apollo_spoke SET heartbeat_ok=TRUE WHERE kind='lite'"
        )
        conn.commit()


def test_promote_asset_incompatible(client, auth_headers):
    init_schema()
    seed_if_empty()
    with connect() as conn:
        conn.execute(
            "UPDATE apollo_spoke SET channel_id='dev', heartbeat_ok=TRUE WHERE kind='lite'"
        )
        conn.commit()
    ab = client.post(
        "/v1/apollo/assets",
        headers=auth_headers,
        json={
            "contents": ["WorkOrder"],
            "compatibleChannels": ["dev"],
            "hotfix": False,
        },
    )
    assert ab.status_code == 200
    r = client.post("/v1/apollo/channels/dev/promote", headers=auth_headers)
    assert r.status_code == 400
    assert r.json()["code"] == "CHANNEL_PROMOTE_ASSET"
