"""TWB.6 — SaaS provisioning + quotas (no PG)."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.membership import reset_membership_store, seed_dev_defaults, is_member
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.orgs import reset_org_store, seed_dev_orgs, get_org
from aos_api.provisioning import (
    assert_workspace_quota,
    reset_provisioning_store,
)
from aos_api.errors import ApiError
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
    reset_provisioning_store()
    for k in ("AGNES_API_KEY", "AGNES_BASE_URL", "AOS_LITELLM_URL"):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth(roles=None, subject="ops-admin"):
    tok = issue_dev_token(
        subject=subject,
        org_id="dev-org",
        project_id="dev-project",
        roles=roles or ["platform_admin"],
    )
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_provision_and_list(api_client):
    r = api_client.post(
        "/v1/ops/tenants",
        headers=_auth(),
        json={
            "orgId": "acme-corp",
            "orgName": "Acme",
            "ownerSubject": "acme-owner",
            "plan": "team",
            "quota": {"maxWorkspaces": 3},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["orgId"] == "acme-corp"
    assert body["quota"]["maxWorkspaces"] == 3
    assert get_org("acme-corp")["name"] == "Acme"
    assert is_member("acme-corp", "dev-project", "acme-owner")

    listed = api_client.get("/v1/ops/tenants", headers=_auth())
    assert listed.status_code == 200
    assert any(i["orgId"] == "acme-corp" for i in listed.json()["items"])


def test_viewer_forbidden(api_client):
    r = api_client.get(
        "/v1/ops/tenants",
        headers=_auth(roles=["viewer"], subject="bob"),
    )
    assert r.status_code == 403


def test_patch_quota_and_assert(api_client):
    api_client.post(
        "/v1/ops/tenants",
        headers=_auth(),
        json={
            "orgId": "beta-co",
            "orgName": "Beta",
            "ownerSubject": "beta-owner",
            "quota": {"maxWorkspaces": 1},
        },
    )
    p = api_client.patch(
        "/v1/ops/tenants/beta-co/quota",
        headers=_auth(),
        json={"maxWorkspaces": 2},
    )
    assert p.status_code == 200
    assert p.json()["quota"]["maxWorkspaces"] == 2

    assert_workspace_quota("beta-co", 1)
    with pytest.raises(ApiError) as ei:
        assert_workspace_quota("beta-co", 2)
    assert ei.value.status_code == 409


def test_duplicate_conflict(api_client):
    payload = {
        "orgId": "dup-org",
        "orgName": "Dup",
        "ownerSubject": "o1",
    }
    assert api_client.post("/v1/ops/tenants", headers=_auth(), json=payload).status_code == 200
    assert api_client.post("/v1/ops/tenants", headers=_auth(), json=payload).status_code == 409
