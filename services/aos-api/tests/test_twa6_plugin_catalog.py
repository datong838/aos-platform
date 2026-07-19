"""TWA.6 — shared catalog vs workspace-scoped plugin configs (no PG)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.routers.plugins import reset_plugin_store
from aos_api import mock_data


@pytest.fixture()
def api_client():
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    reset_plugin_store()
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth(org: str, project: str) -> dict[str, str]:
    tok = issue_dev_token(subject="alice", org_id=org, project_id=project)
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": org,
        "X-Project-Id": project,
    }


def test_catalog_shared_across_workspaces(api_client):
    r1 = api_client.get("/v1/plugin-catalog", headers=_auth("org-a", "prj-1"))
    r2 = api_client.get("/v1/plugin-catalog", headers=_auth("org-a", "prj-2"))
    assert r1.status_code == 200 and r2.status_code == 200
    ids1 = {i["id"] for i in r1.json()["items"]}
    ids2 = {i["id"] for i in r2.json()["items"]}
    assert ids1 == ids2
    assert "llm.openai" in ids1
    assert r1.json()["scope"] == "shared"


def test_configs_isolated_by_project(api_client):
    h1 = _auth("org-a", "prj-1")
    h2 = _auth("org-a", "prj-2")
    created = api_client.post(
        "/v1/plugin-configs",
        headers=h1,
        json={
            "id": "cfg-llm-1",
            "pluginId": "llm.openai",
            "displayName": "Prj1 GPT",
            "secretRef": "vault:ws/prj-1/openai",
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["projectId"] == "prj-1"
    assert "sk-" not in str(created.json())

    assert api_client.get("/v1/plugin-configs", headers=h1).json()["items"]
    assert api_client.get("/v1/plugin-configs", headers=h2).json()["items"] == []

    denied = api_client.get("/v1/plugin-configs/cfg-llm-1", headers=h2)
    assert denied.status_code == 404

    ok = api_client.get("/v1/plugin-configs/cfg-llm-1", headers=h1)
    assert ok.status_code == 200
    assert ok.json()["displayName"] == "Prj1 GPT"


def test_unknown_plugin_rejected(api_client):
    r = api_client.post(
        "/v1/plugin-configs",
        headers=_auth("org-a", "prj-1"),
        json={"pluginId": "no.such", "displayName": "x"},
    )
    assert r.status_code == 400
    assert r.json()["code"] == "PLUGIN_UNKNOWN"
