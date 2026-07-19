"""158 · Full Spoke helm-mock MVP."""

from __future__ import annotations

from aos_api.db import init_schema, seed_if_empty


def _org_a(headers: dict) -> dict:
    return {**headers, "X-Org-Id": "org-a"}


def test_full_spoke_mock_ready_by_default(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_FULL_SPOKE_MODE", "mock")
    init_schema()
    seed_if_empty()
    from aos_api.apollo_catalog import ensure_seed
    from aos_api.db import connect

    with connect() as conn:
        ensure_seed(conn)
        conn.commit()

    fleet = client.get("/v1/apollo/fleet", headers=auth_headers)
    assert fleet.status_code == 200
    hub = fleet.json()["hub"]
    assert hub["fullSpokeRuntimeDeferred"] is True
    assert hub["fullSpokeMockReady"] is True
    assert hub["fullSpokeMode"] == "mock"

    r = client.get("/v1/apollo/spokes/spoke-full-stub", headers=_org_a(auth_headers))
    assert r.status_code == 200
    body = r.json()
    assert body["kind"] == "full"
    assert body["runtime"] == "helm-mock"
    assert body["heartbeatOk"] is True
    assert body["status"] == "online"


def test_full_spoke_heartbeat_and_apply_plan(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_FULL_SPOKE_MODE", "mock")
    init_schema()
    seed_if_empty()
    from aos_api.apollo_catalog import ensure_seed
    from aos_api.db import connect

    with connect() as conn:
        ensure_seed(conn)
        conn.commit()

    h = _org_a(auth_headers)
    hb = client.post(
        "/v1/apollo/spokes/spoke-full-stub/heartbeat",
        headers=h,
        json={"ok": True},
    )
    assert hb.status_code == 200
    assert hb.json()["heartbeatOk"] is True

    ap = client.post(
        "/v1/apollo/spokes/full/apply-plan",
        headers=h,
        json={"planId": "plan-test-158"},
    )
    assert ap.status_code == 200
    assert ap.json()["ok"] is True
    assert ap.json()["planId"] == "plan-test-158"
    assert ap.json()["spoke"]["meta"]["reportedState"] == "Applied(mock)"


def test_full_spoke_plan_artifact(client, auth_headers):
    r = client.get("/v1/apollo/spokes/full/plan", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["chart"] == "aos-spoke-full"
    assert body["k8sDeferred"] is True
    assert "deploy/spoke-full/chart" in body["path"]


def test_apply_plan_rejects_lite(client, auth_headers, monkeypatch):
    monkeypatch.setenv("AOS_FULL_SPOKE_MODE", "mock")
    init_schema()
    seed_if_empty()
    r = client.post(
        "/v1/apollo/spokes/spoke-local-dev/apply-plan",
        headers=auth_headers,
        json={},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "SPOKE_NOT_FULL"
