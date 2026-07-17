"""Apollo Channel / Spoke catalog — scheme 66."""

from aos_api.db import init_schema, seed_if_empty


def test_channels_seeded(client, auth_headers):
    init_schema()
    seed_if_empty()
    r = client.get("/v1/apollo/channels", headers=auth_headers)
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()["items"]}
    assert ids == {"dev", "staging", "stable"}


def test_promote_and_recall(client, auth_headers):
    init_schema()
    seed_if_empty()
    # reset lite spoke to dev for deterministic test
    from aos_api.db import connect

    with connect() as conn:
        conn.execute(
            "UPDATE apollo_spoke SET channel_id='dev' WHERE kind='lite'"
        )
        conn.commit()

    p = client.post("/v1/apollo/channels/dev/promote", headers=auth_headers)
    assert p.status_code == 200
    assert p.json()["to"] == "staging"

    spoke = client.get("/v1/apollo/spokes/spoke-local-dev", headers=auth_headers)
    assert spoke.status_code == 200
    assert spoke.json()["channelId"] == "staging"

    rec = client.post("/v1/apollo/channels/staging/recall", headers=auth_headers)
    assert rec.status_code == 200
    assert rec.json()["to"] == "dev"

    spoke2 = client.get("/v1/apollo/spokes/local", headers=auth_headers)
    assert spoke2.json()["channelId"] == "dev"


def test_promote_stable_blocked(client, auth_headers):
    init_schema()
    seed_if_empty()
    r = client.post("/v1/apollo/channels/stable/promote", headers=auth_headers)
    assert r.status_code == 400
    assert r.json()["code"] == "CHANNEL_PROMOTE_BLOCKED"


def test_fleet_from_catalog(client, auth_headers):
    init_schema()
    seed_if_empty()
    r = client.get("/v1/apollo/fleet", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["hub"]["channelCatalogReady"] is True
    assert body["hub"]["fullSpokeRuntimeDeferred"] is True
    assert len(body["channels"]) == 3
    kinds = {s["kind"] for s in body["spokes"]}
    assert "lite" in kinds
    assert "full" in kinds


def test_full_spoke_runtime_deferred(client, auth_headers):
    init_schema()
    seed_if_empty()
    r = client.get("/v1/apollo/spokes/spoke-full-stub", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["kind"] == "full"
    assert r.json()["runtime"] == "deferred"


def test_ferry_status_catalog_flags(client, auth_headers):
    st = client.get("/v1/apollo/ferry/status", headers=auth_headers)
    assert st.status_code == 200
    body = st.json()
    assert body["channelCatalogReady"] is True
    assert body["fullSpokeRuntimeDeferred"] is True
    assert body["fullChannelDeferred"] is True
