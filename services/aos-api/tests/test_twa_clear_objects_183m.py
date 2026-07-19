"""183m — clear workspace deletes object prefix (mocked)."""
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
def api_client(monkeypatch):
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
    monkeypatch.setenv("AOS_TWA_STORE", "memory")
    monkeypatch.setenv("AOS_CLEAR_DELETE_OBJECTS", "1")
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


def test_clear_calls_delete_prefix(api_client, monkeypatch):
    calls: list[str] = []

    def fake_delete_prefix(*, prefix: str, cfg=None):
        calls.append(prefix)
        return {"deleted": 2, "failed": 0, "prefix": prefix}

    monkeypatch.setattr(
        "aos_api.object_store.delete_prefix", fake_delete_prefix
    )
    h = _auth("dev-org", "dev-project")
    api_client.post(
        "/v1/workspaces",
        headers=h,
        json={"name": "清对象区", "id": "prj-obj-1"},
    )
    h2 = _auth("dev-org", "prj-obj-1")
    r = api_client.post("/v1/workspaces/prj-obj-1/data/clear", headers=h2)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cleared"]["objects"]["deleted"] == 2
    assert calls and calls[0].startswith("dev-org/prj-obj-1/")
