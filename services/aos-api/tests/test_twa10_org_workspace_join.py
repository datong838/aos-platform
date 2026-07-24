"""TWA.10 — create org/workspace + invite + join-request approve."""
from __future__ import annotations

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.membership import reset_membership_store, seed_dev_defaults
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.org_invites import reset_org_invites_store
from aos_api.orgs import reset_org_store, seed_dev_orgs
from aos_api.workspaces_catalog import reset_workspace_catalog, seed_dev_workspaces
from aos_api import mock_data


def _seed_multi_org_test_fixtures() -> None:
    """测试夹具：join/approve 场景用 org-a/org-b（产品默认种子已废止）。"""
    from aos_api.membership import upsert_member
    from aos_api.orgs import ensure_org
    from aos_api.workspaces_catalog import ensure_workspace

    for oid, name in (("org-a", "组织 A"), ("org-b", "组织 B")):
        ensure_org(oid, name=name)
        ensure_workspace(oid, "dev-project", name="默认工作区")
        upsert_member(oid, "dev-project", "alice", "owner", actor_id="alice")


def _scrub_ephemeral_test_orgs() -> None:
    """共享 aos_meta 时清掉多组织夹具/用例产生的临时组织，勿动 org-qyh。"""
    from aos_api.db import connect

    ephemeral = ("org-a", "org-b", "org-new-1", "org-x-unknown")
    try:
        with connect() as conn:
            for oid in ephemeral:
                conn.execute("DELETE FROM meta_membership WHERE org_id=%s", (oid,))
                conn.execute("DELETE FROM meta_workspace WHERE org_id=%s", (oid,))
                conn.execute("DELETE FROM meta_org WHERE id=%s", (oid,))
            conn.execute("DELETE FROM meta_org WHERE id LIKE 'org-new-%'")
            conn.execute(
                "DELETE FROM meta_membership WHERE org_id LIKE 'org-new-%'"
            )
            conn.execute(
                "DELETE FROM meta_workspace WHERE org_id LIKE 'org-new-%' OR project_id LIKE 'prj-rd-%'"
            )
            conn.commit()
    except Exception:  # noqa: BLE001
        pass


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
    _seed_multi_org_test_fixtures()
    reset_org_invites_store()
    for k in ("AGNES_API_KEY", "AGNES_BASE_URL", "AOS_LITELLM_URL"):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    app = create_app()
    with TestClient(app) as c:
        yield c
    _scrub_ephemeral_test_orgs()


def _auth(org: str, project: str, subject: str = "alice") -> dict[str, str]:
    tok = issue_dev_token(subject=subject, org_id=org, project_id=project)
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": org,
        "X-Project-Id": project,
    }


def test_create_org_and_enter(api_client):
    oid = f"org-new-{uuid.uuid4().hex[:8]}"
    r = api_client.post(
        "/v1/orgs",
        headers=_auth("dev-org", "dev-project"),
        json={"name": "新组织", "id": oid},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == oid
    assert body["defaultProjectId"] == "dev-project"
    assert body["workspaceName"] == "默认工作区"

    entered = api_client.post(
        f"/v1/orgs/{oid}/enter",
        headers=_auth("dev-org", "dev-project"),
    )
    assert entered.status_code == 200
    assert entered.json()["orgId"] == oid


def test_create_workspace(api_client):
    ws_id = f"prj-rd-{uuid.uuid4().hex[:8]}"
    r = api_client.post(
        "/v1/workspaces",
        headers=_auth("dev-org", "dev-project"),
        json={"name": "研发工作区", "id": ws_id},
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"] == ws_id
    assert r.json()["name"] == "研发工作区"

    listed = api_client.get("/v1/workspaces", headers=_auth("dev-org", "dev-project"))
    assert listed.status_code == 200
    ids = {i["id"] for i in listed.json()["items"]}
    assert ws_id in ids


def test_invite_accept_by_outsider(api_client):
    inv = api_client.post(
        "/v1/orgs/dev-org/invites",
        headers=_auth("dev-org", "dev-project"),
        json={"role": "editor", "projectId": "dev-project", "maxUses": 2},
    )
    assert inv.status_code == 200, inv.text
    token = inv.json()["token"]

    preview = api_client.get(
        f"/v1/org-invites/{token}",
        headers=_auth("dev-org", "dev-project", subject="carol"),
    )
    assert preview.status_code == 200
    assert preview.json()["orgName"] == "默认组织"
    assert preview.json()["alreadyMember"] is False

    accepted = api_client.post(
        f"/v1/org-invites/{token}/accept",
        headers=_auth("dev-org", "dev-project", subject="carol"),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["role"] == "editor"

    enter = api_client.post(
        "/v1/orgs/dev-org/enter",
        headers=_auth("org-a", "dev-project", subject="carol"),
    )
    assert enter.status_code == 200
    assert enter.json()["orgId"] == "dev-org"


def test_join_request_approve(api_client):
    # carol applies to org-a (not a member)
    req = api_client.post(
        "/v1/orgs/org-a/join-requests",
        headers=_auth("dev-org", "dev-project", subject="carol"),
        json={"message": "请批准加入"},
    )
    assert req.status_code == 200, req.text
    rid = req.json()["id"]

    pending = api_client.get(
        "/v1/orgs/org-a/join-requests",
        headers=_auth("org-a", "dev-project"),
    )
    assert pending.status_code == 200
    assert any(i["id"] == rid for i in pending.json()["items"])

    decided = api_client.post(
        f"/v1/orgs/org-a/join-requests/{rid}/decide",
        headers=_auth("org-a", "dev-project"),
        json={"decision": "approve", "role": "viewer"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"

    enter = api_client.post(
        "/v1/orgs/org-a/enter",
        headers=_auth("dev-org", "dev-project", subject="carol"),
    )
    assert enter.status_code == 200


def test_join_request_reject_cannot_enter(api_client):
    req = api_client.post(
        "/v1/orgs/org-b/join-requests",
        headers=_auth("dev-org", "dev-project", subject="dave"),
        json={},
    )
    assert req.status_code == 200
    rid = req.json()["id"]
    api_client.post(
        f"/v1/orgs/org-b/join-requests/{rid}/decide",
        headers=_auth("org-b", "dev-project"),
        json={"decision": "reject"},
    )
    enter = api_client.post(
        "/v1/orgs/org-b/enter",
        headers=_auth("dev-org", "dev-project", subject="dave"),
    )
    assert enter.status_code == 403


def test_directory_lists_orgs(api_client):
    # 使用未参与 invite 的 subject，避免共享 PG 上 carol 残留成员身份
    r = api_client.get(
        "/v1/orgs/directory",
        headers=_auth("dev-org", "dev-project", subject="erin"),
    )
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(i["id"] == "dev-org" and i["member"] is False for i in items)
