"""TWA.11 — clear data then delete workspace / org."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.membership import reset_membership_store, seed_dev_defaults
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.org_invites import reset_org_invites_store
from aos_api.orgs import reset_org_store, seed_dev_orgs
from aos_api.workspace_isolation import reset_items
from aos_api.workspaces_catalog import reset_workspace_catalog, seed_dev_workspaces
from aos_api import mock_data


@pytest.fixture()
def api_client():
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
    reset_items()
    for k in ("AGNES_API_KEY", "AGNES_BASE_URL", "AOS_LITELLM_URL"):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    os.environ["AOS_AUTH_ALLOW_DEV"] = "1"
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


def test_delete_workspace_blocked_when_not_empty(api_client):
    h = _auth("dev-org", "dev-project")
    created = api_client.post(
        "/v1/workspaces",
        headers=h,
        json={"name": "待删区", "id": "prj-del-1"},
    )
    assert created.status_code == 200, created.text
    h2 = _auth("dev-org", "prj-del-1")
    item = api_client.post(
        "/v1/workspace-items",
        headers=h2,
        json={"name": "block", "id": "it-1"},
    )
    assert item.status_code == 200
    denied = api_client.delete("/v1/workspaces/prj-del-1", headers=h2)
    assert denied.status_code == 409
    assert denied.json()["code"] == "NOT_EMPTY"


def test_clear_then_delete_workspace(api_client):
    h = _auth("dev-org", "dev-project")
    api_client.post(
        "/v1/workspaces",
        headers=h,
        json={"name": "可删区", "id": "prj-del-2"},
    )
    h2 = _auth("dev-org", "prj-del-2")
    api_client.post(
        "/v1/workspace-items",
        headers=h2,
        json={"name": "x", "id": "it-2"},
    )
    cleared = api_client.post("/v1/workspaces/prj-del-2/data/clear", headers=h2)
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["empty"] is True
    deleted = api_client.delete("/v1/workspaces/prj-del-2", headers=h2)
    assert deleted.status_code == 200, deleted.text
    listed = api_client.get("/v1/workspaces", headers=h)
    assert "prj-del-2" not in {i["id"] for i in listed.json()["items"]}


def test_clear_then_delete_org(api_client):
    h = _auth("dev-org", "dev-project")
    created = api_client.post(
        "/v1/orgs",
        headers=h,
        json={"name": "可删组织", "id": "org-del-1"},
    )
    assert created.status_code == 200, created.text
    h_org = _auth("org-del-1", "dev-project")
    api_client.post(
        "/v1/workspace-items",
        headers=h_org,
        json={"name": "keep", "id": "it-org"},
    )
    blocked = api_client.delete("/v1/orgs/org-del-1", headers=h_org)
    assert blocked.status_code == 409
    cleared = api_client.post("/v1/orgs/org-del-1/data/clear", headers=h_org)
    assert cleared.status_code == 200
    assert cleared.json()["empty"] is True
    deleted = api_client.delete("/v1/orgs/org-del-1", headers=h_org)
    assert deleted.status_code == 200, deleted.text
    directory = api_client.get("/v1/orgs/directory", headers=h)
    assert "org-del-1" not in {i["id"] for i in directory.json()["items"]}


def test_non_admin_cannot_clear(api_client):
    # bob is viewer on prj-ops only in seed
    h = _auth("dev-org", "prj-ops", subject="bob")
    r = api_client.post("/v1/workspaces/prj-ops/data/clear", headers=h)
    assert r.status_code == 403
