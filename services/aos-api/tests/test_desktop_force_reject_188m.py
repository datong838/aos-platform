"""188m — force reject old desktop."""
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
from aos_api.version_matrix import check_versions, reset_version_matrix
from aos_api import mock_data


@pytest.fixture()
def api(monkeypatch):
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    reset_membership_store()
    seed_dev_defaults()
    reset_org_store()
    seed_dev_orgs()
    reset_version_matrix()
    monkeypatch.delenv("AOS_DESKTOP_FORCE_REJECT", raising=False)
    os.environ["AOS_AUTH_ALLOW_DEV"] = "1"
    app = create_app()
    with TestClient(app) as c:
        yield c


def _auth(**extra_headers):
    tok = issue_dev_token(subject="alice", org_id="dev-org", project_id="dev-project")
    h = {
        "Authorization": f"Bearer {tok['accessToken']}",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
    }
    h.update(extra_headers)
    return h


def test_force_reject_flag_on_check(monkeypatch):
    monkeypatch.setenv("AOS_DESKTOP_FORCE_REJECT", "1")
    out = check_versions(desktop="0.1.0", spoke="0.3.0", ferry_bundle="1.0")
    assert out["overall"] == "block"
    assert out["forceReject"] is True
    monkeypatch.setenv("AOS_DESKTOP_FORCE_REJECT", "0")
    out2 = check_versions(desktop="0.1.0", spoke="0.3.0", ferry_bundle="1.0")
    assert out2["overall"] == "block"
    assert out2["forceReject"] is False


def test_report_only_still_200(api, monkeypatch):
    monkeypatch.setenv("AOS_DESKTOP_FORCE_REJECT", "0")
    r = api.post(
        "/v1/ops/version-matrix/check",
        headers=_auth(),
        json={"desktop": "0.1.0", "spoke": "0.3.0", "ferryBundle": "1.0"},
    )
    assert r.status_code == 200
    assert r.json()["overall"] == "block"
    assert r.json()["forceReject"] is False


def test_force_reject_gate_403(api, monkeypatch):
    monkeypatch.setenv("AOS_DESKTOP_FORCE_REJECT", "1")
    # matrix check itself must still work (exempt)
    chk = api.post(
        "/v1/ops/version-matrix/check",
        headers=_auth(**{"X-AOS-Desktop-Version": "0.1.0"}),
        json={"desktop": "0.1.0"},
    )
    assert chk.status_code == 200
    assert chk.json()["forceReject"] is True
    # business path blocked
    me = api.get("/v1/me", headers=_auth(**{"X-AOS-Desktop-Version": "0.1.0"}))
    assert me.status_code == 403
    assert me.json()["code"] == "DESKTOP_VERSION_BLOCKED"
    # ok version allowed
    ok = api.get("/v1/me", headers=_auth(**{"X-AOS-Desktop-Version": "0.2.0"}))
    assert ok.status_code == 200
