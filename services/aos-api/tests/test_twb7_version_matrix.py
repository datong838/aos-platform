"""TWB.7 — Ferry ↔ endpoint version matrix (no PG)."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.membership import reset_membership_store, seed_dev_defaults
from aos_api.metrics import reset_metrics
from aos_api.oidc import issue_dev_token
from aos_api.orgs import reset_org_store, seed_dev_orgs
from aos_api import mock_data
from aos_api.version_matrix import (
    check_versions,
    get_matrix,
    reset_version_matrix,
    version_gte,
)


@pytest.fixture()
def api_client():
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    reset_membership_store()
    seed_dev_defaults()
    reset_org_store()
    seed_dev_orgs()
    reset_version_matrix()
    for k in ("AGNES_API_KEY", "AGNES_BASE_URL", "AOS_LITELLM_URL"):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth():
    tok = issue_dev_token(
        subject="ops-admin",
        org_id="dev-org",
        project_id="dev-project",
        roles=["platform_admin"],
    )
    return {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }


def test_version_gte_semverish():
    assert version_gte("0.2.0", "0.2.0")
    assert version_gte("0.2.1", "0.2.0")
    assert version_gte("0.2.0-dev", "0.2.0")
    assert not version_gte("0.1.9", "0.2.0")


def test_check_block_and_ok():
    reset_version_matrix()
    blocked = check_versions(desktop="0.1.0", spoke="0.3.0", ferry_bundle="1.0")
    assert blocked["overall"] == "block"
    assert not blocked["ok"]
    assert any(i["component"] == "desktop" and i["status"] == "block" for i in blocked["items"])

    ok = check_versions(desktop="0.2.0", spoke="0.3.0", ferry_bundle="1.1")
    assert ok["overall"] == "ok"
    assert ok["ok"]


def test_get_matrix_api(api_client):
    r = api_client.get("/v1/ops/version-matrix", headers=_auth())
    assert r.status_code == 200
    body = r.json()
    assert body["hubVersion"]
    assert any(x["component"] == "desktop" for x in body["rules"])


def test_check_api(api_client):
    r = api_client.post(
        "/v1/ops/version-matrix/check",
        headers=_auth(),
        json={"desktop": "0.1.0", "spoke": "0.3.0", "ferryBundle": "1.0"},
    )
    assert r.status_code == 200
    assert r.json()["overall"] == "block"


def test_ferry_status_includes_matrix(api_client):
    r = api_client.get("/v1/apollo/ferry/status", headers=_auth())
    assert r.status_code == 200
    vm = r.json().get("versionMatrix")
    assert vm and vm.get("rules")
    assert get_matrix()["hubVersion"] == vm["hubVersion"]
