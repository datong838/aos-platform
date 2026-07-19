"""TWA.7 — members / enter / audit pytest (no PG)."""
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


def test_bob_only_sees_member_workspaces(api_client):
    r = api_client.get("/v1/workspaces", headers=_auth("dev-org", "prj-ops", "bob"))
    assert r.status_code == 200
    ids = {i["id"] for i in r.json()["items"]}
    assert ids == {"prj-ops"}


def test_bob_cannot_enter_test_workspace(api_client):
    r = api_client.post(
        "/v1/workspaces/dev-project/enter",
        headers=_auth("dev-org", "prj-ops", "bob"),
    )
    assert r.status_code == 403
    assert r.json()["code"] == "WORKSPACE_FORBIDDEN"


def test_alice_add_member_and_audit(api_client):
    h = _auth("dev-org", "dev-project", "alice")
    added = api_client.post(
        "/v1/workspaces/dev-project/members",
        headers=h,
        json={"subject": "carol", "role": "editor"},
    )
    assert added.status_code == 200, added.text
    assert added.json()["role"] == "editor"

    members = api_client.get("/v1/workspaces/dev-project/members", headers=h)
    assert any(m["subject"] == "carol" for m in members.json()["items"])

    # carol can list 测试工作区
    listed = api_client.get(
        "/v1/workspaces", headers=_auth("dev-org", "dev-project", "carol")
    )
    assert "dev-project" in {i["id"] for i in listed.json()["items"]}

    audit = api_client.get("/v1/audit", headers=h)
    assert audit.status_code == 200
    actions = {a["action"] for a in audit.json()["items"]}
    assert "membership.upsert" in actions


def test_viewer_cannot_add_member(api_client):
    r = api_client.post(
        "/v1/workspaces/prj-ops/members",
        headers=_auth("dev-org", "prj-ops", "bob"),
        json={"subject": "dave", "role": "viewer"},
    )
    assert r.status_code == 403
