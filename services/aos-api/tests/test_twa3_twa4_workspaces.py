"""TWA.3 / TWA.4 — workspaces catalog + isolation probe (no PG)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.routers.workspaces import reset_isolation_store
from aos_api import mock_data


@pytest.fixture()
def api_client():
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    reset_isolation_store()
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth(org: str, project: str, subject: str = "alice") -> dict[str, str]:
    tok = issue_dev_token(subject=subject, org_id=org, project_id=project)
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": org,
        "X-Project-Id": project,
    }


def test_twa3_list_workspaces_includes_test_workspace(api_client):
    r = api_client.get("/v1/workspaces", headers=_auth("dev-org", "dev-project"))
    assert r.status_code == 200, r.text
    body = r.json()
    names = {i["name"] for i in body["items"]}
    assert "测试工作区" in names
    test = next(i for i in body["items"] if i["name"] == "测试工作区")
    assert test["deletable"] is True
    assert test["id"] == "dev-project"
    assert body["currentProjectId"] == "dev-project"


def test_twa4_same_org_different_project_isolated(api_client):
    """OrgA/Prj1 cannot read OrgA/Prj2 item by id (404, no leak)."""
    h1 = _auth("org-a", "prj-1")
    h2 = _auth("org-a", "prj-2")

    created = api_client.post(
        "/v1/workspace-items",
        headers=h1,
        json={"id": "secret-1", "name": "only-prj1"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["projectId"] == "prj-1"

    listed1 = api_client.get("/v1/workspace-items", headers=h1)
    assert listed1.status_code == 200
    assert any(i["id"] == "secret-1" for i in listed1.json()["items"])

    listed2 = api_client.get("/v1/workspace-items", headers=h2)
    assert listed2.status_code == 200
    assert listed2.json()["items"] == []

    denied = api_client.get("/v1/workspace-items/secret-1", headers=h2)
    assert denied.status_code == 404
    assert denied.json()["code"] == "NOT_FOUND"

    ok = api_client.get("/v1/workspace-items/secret-1", headers=h1)
    assert ok.status_code == 200
    assert ok.json()["name"] == "only-prj1"


def test_twa4_different_org_isolated(api_client):
    h_a = _auth("org-a", "prj-1")
    h_b = _auth("org-b", "prj-1")
    api_client.post(
        "/v1/workspace-items",
        headers=h_a,
        json={"id": "cross-org", "name": "a-only"},
    )
    r = api_client.get("/v1/workspace-items/cross-org", headers=h_b)
    assert r.status_code == 404


def test_twa4_forged_header_still_blocked(api_client):
    tok = issue_dev_token(subject="alice", org_id="org-a", project_id="prj-1")
    r = api_client.post(
        "/v1/workspace-items",
        headers={
            "Authorization": f"Bearer {tok['accessToken']}",
            "X-Org-Id": "org-a",
            "X-Project-Id": "prj-forged",
        },
        json={"name": "should-fail"},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "AUTH_TENANT_MISMATCH"
