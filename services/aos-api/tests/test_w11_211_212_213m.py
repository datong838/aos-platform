"""211m / 212m / 213m — W11 authz DELETE · outbox retry · pg ingest."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api import mock_data
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.membership import reset_membership_store, seed_dev_defaults
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.org_invites import reset_org_invites_store
from aos_api.orgs import reset_org_store, seed_dev_orgs
from aos_api.person_identity import reset_person_store, seed_dev_persons
from aos_api.provisioning import reset_provisioning_store
from aos_api.workspaces_catalog import reset_workspace_catalog, seed_dev_workspaces


@pytest.fixture()
def client():
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    reset_membership_store()
    seed_dev_defaults()
    reset_org_store()
    seed_dev_orgs()
    reset_workspace_catalog()
    seed_dev_workspaces()
    reset_org_invites_store()
    reset_provisioning_store()
    reset_person_store()
    seed_dev_persons()
    os.environ["AOS_TWA_STORE"] = "memory"
    os.environ["AOS_AUTH_ALLOW_DEV"] = "1"
    for k in (
        "AOS_PG_CONNECTOR_MOCK",
        "AOS_PG_CONNECTOR_DSN",
        "AOS_PG_CONNECTOR_HOST",
    ):
        os.environ.pop(k, None)
    os.environ["AOS_WEBHOOK_DRY_RUN"] = "1"
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth(org="dev-org", subject="alice", roles=None):
    tok = issue_dev_token(
        subject=subject,
        org_id=org,
        project_id="dev-project",
        roles=roles or ["owner", "platform_admin", "admin"],
    )
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": org,
        "X-Project-Id": "dev-project",
    }


def test_211m_authz_tuple_delete(client):
    h = _auth()
    obj = "WorkOrder:w11-del"
    w = client.post(
        "/v1/authz/tuples",
        headers=h,
        json={"relation": "viewer", "object": obj},
    )
    assert w.status_code == 200, w.text
    listed = client.get("/v1/authz/tuples", headers=h, params={"object": obj})
    assert listed.status_code == 200
    assert any(i.get("object") == obj for i in listed.json()["items"])
    d = client.request(
        "DELETE",
        "/v1/authz/tuples",
        headers=h,
        json={"relation": "viewer", "object": obj},
    )
    assert d.status_code == 200, d.text
    assert d.json()["ok"] is True
    listed2 = client.get("/v1/authz/tuples", headers=h, params={"object": obj})
    assert listed2.status_code == 200
    assert not any(i.get("object") == obj for i in listed2.json()["items"])
    missing = client.request(
        "DELETE",
        "/v1/authz/tuples",
        headers=h,
        json={"relation": "viewer", "object": obj},
    )
    assert missing.status_code == 404


def test_212m_outbox_list_and_retry(client):
    h = _auth()
    client.post(
        "/v1/actions/webhooks",
        headers=h,
        json={"url": "http://127.0.0.1:9999/hook", "event": "action.approved"},
    )
    send = client.post(
        "/v1/channels/channel-webhook/send",
        headers=h,
        json={"event": "action.approved", "ping": True},
    )
    assert send.status_code == 200, send.text
    listed = client.get("/v1/channels/outbox", headers=h)
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert len(items) >= 1
    oid = items[0]["id"]
    assert items[0].get("payload") is not None
    r = client.post(f"/v1/channels/outbox/{oid}/retry", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    assert r.json()["retriedId"] == oid
    listed2 = client.get("/v1/channels/outbox", headers=h)
    rows = listed2.json()["items"]
    orig = next(i for i in rows if i["id"] == oid)
    assert orig.get("status") == "retried"
    assert len(rows) >= 2


def test_213m_pg_ingest_stub_without_config(client):
    client.post("/v1/connector-plugins/jdbc-postgres/install", headers=_auth())
    r = client.post(
        "/v1/connectors/jdbc-postgres/ingest",
        headers=_auth(),
        json={"limit": 1},
    )
    assert r.status_code == 501
    assert r.json()["code"] == "CONNECTOR_STUB"


def test_213m_pg_ingest_mock_ok(client, monkeypatch):
    monkeypatch.setenv("AOS_PG_CONNECTOR_MOCK", "1")
    client.post("/v1/connector-plugins/jdbc-postgres/install", headers=_auth())
    r = client.post(
        "/v1/connectors/jdbc-postgres/ingest",
        headers=_auth(),
        json={"limit": 1, "objectType": "WorkOrder"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "mock"
    assert body["written"] >= 1
    assert body["pluginId"] == "jdbc-postgres"
