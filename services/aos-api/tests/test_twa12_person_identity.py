"""TWA.12 / 168 — email/phone member identity."""
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
from aos_api.person_identity import reset_person_store
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
    reset_person_store()
    from aos_api.person_identity import seed_dev_persons

    seed_dev_persons()
    os.environ["AOS_AUTH_ALLOW_DEV"] = "1"
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth(org: str = "dev-org", project: str = "dev-project") -> dict[str, str]:
    tok = issue_dev_token(subject="alice", org_id=org, project_id=project)
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": org,
        "X-Project-Id": project,
    }


def test_add_member_by_email(api_client):
    r = api_client.post(
        "/v1/workspaces/dev-project/members",
        headers=_auth(),
        json={"email": "Carol.Chen@Example.COM", "role": "viewer"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subject"] == "email:carol.chen@example.com"
    assert body["email"] == "carol.chen@example.com"
    assert body["displayLabel"] == "carol.chen@example.com"


def test_add_member_by_phone(api_client):
    r = api_client.post(
        "/v1/workspaces/dev-project/members",
        headers=_auth(),
        json={"phone": "13812345678", "role": "editor"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subject"] == "phone:+8613812345678"
    assert body["phone"] == "+8613812345678"


def test_legacy_subject_still_works(api_client):
    r = api_client.post(
        "/v1/workspaces/dev-project/members",
        headers=_auth(),
        json={"subject": "dave", "role": "viewer"},
    )
    assert r.status_code == 200
    assert r.json()["subject"] == "dave"


def test_invalid_email_400(api_client):
    r = api_client.post(
        "/v1/workspaces/dev-project/members",
        headers=_auth(),
        json={"email": "not-an-email", "role": "viewer"},
    )
    assert r.status_code == 400


def test_seed_members_have_profiles(api_client):
    r = api_client.get("/v1/workspaces/dev-project/members", headers=_auth())
    assert r.status_code == 200
    by_sub = {m["subject"]: m for m in r.json()["items"]}
    assert by_sub["alice"]["email"] == "alice@acme.example"
    assert by_sub["alice"]["phone"] == "+8613800138000"
    assert by_sub["alice"]["displayName"] == "艾丽斯"
    assert by_sub["user:dev"]["email"] == "dev@local.aos"
    assert by_sub["user:dev"]["displayLabel"] == "本机开发者"


def test_patch_own_profile(api_client):
    h = {
        "Authorization": "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    me = api_client.get("/v1/me", headers=h)
    assert me.status_code == 200
    assert me.json()["subject"] == "user:dev"
    assert me.json()["profile"]["displayName"] == "本机开发者"

    patched = api_client.patch(
        "/v1/me/profile",
        headers=h,
        json={
            "displayName": "张三（本机）",
            "email": "zhangsan@local.aos",
            "phone": "13900001111",
            "title": "现场调试",
        },
    )
    assert patched.status_code == 200, patched.text
    prof = patched.json()["profile"]
    assert prof["displayName"] == "张三（本机）"
    assert prof["email"] == "zhangsan@local.aos"
    assert prof["phone"] == "+8613900001111"
    assert patched.json()["subject"] == "user:dev"

    listed = api_client.get("/v1/workspaces/dev-project/members", headers=h)
    by = {m["subject"]: m for m in listed.json()["items"]}
    assert by["user:dev"]["displayName"] == "张三（本机）"
    assert by["user:dev"]["email"] == "zhangsan@local.aos"
