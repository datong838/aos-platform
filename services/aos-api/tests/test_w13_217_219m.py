"""217m / 219m — REST/File ingest · adjacency graph-health drill."""
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
        "AOS_REST_CONNECTOR_URL",
        "AOS_REST_CONNECTOR_TOKEN",
        "AOS_REST_CONNECTOR_MOCK",
        "AOS_FILE_LOCAL_ROOT",
        "AOS_FILE_LOCAL_MOCK",
    ):
        os.environ.pop(k, None)
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth():
    tok = issue_dev_token(
        subject="alice",
        org_id="dev-org",
        project_id="dev-project",
        roles=["owner", "platform_admin", "admin"],
    )
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_217m_rest_ingest_stub(client):
    client.post("/v1/connector-plugins/rest-generic/install", headers=_auth())
    r = client.post(
        "/v1/connectors/rest-generic/ingest",
        headers=_auth(),
        json={"limit": 1},
    )
    assert r.status_code == 501
    assert r.json()["code"] == "CONNECTOR_STUB"


def test_217m_rest_ingest_mock(client, monkeypatch):
    monkeypatch.setenv("AOS_REST_CONNECTOR_MOCK", "1")
    client.post("/v1/connector-plugins/rest-generic/install", headers=_auth())
    r = client.post(
        "/v1/connectors/rest-generic/ingest",
        headers=_auth(),
        json={"limit": 1, "objectType": "WorkOrder"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["written"] >= 1
    assert body["pluginId"] == "rest-generic"


def test_217m_file_local_ingest_stub(client):
    client.post("/v1/connector-plugins/file-local/install", headers=_auth())
    r = client.post(
        "/v1/connectors/file-local/ingest",
        headers=_auth(),
        json={"limit": 1},
    )
    assert r.status_code == 501
    assert r.json()["code"] == "CONNECTOR_STUB"


def test_217m_file_local_ingest_mock(client, monkeypatch):
    monkeypatch.setenv("AOS_FILE_LOCAL_MOCK", "1")
    client.post("/v1/connector-plugins/file-local/install", headers=_auth())
    r = client.post(
        "/v1/connectors/file-local/ingest",
        headers=_auth(),
        json={"limit": 2, "objectType": "WorkOrder"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["written"] >= 1
    assert body["pluginId"] == "file-local"


def test_219m_adjacency_graph_health_drill(client):
    """≠ 真 AGE：断言邻接表绕行字段。"""
    h = _auth()
    gh = client.get("/v1/ontology/graph-health", headers=h)
    assert gh.status_code == 200, gh.text
    body = gh.json()
    metrics = body.get("metrics") or {}
    assert metrics.get("engine") == "adjacency_table"
    assert metrics.get("ageAvailable") is False
    # neighbors on a seeded-ish id: only assert engine when 200
    nb = client.get("/v1/ontology/objects/WorkOrder/wo-1/neighbors", headers=h)
    if nb.status_code == 200:
        assert nb.json().get("engine") == "adjacency_table"
