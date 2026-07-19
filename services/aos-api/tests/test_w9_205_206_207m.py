"""205m / 206m / 207m — W9 postgres connector · storage quota · authz list."""
from __future__ import annotations

import base64
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
    os.environ.pop("AOS_PG_CONNECTOR_MOCK", None)
    os.environ.pop("AOS_PG_CONNECTOR_DSN", None)
    os.environ.pop("AOS_PG_CONNECTOR_HOST", None)
    os.environ.pop("AOS_MAX_STORAGE_GB", None)
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


def test_205m_pg_connector_stub_without_config(client):
    client.post("/v1/connector-plugins/jdbc-postgres/install", headers=_auth())
    r = client.get("/v1/connectors/jdbc-postgres/health", headers=_auth())
    assert r.status_code == 501
    assert r.json()["code"] == "CONNECTOR_STUB"


def test_205m_pg_connector_mock_ok(client, monkeypatch):
    monkeypatch.setenv("AOS_PG_CONNECTOR_MOCK", "1")
    client.post("/v1/connector-plugins/jdbc-postgres/install", headers=_auth())
    h = client.get("/v1/connectors/jdbc-postgres/health", headers=_auth())
    assert h.status_code == 200, h.text
    assert h.json()["mode"] == "mock"
    assert h.json()["ok"] is True
    p = client.post(
        "/v1/connectors/jdbc-postgres/probe",
        headers=_auth(),
        json={"limit": 1},
    )
    assert p.status_code == 200
    assert p.json()["pluginId"] == "jdbc-postgres"


def test_206m_storage_quota_exceeded(client):
    ops = _auth("dev-org", "ops-admin", ["platform_admin"])
    prov = client.post(
        "/v1/ops/tenants",
        headers=ops,
        json={
            "orgId": "stor-org",
            "orgName": "Stor",
            "ownerSubject": "stor-owner",
            "quota": {"maxStorageGb": 0, "maxMembers": 20, "maxWorkspaces": 5},
        },
    )
    assert prov.status_code == 200, prov.text
    # maxStorageGb=0 → any positive upload exceeds
    h = _auth("stor-org", "stor-owner", ["owner", "admin"])
    payload = base64.b64encode(b"hello-storage").decode("ascii")
    r = client.post(
        "/v1/media-sets",
        headers=h,
        json={"name": "a.bin", "contentType": "application/octet-stream", "bytesBase64": payload},
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "QUOTA_EXCEEDED"


def test_207m_authz_list_tuples(client):
    h = _auth()
    obj = "WorkOrder:w9-demo"
    w = client.post(
        "/v1/authz/tuples",
        headers=h,
        json={"relation": "viewer", "object": obj},
    )
    assert w.status_code == 200, w.text
    listed = client.get(
        "/v1/authz/tuples",
        headers=h,
        params={"object": obj},
    )
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    assert any(i.get("object") == obj and i.get("relation") == "viewer" for i in items)
