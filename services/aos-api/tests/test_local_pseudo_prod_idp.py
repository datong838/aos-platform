"""156 · Local pseudo-production IdP matrix (no Docker / no PG required).

Asserts production-shaped gate: AOS_AUTH_ALLOW_DEV=0 rejects Bearer ``dev``,
while an OIDC-shaped JWT still authenticates via /v1/me.

≠ customer-site IdP acceptance (微商城等后序按 handbook 60 §6).
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from aos_api.idempotency import idempotency_store
from aos_api.main import create_app
from aos_api.metrics import reset_metrics
from aos_api import mock_data
from aos_api.oidc import issue_dev_token


@pytest.fixture()
def client_auth(monkeypatch):
    """Auth-only client: no PG seed (pseudo-prod matrix must stay green offline)."""
    idempotency_store.clear()
    mock_data.reset_mock_state()
    reset_metrics()
    for k in (
        "AGNES_API_KEY",
        "AGNES_BASE_URL",
        "AGNES_TEXT_MODEL",
        "AGNES_IMAGE_MODEL",
        "AOS_LITELLM_URL",
    ):
        os.environ.pop(k, None)
    os.environ["AOS_LITELLM_FALLBACK"] = "mock"
    # default ALLOW_DEV before per-test monkeypatch
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "1")
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_pseudo_prod_rejects_bearer_dev(client_auth, monkeypatch):
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")
    r = client_auth.get(
        "/v1/me",
        headers={
            "Authorization": "Bearer dev",
            "X-Org-Id": "dev-org",
            "X-Project-Id": "dev-project",
        },
    )
    assert r.status_code == 401
    assert r.json()["code"] == "AUTH_DEV_DISABLED"


def test_pseudo_prod_oidc_jwt_still_works(client_auth, monkeypatch):
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")
    tok = issue_dev_token(subject="pseudo-alice", org_id="org-p", project_id="prj-p")
    assert tok["tokenKind"] == "oidc"
    r = client_auth.get(
        "/v1/me",
        headers={"Authorization": f"Bearer {tok['accessToken']}"},
    )
    assert r.status_code == 200
    me = r.json()
    assert me["subject"] == "pseudo-alice"
    assert me["orgId"] == "org-p"
    assert me["tokenKind"] == "oidc"
    assert me["tokenKind"] != "dev"


def test_pseudo_prod_oidc_config_reports_allow_dev_false(client_auth, monkeypatch):
    monkeypatch.setenv("AOS_AUTH_ALLOW_DEV", "0")
    r = client_auth.get("/v1/auth/oidc")
    assert r.status_code == 200
    body = r.json()
    assert body["allowDevToken"] is False
