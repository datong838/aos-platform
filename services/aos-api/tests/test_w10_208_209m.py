"""208m / 209m — W10 sqlserver connector · webhook delete/sign."""
from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi.testclient import TestClient
from urllib import request as urlrequest

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
        "AOS_MSSQL_CONNECTOR_MOCK",
        "AOS_MSSQL_CONNECTOR_DSN",
        "AOS_MSSQL_CONNECTOR_HOST",
        "AOS_SQLSERVER_HOST",
        "AOS_WEBHOOK_SIGNING_SECRET",
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


def test_208m_mssql_stub_without_config(client):
    client.post("/v1/connector-plugins/jdbc-sqlserver/install", headers=_auth())
    r = client.get("/v1/connectors/jdbc-sqlserver/health", headers=_auth())
    assert r.status_code == 501
    assert r.json()["code"] == "CONNECTOR_STUB"


def test_208m_mssql_mock_ok(client, monkeypatch):
    monkeypatch.setenv("AOS_MSSQL_CONNECTOR_MOCK", "1")
    client.post("/v1/connector-plugins/jdbc-sqlserver/install", headers=_auth())
    h = client.get("/v1/connectors/jdbc-sqlserver/health", headers=_auth())
    assert h.status_code == 200, h.text
    assert h.json()["mode"] == "mock"
    assert h.json()["ok"] is True
    p = client.post(
        "/v1/connectors/jdbc-sqlserver/probe",
        headers=_auth(),
        json={"limit": 1},
    )
    assert p.status_code == 200
    assert p.json()["pluginId"] == "jdbc-sqlserver"


def test_209m_webhook_delete(client):
    h = _auth()
    r = client.post(
        "/v1/actions/webhooks",
        headers=h,
        json={"url": "http://127.0.0.1:9999/hook", "event": "action.approved"},
    )
    assert r.status_code == 200
    wid = r.json()["id"]
    d = client.delete(f"/v1/actions/webhooks/{wid}", headers=h)
    assert d.status_code == 200, d.text
    assert d.json()["ok"] is True
    listed = client.get("/v1/actions/webhooks", headers=h)
    assert listed.status_code == 200
    assert not any(i["id"] == wid for i in listed.json()["items"])
    missing = client.delete(f"/v1/actions/webhooks/{wid}", headers=h)
    assert missing.status_code == 404


def test_209m_webhook_signing_header(client, monkeypatch):
    monkeypatch.setenv("AOS_WEBHOOK_DRY_RUN", "0")
    monkeypatch.setenv("AOS_WEBHOOK_SIGNING_SECRET", "w10-secret")
    captured: dict = {}

    class _Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _urlopen(req, timeout=5):
        captured["headers"] = dict(req.header_items()) if hasattr(req, "header_items") else {}
        # urllib Request stores headers case-insensitive via .headers
        captured["headers"] = {k: v for k, v in req.headers.items()}
        captured["data"] = req.data
        return _Resp()

    monkeypatch.setattr(urlrequest, "urlopen", _urlopen)
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
    body = send.json()
    assert any(d.get("signed") for d in body.get("deliveries") or [])
    sig = captured["headers"].get("X-aos-signature") or captured["headers"].get("X-AOS-Signature")
    assert sig and str(sig).startswith("sha256=")
    expect = hmac.new(
        b"w10-secret",
        captured["data"],
        hashlib.sha256,
    ).hexdigest()
    assert sig == f"sha256={expect}"
