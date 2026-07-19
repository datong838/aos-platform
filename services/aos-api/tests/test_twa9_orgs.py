"""TWA.9 — multi-org list/enter + spoke org filter (no PG required for org APIs)."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api.apollo_catalog import filter_spokes_by_org
from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.membership import reset_membership_store, seed_dev_defaults
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.orgs import reset_org_store, seed_dev_orgs
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
    for k in ("AGNES_API_KEY", "AGNES_BASE_URL", "AOS_LITELLM_URL"):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth(org: str, project: str, subject: str = "alice"):
    tok = issue_dev_token(subject=subject, org_id=org, project_id=project)
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": org,
        "X-Project-Id": project,
    }


def test_list_orgs_for_alice(api_client):
    r = api_client.get("/v1/orgs", headers=_auth("dev-org", "dev-project"))
    assert r.status_code == 200
    ids = {i["id"] for i in r.json()["items"]}
    assert "dev-org" in ids
    assert "org-a" in ids
    assert "org-b" in ids


def test_enter_org_ok(api_client):
    r = api_client.post("/v1/orgs/org-a/enter", headers=_auth("dev-org", "dev-project"))
    assert r.status_code == 200
    body = r.json()
    assert body["orgId"] == "org-a"
    assert body["projectId"]
    assert "orgName" in body


def test_enter_org_denied_for_outsider(api_client):
    # bob only has prj-ops on orgs from seed — grant nothing on org-x
    r = api_client.post(
        "/v1/orgs/org-x-unknown/enter",
        headers=_auth("dev-org", "prj-ops", subject="bob"),
    )
    assert r.status_code == 403


def test_me_includes_orgs(api_client):
    r = api_client.get("/v1/me", headers=_auth("dev-org", "dev-project"))
    assert r.status_code == 200
    body = r.json()
    assert body["orgName"]
    assert isinstance(body.get("orgs"), list)
    assert any(o["id"] == "dev-org" for o in body["orgs"])


def test_filter_spokes_by_org():
    items = [
        {"id": "s1", "orgId": "dev-org"},
        {"id": "s2", "orgId": "org-a"},
        {"id": "s3", "orgId": "dev-org"},
    ]
    out = filter_spokes_by_org(items, "dev-org")
    assert [x["id"] for x in out] == ["s1", "s3"]
