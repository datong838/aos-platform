"""189m — create workspace hooks SaaS quota."""
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
from aos_api.provisioning import reset_provisioning_store
from aos_api.workspaces_catalog import reset_workspace_catalog, seed_dev_workspaces
from aos_api import mock_data


@pytest.fixture()
def api():
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
    os.environ["AOS_TWA_STORE"] = "memory"
    os.environ["AOS_AUTH_ALLOW_DEV"] = "1"
    os.environ.pop("AOS_MAX_WORKSPACES_PER_ORG", None)
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth(org="acme-corp", subject="acme-owner", roles=None):
    tok = issue_dev_token(
        subject=subject,
        org_id=org,
        project_id="dev-project",
        roles=roles or ["platform_admin", "owner"],
    )
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": org,
        "X-Project-Id": "dev-project",
    }


def test_create_workspace_quota_exceeded(api):
    ops = _auth("dev-org", "ops-admin", ["platform_admin"])
    prov = api.post(
        "/v1/ops/tenants",
        headers=ops,
        json={
            "orgId": "acme-corp",
            "orgName": "Acme",
            "ownerSubject": "acme-owner",
            "quota": {"maxWorkspaces": 1},
        },
    )
    assert prov.status_code == 200, prov.text
    # provision already created default workspace membership; catalog may have 0–2
    # set quota to current count so next create fails
    h = _auth()
    listed = api.get("/v1/workspaces", headers=h)
    assert listed.status_code == 200
    n = len(listed.json()["items"])
    # patch quota to current count
    patch = api.patch(
        "/v1/ops/tenants/acme-corp/quota",
        headers=ops,
        json={"maxWorkspaces": max(1, n)},
    )
    assert patch.status_code == 200, patch.text
    denied = api.post(
        "/v1/workspaces",
        headers=h,
        json={"name": "超额区", "id": "ws-over"},
    )
    assert denied.status_code == 409, denied.text
    assert denied.json()["code"] == "QUOTA_EXCEEDED"


def test_env_max_workspaces(api, monkeypatch):
    monkeypatch.setenv("AOS_MAX_WORKSPACES_PER_ORG", "0")
    h = _auth("dev-org", "alice", ["owner", "admin"])
    # ensure alice can manage
    r = api.post(
        "/v1/workspaces",
        headers=h,
        json={"name": "应被拒", "id": "ws-env-0"},
    )
    assert r.status_code == 409
    assert r.json()["code"] == "QUOTA_EXCEEDED"
